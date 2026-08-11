"""S26 (SPEC §5.10.3/§5.13.3, plan §18-L7): grounded, personalized stage narratives.

One entrypoint, five call sites (`graph/nodes.py`'s `finalize_exam` x2, `submit_answer`,
`intervention_choice`, and `routers/sessions.py`'s connect path for `pre_intro`) - each
builds its own `StageNarrativePayload` from already-resolved evidence (skill *names*,
never ids; numbers already computed, never raw DB rows - same discipline
`history.py`'s module docstring establishes for the parent dashboard) and calls
`generate_stage_narrative` here. The model's `narrative_text` is only trusted once
`intellichoice_shared.numeric_grounding.grounding_failure` confirms every number in it
already exists in that same payload *and* that it does not state the known pre/post pair in
reverse (SPEC §5.25.3's "invalid -> deterministic fallback", generalized from schema
validity to numeric grounding) - a gateway failure or a failed grounding check both fall
back to `_fallback_text`, a plain Python template built only from the same payload fields,
so a fallback narrative is grounded by construction.

**Each payload carries only its own stage's fields, and that is load-bearing rather than
tidy** (AUD-L-09/D-098 mitigation 2): a `study_outro` payload holds hint/solution/video
counts and no scores, so there is no score in its evidence for a narrative to misattribute
in the first place. Adding a field to a stage that does not need it widens what that
stage's prose can get wrong - `test_stage_payloads_stay_narrow.py` fails when it happens.
"""

import logging
from dataclasses import dataclass

from intellichoice_db.models.stage_transition import StageTransition
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.stage_transition import StageTransitionRepository
from intellichoice_db.repositories.study import StudyRepository
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    StageNarrativePayload,
    StageNarrativeResponse,
)
from intellichoice_shared.numeric_grounding import grounding_failure
from intellichoice_shared.profiles import ProfileAdapter

logger = logging.getLogger(__name__)

_MAX_OUTPUT_TOKENS = 400


async def payload_from_marker(
    *,
    profile_adapter: ProfileAdapter,
    curriculum_repo: CurriculumRepository,
    study_repo: StudyRepository,
    student_external_id: str,
    marker: dict,
) -> tuple[StageNarrativePayload, str | None]:
    """Resolve an ids-only `pre_outro`/`study_step`/`study_outro` marker into the full
    `StageNarrativePayload` + `related_skill_id`. Shared by the inline node path and the
    background scheduler so both build the same payload from the same ids; takes the repos
    rather than a `TurnContext` so the background task can pass its own session's repos.
    Skill *names* and grade are resolved here, at generation time - never carried in the
    marker (which is checkpointed), keeping the SPEC §5.30 PII rule intact.
    """
    profile = await profile_adapter.get_student_profile(student_external_id)
    assert profile is not None
    grade = profile.grade

    if marker["stage"] == "pre_outro":
        # D-241. The study plan's ranked target skills are both "the student's weak topics"
        # and "what study serves next", which is exactly what `pre_outro` says. Resolved
        # here from ids for the same reason as `study_step` below: names are PII-adjacent
        # and the marker is checkpointed (SPEC §5.30).
        names = []
        for skill_id in marker["target_skill_ids"]:
            skill = await curriculum_repo.get_skill(skill_id)
            names.append(skill.name if skill is not None else skill_id)
        return (
            StageNarrativePayload(
                stage="pre_outro",
                grade=grade,
                weak_skill_names=names,
                target_skill_name=names[0] if names else None,
            ),
            None,
        )

    if marker["stage"] == "study_step":

        async def _name(skill_id: str) -> str:
            skill = await curriculum_repo.get_skill(skill_id)
            return skill.name if skill is not None else skill_id

        return (
            StageNarrativePayload(
                stage="study_step",
                grade=grade,
                completed_skill_name=await _name(marker["completed_skill_id"]),
                target_skill_name=await _name(marker["target_skill_id"]),
            ),
            marker["target_skill_id"],
        )

    attempts = await study_repo.get_attempts(marker["study_session_id"])
    return (
        StageNarrativePayload(
            stage="study_outro",
            grade=grade,
            hint_count=sum(1 for a in attempts if a.hint_used),
            solution_count=sum(1 for a in attempts if a.solution_used),
            video_count=sum(1 for a in attempts if a.video_used),
        ),
        None,
    )

_SYSTEM_PROMPT = (
    "You are writing a short, warm, growth-oriented message for a K-12 student using a "
    "math tutoring app (SPEC §5.10.3: use phrases like 'skills to strengthen' and "
    "'almost there', never discouraging language). Write 1-3 sentences. Only reference "
    "names and numbers that appear in the data you were given - never invent a score, "
    "a gain, a count, or a skill name that isn't already there. "
    # A 'Study plan, weakest first' line lists the whole topic in priority order, and the
    # model was reading it as a list of failures: a student who scored 7 of 10 was told they
    # had five skills to strengthen, two of which they had mastered. The tone guidance above
    # is about *how* to say things, not a licence to assert weakness the data does not show.
    "A study-plan list is the order skills will be practised in, not a list of things the "
    "student is bad at - describe it as what comes next, and only call a skill out as "
    "needing work if a number you were given says so. "
    # D-272. Measured on screen 2026-08-10: the message named all five skills of
    # `linear_equations` in one sentence, each of them a full clause ("Solve linear
    # equations with negative or fractional coefficients"), and the evidence box below it
    # repeated the same five. Two hundred-odd words of list, for a child, between them and
    # the question. The names stay in the payload so any mention is still grounded; what
    # changes is how many the message is allowed to spend.
    "Name at most one skill - the one coming next. If the data lists more, say how many "
    "there are rather than listing them. "
    # D-217 (point 3): rendered as plain text, so no Markdown or LaTeX.
    "Write plain sentences only - no Markdown headings or bullet characters and no LaTeX."
)


# D-272: how many skill names the evidence box prints before it starts counting instead.
_EVIDENCE_SKILL_LIMIT = 2


@dataclass(frozen=True)
class StageNarrativeResult:
    narrative_text: str
    cost_cents: float
    generated: bool
    evidence_summary: list[str]


def _evidence_summary(payload: StageNarrativePayload) -> list[str]:
    """Plain-language "How we personalized this" lines for `StageTransitionScreen` -
    built from the exact same already-resolved fields (names, never ids) used for the
    Bedrock payload and the numeric-grounding check, never a raw dict dump.
    """
    lines: list[str] = []
    if payload.attendance_status is not None:
        lines.append(f"Attendance: {payload.attendance_status}")
    if payload.pre_raw_score is not None:
        lines.append(f"Pre-exam score: {payload.pre_raw_score}")
    if payload.post_raw_score is not None:
        lines.append(f"Post-exam score: {payload.post_raw_score}")
    if payload.raw_gain is not None:
        lines.append(f"Growth: {payload.raw_gain} points")
    if payload.weak_skill_names:
        # "Your study plan, weakest first", not "skills to strengthen".
        #
        # `study_plan.py` ranks every skill in the topic by mastery and takes
        # `ranked[:BASE_PROBLEM_COUNT]` - and `BASE_PROBLEM_COUNT` is 5 while
        # `linear_equations` has exactly 5 skills. So this list is *the whole topic in
        # priority order*, never a subset that failed a weakness test. Measured on staging
        # 2026-08-07: a student who answered 7 of 10 correctly was told they had five
        # "skills to strengthen" - including two the dashboard scored at 100%.
        #
        # The ordering is genuinely useful and is left alone; only the claim about it is
        # corrected. `Next up:` below remains the actionable line.
        #
        # D-272: truncated for display. Five skill names, each a full clause, is a
        # paragraph of list in a box headed "why this is your next step" - and the student
        # only acts on the first one. The count keeps it honest about what was hidden;
        # the full list is still in the stored evidence and in the payload.
        shown = list(payload.weak_skill_names[:_EVIDENCE_SKILL_LIMIT])
        hidden = len(payload.weak_skill_names) - len(shown)
        listed = ", ".join(shown) + (f", and {hidden} more" if hidden > 0 else "")
        lines.append(f"Study plan, weakest first: {listed}")
    if payload.completed_skill_name is not None:
        lines.append(f"Just completed: {payload.completed_skill_name}")
    if payload.target_skill_name is not None:
        lines.append(f"Next up: {payload.target_skill_name}")
    if payload.hint_count is not None:
        lines.append(f"Hints used: {payload.hint_count}")
    if payload.solution_count is not None:
        lines.append(f"Solutions viewed: {payload.solution_count}")
    if payload.video_count is not None:
        lines.append(f"Videos suggested: {payload.video_count}")
    if payload.relevant_learning_facts:
        lines.extend(payload.relevant_learning_facts)
    return lines


def _fallback_text(payload: StageNarrativePayload) -> str:
    if payload.stage == "pre_intro":
        return "Welcome back! Let's see what you remember today."
    if payload.stage == "pre_outro":
        parts = []
        if payload.pre_raw_score is not None:
            parts.append(f"You scored {payload.pre_raw_score} on the pre-exam.")
        # D-272: the full list is gone from here. It said the same thing as the line
        # below it - "your plan starts with A, B, C, D, E" immediately followed by "your
        # plan starts with A" - and the count is the part a student can act on.
        if payload.target_skill_name:
            parts.append(f"First up: {payload.target_skill_name}.")
        if payload.weak_skill_names and len(payload.weak_skill_names) > 1:
            rest = len(payload.weak_skill_names) - 1
            parts.append(f"Then {rest} more skill{'s' if rest != 1 else ''} after that.")
        return " ".join(parts) or "Let's get started with your study plan."
    if payload.stage == "study_step":
        parts = []
        if payload.completed_skill_name:
            parts.append(f"Nice work on {payload.completed_skill_name}!")
        if payload.target_skill_name:
            parts.append(f"Let's move on to {payload.target_skill_name}.")
        return " ".join(parts) or "Let's keep going."
    if payload.stage == "study_outro":
        parts = []
        if payload.hint_count is not None:
            parts.append(f"You used {payload.hint_count} hints")
        if payload.solution_count is not None:
            parts.append(f"viewed {payload.solution_count} solutions")
        summary = " and ".join(parts)
        if summary:
            return f"{summary} this session. Time for your post-exam!"
        return "Great work studying today. Time for your post-exam!"
    if payload.stage == "post_outro":
        parts = []
        if payload.pre_raw_score is not None and payload.post_raw_score is not None:
            parts.append(f"You went from {payload.pre_raw_score} to {payload.post_raw_score}.")
        if payload.raw_gain is not None:
            parts.append(f"That's a gain of {payload.raw_gain} points.")
        return " ".join(parts) or "Great work completing your post-exam!"
    return "Keep up the great work!"


async def generate_stage_narrative(
    *,
    gateway: BedrockGateway,
    repo: StageTransitionRepository,
    student_external_id: str,
    learning_session_id: str,
    payload: StageNarrativePayload,
    related_skill_id: str | None = None,
    # S36/AUD-L-02: no default. This used to default to 0.0 and `routers/stream.py`'s
    # `pre_intro` call relied on it, which disabled the gateway's cost ceiling for that
    # path. Required now, so omitting it is a typecheck failure rather than silent
    # unbounded spend.
    session_spend_cents: float,
) -> StageNarrativeResult:
    """Idempotent per (session, stage[, skill]): a second call for the same key returns
    the already-persisted narrative without a new Bedrock call (bounds `pre_intro` and
    each `study_step` firing to exactly one call each, regardless of client retries or
    reconnects).
    """
    existing = await repo.get_for_session_stage(
        learning_session_id, payload.stage, related_skill_id=related_skill_id
    )
    if existing is not None:
        return StageNarrativeResult(
            narrative_text=existing.narrative_text,
            cost_cents=0.0,
            generated=existing.generated,
            evidence_summary=_evidence_summary(StageNarrativePayload(**existing.evidence)),
        )

    evidence = payload.model_dump()
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.STAGE_NARRATIVE,
            system_prompt=_SYSTEM_PROMPT,
            payload=payload,
            response_model=StageNarrativeResponse,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        logger.warning("stage narrative generation fell back to a template: %s", exc)
        narrative_text, cost_cents, generated = _fallback_text(payload), exc.cost_cents, False
    else:
        failure = grounding_failure(result.value.narrative_text, evidence)
        if failure is None:
            narrative_text = result.value.narrative_text
            cost_cents = result.cost_cents
            generated = True
        else:
            # AUD-L-09: the reason is in the log because the two are different events - a
            # fabricated number is the model inventing, an inverted score pair is the model
            # misreading numbers it was handed. Without it, a rise in rejections says
            # nothing about which rule is firing, and an `inverted_score_pair` that never
            # appears cannot be distinguished from one that cannot fire.
            logger.warning(
                "stage narrative failed numeric grounding; using template instead",
                extra={"reason": failure, "stage": payload.stage},
            )
            narrative_text = _fallback_text(payload)
            cost_cents = result.cost_cents
            generated = False

    await repo.record(
        StageTransition(
            student_external_id=student_external_id,
            learning_session_id=learning_session_id,
            stage=payload.stage,
            related_skill_id=related_skill_id,
            narrative_text=narrative_text,
            evidence=evidence,
            generated=generated,
            cost_cents=cost_cents,
        )
    )
    return StageNarrativeResult(
        narrative_text=narrative_text,
        cost_cents=cost_cents,
        generated=generated,
        evidence_summary=_evidence_summary(payload),
    )
