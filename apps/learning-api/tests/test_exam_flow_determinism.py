"""SPEC §5.31.1 deterministic evaluator (S30, plan §13): identical inputs to the exam
scoring/gain pipeline must produce identical results every time - no LLM, no clock, no
unseeded RNG anywhere on this path (CLAUDE.md non-negotiable #2, "deterministic core").
Pure-function level only (no DB) - `compute_learning_gain`'s own DB-joined behavior is
already covered end-to-end by `test_learning_flow.py`'s full-cycle tests; this file
isolates the part that's easy for a future change to silently make non-deterministic
(dict/set iteration order, floating-point accumulation order).
"""

from intellichoice_db.models.mastery import StudyAttempt
from learning_api.services import study_outcomes
from learning_api.services.grading import grade
from learning_api.services.learning_gain import support_dependency
from learning_api.services.mastery_bootstrap import GradedAttempt, weighted_score


def test_grade_is_deterministic() -> None:
    assert grade("b", "b") == grade("b", "b") is True
    assert grade("a", "b") == grade("a", "b") is False
    assert grade(None, "b") == grade(None, "b") is False


def test_weighted_score_is_deterministic_regardless_of_call_count() -> None:
    attempts = [
        GradedAttempt(skill_id="skill-1", difficulty=2, is_correct=True),
        GradedAttempt(skill_id="skill-1", difficulty=4, is_correct=False),
        GradedAttempt(skill_id="skill-2", difficulty=3, is_correct=True),
    ]
    first = weighted_score(attempts)
    for _ in range(5):
        assert weighted_score(attempts) == first


def _study_attempt(outcome_label: str) -> StudyAttempt:
    return StudyAttempt(
        student_external_id="student-ext-determinism",
        study_session_id="study-session-determinism",
        question_variant_id="variant-determinism",
        selected_option="a",
        is_correct=outcome_label == study_outcomes.INDEPENDENT_CORRECT,
        outcome_label=outcome_label,
    )


def test_support_dependency_is_deterministic_across_repeated_calls() -> None:
    attempts = [
        _study_attempt(study_outcomes.INDEPENDENT_CORRECT),
        _study_attempt(study_outcomes.CORRECT_AFTER_HINT),
        _study_attempt(study_outcomes.CORRECT_AFTER_SOLUTION),
        _study_attempt(study_outcomes.UNRESOLVED),
    ]
    first = support_dependency(attempts)
    for _ in range(5):
        assert support_dependency(attempts) == first
