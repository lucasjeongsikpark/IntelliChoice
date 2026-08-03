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


# --- D-163 cause 1: percent renderings of proportions -------------------------------
#
# Each widened rule is paired with a control that must still fail. The measurement that
# motivated these is `scripts/measure_report_grounding.py`; the numbers below are real
# ones it produced (0.8333 -> "83%", 0.625 -> "63%", and the invented "30 percentage
# points" that must keep being caught).


def test_grounded_when_a_proportion_is_written_as_a_whole_percent() -> None:
    evidence = {"mastery_by_skill": {"adding fractions": 0.8333333333333334}}
    assert is_grounded("They have mastered adding fractions at 83%.", evidence)


def test_grounded_on_a_half_percent_that_python_would_round_to_even() -> None:
    """`round(62.5)` is 62, so a `round()`-based rule would reject the equally correct
    "63%" for an evidence value of 0.625. The tolerance is absolute for this reason.
    """
    evidence = {"mastery_by_skill": {"multiplying decimals": 0.625}}
    assert is_grounded("Multiplying decimals sits at 63%.", evidence)
    assert is_grounded("Multiplying decimals sits at 62%.", evidence)


def test_not_grounded_when_the_percent_is_not_close_to_any_proportion() -> None:
    evidence = {"overall_accuracy": 0.6666666666666666}
    assert not is_grounded("Their accuracy reached 91%.", evidence)


def test_percent_rule_does_not_apply_to_values_outside_zero_to_one() -> None:
    """The bound is what keeps this from being a 100x fail-open: a gain of 3 points must
    never ground the claim "improved 300%".
    """
    evidence = {"raw_gain": 3.0, "attempts_count": 26}
    assert not is_grounded("Your child improved 300%!", evidence)
    assert not is_grounded("They answered 2600 questions.", evidence)


def test_not_grounded_on_a_trend_the_model_computed_itself() -> None:
    """The exact fabrication the measurement caught the real model producing: a
    from/to/difference sentence over a payload holding no trend at all.
    """
    evidence = {"overall_accuracy": 0.6666666666666666, "mastery_by_skill": {"a": 0.4166666667}}
    assert not is_grounded("Accuracy improved from 40% to 70%, a gain of 30 points.", evidence)


# --- D-163 cause 2: thousands separators --------------------------------------------


def test_extracts_a_grouped_number_as_one_value() -> None:
    assert extract_numbers("1,284 hints and 317 solutions") == [1284, 317]


def test_extracts_multiple_grouping_levels() -> None:
    assert extract_numbers("12,345,678 attempts") == [12345678]


def test_a_comma_between_two_numbers_is_not_read_as_grouping() -> None:
    """Without the lookbehind, "In 2026, 317 solutions" matches "026,317" and invents
    26317 - a number in neither the text nor the evidence.
    """
    assert extract_numbers("In 2026, 317 solutions") == [2026, 317]


def test_grounded_when_a_count_is_written_with_a_thousands_separator() -> None:
    evidence = {"hint_count": 1284}
    assert is_grounded("They used 1,284 hints.", evidence)


def test_not_grounded_on_a_grouped_number_that_is_not_in_evidence() -> None:
    evidence = {"hint_count": 1284}
    assert not is_grounded("They used 9,999 hints.", evidence)


# --- D-163 cause 3: numbers inside evidence strings ---------------------------------


def test_grounded_on_a_number_the_evidence_states_inside_a_label() -> None:
    """The prompt tells the model to name the window a figure comes from, and the window
    label itself is where the threshold lives - so quoting it must be groundable.
    """
    evidence = {
        "weak_skill_window_label": "listing only skills below 70% - the same cut the "
        "study plan uses to choose what to work on next.",
        "mastery_by_skill": {"subtracting fractions": 0.4166666666666667},
    }
    assert is_grounded("Two skills are below 70% and need work.", evidence)


def test_grounded_on_the_date_range_the_report_is_headed_with() -> None:
    evidence = {"date_range_label": "2026-07-01 to 2026-07-31", "attempts_count": 26}
    assert is_grounded("Over July 2026 they completed 26 attempts.", evidence)


def test_not_grounded_on_a_number_absent_from_every_string_and_value() -> None:
    evidence = {"date_range_label": "2026-07-01 to 2026-07-31", "attempts_count": 26}
    assert not is_grounded("Over July 2026 they completed 88 attempts.", evidence)


def test_dict_keys_are_evidence_too() -> None:
    evidence = {"mastery_by_skill": {"adding 2-digit numbers": 0.9}}
    assert is_grounded("Adding 2-digit numbers is going well.", evidence)
