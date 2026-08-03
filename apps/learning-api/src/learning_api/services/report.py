"""SPEC §5.14.2-§5.14.4, ROADMAP S28 (plan §12, §18-L9): audience-gated student
reports. Mirrors `services/stage_narrative.py`'s design: one entrypoint, a deterministic
`verified_facts` payload built *before* the Bedrock call, a numeric-grounding check on
the model's output, and a facts-only deterministic fallback (never a silently-accepted
ungrounded model output) on either a gateway failure or a failed grounding check.

Audience gating happens here, not in the router: `build_report_facts` only ever
populates the fields SPEC §5.14.2 (student)/§5.14.3 (parent)/§5.14.4 (tutor) authorize
for that audience - `audience` itself is always resolved server-side from the caller's
role by the route handler, never taken from a request body (CLAUDE.md non-negotiable
#3). `branch_manager` reuses the tutor field set as a single-student stand-in this
session - real cross-student cohort aggregation needs a student->branch roster this
codebase doesn't have yet (PROGRESS.md carry-over, session-start scope decision).
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from intellichoice_db.models.cost_reservation import SCOPE_STUDENT_REPORT
from intellichoice_db.models.student_report import StudentReport
from intellichoice_db.repositories.cost_reservation import (
    CeilingReachedError,
    CostReservationRepository,
)
from intellichoice_db.repositories.student_report import StudentReportRepository
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    ReportInterpretationPayload,
    ReportInterpretationResponse,
)
from intellichoice_shared.mastery_policy import WEAK_SKILL_THRESHOLD
from intellichoice_shared.numeric_grounding import is_grounded

from learning_api.services.dashboard import MASTERY_WINDOW_LABEL, DashboardData

logger = logging.getLogger(__name__)

# S43, from D-115's carry-over (ii). This was flagged as the same "fixed cap over a
# growing input" shape as the reranker, and it is *not* - `ReportInterpretationResponse`
# is two prose fields plus `reasoning`, and their length is a function of the writing task,
# not of how much history went in. So a flat cap is the right shape here (the D-115 §10
# distinction, in the direction that says leave it alone).
#
# The measurement found a different defect instead: 500 was too small for the prompt's own
# instructions. Serialized response size against words-per-paragraph -
#
#     words/para    40    60    80   100   120   150
#     tokens       305   448   591   733   876  1091
#
# - so "two short paragraphs" truncates from about 70 words each, and D-115 measured this
# same model emitting p50 ~375 words for a chat answer. A truncated report is not a short
# report: `generate_structured` raises, and the caller falls back to the deterministic
# text, so the parent silently gets the un-personalized version. 1024 covers ~140 words per
# paragraph with the `reasoning` field filled, and stays well inside the gateway's 4000
# hard ceiling. Raising it moves REPORT_RESERVATION_ESTIMATE_CENTS below - they are
# coupled, and `test_cost_reservation_estimates.py` enforces that they stay so.
_MAX_OUTPUT_TOKENS = 1024

# S36/AUD-L-02: per-day, per-student ceiling on report-driven Bedrock spend - the sibling
# of `tutor_chat.DAILY_COST_CEILING_CENTS`, for the same reason. `POST /students/{id}/report`
# is an on-demand endpoint with no idempotency key (one fresh row, and one fresh Bedrock
# call, per click), so the per-session budget SPEC §5.25.1 describes cannot apply to it -
# there is no session. Before this ceiling existed the endpoint passed `session_spend_cents
# =0.0` on every call, which made the gateway's own budget check unconditionally pass, so
# a single authenticated caller's only limit was the 6,000-request/60s global per-IP rate
# limiter - not a cost control by any reading.
#
# 50 cents/student/day is deliberately below chat's 100: a report is a once-or-twice-a-day
# action for a real parent, where chat is conversational. At the deployed model's real rate
# (Haiku 4.5, 0.1/0.5 cents per 1K in/out) a report costs roughly 0.45 cents, so this still
# allows ~100 reports per student per day before degrading - far beyond real use, while
# bounding abuse to cents rather than dollars per student. A placeholder until real usage
# data exists, same posture as every other tuned constant here.
DAILY_REPORT_COST_CEILING_CENTS = 50.0

# AUD-X-08: what one report call reserves against the ceiling *before* it runs, replaced
# by the real cost once it returns. Must be an over-estimate - under-reserving reopens the
# race it exists to close, since a caller could slip in under a total that is about to
# grow. `test_cost_reservation_estimates.py` asserts this still bounds the real gateway's
# own `worst_case_cost_cents` for PARENT_REPORT at `_MAX_OUTPUT_TOKENS`, so a model or
# pricing change that invalidates it fails the suite rather than quietly under-counting.
#
# 2.136 cents is the worst case on the most expensive priced model (Sonnet 5 at 0.3/1.5
# per 1K, over the gateway's 2000-input-token assumption plus `_MAX_OUTPUT_TOKENS`), which
# is also the unpriced-model fallback rate. Rounded up. The deployed model (Haiku 4.5) is
# ~0.7. The over-estimate is only charged while the call is in flight - `settle` replaces
# it with the real cost within the same request - so it costs throughput nothing in
# practice.
#
# S43: raised from 1.5 alongside `_MAX_OUTPUT_TOKENS` 500 -> 1024. The guard test caught
# the coupling before the change shipped, which is what it is for. The daily ceiling below
# is unchanged and still permits ~70 reports/student/day at the deployed model's real rate.
REPORT_RESERVATION_ESTIMATE_CENTS = 2.25

_SYSTEM_PROMPT = (
    "You are writing a short progress report for a K-12 math tutoring app. Write two "
    "short paragraphs: an interpretation of the data, then concrete recommendations. "
    "Use growth-oriented, age-appropriate language for a student audience (SPEC "
    "§5.10.3: 'skills to strengthen', 'almost there', never discouraging language); use "
    "plain, factual language for parent/tutor/branch_manager audiences. Only reference "
    "numbers and skill names that appear in the data you were given - never invent a "
    "score, a gain, a count, or a skill name that isn't already there. "
    # AUD-L-15: the labels are only worth carrying if the thing writing the prose is told
    # they mean something. Mastery and "skills to strengthen" now share one window, but
    # they still sit beside range-filtered figures (attempts, usage, accuracy, gain) - so
    # left to itself the model reads an all-time score against a 30-day attempt count and
    # reconciles them, picking one or averaging or calling the data inconsistent. All three
    # are wrong: each is a correct measurement of its own window.
    "The figures come from different windows, described by date_range_label, "
    "mastery_window_label and weak_skill_window_label. Never merge or reconcile figures "
    "from different windows, and never treat a disagreement between them as an error: a "
    "skill can be mastered in one window and still need work in another. When you cite a "
    "mastery score or a skill needing work, say which window it comes from, in plain "
    "words the audience would use."
)

# AUD-L-15 (D-156): "skills to strengthen" is now the same question as "which skills are
# weak", asked of the same number.
#
# It used to be its own thing - `pre_post_by_skill` filtered at a hardcoded 0.8 on raw
# post-exam accuracy - while `topic_resolver` decided what to *study* with
# `WEAK_SKILL_THRESHOLD` (0.7) on the difficulty-weighted mastery score. Two cuts on two
# quantities over two windows, both called "weak", and nothing reconciled them: a parent
# could be told to strengthen a skill the study plan was not targeting, or not told about
# one it was. The report is the document that tells a family what to work on next, so the
# one thing it must not do is disagree with what the system will actually work on next.
#
# Both now read `mastery.weighted_score < WEAK_SKILL_THRESHOLD`. That became the right
# source in this same change: mastery now includes the post-exam, so it carries the
# post-exam signal the old 0.8 cut existed to capture.
#
# `learning_gain.unresolved_skills` deliberately keeps its own post-exam-only computation.
# It is not a statement about current standing - it is a frozen record of how one cycle
# ended, stored on the `LearningGain` row, and re-pointing it at live mastery would make a
# historical row change meaning after the fact.
_WEAK_SKILL_WINDOW_LABEL = (
    f"{MASTERY_WINDOW_LABEL[:-1]}, listing only skills below {{threshold:.0%}} - the same "
    "cut the study plan uses to choose what to work on next."
)

# SPEC §5.14.2/§5.14.3/§5.14.4 - which verified_facts fields each audience may see.
_AUDIENCE_FIELDS: dict[str, set[str]] = {
    "student": {
        "pre_raw_score",
        "post_raw_score",
        "raw_gain",
        "overall_accuracy",
        "mastery_by_skill",
        "weak_skill_names",
        "hint_count",
        "solution_count",
        "video_count",
        "independent_correct_rate",
        "attempts_count",
        "time_spent_minutes",
        "relevant_learning_facts",
    },
    "parent": {
        "pre_raw_score",
        "post_raw_score",
        "raw_gain",
        "overall_accuracy",
        "mastery_by_skill",
        "weak_skill_names",
        "hint_count",
        "solution_count",
        "video_count",
        "independent_correct_rate",
        "attempts_count",
        "time_spent_minutes",
        "tutor_review_flagged",
        "relevant_learning_facts",
    },
    # SPEC §5.14.4: pre/post scores, gain, skills to strengthen, tutor-review
    # requirement, recommended focus - no usage/mastery/time detail, no chat/location/
    # images (not present in this payload anyway).
    "tutor": {
        "pre_raw_score",
        "post_raw_score",
        "raw_gain",
        "weak_skill_names",
        "tutor_review_flagged",
        "relevant_learning_facts",
    },
}
_AUDIENCE_FIELDS["branch_manager"] = _AUDIENCE_FIELDS["tutor"]


@dataclass(frozen=True)
class StudentReportResult:
    interpretation_text: str
    recommendations_text: str
    verified_facts: dict
    generated: bool
    cost_cents: float
    created_at: datetime


def _overall_accuracy(dashboard: DashboardData) -> float | None:
    total_attempts = sum(point.attempts for point in dashboard.accuracy_trend)
    if total_attempts == 0:
        return None
    weighted = sum(point.accuracy * point.attempts for point in dashboard.accuracy_trend)
    return weighted / total_attempts


def build_report_facts(
    *,
    audience: str,
    grade: str,
    date_range_label: str,
    dashboard: DashboardData,
    relevant_learning_facts: list[str],
) -> ReportInterpretationPayload:
    allowed = _AUDIENCE_FIELDS[audience]
    full = {
        "pre_raw_score": dashboard.latest_pre_raw_score,
        "post_raw_score": dashboard.latest_post_raw_score,
        "raw_gain": dashboard.latest_raw_gain,
        "overall_accuracy": _overall_accuracy(dashboard),
        "mastery_by_skill": {p.skill_name: p.weighted_score for p in dashboard.mastery_by_skill},
        "weak_skill_names": [
            p.skill_name
            for p in dashboard.mastery_by_skill
            if p.weighted_score < WEAK_SKILL_THRESHOLD
        ],
        "hint_count": dashboard.usage.hint_count,
        "solution_count": dashboard.usage.solution_count,
        "video_count": dashboard.usage.video_count,
        "independent_correct_rate": (
            dashboard.usage.independent_count / dashboard.usage.total_attempts
            if dashboard.usage.total_attempts
            else None
        ),
        "attempts_count": dashboard.attempts_count,
        "time_spent_minutes": dashboard.time_spent_minutes,
        "tutor_review_flagged": dashboard.tutor_review_flagged,
        "relevant_learning_facts": relevant_learning_facts,
    }
    gated = {key: value for key, value in full.items() if key in allowed}
    return ReportInterpretationPayload(
        audience=audience,  # type: ignore[arg-type]
        grade=grade,
        date_range_label=date_range_label,
        # AUD-L-15: a window label rides with its figure through the same audience gate.
        # A tutor payload carries no `mastery_by_skill`, so a mastery window label there
        # would describe a number that is not in the payload - and an unexplained window
        # in the prompt is a new way for the model to invent a sentence.
        mastery_window_label=(MASTERY_WINDOW_LABEL if "mastery_by_skill" in allowed else ""),
        weak_skill_window_label=(
            _WEAK_SKILL_WINDOW_LABEL.format(threshold=WEAK_SKILL_THRESHOLD)
            if "weak_skill_names" in allowed
            else ""
        ),
        **gated,
    )


def _fallback_texts(payload: ReportInterpretationPayload) -> tuple[str, str]:
    parts = []
    if payload.pre_raw_score is not None and payload.post_raw_score is not None:
        parts.append(f"Score went from {payload.pre_raw_score} to {payload.post_raw_score}.")
    if payload.raw_gain is not None:
        parts.append(f"That's a gain of {payload.raw_gain} points.")
    if payload.weak_skill_names:
        parts.append(f"Skills to strengthen: {', '.join(payload.weak_skill_names)}.")
    interpretation = " ".join(parts) or "No verified activity in this date range yet."

    recommendation_parts = []
    if payload.weak_skill_names:
        recommendation_parts.append(f"Focus practice on {', '.join(payload.weak_skill_names)}.")
    if payload.tutor_review_flagged:
        recommendation_parts.append("A tutor review is recommended.")
    recommendations = " ".join(recommendation_parts) or "Keep up the regular practice."
    return interpretation, recommendations


async def generate_student_report(
    *,
    gateway: BedrockGateway,
    repo: StudentReportRepository,
    cost_ledger: CostReservationRepository,
    student_external_id: str,
    payload: ReportInterpretationPayload,
    session_spend_cents: float,
) -> StudentReportResult:
    """`session_spend_cents` is deliberately required, with no default. It used to default
    to 0.0, and the only caller relied on that default - which silently disabled the
    gateway's cost ceiling for this path entirely (AUD-L-02). A cost parameter with a
    permissive default is a fail-open default, the bug class this project has now produced
    four times; making it required means a future caller that forgets it fails typecheck
    instead of quietly spending money without a ceiling.

    `cost_ledger` is required for the same reason, and closes AUD-X-08: the ceiling used to
    be `read spend, then spend`, with the spending row committed at request teardown, so
    concurrent callers each read a stale total and 10 concurrent reports cost 10x the
    ceiling. The reservation below is committed before the model call, so an in-flight call
    is visible to every other caller.
    """
    evidence = payload.model_dump()

    try:
        reservation = await cost_ledger.reserve(
            scope=SCOPE_STUDENT_REPORT,
            subject_external_id=student_external_id,
            estimate_cents=REPORT_RESERVATION_ESTIMATE_CENTS,
            ceiling_cents=DAILY_REPORT_COST_CEILING_CENTS,
        )
    except CeilingReachedError as exc:
        # Degrades to the same deterministic facts-only template a gateway failure or a
        # failed grounding check already produces, rather than erroring: the caller still
        # gets their real, verified numbers, just without the LLM's prose around them.
        # SPEC §5.25.3/§5.27's "deterministic fallback" rule, reused rather than reinvented.
        logger.warning("report generation hit the per-day cost ceiling: %s", exc)
        interpretation_text, recommendations_text = _fallback_texts(payload)
        row = await repo.create(
            StudentReport(
                student_external_id=student_external_id,
                audience=payload.audience,
                verified_facts=evidence,
                interpretation_text=interpretation_text,
                recommendations_text=recommendations_text,
                generated=False,
                cost_cents=0.0,
            )
        )
        return StudentReportResult(
            interpretation_text=interpretation_text,
            recommendations_text=recommendations_text,
            generated=False,
            verified_facts=evidence,
            cost_cents=0.0,
            created_at=row.created_at,
        )

    try:
        result = await gateway.generate_structured(
            task=BedrockTask.PARENT_REPORT,
            system_prompt=_SYSTEM_PROMPT,
            payload=payload,
            response_model=ReportInterpretationResponse,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        logger.warning("report generation fell back to a facts-only template: %s", exc)
        interpretation_text, recommendations_text = _fallback_texts(payload)
        cost_cents, generated = exc.cost_cents, False
    else:
        if is_grounded(result.value.interpretation_text, evidence) and is_grounded(
            result.value.recommendations_text, evidence
        ):
            interpretation_text = result.value.interpretation_text
            recommendations_text = result.value.recommendations_text
            cost_cents, generated = result.cost_cents, True
        else:
            logger.warning("report failed numeric grounding; using facts-only template")
            interpretation_text, recommendations_text = _fallback_texts(payload)
            cost_cents, generated = result.cost_cents, False

    # Replace the estimate with what the call actually cost. A failed call still costs
    # whatever it burned before failing (`exc.cost_cents`), so this runs on every path out
    # of the try/except above - an unsettled reservation stays charged at its estimate.
    await cost_ledger.settle(reservation.reservation_id, cost_cents)

    row = await repo.create(
        StudentReport(
            student_external_id=student_external_id,
            audience=payload.audience,
            verified_facts=evidence,
            interpretation_text=interpretation_text,
            recommendations_text=recommendations_text,
            generated=generated,
            cost_cents=cost_cents,
        )
    )
    return StudentReportResult(
        interpretation_text=row.interpretation_text,
        recommendations_text=row.recommendations_text,
        verified_facts=row.verified_facts,
        generated=row.generated,
        cost_cents=row.cost_cents,
        created_at=row.created_at,
    )
