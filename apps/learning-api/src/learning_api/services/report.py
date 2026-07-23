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

from intellichoice_db.models.student_report import StudentReport
from intellichoice_db.repositories.student_report import StudentReportRepository
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    ReportInterpretationPayload,
    ReportInterpretationResponse,
)
from intellichoice_shared.numeric_grounding import is_grounded

from learning_api.services.dashboard import DashboardData

logger = logging.getLogger(__name__)

_MAX_OUTPUT_TOKENS = 500

_SYSTEM_PROMPT = (
    "You are writing a short progress report for a K-12 math tutoring app. Write two "
    "short paragraphs: an interpretation of the data, then concrete recommendations. "
    "Use growth-oriented, age-appropriate language for a student audience (SPEC "
    "§5.10.3: 'skills to strengthen', 'almost there', never discouraging language); use "
    "plain, factual language for parent/tutor/branch_manager audiences. Only reference "
    "numbers and skill names that appear in the data you were given - never invent a "
    "score, a gain, a count, or a skill name that isn't already there."
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
            p.skill_name for p in dashboard.pre_post_by_skill if p.post_accuracy < 0.8
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
    student_external_id: str,
    payload: ReportInterpretationPayload,
    session_spend_cents: float = 0.0,
) -> StudentReportResult:
    evidence = payload.model_dump()
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
