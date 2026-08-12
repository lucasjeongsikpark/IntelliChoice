"""Export approved authored templates to their versioned file (D-190).

Run with: uv run python -m intellichoice_curriculum.export_cli [--topic TOPIC_ID]

The last step of the authoring workflow, after `pipeline_cli` produces candidates and
`review_cli` approves them: `make question-gen-authored` -> `make question-review` ->
`make question-export`, then commit the file. Approval lives in one database until this
runs; afterwards it lives in git, where it reaches every environment through the same
`curriculum/` directory the taxonomy already ships in.

Writes whole files rather than merging into them, so the file always says exactly what the
database's approved set is - a diff that removes an item means it was rejected or
superseded, which is information a merge would hide. Committing the diff is the deliberate
step, and it is where a human sees what is about to ship.
"""

import argparse
import asyncio
from pathlib import Path
from typing import Literal

import yaml
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import QuestionTemplate
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.figures import FigureSpec
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.authored_bank import (
    AUTHORED_MODE,
    DEFAULT_AUTHORED_ROOT,
    AuthoredBankFile,
    AuthoredTemplateDef,
)
from intellichoice_curriculum.content import load_curriculum


class ExportError(Exception):
    """An approved template could not be exported without losing something."""


async def build_bank_file(
    session: AsyncSession, *, topic_id: str, curriculum_version: str
) -> AuthoredBankFile:
    repo = QuestionRepository(session)
    rows = (
        (
            await session.execute(
                select(QuestionTemplate)
                .where(QuestionTemplate.authoring_mode == AUTHORED_MODE)
                .where(
                    QuestionTemplate.validation_status == "approved",
                    # D-210: approved but retired is no longer exported. The bank file is
                    # what the serving path draws from, so "what the database would
                    # export" has to mean the same thing - otherwise retiring an item
                    # makes the file and the export permanently disagree.
                    QuestionTemplate.active_status == "active",
                )
                .where(QuestionTemplate.topic_id == topic_id)
                .order_by(
                    QuestionTemplate.skill_id,
                    QuestionTemplate.difficulty_label,
                    QuestionTemplate.question_template_id,
                )
            )
        )
        .scalars()
        .all()
    )

    templates = []
    for row in rows:
        variant = await repo.get_variant_for_template(row.question_template_id)
        if variant is None:
            # Unservable (D-189) and unexportable for the same reason: an authored
            # template's content lives on its canonical variant. Refusing beats writing a
            # file that loads into an item nothing can render.
            raise ExportError(
                f"{row.question_template_id} is approved but has no canonical variant"
            )
        templates.append(
            AuthoredTemplateDef(
                question_template_id=row.question_template_id,
                topic_id=row.topic_id,
                skill_id=row.skill_id,
                grade_band=row.grade_band,
                difficulty_label=row.difficulty_label,
                difficulty_confidence=row.difficulty_confidence,
                estimated_time_seconds=row.estimated_time_seconds,
                common_error_tags=list(row.common_error_tags or []),
                generator_model=row.generator_model,
                review_model_versions=dict(row.review_model_versions or {}),
                review_priority=row.review_priority,
                version=row.version,
                stem=row.stem or "",
                context_block=row.context_block,
                answer_expression=row.answer_expression,
                # The column is JSON; the bank def wants the model. Validated rather
                # than cast, so a row whose figure was written by an older shape
                # fails here instead of reaching a file.
                figure_spec=(
                    TypeAdapter(FigureSpec).validate_python(row.figure_spec)
                    if row.figure_spec
                    else None
                ),
                figure_reading=row.figure_reading,
                hint_ladder=list(row.hint_ladder or []),
                canonical_solution=dict(row.canonical_solution or {}),
                random_seed=variant.random_seed,
                rendered_question=variant.rendered_question,
                option_a=variant.option_a,
                option_b=variant.option_b,
                option_c=variant.option_c,
                option_d=variant.option_d,
                # Checked rather than cast (D-273). `question_variants.correct_option` is a
                # plain text column, so the narrowing on `AuthoredTemplateDef` cannot be
                # taken on trust here the way it can inside the file format. A row that
                # somehow holds anything else should stop the export with the id attached,
                # not be written into a bank file that then fails to load in every
                # environment at once.
                correct_option=_checked_option(row.question_template_id, variant.correct_option),
            )
        )
    return AuthoredBankFile(
        curriculum_version=curriculum_version, topic_id=topic_id, templates=templates
    )



def _checked_option(template_id: str, value: str) -> Literal["a", "b", "c", "d"]:
    """Narrow a database text column to the four options the file format allows."""
    if value not in ("a", "b", "c", "d"):
        raise ValueError(
            f"{template_id}: correct_option is {value!r}, which is not one of a/b/c/d - "
            f"exporting it would write a bank file that fails to load everywhere"
        )
    return value  # type: ignore[return-value]


def render_bank_file(bank: AuthoredBankFile) -> str:
    """YAML, block style, keys in declaration order rather than sorted.

    The file is meant to be read by whoever reviews the pull request that adds content, so
    the stem and its options stay adjacent and multi-line hints stay readable. `sort_keys`
    off keeps `stem` near the top instead of buried between `random_seed` and `version`.
    """
    return yaml.safe_dump(
        bank.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Export approved authored templates to YAML")
    parser.add_argument(
        "--topic",
        default=None,
        help="Only export this topic (default: every topic that has approved authored content)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_AUTHORED_ROOT,
        help=f"Directory to write <topic_id>.yaml into (default: {DEFAULT_AUTHORED_ROOT})",
    )
    args = parser.parse_args()

    curriculum = load_curriculum()
    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            topic_ids = (
                [args.topic]
                if args.topic
                else sorted(
                    (
                        await session.execute(
                            select(QuestionTemplate.topic_id)
                            .where(QuestionTemplate.authoring_mode == AUTHORED_MODE)
                            .where(
                    QuestionTemplate.validation_status == "approved",
                    # D-210: approved but retired is no longer exported. The bank file is
                    # what the serving path draws from, so "what the database would
                    # export" has to mean the same thing - otherwise retiring an item
                    # makes the file and the export permanently disagree.
                    QuestionTemplate.active_status == "active",
                )
                            .distinct()
                        )
                    )
                    .scalars()
                    .all()
                )
            )
            if not topic_ids:
                print("no approved authored templates to export")
                return
            args.out.mkdir(parents=True, exist_ok=True)
            for topic_id in topic_ids:
                bank = await build_bank_file(
                    session,
                    topic_id=topic_id,
                    curriculum_version=curriculum.curriculum_version,
                )
                path = args.out / f"{topic_id}.yaml"
                path.write_text(render_bank_file(bank))
                print(f"wrote {len(bank.templates)} approved templates to {path}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
