"""AUD-L-16: read the persisted policy snapshot back, so it governs behaviour instead of
merely describing it.

Both snapshots — `assessment_sessions.policy` and `study_sessions.intervention_policy` — were
written at creation and **never read anywhere**. Runtime behaviour came from hardcoded
phase-string checks that happened to agree with them (`routers/sessions.py`'s chat gate
returned 409 unless `phase == "study"`, with a comment saying it was "matching `exam_policy`'s
`hints_allowed=False`" — i.e. the policy was documentation, not the mechanism).

**Why that is a defect even though the two agree today.** The snapshot exists for exactly one
reason, stated in `AssessmentSession.policy`'s own comment: *"stored so a later change to the
policy constants can't retroactively alter an already-in-progress exam's rules."* While the
constant is what is actually read, that guarantee is not implemented — retuning
`_POLICIES["study"]["hints_allowed"]` would change the rules under every in-flight session,
which is the one thing snapshotting is for.

**Behaviour is deliberately unchanged today** (D-169's precedent: wire it, state the inertness,
test the masking). With the shipped constants the outcomes are identical — pre/post exam refuse,
study allows, any other phase refuses. What changes is *where the answer comes from*, which is
what makes the guarantee real and what the masking tests assert.
"""

from dataclasses import dataclass
from typing import Literal

from intellichoice_db.models.assessment import AssessmentSession
from intellichoice_db.models.mastery import StudySession
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from learning_api.services import exam_policy

PolicySource = Literal[
    "assessment_snapshot",
    "study_snapshot",
    "constant_fallback",
    "phase_has_no_policy",
]


@dataclass(frozen=True)
class EffectiveAssistancePolicy:
    """Whether assistance (hints, and the chat surface alongside them) is permitted right now,
    plus where that answer came from. `source` is not decoration: it is how a test tells
    "the snapshot said so" apart from "the snapshot was missing and the constant said so",
    which are the same boolean and different guarantees.
    """

    hints_allowed: bool
    source: PolicySource


async def effective_assistance_policy(
    db: AsyncSession, state: dict
) -> EffectiveAssistancePolicy:
    phase = state.get("phase")

    if phase in ("pre_exam", "post_exam"):
        session_id = state.get(
            "pre_assessment_session_id" if phase == "pre_exam" else "post_assessment_session_id"
        )
        snapshot = await _assessment_policy_snapshot(db, session_id)
        if snapshot is None:
            # `AssessmentSession.policy` is nullable and its own comment says rows created
            # before S22 were never backfilled, so this is a real path and not defensive
            # padding. Falling back to the constant is the only option that keeps those
            # sessions working; it is reported as `constant_fallback` rather than silently
            # passed off as the snapshot's answer.
            return EffectiveAssistancePolicy(
                hints_allowed=exam_policy.get_policy(phase).hints_allowed,
                source="constant_fallback",
            )
        return EffectiveAssistancePolicy(
            hints_allowed=bool(snapshot.get("hints_allowed", False)),
            source="assessment_snapshot",
        )

    if phase == "study":
        snapshot = await _intervention_policy_snapshot(db, state.get("study_session_id"))
        if snapshot is None or "hints_enabled" not in snapshot:
            return EffectiveAssistancePolicy(
                hints_allowed=exam_policy.get_policy("study").hints_allowed,
                source="constant_fallback",
            )
        return EffectiveAssistancePolicy(
            hints_allowed=bool(snapshot["hints_enabled"]),
            source="study_snapshot",
        )

    # `created`, `completed`, and anything else: no assessment or study session exists, so
    # there is no snapshot to honour and no policy that grants assistance. Refusing here is
    # the same answer the old `phase != "study"` check gave, and it fails closed by default.
    return EffectiveAssistancePolicy(hints_allowed=False, source="phase_has_no_policy")


async def _assessment_policy_snapshot(db: AsyncSession, session_id: str | None) -> dict | None:
    if session_id is None:
        return None
    row = (
        await db.execute(
            select(AssessmentSession.policy).where(
                AssessmentSession.assessment_session_id == session_id
            )
        )
    ).scalar_one_or_none()
    return row if isinstance(row, dict) else None


async def _intervention_policy_snapshot(db: AsyncSession, session_id: str | None) -> dict | None:
    if session_id is None:
        return None
    row = (
        await db.execute(
            select(StudySession.intervention_policy).where(
                StudySession.study_session_id == session_id
            )
        )
    ).scalar_one_or_none()
    return row if isinstance(row, dict) else None
