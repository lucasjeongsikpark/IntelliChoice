"""S26 (SPEC §5.10.3/§5.13.3, plan §18-L7) - `services/stage_narrative.py`'s
generation/grounding/fallback/persistence logic, isolated from the graph via a scripted
fake `BedrockGateway` (same pattern as `packages/memory/tests/test_consolidation.py`'s
`_FakeGateway` and `apps/learning-api/tests/test_tutor_service.py`'s). Real Postgres via
a rollback session (D-013 pattern) - skips cleanly when Postgres is unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from intellichoice_db.engine import create_engine
from intellichoice_db.repositories.stage_transition import StageTransitionRepository
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    StageNarrativePayload,
    StageNarrativeResponse,
)
from learning_api.services.stage_narrative import generate_stage_narrative
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM stage_transitions LIMIT 1"))
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

STUDENT_ID = "stage-narrative-test-student-1"


class _FakeGateway:
    """Returns each queued `StageNarrativeResponse`/`BedrockGatewayError` in order, one
    per `generate_structured` call - a second call past the queue raises `IndexError`,
    which is exactly how the idempotency test below proves no second call happened.
    """

    def __init__(self, outcomes: list[StageNarrativeResponse | BedrockGatewayError]) -> None:
        self._outcomes = list(outcomes)

    async def generate_structured(self, *, task: BedrockTask, **kwargs) -> BedrockGenerationResult:
        del task, kwargs
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BedrockGatewayError):
            raise outcome
        return BedrockGenerationResult(
            value=outcome,
            input_tokens=10,
            output_tokens=10,
            cost_cents=0.5,
            model_id="test-model",
            repaired=False,
        )

    async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
        raise NotImplementedError


def _payload(**overrides) -> StageNarrativePayload:
    fields = {
        "stage": "pre_outro",
        "grade": "7th grade",
        "weak_skill_names": ["Solve one-step linear equations"],
        "target_skill_name": "Solve one-step linear equations",
    }
    fields.update(overrides)
    return StageNarrativePayload(**fields)


def test_gateway_failure_falls_back_to_deterministic_template() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StageTransitionRepository(session)
            gateway = _FakeGateway([BedrockGatewayError("simulated failure", cost_cents=0.2)])

            result = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-1",
                payload=_payload(),
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert result.cost_cents == 0.2
            assert "Solve one-step linear equations" in result.narrative_text

            stored = await repo.get_for_session_stage("session-1", "pre_outro")
            assert stored is not None
            assert stored.generated is False
            assert stored.narrative_text == result.narrative_text

    asyncio.run(run())


def test_ungrounded_response_falls_back_to_deterministic_template() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StageTransitionRepository(session)
            # 42 appears nowhere in the payload's evidence - an invented number.
            gateway = _FakeGateway(
                [StageNarrativeResponse(narrative_text="You scored 42 points today!")]
            )

            result = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-2",
                payload=_payload(),
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert "42" not in result.narrative_text

    asyncio.run(run())


def test_grounded_response_is_trusted_as_is() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StageTransitionRepository(session)
            gateway = _FakeGateway(
                [
                    StageNarrativeResponse(
                        narrative_text="Let's strengthen Solve one-step linear equations!"
                    )
                ]
            )

            result = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-3",
                payload=_payload(),
                session_spend_cents=0.0,
            )

            assert result.generated is True
            assert result.narrative_text == "Let's strengthen Solve one-step linear equations!"

    asyncio.run(run())


def test_second_call_for_the_same_stage_is_idempotent_no_new_gateway_call() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StageTransitionRepository(session)
            # Only one outcome queued - a second `generate_structured` call would raise
            # IndexError, proving the idempotency check short-circuited before it.
            gateway = _FakeGateway(
                [StageNarrativeResponse(narrative_text="Welcome back! Let's get started.")]
            )

            first = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-4",
                payload=_payload(stage="pre_intro", weak_skill_names=[], target_skill_name=None),
                session_spend_cents=0.0,
            )
            second = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-4",
                payload=_payload(stage="pre_intro", weak_skill_names=[], target_skill_name=None),
                session_spend_cents=0.0,
            )

            assert second.narrative_text == first.narrative_text
            assert second.cost_cents == 0.0

            rows = await repo.list_for_session("session-4")
            assert len(rows) == 1

    asyncio.run(run())


def test_study_step_calls_are_scoped_by_related_skill_id() -> None:
    """A second `study_step` firing for a *different* skill transition must not be
    treated as a duplicate of the first - `related_skill_id` is part of the
    idempotency key.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StageTransitionRepository(session)
            gateway = _FakeGateway(
                [
                    StageNarrativeResponse(narrative_text="Nice work! Let's move on."),
                    StageNarrativeResponse(narrative_text="Great job! Onward."),
                ]
            )

            first = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-5",
                payload=_payload(stage="study_step"),
                related_skill_id="skill-a",
                session_spend_cents=0.0,
            )
            second = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-5",
                payload=_payload(stage="study_step"),
                related_skill_id="skill-b",
                session_spend_cents=0.0,
            )

            assert first.generated is True
            assert second.generated is True
            assert first.narrative_text != second.narrative_text

            rows = await repo.list_for_session("session-5")
            assert {r.related_skill_id for r in rows} == {"skill-a", "skill-b"}

    asyncio.run(run())
