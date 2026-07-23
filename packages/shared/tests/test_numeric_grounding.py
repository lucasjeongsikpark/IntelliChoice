from intellichoice_shared.numeric_grounding import extract_numbers, is_grounded


def test_extracts_integers_and_decimals() -> None:
    assert extract_numbers("You solved 3 of 5 questions, up 2.5 points") == [3, 5, 2.5]


def test_extracts_no_numbers_from_plain_text() -> None:
    assert extract_numbers("Great effort today!") == []


def test_grounded_on_exact_match() -> None:
    evidence = {"raw_gain": 3, "weak_skill_names": ["fractions"]}
    assert is_grounded("You improved by 3 points in fractions.", evidence)


def test_grounded_on_nearest_integer_rounding() -> None:
    evidence = {"normalized_gain": 0.6666666667}
    assert is_grounded("Your growth rate was about 1.", evidence)


def test_grounded_on_one_decimal_rounding() -> None:
    evidence = {"raw_gain": 2.6666666667}
    assert is_grounded("You grew by about 2.7 points.", evidence)


def test_not_grounded_on_invented_number() -> None:
    evidence = {"raw_gain": 3, "pre_raw_score": 5}
    assert not is_grounded("You improved by 10 points!", evidence)


def test_grounded_with_no_numbers_in_narrative() -> None:
    evidence = {"raw_gain": 3}
    assert is_grounded("Great job on your growth today!", evidence)


def test_grounding_recurses_into_nested_lists_and_dicts() -> None:
    evidence = {"skill_level_gain": {"fractions": 2, "algebra": [1, 4]}}
    assert is_grounded("You gained 4 points in algebra.", evidence)


def test_bool_values_are_not_treated_as_groundable_numbers() -> None:
    evidence = {"generated": True, "raw_gain": 3}
    assert not is_grounded("You solved 1 question correctly.", evidence)
