"""D-190: approved authored content as a versioned file the loader reads.

The gap these cover was found by CI, not by reasoning: D-189 approved five authored items
locally, the suite went green, and CI failed because its database is seeded from
`loader.py` and had none of them. Approval was a row update in one database, so no
reviewed item could reach CI, staging or production.

Real Postgres via a rollback session (D-013), same pattern as `test_loader.py`.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import yaml
from intellichoice_curriculum.authored_bank import (
    AuthoredBankFile,
    AuthoredTemplateDef,
    load_authored_bank,
)
from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.export_cli import build_bank_file, render_bank_file
from intellichoice_curriculum.loader import (
    CurriculumLoadError,
    LoadSummary,
    _load_authored_templates,
)
from intellichoice_db.engine import create_engine
from intellichoice_db.repositories.questions import QuestionRepository
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM topics LIMIT 1"))
                except Exception:
                    return "Postgres schema is not migrated (run `make up && make db-upgrade`)"
            return None
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)


@asynccontextmanager
async def _rollback_session() -> AsyncIterator[AsyncSession]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()


def _item(**overrides: object) -> AuthoredTemplateDef:
    base: dict[str, object] = dict(
        question_template_id="authored-bank-test-item",
        topic_id="linear_equations",
        skill_id="linear_one_step",
        grade_band="6-7",
        difficulty_label=1,
        estimated_time_seconds=45,
        generator_model="test",
        stem="Solve for x: x + 3 = 7",
        hint_ladder=["What undoes adding 3?", "Subtract 3 from both sides.", "Compute 7 - 3."],
        canonical_solution={
            "steps": [
                {"step_number": 1, "explanation": "Subtract 3.", "expression": "x = 7 - 3"}
            ],
            "final_answer": "4",
        },
        answer_expression="Eq(x + 3, 7)",
        random_seed=1,
        rendered_question="Solve for x: x + 3 = 7",
        option_a="4",
        option_b="5",
        option_c="10",
        option_d="3",
        correct_option="a",
    )
    base.update(overrides)
    return AuthoredTemplateDef(**base)  # type: ignore[arg-type]


def test_the_repo_bank_file_parses_and_every_item_still_validates() -> None:
    """The file is hand-editable YAML that loads into production, so it is guarded here.

    This is the cheap half of the load-time gate: it runs with no database and fails on a
    typo, a broken schema, or an edit that leaves an item's options disagreeing with its
    answer - without waiting for someone to run the loader.
    """
    banks = load_authored_bank()
    for topic_id, templates in banks.items():
        assert templates, f"{topic_id}.yaml exists but declares no templates"
        ids = [t.question_template_id for t in templates]
        assert len(set(ids)) == len(ids), f"duplicate template ids in {topic_id}.yaml"
        for template in templates:
            result = validate_authored_item(
                template.difficulty_label, template.to_generated_item()
            )
            assert result.passed, f"{template.question_template_id}: {result.failures}"


def test_the_repo_bank_file_matches_what_the_database_would_export() -> None:
    """Catches the drift that D-189 shipped: approved locally, never exported.

    An item approved in a database but absent from the file reaches no other environment,
    which is the exact failure this whole mechanism exists to prevent - so it fails here,
    in the repository, rather than silently on someone else's machine.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        on_disk = load_authored_bank()
        async with _rollback_session() as session:
            for topic_id, expected in on_disk.items():
                exported = await build_bank_file(
                    session,
                    topic_id=topic_id,
                    curriculum_version=curriculum.curriculum_version,
                )
                assert exported.templates == expected, (
                    f"{topic_id}.yaml is out of date with the approved set in the database "
                    f"- run `make question-export` and commit the diff"
                )

    asyncio.run(run())


def test_export_round_trips_through_yaml_unchanged() -> None:
    """Rendering and re-parsing must be lossless, or the file is not the content."""
    bank = AuthoredBankFile(
        curriculum_version="2026.1", topic_id="linear_equations", templates=[_item()]
    )
    reparsed = AuthoredBankFile.model_validate(yaml.safe_load(render_bank_file(bank)))
    assert reparsed == bank


def test_loading_is_idempotent_and_lands_approved_and_servable() -> None:
    """A second load is a no-op, and what lands is immediately deliverable."""

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            repo = QuestionRepository(session)
            item = _item()

            summary = LoadSummary()
            await _load_authored_templates(session, curriculum, [item], summary)
            assert (summary.templates_created, summary.variants_created) == (1, 1)

            template = await repo.get_template(item.question_template_id)
            assert template is not None
            # Approved and active on arrival: the human approval happened before the
            # export, and the file is the record of it (D-026).
            assert template.validation_status == "approved"
            assert template.active_status == "active"
            assert template.authoring_mode == "authored"
            # The canonical variant is what D-189's serving path reads.
            variant = await repo.get_variant_for_template(item.question_template_id)
            assert variant is not None
            assert variant.rendered_question == item.rendered_question
            assert variant.correct_option == item.correct_option
            # Deliverable through the unchanged runtime selection query.
            active = await repo.get_active_questions(item.topic_id, difficulty=1)
            assert item.question_template_id in {t.question_template_id for t in active}

            again = LoadSummary()
            await _load_authored_templates(session, curriculum, [item], again)
            assert (again.templates_created, again.templates_skipped_existing) == (0, 1)

    asyncio.run(run())


def test_an_edited_item_whose_answer_no_longer_matches_fails_the_load() -> None:
    """The reason the loader re-validates instead of trusting the file.

    Changing a correct answer without changing the options is the plausible hand-edit, and
    it is the one that would put a wrong answer in front of a student. The load aborts
    rather than inserting - same posture the shape bank's loader has.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            broken = _item(
                question_template_id="authored-bank-test-broken",
                # Options still say 4; the expression now solves to 5.
                answer_expression="Eq(x + 3, 8)",
            )
            with pytest.raises(CurriculumLoadError) as excinfo:
                await _load_authored_templates(session, curriculum, [broken], LoadSummary())
            assert "does not match declared correct option" in str(excinfo.value)

            repo = QuestionRepository(session)
            assert await repo.get_template(broken.question_template_id) is None

    asyncio.run(run())
