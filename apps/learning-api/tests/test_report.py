"""ROADMAP S28 (SPEC §5.14.2-§5.14.4, plan §18-L9) - `services/report.py`'s audience
gating, grounding/fallback, and persistence logic, isolated from the router via a
scripted fake `BedrockGateway` (same pattern as `test_stage_narrative.py`'s
`_FakeGateway`). Real Postgres via a rollback session (D-013) - skips cleanly when
Postgres is unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from intellichoice_db.engine import create_engine
from intellichoice_db.models.student_report import StudentReport
from intellichoice_db.repositories.student_report import StudentReportRepository
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    ReportInterpretationPayload,
    ReportInterpretationResponse,
)
from learning_api.services.dashboard import (
    DashboardData,
    MasterySkillPoint,
    PrePostSkillPoint,
    UsageBreakdown,
)
from learning_api.services.report import (
    DAILY_REPORT_COST_CEILING_CENTS,
    build_report_facts,
    generate_student_report,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM student_reports LIMIT 1"))
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

STUDENT_ID = "report-test-student-1"


class _FakeGateway:
    def __init__(self, outcomes: list) -> None:
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


def _dashboard() -> DashboardData:
    return DashboardData(
        mastery_by_skill=[MasterySkillPoint(skill_name="Two-Step Equations", weighted_score=0.6)],
        pre_post_by_skill=[
            PrePostSkillPoint(skill_name="Two-Step Equations", pre_accuracy=0.4, post_accuracy=0.6)
        ],
        gains_over_time=[],
        accuracy_trend=[],
        difficulty_progression=[],
        usage=UsageBreakdown(
            hint_count=2, solution_count=1, video_count=0, independent_count=3, total_attempts=6
        ),
        attempts_count=6,
        time_spent_minutes=12.5,
        latest_pre_raw_score=4.0,
        latest_post_raw_score=6.0,
        latest_raw_gain=2.0,
        tutor_review_flagged=True,
    )


def _payload(audience: str) -> ReportInterpretationPayload:
    return build_report_facts(
        audience=audience,
        grade="7th grade",
        date_range_label="last 30 days",
        dashboard=_dashboard(),
        relevant_learning_facts=["Consistently makes sign errors on two-step equations."],
    )


def test_student_facts_omit_tutor_review_flag() -> None:
    payload = _payload("student")
    assert payload.tutor_review_flagged is None
    assert payload.pre_raw_score == 4.0
    assert payload.weak_skill_names == ["Two-Step Equations"]


def test_parent_facts_include_tutor_review_flag() -> None:
    payload = _payload("parent")
    assert payload.tutor_review_flagged is True
    assert payload.hint_count == 2


def test_tutor_facts_exclude_usage_and_mastery_detail() -> None:
    payload = _payload("tutor")
    assert payload.tutor_review_flagged is True
    assert payload.hint_count is None
    assert payload.mastery_by_skill == {}
    assert payload.time_spent_minutes is None
    assert payload.pre_raw_score == 4.0


def test_branch_manager_facts_match_tutor_field_set() -> None:
    tutor_payload = _payload("tutor")
    branch_manager_payload = _payload("branch_manager")
    assert tutor_payload.model_dump(exclude={"audience"}) == branch_manager_payload.model_dump(
        exclude={"audience"}
    )


def test_gateway_failure_falls_back_to_facts_only_template() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            gateway = _FakeGateway([BedrockGatewayError("simulated failure", cost_cents=0.2)])

            result = await generate_student_report(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert result.cost_cents == 0.2
            assert "4.0" in result.interpretation_text or "6.0" in result.interpretation_text

            stored = await repo.list_for_student(STUDENT_ID)
            assert len(stored) == 1
            assert stored[0].generated is False

    asyncio.run(run())


def test_ungrounded_response_falls_back_to_facts_only_template() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            # 99 appears nowhere in the payload's evidence - an invented number.
            gateway = _FakeGateway(
                [
                    ReportInterpretationResponse(
                        interpretation_text="You scored 99 points today!",
                        recommendations_text="Keep it up.",
                    )
                ]
            )

            result = await generate_student_report(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert "99" not in result.interpretation_text

    asyncio.run(run())


def test_grounded_response_is_trusted_as_is() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            gateway = _FakeGateway(
                [
                    ReportInterpretationResponse(
                        interpretation_text="Score improved from 4.0 to 6.0.",
                        recommendations_text="Focus on Two-Step Equations.",
                    )
                ]
            )

            result = await generate_student_report(
                gateway=gateway,
                repo=repo,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                session_spend_cents=0.0,
            )

            assert result.generated is True
            assert result.interpretation_text == "Score improved from 4.0 to 6.0."

            stored = await repo.list_for_student(STUDENT_ID)
            assert stored[0].generated is True
            assert stored[0].audience == "parent"

    asyncio.run(run())


class _ExplodingGateway:
    """Fails the test if Bedrock is called at all - the ceiling must short-circuit
    *before* the call, not bill for one and then refuse the next.
    """

    async def generate_structured(self, **kwargs) -> BedrockGenerationResult:
        del kwargs
        raise AssertionError("Bedrock was called despite the per-day cost ceiling")

    async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
        raise NotImplementedError


async def _seed_spend(repo: StudentReportRepository, cents: float) -> None:
    await repo.create(
        StudentReport(
            student_external_id=STUDENT_ID,
            audience="parent",
            verified_facts={},
            interpretation_text="seeded",
            recommendations_text="seeded",
            generated=True,
            cost_cents=cents,
        )
    )


def test_report_generation_stops_calling_bedrock_at_the_daily_cost_ceiling() -> None:
    """S36/AUD-L-02 regression. Before the fix this endpoint had no cost ceiling at all:
    it passed `session_spend_cents=0.0` on every call, so the gateway's own budget check
    could never fire, and one authenticated caller could drive unlimited Bedrock spend
    bounded only by a 6,000-request/60s per-IP rate limiter.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            await _seed_spend(repo, DAILY_REPORT_COST_CEILING_CENTS)

            result = await generate_student_report(
                gateway=_ExplodingGateway(),
                repo=repo,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                session_spend_cents=DAILY_REPORT_COST_CEILING_CENTS,
            )

            # Degrades to the facts-only template rather than erroring: the caller still
            # gets their real verified numbers.
            assert result.generated is False
            assert result.cost_cents == 0.0
            assert "4.0" in result.interpretation_text or "6.0" in result.interpretation_text

    asyncio.run(run())


def test_report_generation_still_runs_just_below_the_daily_cost_ceiling() -> None:
    """The boundary in the other direction - a ceiling that also blocks legitimate use is
    a different bug, so the threshold is pinned from both sides.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            await _seed_spend(repo, DAILY_REPORT_COST_CEILING_CENTS - 0.5)

            result = await generate_student_report(
                gateway=_FakeGateway(
                    [
                        ReportInterpretationResponse(
                            interpretation_text="Score improved from 4.0 to 6.0.",
                            recommendations_text="Focus on Two-Step Equations.",
                        )
                    ]
                ),
                repo=repo,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                session_spend_cents=DAILY_REPORT_COST_CEILING_CENTS - 0.5,
            )

            assert result.generated is True

    asyncio.run(run())


def test_spend_query_only_counts_this_students_reports_inside_the_window() -> None:
    """The ceiling must not be tripped by another student's spend, nor by this student's
    spend from a week ago - either would deny a legitimate report.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            await _seed_spend(repo, 30.0)
            await repo.create(
                StudentReport(
                    student_external_id="some-other-student",
                    audience="parent",
                    verified_facts={},
                    interpretation_text="seeded",
                    recommendations_text="seeded",
                    generated=True,
                    cost_cents=40.0,
                )
            )

            recent = await repo.get_spend_cents_since(
                STUDENT_ID, datetime.now(UTC) - timedelta(hours=24)
            )
            assert recent == pytest.approx(30.0)

            future_window = await repo.get_spend_cents_since(
                STUDENT_ID, datetime.now(UTC) + timedelta(hours=1)
            )
            assert future_window == pytest.approx(0.0)

    asyncio.run(run())
