from intellichoice_shared.numeric_grounding import (
    INVERTED_SCORE_PAIR,
    UNGROUNDED_NUMBER,
    extract_numbers,
    grounding_failure,
    is_grounded,
)


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


# --- AUD-L-09 (D-098 mitigation 1): the directional check ---------------------------
#
# Provenance was the only property checked: every number in "your score fell from 6 to 4"
# is in the evidence for a student who went 4 -> 6, so the sentence shipped to a parent.
# The rule below judges exactly one thing - an explicit `from X to Y` transition whose two
# numbers are the known pre/post pair in reverse - which is the damaging class D-098 named.
# Everything else about attribution stays unchecked, deliberately and by decision.


def test_a_known_gain_stated_in_reverse_is_rejected() -> None:
    """The finding's own example. Both numbers are in evidence, so the provenance check
    passes and passed before this rule existed.
    """
    evidence = {"pre_raw_score": 4.0, "post_raw_score": 6.0, "raw_gain": 2.0}
    assert not is_grounded("Your score fell from 6 to 4 this session.", evidence)
    assert grounding_failure("Your score fell from 6 to 4 this session.", evidence) == (
        INVERTED_SCORE_PAIR
    )


def test_the_same_pair_in_the_right_order_is_accepted() -> None:
    """The control: the rule must not reject the sentence the fallback template itself
    writes (`report._fallback_texts` -> "Score went from 4 to 6.").
    """
    evidence = {"pre_raw_score": 4.0, "post_raw_score": 6.0, "raw_gain": 2.0}
    assert is_grounded("Score went from 4 to 6. That's a gain of 2 points.", evidence)
    assert grounding_failure("Score went from 4 to 6.", evidence) is None


def test_a_decline_stated_in_reverse_is_rejected_too() -> None:
    """Symmetric on purpose: inverting a real decline into a gain is the same defect, and
    growth-oriented language (SPEC §5.10.3) is the phrasing most likely to produce it.
    """
    evidence = {"pre_raw_score": 8.0, "post_raw_score": 5.0, "raw_gain": -3.0}
    assert not is_grounded("You improved from 5 to 8!", evidence)


def test_the_verb_between_the_numbers_is_not_what_decides() -> None:
    """`from`/`to` is the assertion; the verb is prose. "improved from 6 to 4" is rejected
    for a 4 -> 6 student on the numbers alone, so no verb list has to be maintained.
    """
    evidence = {"pre_raw_score": 4.0, "post_raw_score": 6.0}
    assert not is_grounded("Your score improved from 6 to 4.", evidence)
    assert not is_grounded("Your score went from 6 to 4.", evidence)


def test_an_intervening_word_inside_the_transition_is_still_read() -> None:
    evidence = {"pre_raw_score": 4.0, "post_raw_score": 6.0}
    assert not is_grounded("Your score dropped from 6 down to 4.", evidence)
    assert not is_grounded("It moved from 6 all the way to 4.", evidence)


def test_rounding_tolerance_applies_to_the_pair_as_well() -> None:
    """The pair is matched with the same tolerance as provenance, so a model rounding
    6.4 to "6" cannot slip an inverted claim through on the rounding alone.
    """
    evidence = {"pre_raw_score": 4.2, "post_raw_score": 6.4}
    assert not is_grounded("Your score fell from 6 to 4.", evidence)


def test_equal_scores_have_no_order_to_invert() -> None:
    evidence = {"pre_raw_score": 5.0, "post_raw_score": 5.0}
    assert is_grounded("Your score held at 5, from 5 to 5.", evidence)


def test_the_check_needs_both_scores_and_says_nothing_without_them() -> None:
    """A stage narrative that carries only one of the two (or neither) is outside this
    rule entirely - `study_outro` and `pre_intro` never carry scores at all.
    """
    evidence = {"post_raw_score": 6.0, "hint_count": 4}
    assert is_grounded("It went from 6 to 4.", evidence)


def test_a_transition_between_two_unrelated_numbers_is_left_alone() -> None:
    evidence = {"pre_raw_score": 4.0, "post_raw_score": 6.0, "hint_count": 9, "video_count": 3}
    assert is_grounded("Hint use went from 9 to 3 as you got more independent.", evidence)


def test_a_collision_with_another_figures_pair_is_rejected_fail_closed() -> None:
    """The rule's known false-rejection class, pinned so it stays a decision. With scores
    4 -> 6 and hints 6 -> 4, a *faithful* sentence about hints is indistinguishable from an
    inverted one about scores: numbers alone carry no field identity, which is the whole
    finding. Rejecting costs the parent the prose and keeps the correct figures
    (`_fallback_texts`); accepting risks telling them their child's score fell when it rose.
    """
    evidence = {"pre_raw_score": 4.0, "post_raw_score": 6.0, "hint_count": 6, "solution_count": 4}
    assert not is_grounded("Hint use fell from 6 to 4 as you got more independent.", evidence)


def test_an_ungrounded_number_is_reported_as_its_own_reason() -> None:
    """The two failure modes are logged apart because they mean different things: an
    invented number is the model fabricating, an inverted pair is the model misreading a
    number it was given. A single "failed grounding" counter cannot tell them apart.
    """
    evidence = {"pre_raw_score": 4.0, "post_raw_score": 6.0}
    assert grounding_failure("You scored 11 points.", evidence) == UNGROUNDED_NUMBER


def test_an_ungrounded_number_outranks_the_pair_check() -> None:
    """Both wrong at once: the number check runs first, so the reason is the more basic
    one. Asserted so the ordering is fixed rather than incidental to how it reads.
    """
    evidence = {"pre_raw_score": 4.0, "post_raw_score": 6.0}
    assert grounding_failure("You fell from 6 to 4, missing 11 points.", evidence) == (
        UNGROUNDED_NUMBER
    )
