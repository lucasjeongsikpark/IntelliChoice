"""SPEC §5.9/§5.13, plan §18-L3: per-session-type `AssessmentPolicy` - deterministic
config, "procedural memory" in the §5.15.1 sense, never derived from an LLM.

D-064: this session kept grade-on-submit (each `/answers` call grades immediately) rather
than the plan's recommended save-then-finalize model, and gave pre/post exams a real
default timer rather than staying untimed. `feedback_visibility="hidden_until_finalize"`
therefore only controls what the *response* shows, not when grading happens - the grade is
always computed and stored the instant an answer is submitted.
"""

from typing import Literal

from pydantic import BaseModel

SessionType = Literal["pre_exam", "study", "post_exam"]

# 20 minutes for the fixed 10-question set (SPEC §5.9.1/§5.13.2) - ~2 min/question across
# 5 difficulty tiers. One constant, easy to retune; not derived from any measured data yet
# (same "placeholder until real usage exists" posture as other tuned constants in this repo).
EXAM_TIME_LIMIT_SECONDS = 1200


class AssessmentPolicy(BaseModel):
    model_config = {"extra": "forbid"}

    session_type: SessionType
    time_limit_seconds: int | None
    # "free" = skip/flag/jump between items (pre/post exam); "sequential" = one question at
    # a time, no jumping (study's existing per-skill retry ladder, D-028, untouched).
    navigation: Literal["free", "sequential"]
    hints_allowed: bool
    feedback_visibility: Literal["immediate", "hidden_until_finalize"]


_POLICIES: dict[SessionType, AssessmentPolicy] = {
    "pre_exam": AssessmentPolicy(
        session_type="pre_exam",
        time_limit_seconds=EXAM_TIME_LIMIT_SECONDS,
        navigation="free",
        hints_allowed=False,
        feedback_visibility="hidden_until_finalize",
    ),
    "post_exam": AssessmentPolicy(
        session_type="post_exam",
        time_limit_seconds=EXAM_TIME_LIMIT_SECONDS,
        navigation="free",
        hints_allowed=False,
        feedback_visibility="hidden_until_finalize",
    ),
    "study": AssessmentPolicy(
        session_type="study",
        time_limit_seconds=None,
        navigation="sequential",
        hints_allowed=True,
        feedback_visibility="immediate",
    ),
}


def get_policy(session_type: SessionType) -> AssessmentPolicy:
    return _POLICIES[session_type]
