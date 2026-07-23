"""Pure-function tests for the S10 retry ladder and outcome labels (SPEC §5.11.5, §5.11.7).
These carry the Phase 10 "identical inputs reproduce identical routing" (§5.31.1)
guarantee at the deterministic core, with no I/O. The video option itself is no longer
pure (S15 replaced the stub catalog with a real Postgres+Bedrock lookup) - see
`apps/learning-api/tests/test_video_catalog.py`.
"""

import asyncio

from intellichoice_db.models.assessment import AssessmentAttempt
from intellichoice_db.models.mastery import StudyAttempt
from learning_api.services import study_outcomes
from learning_api.services.learning_gain import support_dependency
from learning_api.services.mastery_bootstrap import resolve_graded_attempts


def test_correct_label_independent_when_no_support() -> None:
    assert study_outcomes.correct_label(frozenset()) == study_outcomes.INDEPENDENT_CORRECT


def test_correct_label_after_hint() -> None:
    history = frozenset({study_outcomes.HINT})
    assert study_outcomes.correct_label(history) == study_outcomes.CORRECT_AFTER_HINT


def test_correct_label_after_video() -> None:
    history = frozenset({study_outcomes.VIDEO})
    assert study_outcomes.correct_label(history) == study_outcomes.CORRECT_AFTER_VIDEO


def test_correct_label_solution_takes_precedence_over_hint() -> None:
    # Most-revealing support wins: solution outranks a hint used earlier on the same line.
    history = frozenset({study_outcomes.HINT, study_outcomes.SOLUTION})
    assert study_outcomes.correct_label(history) == study_outcomes.CORRECT_AFTER_SOLUTION


def test_incorrect_label_interim_without_solution() -> None:
    assert (
        study_outcomes.incorrect_label(frozenset(), terminal=False) == study_outcomes.INCORRECT
    )


def test_incorrect_label_answer_revealed_after_solution() -> None:
    history = frozenset({study_outcomes.SOLUTION})
    assert (
        study_outcomes.incorrect_label(history, terminal=False)
        == study_outcomes.ANSWER_REVEALED
    )


def test_incorrect_label_terminal_is_unresolved() -> None:
    history = frozenset({study_outcomes.SOLUTION})
    assert study_outcomes.incorrect_label(history, terminal=True) == study_outcomes.UNRESOLVED


def test_only_independent_correct_counts_as_independent() -> None:
    assert study_outcomes.counts_as_independent(study_outcomes.INDEPENDENT_CORRECT) is True
    for label in (
        study_outcomes.CORRECT_AFTER_HINT,
        study_outcomes.CORRECT_AFTER_VIDEO,
        study_outcomes.CORRECT_AFTER_SOLUTION,
        study_outcomes.ANSWER_REVEALED,
        study_outcomes.UNRESOLVED,
        study_outcomes.INCORRECT,
        None,
    ):
        assert study_outcomes.counts_as_independent(label) is False


def test_ladder_escalates_then_exhausts() -> None:
    # SPEC §5.11.7: retry same -> retry same (more support) -> prerequisite -> exhausted.
    assert study_outcomes.ladder_step(1).kind == "retry_same"
    assert study_outcomes.ladder_step(1).support_recommendation is None

    second = study_outcomes.ladder_step(2)
    assert second.kind == "retry_same"
    assert second.support_recommendation == study_outcomes.MORE_EXPLICIT_SUPPORT_MESSAGE

    third = study_outcomes.ladder_step(3)
    assert third.kind == "prerequisite"
    assert third.support_recommendation == study_outcomes.EASIER_PREREQUISITE_MESSAGE

    assert study_outcomes.ladder_step(4).kind == "exhausted"
    assert study_outcomes.ladder_step(5).kind == "exhausted"


def test_ladder_is_deterministic() -> None:
    # §5.31.1: identical attempt counts route identically every time.
    for n in range(1, 6):
        assert study_outcomes.ladder_step(n) == study_outcomes.ladder_step(n)


def _study_attempt(*, is_correct: bool, outcome_label: str | None) -> StudyAttempt:
    return StudyAttempt(
        student_external_id="s",
        study_session_id="ss",
        question_variant_id="v",
        selected_option="a",
        is_correct=is_correct,
        outcome_label=outcome_label,
    )


def test_support_dependency_splits_by_resolving_label() -> None:
    attempts = [
        _study_attempt(is_correct=True, outcome_label=study_outcomes.INDEPENDENT_CORRECT),
        _study_attempt(is_correct=True, outcome_label=study_outcomes.CORRECT_AFTER_HINT),
        _study_attempt(is_correct=True, outcome_label=study_outcomes.CORRECT_AFTER_VIDEO),
        _study_attempt(is_correct=True, outcome_label=study_outcomes.CORRECT_AFTER_SOLUTION),
        _study_attempt(is_correct=False, outcome_label=study_outcomes.UNRESOLVED),
        # Interim/answer-revealed attempts are not resolving and don't count in the totals.
        _study_attempt(is_correct=False, outcome_label=study_outcomes.INCORRECT),
        _study_attempt(is_correct=False, outcome_label=study_outcomes.ANSWER_REVEALED),
    ]
    dep = support_dependency(attempts)
    assert dep.independent_correct_rate == 0.2  # 1 of 5 resolving lines
    assert dep.hint_dependency == 0.4  # hint + video, 2 of 5
    assert dep.solution_dependency == 0.2  # 1 of 5


def test_support_dependency_empty_is_all_zero() -> None:
    dep = support_dependency([])
    assert (dep.independent_correct_rate, dep.hint_dependency, dep.solution_dependency) == (
        0.0,
        0.0,
        0.0,
    )


class _FakeVariant:
    question_variant_id = "v"
    question_template_id = "t"


class _FakeTemplate:
    skill_id = "linear_two_step"
    difficulty_label = 2


class _FakeQuestionRepo:
    async def get_variant(self, _variant_id: str) -> _FakeVariant:
        return _FakeVariant()

    async def get_template(self, _template_id: str) -> _FakeTemplate:
        return _FakeTemplate()


def test_assisted_study_correct_does_not_count_toward_independent_mastery() -> None:
    """SPEC §5.10.3/§5.11.5: a correct study answer that leaned on the solution is graded
    as incorrect for mastery, while an assessment correct and an independent study correct
    both count.
    """

    async def run() -> None:
        repo = _FakeQuestionRepo()
        assisted = _study_attempt(
            is_correct=True, outcome_label=study_outcomes.CORRECT_AFTER_SOLUTION
        )
        independent = _study_attempt(
            is_correct=True, outcome_label=study_outcomes.INDEPENDENT_CORRECT
        )
        exam = AssessmentAttempt(
            student_external_id="s",
            assessment_session_id="a",
            question_variant_id="v",
            selected_option="a",
            correct_option="a",
            is_correct=True,
            response_time_ms=1000,
        )

        graded = await resolve_graded_attempts(repo, [assisted, independent, exam])  # type: ignore[arg-type]
        assert [g.is_correct for g in graded] == [False, True, True]

    asyncio.run(run())
