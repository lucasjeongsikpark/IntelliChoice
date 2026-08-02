"""Learning-gain metrics (SPEC §5.13.3), from pre vs. post assessment attempts plus the
study phase's support usage.

The pre/post metrics (raw/weighted/normalized gain, difficulty transition, per-skill gain,
post-exam unresolved skills) come from the two exams. `independent_correct_rate`,
`hint_dependency`, and `solution_dependency` are now derived from the study attempts'
§5.11.7 outcome labels (S10) instead of the S8 placeholder of post-accuracy/0.0/0.0.
"""

from dataclasses import dataclass

from intellichoice_db.models.assessment import AssessmentAttempt
from intellichoice_db.models.mastery import StudyAttempt
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.mastery_policy import WEAK_SKILL_THRESHOLD

from learning_api.services import study_outcomes
from learning_api.services.mastery_bootstrap import (
    highest_consistent_difficulty,
    raw_accuracy,
    resolve_graded_attempts,
    weighted_score,
)

# The labels that *resolve* a study skill line (its final attempt), one per line.
_RESOLVING_LABELS = frozenset(
    {
        study_outcomes.INDEPENDENT_CORRECT,
        study_outcomes.CORRECT_AFTER_HINT,
        study_outcomes.CORRECT_AFTER_VIDEO,
        study_outcomes.CORRECT_AFTER_SOLUTION,
        study_outcomes.UNRESOLVED,
    }
)


@dataclass(frozen=True)
class SupportDependency:
    independent_correct_rate: float
    hint_dependency: float
    solution_dependency: float


def support_dependency(study_attempts: list[StudyAttempt]) -> SupportDependency:
    """Fractions of resolved study skill lines by support level (SPEC §5.13.3). One
    resolving attempt per skill line, keyed on its final outcome label:
    `independent_correct` -> independent; `correct_after_hint`/`correct_after_video` ->
    hint dependency (a nudge short of the full solution); `correct_after_solution` ->
    solution dependency. Returns all-zero when there was no study phase.
    """
    resolving = [
        a for a in study_attempts if a.outcome_label in _RESOLVING_LABELS
    ]
    total = len(resolving)
    if total == 0:
        return SupportDependency(0.0, 0.0, 0.0)
    independent = sum(1 for a in resolving if a.outcome_label == study_outcomes.INDEPENDENT_CORRECT)
    _hint_labels = (study_outcomes.CORRECT_AFTER_HINT, study_outcomes.CORRECT_AFTER_VIDEO)
    hint = sum(1 for a in resolving if a.outcome_label in _hint_labels)
    solution = sum(
        1 for a in resolving if a.outcome_label == study_outcomes.CORRECT_AFTER_SOLUTION
    )
    return SupportDependency(independent / total, hint / total, solution / total)


@dataclass(frozen=True)
class LearningGainResult:
    pre_raw_score: float
    post_raw_score: float
    raw_gain: float
    weighted_gain: float
    normalized_gain: float | None
    normalized_gain_status: str | None
    skill_level_gain: dict
    difficulty_transition: dict
    independent_correct_rate: float
    hint_dependency: float
    solution_dependency: float
    unresolved_skills: list[str]
    response_time_change_ms: int


def _average(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


async def compute_learning_gain(
    *,
    question_repo: QuestionRepository,
    pre_attempts: list[AssessmentAttempt],
    post_attempts: list[AssessmentAttempt],
    study_attempts: list[StudyAttempt] | None = None,
) -> LearningGainResult:
    pre_graded = await resolve_graded_attempts(question_repo, pre_attempts)
    post_graded = await resolve_graded_attempts(question_repo, post_attempts)

    pre_raw = float(sum(1 for a in pre_graded if a.is_correct))
    post_raw = float(sum(1 for a in post_graded if a.is_correct))
    # `max_score` is the attempt count, and it is the *item* count only because
    # `uq_assessment_attempts_session_variant` allows one attempt per item and
    # `flow.finalize_exam` synthesizes one for every item left unanswered. That was not
    # true before AUD-L-10: a second answer under a new key made a 10-item exam score
    # 10/11 and silently replaced `not_applicable_pre_max` below with a computed gain.
    # If that constraint is ever relaxed, this line has to start counting items instead.
    max_score = float(len(pre_graded)) or 1.0

    if pre_raw >= max_score:
        normalized_gain: float | None = None
        normalized_gain_status: str | None = "not_applicable_pre_max"
    else:
        normalized_gain = (post_raw - pre_raw) / (max_score - pre_raw)
        normalized_gain_status = None

    skill_ids = {a.skill_id for a in pre_graded} | {a.skill_id for a in post_graded}
    skill_level_gain: dict[str, dict[str, float]] = {}
    unresolved_skills: list[str] = []
    for skill_id in sorted(skill_ids):
        pre_for_skill = [a for a in pre_graded if a.skill_id == skill_id]
        post_for_skill = [a for a in post_graded if a.skill_id == skill_id]
        pre_accuracy = raw_accuracy(pre_for_skill)
        post_accuracy = raw_accuracy(post_for_skill)
        skill_level_gain[skill_id] = {
            "pre_accuracy": pre_accuracy,
            "post_accuracy": post_accuracy,
            "gain": post_accuracy - pre_accuracy,
        }
        if weighted_score(post_for_skill) < WEAK_SKILL_THRESHOLD:
            unresolved_skills.append(skill_id)

    avg_pre_response_ms = _average([a.response_time_ms for a in pre_attempts])
    avg_post_response_ms = _average([a.response_time_ms for a in post_attempts])

    dependency = support_dependency(study_attempts or [])

    return LearningGainResult(
        pre_raw_score=pre_raw,
        post_raw_score=post_raw,
        raw_gain=post_raw - pre_raw,
        weighted_gain=weighted_score(post_graded) - weighted_score(pre_graded),
        normalized_gain=normalized_gain,
        normalized_gain_status=normalized_gain_status,
        skill_level_gain=skill_level_gain,
        difficulty_transition={
            "pre": highest_consistent_difficulty(pre_graded),
            "post": highest_consistent_difficulty(post_graded),
        },
        independent_correct_rate=dependency.independent_correct_rate,
        hint_dependency=dependency.hint_dependency,
        solution_dependency=dependency.solution_dependency,
        unresolved_skills=unresolved_skills,
        response_time_change_ms=int(avg_post_response_ms - avg_pre_response_ms),
    )
