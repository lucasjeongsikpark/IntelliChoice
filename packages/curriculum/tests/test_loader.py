import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.questions import QuestionRepository
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    """Mirrors packages/db/tests/conftest.py's probe (D-008/D-013 style), inlined
    here rather than shared: pytest's importlib import-mode names test-package
    conftest modules by their directory, and this repo already has a
    packages/db/tests package, so a same-named tests/conftest.py collides.
    """

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


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)


def test_loading_curriculum_produces_the_expected_final_state() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            summary = await load_curriculum_and_templates(session)

            # Idempotent by natural key: whether this call creates rows or finds
            # them already loaded (e.g. from a prior `make curriculum-load` run
            # against this same dev DB) depends on prior state - what must always
            # hold is the created+skipped total and the resulting data shape.
            assert summary.templates_created + summary.templates_skipped_existing == 50

            curriculum_repo = CurriculumRepository(session)
            topic = await curriculum_repo.get_topic("linear_equations")
            assert topic is not None
            assert topic.name == "Linear Equations"

            question_repo = QuestionRepository(session)
            active = await question_repo.get_active_questions("linear_equations", difficulty=1)
            assert len(active) == 10

    asyncio.run(run())


def test_loader_is_idempotent() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            await load_curriculum_and_templates(session)
            second = await load_curriculum_and_templates(session)

            assert second.topics_created == 0
            assert second.skills_created == 0
            assert second.templates_created == 0
            assert second.templates_skipped_existing == 50

    asyncio.run(run())


def test_loader_rejects_a_template_that_fails_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    from intellichoice_curriculum import loader
    from intellichoice_curriculum.templates.model import QuestionTemplateDef
    from intellichoice_curriculum.validation import ValidationResult

    def _always_fails(*args: object, **kwargs: object) -> object:
        result = ValidationResult()
        result.fail("forced failure for this test")
        return result

    monkeypatch.setattr(loader, "validate_variant", _always_fails)
    # A synthetic topic_id guarantees this template can never already exist in the
    # DB (unlike the real linear_equations bank, which `make curriculum-load` may
    # have already persisted), so the loader is forced to actually attempt it.
    monkeypatch.setattr(
        loader,
        "TEMPLATE_BANKS",
        {
            "zzz_test_topic_never_loaded": [
                QuestionTemplateDef(
                    topic_id="linear_equations",
                    skill_id="linear_one_step",
                    grade_band="6-7",
                    difficulty_label=1,
                    parameter_schema={"b": {"min": 1, "max": 9}, "x": {"min": 1, "max": 9}},
                    solution_function="one_step_add",
                    correct_option_generator="format_integer",
                    distractor_generators=[
                        "distractor_sign_flip",
                        "distractor_off_by_one",
                        "distractor_scaled",
                    ],
                    estimated_time_seconds=25,
                )
            ]
        },
    )

    async def run() -> None:
        async with _rollback_session() as session:
            with pytest.raises(loader.CurriculumLoadError):
                await load_curriculum_and_templates(session)

    asyncio.run(run())
