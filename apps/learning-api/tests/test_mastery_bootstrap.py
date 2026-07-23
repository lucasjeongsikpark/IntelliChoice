from learning_api.services.mastery_bootstrap import (
    GradedAttempt,
    accuracy_by_difficulty,
    highest_consistent_difficulty,
    raw_accuracy,
    recommended_difficulty,
    weighted_score,
)


def _attempt(difficulty: int, is_correct: bool, skill_id: str = "skill-1") -> GradedAttempt:
    return GradedAttempt(skill_id=skill_id, difficulty=difficulty, is_correct=is_correct)


def test_raw_accuracy_empty_is_zero() -> None:
    assert raw_accuracy([]) == 0.0


def test_raw_accuracy_counts_correct_fraction() -> None:
    attempts = [_attempt(1, True), _attempt(1, True), _attempt(1, False), _attempt(1, False)]
    assert raw_accuracy(attempts) == 0.5


def test_weighted_score_matches_spec_formula() -> None:
    # §5.10.1 example: one correct at difficulty 2 (weight 1.4), one wrong at difficulty 4
    # (weight 2.5). Weighted score = 1.4 / (1.4 + 2.5).
    attempts = [_attempt(2, True), _attempt(4, False)]
    assert weighted_score(attempts) == 1.4 / (1.4 + 2.5)


def test_weighted_score_empty_is_zero() -> None:
    assert weighted_score([]) == 0.0


def test_accuracy_by_difficulty_groups_correctly() -> None:
    attempts = [_attempt(1, True), _attempt(1, False), _attempt(3, True)]
    result = accuracy_by_difficulty(attempts)
    assert result == {"1": 0.5, "3": 1.0}


def test_highest_consistent_difficulty_stops_at_first_miss() -> None:
    attempts = [
        _attempt(1, True),
        _attempt(1, True),
        _attempt(2, True),
        _attempt(2, True),
        _attempt(3, False),
        _attempt(3, True),
        _attempt(4, True),
    ]
    assert highest_consistent_difficulty(attempts) == 2


def test_highest_consistent_difficulty_none_when_first_difficulty_fails() -> None:
    attempts = [_attempt(1, False), _attempt(2, True)]
    assert highest_consistent_difficulty(attempts) is None


def test_highest_consistent_difficulty_all_correct() -> None:
    attempts = [_attempt(1, True), _attempt(2, True), _attempt(5, True)]
    assert highest_consistent_difficulty(attempts) == 5


def test_recommended_difficulty_none_without_attempts() -> None:
    assert recommended_difficulty([]) is None


def test_recommended_difficulty_steps_up_when_mastered() -> None:
    # All correct at difficulty 3 (accuracy 1.0 >= 0.8) -> route up a level.
    attempts = [_attempt(3, True), _attempt(3, True)]
    assert recommended_difficulty(attempts) == 4


def test_recommended_difficulty_holds_when_passing() -> None:
    # 50% at difficulty 3 (0.5 <= accuracy < 0.8) -> hold at the current level.
    attempts = [_attempt(3, True), _attempt(3, False)]
    assert recommended_difficulty(attempts) == 3


def test_recommended_difficulty_steps_down_when_struggling() -> None:
    # All wrong at difficulty 3 (accuracy 0.0 < 0.5) -> route down a level.
    attempts = [_attempt(3, False), _attempt(3, False)]
    assert recommended_difficulty(attempts) == 2


def test_recommended_difficulty_clamps_to_range() -> None:
    assert recommended_difficulty([_attempt(5, True)]) == 5  # can't exceed 5
    assert recommended_difficulty([_attempt(1, False)]) == 1  # can't drop below 1


def test_recommended_difficulty_is_deterministic() -> None:
    # §5.31.1 deterministic evaluator: identical inputs -> identical routing.
    attempts = [_attempt(2, True), _attempt(2, False), _attempt(2, True)]
    assert recommended_difficulty(attempts) == recommended_difficulty(attempts)
