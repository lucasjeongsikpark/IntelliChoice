"""ROADMAP S28 (SPEC §5.14.2-§5.14.4, plan §18-L9) - `services/report.py`'s audience
gating, grounding/fallback, and persistence logic, isolated from the router via a
scripted fake `BedrockGateway` (same pattern as `test_stage_narrative.py`'s
`_FakeGateway`). Real Postgres via a rollback session (D-013) - skips cleanly when
Postgres is unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.models.cost_reservation import SCOPE_STUDENT_REPORT
from intellichoice_db.repositories.cost_reservation import CostReservationRepository
from intellichoice_db.repositories.student_report import StudentReportRepository
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    ReportInterpretationPayload,
    ReportInterpretationResponse,
)
from intellichoice_shared.mastery_policy import WEAK_SKILL_THRESHOLD
from learning_api.services.dashboard import (
    DashboardData,
    MasterySkillPoint,
    PrePostSkillPoint,
    UsageBreakdown,
)
from learning_api.services.report import (
    _SYSTEM_PROMPT,
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


# --- AUD-L-15 (D-156): windows, and one definition of "weak" -------------------------
#
# Two defects under one finding. `mastery_by_skill` and `weak_skill_names` arrived under a
# single `date_range_label` that described neither, and they were computed from different
# sources with different cuts - mastery from pre+study at `WEAK_SKILL_THRESHOLD` (0.7,
# difficulty-weighted), "skills to strengthen" from post-exam accuracy at a hardcoded 0.8.
# S36's `aud-student-premax` came out reading mastery 1.000 for `linear_distribute` beside
# "Skills to strengthen: ... distribution", labelled "all time", both marked verified.
#
# Both halves are closed here. Mastery now includes the post-exam (see
# `test_learning_flow.py::test_mastery_counts_the_post_exam`), and "skills to strengthen"
# is now the same number under the same cut the study plan uses - so the report cannot
# recommend working on something different from what the system will actually work on.
# What remains genuinely two windows is mastery (all-time) versus the range-filtered
# aggregates, and each now says so.


def _premax_dashboard() -> DashboardData:
    """The shape S36's `aud-student-premax` used to produce: mastery reading a perfect
    1.000 for a skill whose post-exam accuracy was 0.0, because only one of the two fed
    mastery. Kept as a fixture precisely because the report can no longer be made to
    contradict itself from it.
    """
    data = _dashboard()
    return replace(
        data,
        mastery_by_skill=[MasterySkillPoint(skill_name="Distribution", weighted_score=1.0)],
        pre_post_by_skill=[
            PrePostSkillPoint(skill_name="Distribution", pre_accuracy=1.0, post_accuracy=0.0)
        ],
    )


def _weak_dashboard() -> DashboardData:
    """One skill under the shared cut, one over it."""
    data = _dashboard()
    return replace(
        data,
        mastery_by_skill=[
            MasterySkillPoint(skill_name="Distribution", weighted_score=0.35),
            MasterySkillPoint(skill_name="One-Step Equations", weighted_score=0.92),
        ],
    )


def test_skills_to_strengthen_use_the_study_plans_own_cut() -> None:
    """The reconciliation. A parent being told to work on X while `topic_resolver` targets
    Y is the failure this closes, so both now read `mastery.weighted_score` against
    `WEAK_SKILL_THRESHOLD`.
    """
    payload = build_report_facts(
        audience="parent",
        grade="7th grade",
        date_range_label="all time",
        dashboard=_weak_dashboard(),
        relevant_learning_facts=[],
    )
    assert payload.weak_skill_names == ["Distribution"]
    assert payload.mastery_by_skill == {"Distribution": 0.35, "One-Step Equations": 0.92}
    # Stated in the label, so a reader can check the claim rather than trust it.
    assert f"{WEAK_SKILL_THRESHOLD:.0%}" in payload.weak_skill_window_label


def test_the_threshold_itself_is_not_weak() -> None:
    """Pins the boundary. "Weak" is strictly below the cut in `topic_resolver` and in the
    AUD-L-13 memory floor; a report that disagreed at the boundary would reintroduce the
    exact split this change removed, one skill wide.
    """
    data = replace(
        _dashboard(),
        mastery_by_skill=[
            MasterySkillPoint(skill_name="Distribution", weighted_score=WEAK_SKILL_THRESHOLD)
        ],
    )
    payload = build_report_facts(
        audience="parent",
        grade="7th grade",
        date_range_label="all time",
        dashboard=data,
        relevant_learning_facts=[],
    )
    assert payload.weak_skill_names == []


def test_the_premax_contradiction_can_no_longer_be_built() -> None:
    """The finding's own reproduction, run against the fixed code. Feeding the exact shape
    that produced "mastery 1.000 and needs work" now yields no weak skill at all: the two
    figures cannot disagree because they are the same number. The stale `pre_post_by_skill`
    row is still in the dashboard and is deliberately ignored - a report that fell back to
    it would recreate the split.
    """
    payload = build_report_facts(
        audience="parent",
        grade="7th grade",
        date_range_label="all time",
        dashboard=_premax_dashboard(),
        relevant_learning_facts=[],
    )
    assert payload.mastery_by_skill == {"Distribution": 1.0}
    assert payload.weak_skill_names == []


def test_mastery_states_a_window_the_date_range_label_does_not_cover() -> None:
    """The half of AUD-L-15 that survives the reconciliation: mastery is not date-filtered
    at all (`build_dashboard` reads `mastery_repo.list_for_student`, which takes no range),
    so under any range label it is still all-time. "all time" was the label in the
    reproduction and is the most misleading case - it reads as "everything we know", which
    is what the range-filtered figures beside it are not.
    """
    payload = build_report_facts(
        audience="parent",
        grade="7th grade",
        date_range_label="2026-07-01 to 2026-07-31",
        dashboard=_weak_dashboard(),
        relevant_learning_facts=[],
    )
    assert payload.date_range_label == "2026-07-01 to 2026-07-31"
    assert payload.mastery_window_label != payload.date_range_label
    # Says which phases feed it, and that the requested range does not apply to it.
    assert "post-exam" in payload.mastery_window_label.lower()
    assert "date range" in payload.mastery_window_label.lower()


def test_a_window_label_is_absent_when_its_figure_is_gated_away() -> None:
    """Audience gating governs the labels too. A tutor payload carries no
    `mastery_by_skill`, so a mastery window label would describe a number that is not
    there. `weak_skill_names` *is* in the tutor field set - and is still derived from
    mastery, which SPEC §5.14.4 withholds - so its own label must stay.
    """
    payload = build_report_facts(
        audience="tutor",
        grade="7th grade",
        date_range_label="last 30 days",
        dashboard=_weak_dashboard(),
        relevant_learning_facts=[],
    )
    assert payload.mastery_by_skill == {}
    assert payload.mastery_window_label == ""
    assert payload.weak_skill_names == ["Distribution"]
    assert payload.weak_skill_window_label


def test_the_model_is_told_not_to_merge_the_windows() -> None:
    """The labels only help if the thing writing the prose is told they mean something.
    Without this the model reads an all-time figure beside a 30-day one and reconciles
    them itself.
    """
    assert "different windows" in _SYSTEM_PROMPT


def test_gateway_failure_falls_back_to_facts_only_template() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            ledger = _cost_ledger()
            gateway = _FakeGateway([BedrockGatewayError("simulated failure", cost_cents=0.2)])

            result = await generate_student_report(
                gateway=gateway,
                repo=repo,
                cost_ledger=ledger,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                idempotency_key="report-gateway-failure",
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
            ledger = _cost_ledger()
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
                cost_ledger=ledger,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                idempotency_key="report-ungrounded-output",
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert "99" not in result.interpretation_text

    asyncio.run(run())


def test_an_inverted_score_pair_falls_back_to_facts_only_template() -> None:
    """AUD-L-09 through the path that actually runs. The unit rule lives in
    `packages/shared/tests/test_numeric_grounding.py`; this asserts that *this service*
    consults it - D-159's lesson, where a guard was written into a function with no callers
    and every status-code assertion still passed.

    Every number below is in the evidence (4.0 and 6.0 are the payload's own scores), so the
    provenance check accepts this sentence and accepted it before the directional rule
    existed. The parent's real result is a two-point gain.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            ledger = _cost_ledger()
            gateway = _FakeGateway(
                [
                    ReportInterpretationResponse(
                        interpretation_text="Their score fell from 6.0 to 4.0 this month.",
                        recommendations_text="Focus on Two-Step Equations.",
                    )
                ]
            )

            result = await generate_student_report(
                gateway=gateway,
                repo=repo,
                cost_ledger=ledger,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                idempotency_key="report-inverted-pair",
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert "fell from" not in result.interpretation_text
            # The fallback still carries the real figures, in the real order - which is why
            # rejecting costs the parent the prose and not the numbers.
            assert "from 4.0 to 6.0" in result.interpretation_text

    asyncio.run(run())


def test_an_inverted_pair_in_the_recommendations_rejects_the_whole_report() -> None:
    """Both texts are checked, and one bad text drops both: a report whose interpretation is
    faithful and whose recommendations invert the same pair is not half-shippable.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            ledger = _cost_ledger()
            gateway = _FakeGateway(
                [
                    ReportInterpretationResponse(
                        interpretation_text="Score improved from 4.0 to 6.0.",
                        recommendations_text="Since they slid from 6.0 to 4.0, review daily.",
                    )
                ]
            )

            result = await generate_student_report(
                gateway=gateway,
                repo=repo,
                cost_ledger=ledger,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                idempotency_key="report-inverted-recommendations",
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert "slid from" not in result.recommendations_text

    asyncio.run(run())


def test_grounded_response_is_trusted_as_is() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            ledger = _cost_ledger()
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
                cost_ledger=ledger,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                idempotency_key="report-grounded-output",
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


def _cost_ledger() -> CostReservationRepository:
    """S42/AUD-X-08: the ledger commits on its own connection, so it deliberately does not
    join the enclosing rollback session - `_clear_ledger` cleans up instead.
    """
    return CostReservationRepository(create_session_factory(create_engine()))


async def _clear_ledger() -> None:
    engine = create_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM cost_reservations WHERE subject_external_id = :s"),
                {"s": STUDENT_ID},
            )
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def clean_ledger() -> Iterator[None]:
    """The ledger commits for real, so it outlives the rollback session every other
    fixture here relies on. Clears before as well as after, so a run interrupted midway
    cannot leave spend behind that silently trips the next run's ceiling.
    """
    asyncio.run(_clear_ledger())
    yield
    asyncio.run(_clear_ledger())


async def _seed_spend(ledger: CostReservationRepository, cents: float) -> None:
    """Puts `cents` of settled spend on this student's report ceiling."""
    reservation = await ledger.reserve(
        scope=SCOPE_STUDENT_REPORT,
        subject_external_id=STUDENT_ID,
        estimate_cents=cents,
        ceiling_cents=float("inf"),
    )
    await ledger.settle(reservation.reservation_id, cents)


def test_report_generation_stops_calling_bedrock_at_the_daily_cost_ceiling() -> None:
    """S36/AUD-L-02 regression. Before the fix this endpoint had no cost ceiling at all:
    it passed `session_spend_cents=0.0` on every call, so the gateway's own budget check
    could never fire, and one authenticated caller could drive unlimited Bedrock spend
    bounded only by a 6,000-request/60s per-IP rate limiter.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            ledger = _cost_ledger()
            await _seed_spend(ledger, DAILY_REPORT_COST_CEILING_CENTS)

            result = await generate_student_report(
                gateway=_ExplodingGateway(),
                repo=repo,
                cost_ledger=ledger,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                idempotency_key="report-ceiling-reached",
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
            ledger = _cost_ledger()
            await _seed_spend(ledger, DAILY_REPORT_COST_CEILING_CENTS - 0.5)

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
                cost_ledger=ledger,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                idempotency_key="report-under-ceiling",
                session_spend_cents=DAILY_REPORT_COST_CEILING_CENTS - 0.5,
            )

            assert result.generated is True

    asyncio.run(run())


def test_the_ceiling_is_scoped_to_this_student() -> None:
    """The ceiling must not be tripped by another student's spend - that would deny a
    legitimate report. The window and per-surface halves of this moved to
    `packages/db/tests/test_cost_reservation.py` along with the spend query itself
    (S42/AUD-X-08); what is worth keeping here is that the *service* asks for the right
    subject.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            ledger = _cost_ledger()
            other = await ledger.reserve(
                scope=SCOPE_STUDENT_REPORT,
                subject_external_id="some-other-student",
                estimate_cents=DAILY_REPORT_COST_CEILING_CENTS,
                ceiling_cents=float("inf"),
            )
            await ledger.settle(other.reservation_id, DAILY_REPORT_COST_CEILING_CENTS)

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
                cost_ledger=ledger,
                student_external_id=STUDENT_ID,
                payload=_payload("parent"),
                idempotency_key="report-other-student-spend",
                session_spend_cents=0.0,
            )
            assert result.generated is True

            engine = create_engine()
            try:
                async with engine.begin() as conn:
                    await conn.execute(
                        text(
                            "DELETE FROM cost_reservations "
                            "WHERE subject_external_id = 'some-other-student'"
                        )
                    )
            finally:
                await engine.dispose()

    asyncio.run(run())


def _empty_dashboard() -> DashboardData:
    """A student who has not answered anything yet - the case D-218 walked on staging."""
    return DashboardData(
        mastery_by_skill=[],
        pre_post_by_skill=[],
        gains_over_time=[],
        accuracy_trend=[],
        difficulty_progression=[],
        usage=UsageBreakdown(
            hint_count=0, solution_count=0, video_count=0, independent_count=0, total_attempts=0
        ),
        attempts_count=0,
        time_spent_minutes=0.0,
        latest_pre_raw_score=None,
        latest_post_raw_score=None,
        latest_raw_gain=None,
        tutor_review_flagged=False,
    )


def _empty_payload(audience: str) -> ReportInterpretationPayload:
    return build_report_facts(
        audience=audience,
        grade="2nd grade",
        date_range_label="last 30 days",
        dashboard=_empty_dashboard(),
        relevant_learning_facts=[],
    )


def test_zero_attempt_report_never_reaches_the_model() -> None:
    """D-218. Walked on staging 2026-08-07: a child with zero attempts produced a real, paid
    generation whose entire content was determined by "there is no data". `_ExplodingGateway`
    is the assertion - the short-circuit has to land before the call, not refund it after.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = StudentReportRepository(session)
            result = await generate_student_report(
                gateway=_ExplodingGateway(),
                repo=repo,
                cost_ledger=_cost_ledger(),
                student_external_id=STUDENT_ID,
                payload=_empty_payload("parent"),
                idempotency_key="report-zero-attempts",
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert result.cost_cents == 0.0
            assert "not completed any graded work" in result.interpretation_text

            stored = await repo.list_for_student(STUDENT_ID)
            assert len(stored) == 1
            assert stored[0].generated is False

    asyncio.run(run())


def test_zero_attempt_report_speaks_to_the_student_in_their_own_report() -> None:
    """SPEC §5.10.3: the student's own report addresses them, not a third party. The parent
    wording ("your student has not...") would be strange read by the child it is about.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            result = await generate_student_report(
                gateway=_ExplodingGateway(),
                repo=StudentReportRepository(session),
                cost_ledger=_cost_ledger(),
                student_external_id=STUDENT_ID,
                payload=_empty_payload("student"),
                idempotency_key="report-zero-attempts-student",
                session_spend_cents=0.0,
            )

            assert result.generated is False
            assert "your student" not in result.interpretation_text.lower()
            assert "you haven't finished" in result.interpretation_text

    asyncio.run(run())


def test_a_student_with_scores_but_no_attempts_still_gets_a_generated_report() -> None:
    """The short-circuit is `attempts_count == 0` **and** no pre-exam score, deliberately.
    A completed cycle is something to interpret even if the attempt counter disagrees, and
    silently serving "no activity" over a real score would be the worse failure.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            dashboard = replace(_empty_dashboard(), latest_pre_raw_score=4.0)
            payload = build_report_facts(
                audience="parent",
                grade="7th grade",
                date_range_label="last 30 days",
                dashboard=dashboard,
                relevant_learning_facts=[],
            )
            # A gateway *error* rather than a success, so this asserts that the model path was
            # entered without also depending on the grounding check passing. The 0.2c is
            # billed by the failing call and cannot appear on the short-circuit path, which
            # never touches the gateway and always reports 0.0.
            result = await generate_student_report(
                gateway=_FakeGateway([BedrockGatewayError("simulated failure", cost_cents=0.2)]),
                repo=StudentReportRepository(session),
                cost_ledger=_cost_ledger(),
                student_external_id=STUDENT_ID,
                payload=payload,
                idempotency_key="report-scores-without-attempts",
                session_spend_cents=0.0,
            )

            assert result.cost_cents == 0.2

    asyncio.run(run())
