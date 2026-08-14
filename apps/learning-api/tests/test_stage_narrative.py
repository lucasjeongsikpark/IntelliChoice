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
from learning_api.services.stage_narrative import _fallback_text, generate_stage_narrative
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


def test_an_inverted_score_pair_falls_back_to_the_template() -> None:
    """AUD-L-09 on the student-facing half, through the service rather than the unit. Only
    `post_outro` carries both scores (`test_stage_payloads_stay_narrow.py` pins that), so it
    is the only stage where this can happen at all.

    Both numbers are the payload's own, so this text was grounded and shipped before the
    directional rule existed - to a student who had just improved by 2 points, in a product
    whose whole framing is growth-oriented (SPEC §5.10.3).
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StageTransitionRepository(session)
            gateway = _FakeGateway(
                [StageNarrativeResponse(narrative_text="Your score slipped from 6 to 4.")]
            )

            result = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-inverted",
                payload=_payload(
                    stage="post_outro",
                    pre_raw_score=4.0,
                    post_raw_score=6.0,
                    raw_gain=2.0,
                ),
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert "slipped" not in result.narrative_text
            # `4`, not `4.0`: the payload field is a float because the schema is shared, but
            # a raw score is a whole number of questions and the student is shown a score,
            # not a measurement. Grounding still holds - `_matches` accepts a value rounded
            # to the nearest integer, so the payload's `4.0` grounds the text `4`.
            assert "from 4 to 6" in result.narrative_text

    asyncio.run(run())


def test_the_same_pair_in_the_right_order_is_still_trusted() -> None:
    """The control for the test above: the rule must not reject the ordinary post-exam
    sentence, which is the one this stage exists to produce.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StageTransitionRepository(session)
            gateway = _FakeGateway(
                [StageNarrativeResponse(narrative_text="You went from 4 to 6 - nice work!")]
            )

            result = await generate_stage_narrative(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                learning_session_id="session-ordered",
                payload=_payload(
                    stage="post_outro",
                    pre_raw_score=4.0,
                    post_raw_score=6.0,
                    raw_gain=2.0,
                ),
                session_spend_cents=0.0,
            )

            assert result.generated is True
            assert result.narrative_text == "You went from 4 to 6 - nice work!"

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


def test_the_fallback_counts_one_hint_as_a_hint_and_not_as_hints() -> None:
    """The copy defect a student actually reads. `study_outro`'s fallback said "You used 1
    hints and viewed 1 solutions", which is the kind of small wrongness that teaches a reader
    the rest of the sentence is boilerplate - and this fallback is not a rare path: any
    gateway failure or grounding rejection lands on it.

    Both counts and both directions in one test, because "1 hint" alone would still pass with
    the plural branch broken.
    """
    one = _fallback_text(
        _payload(stage="study_outro", hint_count=1, solution_count=1, video_count=0)
    )
    assert "You used 1 hint and viewed 1 solution" in one

    many = _fallback_text(
        _payload(stage="study_outro", hint_count=3, solution_count=2, video_count=0)
    )
    assert "3 hints" in many
    assert "2 solutions" in many


def test_the_fallback_shows_whole_scores_as_integers() -> None:
    """`post_outro` read "You went from 2.0 to 10.0. That's a gain of 8.0 points." beside a
    UI that prints integers everywhere else. The payload fields are floats because one schema
    serves every stage, which is a wire concern and not something a K-12 student should be
    shown.

    A fractional value keeps one decimal rather than being rounded away - the guard against
    "fix the display, lose the number".
    """
    whole = _fallback_text(
        _payload(stage="post_outro", pre_raw_score=2.0, post_raw_score=10.0, raw_gain=8.0)
    )
    assert "from 2 to 10" in whole
    assert "8 points" in whole
    assert "2.0" not in whole and "10.0" not in whole and "8.0" not in whole

    assert "1 point." in _fallback_text(
        _payload(stage="post_outro", pre_raw_score=9.0, post_raw_score=10.0, raw_gain=1.0)
    )
    assert "1.5 points" in _fallback_text(
        _payload(stage="post_outro", pre_raw_score=8.5, post_raw_score=10.0, raw_gain=1.5)
    )
