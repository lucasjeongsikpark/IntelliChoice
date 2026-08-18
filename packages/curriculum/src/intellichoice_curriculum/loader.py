"""CLI loader: curriculum/internal_math YAML -> Postgres.

Run with: uv run python -m intellichoice_curriculum.loader

Loads the taxonomy (topics/skills) and the approved authored items from
`curriculum/internal_math/authored/*.yaml`. Idempotent — safe to re-run (mirrors the MySQL
seed fixtures' upsert-by-natural-key pattern, D-002): ids come from the files, so a second
run recognizes and skips what already exists instead of inserting duplicates. An item that
fails the §5.8.5 validation suite is never inserted — the whole run aborts.

D-226 removed the second thing this loaded. Until then it also generated and validated 50
parameterized *shape* templates from `templates/linear_equations.py`, which `_servable()`
had filtered out of every serving read since D-210 — so every deploy paid to build and
validate content no student could be shown. Nothing here renders from a seed any more; an
authored item *is* its content.
"""

import asyncio
import logging
from dataclasses import dataclass

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.curriculum import Skill, Topic
from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_CANONICAL,
    QuestionTemplate,
    QuestionVariant,
)
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_observability.logging_config import configure_logging
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.authored_bank import (
    AUTHORED_MODE,
    AUTHORED_SOLUTION_FUNCTION,
    AuthoredTemplateDef,
    load_authored_bank,
)
from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_curriculum.content import CurriculumContent, load_curriculum


class CurriculumLoadError(Exception):
    """An authored item failed the §5.8.5 validation suite - never inserted.

    D-226 removed the shape bank this also used to guard. The remaining source of a load
    failure is `curriculum/internal_math/authored/*.yaml`, which is hand-editable and is
    re-validated on every load in every environment (D-190) rather than trusted.
    """


@dataclass
class LoadSummary:
    topics_created: int = 0
    skills_created: int = 0
    templates_created: int = 0
    templates_skipped_existing: int = 0
    variants_created: int = 0
    # D-210: authored templates retired because the bank file no longer lists them.
    templates_retired: int = 0
    # D-235: authored templates already present whose file content had changed.
    templates_updated: int = 0


async def _load_taxonomy(
    session: AsyncSession, curriculum: CurriculumContent, summary: LoadSummary
) -> None:
    repo = CurriculumRepository(session)

    for topic_def in curriculum.topics:
        if await repo.get_topic(topic_def.topic_id) is not None:
            continue
        await repo.create_topic(
            Topic(
                topic_id=topic_def.topic_id,
                curriculum_version=curriculum.curriculum_version,
                name=topic_def.name,
                grade_band=topic_def.grade_band,
            )
        )
        summary.topics_created += 1

    for skill_def in curriculum.skills:
        if await repo.get_skill(skill_def.skill_id) is not None:
            continue
        await repo.create_skill(
            Skill(skill_id=skill_def.skill_id, topic_id=skill_def.topic_id, name=skill_def.name)
        )
        summary.skills_created += 1


def _file_owned_template_fields(
    template_def: AuthoredTemplateDef, curriculum: CurriculumContent
) -> dict[str, object]:
    """The template columns the bank file is the source of truth for (D-235).

    One definition used by both the insert and the update, so the two cannot drift into
    disagreeing about what a load is allowed to write. Everything absent from here is
    either lifecycle state the database owns or a constant of authored mode.
    """
    return {
        "question_template_id": template_def.question_template_id,
        "curriculum_version": curriculum.curriculum_version,
        "topic_id": template_def.topic_id,
        "skill_id": template_def.skill_id,
        "grade_band": template_def.grade_band,
        "difficulty_label": template_def.difficulty_label,
        "difficulty_confidence": template_def.difficulty_confidence,
        "common_error_tags": template_def.common_error_tags,
        "estimated_time_seconds": template_def.estimated_time_seconds,
        "generator_model": template_def.generator_model,
        "review_model_versions": template_def.review_model_versions,
        "stem": template_def.stem,
        "context_block": template_def.context_block,
        "answer_expression": template_def.answer_expression,
        # `mode="json"` is load-bearing, not cosmetic (D-279). `CoordinateGridFigure`
        # types its points as tuples; a plain `model_dump()` returns Python tuples, and
        # the JSON column returns them as lists - so the stored value never equalled the
        # file value and every load rewrote all six coordinate items. A tuple-typed field
        # in a JSON column is idempotent only when it is dumped the way it is stored.
        "figure_spec": (
            template_def.figure_spec.model_dump(mode="json") if template_def.figure_spec else None
        ),
        "figure_reading": template_def.figure_reading,
        "hint_ladder": template_def.hint_ladder,
        "canonical_solution": template_def.canonical_solution,
        "review_priority": template_def.review_priority,
        "version": template_def.version,
    }


def _file_owned_variant_fields(template_def: AuthoredTemplateDef) -> dict[str, object]:
    """The canonical variant's columns the file owns - the item as a student sees it."""
    return {
        "random_seed": template_def.random_seed,
        "rendered_question": template_def.rendered_question,
        "option_a": template_def.option_a,
        "option_b": template_def.option_b,
        "option_c": template_def.option_c,
        "option_d": template_def.option_d,
        "correct_option": template_def.correct_option,
    }


def _drifted(row: object, fields: dict[str, object]) -> set[str]:
    return {field for field, value in fields.items() if getattr(row, field) != value}


def _gate(template_def: AuthoredTemplateDef, curriculum: CurriculumContent) -> None:
    """The §5.8.5 deterministic gate, on the insert path and the update path alike.

    Being reachable from the update path is the point: this file is hand-editable YAML
    loaded into every environment, and before D-235 an edit to an item a database already
    had never got here at all.

    `curriculum` is passed for one reason: the skill's `answer_form` (D-308). It has to be
    the *same* value the pipeline used, so both read it through `CurriculumContent.answer_form`
    rather than each looking the skill up its own way.
    """
    result = validate_authored_item(
        template_def.difficulty_label,
        template_def.to_generated_item(),
        figure=template_def.figure_spec,
        figure_reading=template_def.figure_reading,
        answer_form=curriculum.answer_form(template_def.skill_id),
    )
    if not result.passed:
        raise CurriculumLoadError(
            f"authored template {template_def.question_template_id} failed validation: "
            f"{result.failures}"
        )


async def _load_authored_templates(
    session: AsyncSession,
    curriculum: CurriculumContent,
    topic_id: str,
    templates: list[AuthoredTemplateDef],
    summary: LoadSummary,
) -> None:
    """Load approved authored items from their versioned file (D-190).

    There is no rendering to generate - the content is the artifact, so the canonical
    variant is written from the file rather than recomputed from a seed. Validation is
    `validate_authored_item`, the same §5.8.5 gate the pipeline applied, because this file
    is hand-editable YAML that is loaded into every environment including production. A
    file whose options no longer agree with its answer fails the load rather than reaching
    a student.

    A re-run whose file is unchanged is a no-op. An item already present whose file content
    has changed is **re-gated and updated in place** (D-235).

    That last part used to be a skip-by-id, and the skip sat *above* the gate, so both
    promises this docstring and `authored_bank`'s make - "re-validated on load, not trusted",
    "editing a correct answer without editing its options fails the load" - held only for an
    item the environment had never seen. Every long-lived database silently kept its old
    copy while the load reported success. D-235 found it the direct way: 16 items were
    re-tiered, and `make curriculum-load` said "127 already existed, 0 created".

    Only the columns the *file* owns are written. `active_status` and `validation_status`
    are lifecycle state owned by the database (D-210's retirement, `review_cli`'s approval),
    and a load must not resurrect a retired item just by listing it.
    """
    repo = QuestionRepository(session)

    # D-210: **the bank file decides what is servable.** Until then a *removal* never
    # propagated - a template dropped from the file kept being served forever by every
    # database that had already loaded it. (An *edit* did not propagate either; that half
    # went unnoticed for another twelve decisions and was fixed in D-235, below.)
    #
    # That is not hypothetical. Five of the forty-eight approved items were bare equations
    # ("Solve for x: 2x + 7 = 19"), evidently the original pre-D-186 seeds. Deleting them
    # from the file changed nothing: a pinned pre-exam capture still served one.
    #
    # Retiring rather than deleting, so the row and its attempt history survive for
    # reporting; `active_status` is what the serving path filters on.
    #
    # Guarded on a non-empty list on purpose. An empty `templates` means "this file failed
    # to parse or was not found", and retiring the entire authored bank on that is a much
    # worse failure than not retiring anything.
    #
    # **Scoped to this file's own topic (D-222).** `get_authored_templates()` is
    # deliberately unfiltered - a retired row must still be found so it can be reactivated -
    # so the topic check belongs here, at the one caller that knows which file it is
    # loading. Without it, the very first day a second authored bank file exists, the two
    # loads retire each other: `fraction_operations` retires all 47 `linear_equations`
    # items for not being in its file, then `linear_equations` retires the 15 items
    # `fraction_operations` just created. One `make curriculum-load` and no topic is
    # servable at all, because `_servable()` filters on `active_status`. The bug was
    # invisible while exactly one topic had authored content, and its blast radius is
    # every environment, production included.
    if templates:
        wanted = {t.question_template_id for t in templates}
        for existing in await repo.get_authored_templates():
            if existing.topic_id != topic_id:
                continue
            if existing.question_template_id not in wanted and existing.active_status == "active":
                await repo.set_active_status(existing.question_template_id, "retired")
                summary.templates_retired += 1

    for template_def in templates:
        template_fields = _file_owned_template_fields(template_def, curriculum)
        variant_fields = _file_owned_variant_fields(template_def)

        existing = await repo.get_template(template_def.question_template_id)
        if existing is not None:
            existing_variant = await repo.get_variant_for_template(
                template_def.question_template_id
            )
            drifted = _drifted(existing, template_fields)
            if existing_variant is not None:
                drifted |= _drifted(existing_variant, variant_fields)
            if not drifted:
                summary.templates_skipped_existing += 1
                continue

            _gate(template_def, curriculum)
            for field, value in template_fields.items():
                setattr(existing, field, value)
            if existing_variant is not None:
                for field, value in variant_fields.items():
                    setattr(existing_variant, field, value)
            await session.flush()
            summary.templates_updated += 1
            continue

        _gate(template_def, curriculum)

        template = await repo.create_template(
            QuestionTemplate(
                **template_fields,
                question_type="multiple_choice",
                parameter_schema={},
                solution_function=AUTHORED_SOLUTION_FUNCTION,
                correct_option_generator=AUTHORED_SOLUTION_FUNCTION,
                distractor_generators=[],
                # Lifecycle, not content: set once on arrival and owned by the database
                # afterwards, which is why the update path above does not touch them. The
                # human approval happened before the export and the file is its record
                # (D-026); retirement is D-210's, and a load must not undo it.
                validation_status="approved",
                active_status="active",
                authoring_mode=AUTHORED_MODE,
                # Not exported - see `authored_bank`'s module docstring. Nothing on the
                # serving path reads it; authoring environments re-embed.
                stem_embedding=None,
            )
        )
        summary.templates_created += 1

        await repo.create_variant(
            QuestionVariant(
                # The item's own rendering, which is what `build_variant_row` serves from
                # (D-189) - an authored template has no shape to render.
                origin=VARIANT_ORIGIN_CANONICAL,
                question_template_id=template.question_template_id,
                parameter_values={},
                **variant_fields,
            )
        )
        summary.variants_created += 1


async def load_curriculum_and_templates(session: AsyncSession) -> LoadSummary:
    curriculum = load_curriculum()
    summary = LoadSummary()
    await _load_taxonomy(session, curriculum, summary)
    for topic_id, authored_templates in load_authored_bank().items():
        await _load_authored_templates(session, curriculum, topic_id, authored_templates, summary)
    return summary


_log = logging.getLogger(__name__)


async def main() -> None:
    # D-244 closes a carry-over that had stood for twelve decisions. The deploy runs this
    # as an ECS ops task and asserts only `test "$EXIT_CODE" = "0"` - so the summary line
    # below, which is the one place that distinguishes created / updated / unchanged /
    # retired, went to CloudWatch as unstructured text nobody could query and nothing could
    # alarm on. D-235's defect hid behind exactly that line ("127 already existed, 0
    # created") for twelve decisions.
    #
    # The `print` stays: it is what a human running `make` reads. The record below is what
    # a metric filter and a Logs Insights query can read.
    configure_logging()
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            summary = await load_curriculum_and_templates(session)
            await session.commit()
        print(
            f"Loaded curriculum: {summary.topics_created} topics, {summary.skills_created} "
            f"skills, {summary.templates_created} templates created "
            f"({summary.templates_updated} updated, "
            f"{summary.templates_skipped_existing} unchanged, "
            f"{summary.templates_retired} retired), "
            f"{summary.variants_created} sample variants."
        )
        _log.info(
            "curriculum_load_complete",
            extra={
                "topics_created": summary.topics_created,
                "skills_created": summary.skills_created,
                "templates_created": summary.templates_created,
                "templates_updated": summary.templates_updated,
                "templates_unchanged": summary.templates_skipped_existing,
                "templates_retired": summary.templates_retired,
                "variants_created": summary.variants_created,
            },
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
