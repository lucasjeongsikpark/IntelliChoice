from intellichoice_evals.leak_sample import LEAK_CASES, sweep_for_unexpected_leaks


def test_golden_leak_sample_all_behave_as_documented() -> None:
    assert sweep_for_unexpected_leaks() == []


def test_negative_integer_leak_case_is_present() -> None:
    # Regression case for D-079 - a leading "-" used to defeat the old `\b`-anchored
    # check entirely, so a negative-answer leak was never caught.
    case = next(c for c in LEAK_CASES if c.id == "verbatim_negative_integer")
    assert case.expect_leak is True
    assert case.correct_answer_text == "-4"
