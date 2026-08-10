"""Pure unit tests for `authored_validation.py`'s deterministic §5.8.5 checks - no
Postgres needed, unlike `test_authored_pipeline.py`'s end-to-end tests.
"""

import pytest
from intellichoice_curriculum.authored_validation import (
    answer_leaked_beyond_the_question,
    answer_text_leaked,
    hint_ladder_monotonicity_violations,
    validate_authored_item,
)
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)
from pydantic import ValidationError


def _good_item(**overrides: object) -> AuthoredGeneratedItemResponse:
    base: dict[str, object] = dict(
        stem="Solve: what is 2 + 2?",
        option_a="4",
        option_b="5",
        option_c="6",
        option_d="3",
        correct_option="a",
        equation="Eq(x, 2 + 2)",
        hint_ladder=[
            "Think about combining two small groups of objects.",
            "Try counting up from 2 by 2 more.",
            "Add the two numbers together directly.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(step_number=1, explanation="Add the numbers.", expression="2 + 2")
            ],
            final_answer="4",
        ),
        misconception_tags=["off_by_one"],
        estimated_time_seconds=30,
        proposed_difficulty=1,
        difficulty_rationale=(
            "One addition with single-digit whole numbers and no equation to rearrange."
        ),
        required_prerequisites=["single-digit addition"],
    )
    base.update(overrides)
    return AuthoredGeneratedItemResponse(**base)  # type: ignore[arg-type]


def test_valid_item_passes_every_check() -> None:
    result = validate_authored_item(1, _good_item())
    assert result.passed
    assert result.failures == []


def test_two_correct_options_rejected() -> None:
    item = _good_item(option_b="4")
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("unique" in f or "exactly one option" in f for f in result.failures)


def test_sympy_disagreement_with_declared_answer_rejected() -> None:
    item = _good_item(equation="Eq(x, 2 + 2)", correct_option="b")  # option_b == "5"
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("does not match declared correct option" in f for f in result.failures)


def test_correct_answer_written_as_an_equation_is_accepted() -> None:
    """Both of these are what a real model actually wrote, and both were rejected.

    The first real-Bedrock authoring run (2026-08-05) lost six of eleven candidates to
    option formatting rather than to wrong math: `sympy.sympify` accepts neither `'x = 7'`
    nor a typographic minus, so the independent-solve gate reported a mismatch for items
    whose answers were right. The value each option denotes is unchanged by either
    repair - that is what makes accepting them safe.
    """
    restated = _good_item(
        equation="Eq(x, 3 + 4)",
        option_a="x = 7",
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="Add.", expression="3 + 4")],
            final_answer="7",
        ),
    )
    result = validate_authored_item(1, restated)
    assert result.passed, result.failures

    typographic_minus = _good_item(
        stem="Solve for x: 2x + 7 = 1",
        equation="Eq(2*x + 7, 1)",
        option_a="−3",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(step_number=1, explanation="Subtract 7.", expression="2x = -6")
            ],
            final_answer="−3",
        ),
    )
    result = validate_authored_item(1, typographic_minus)
    assert result.passed, result.failures


def test_a_word_problem_answer_with_a_unit_is_verified_rather_than_exempt() -> None:
    """The gate penalised word problems, which is where units naturally appear.

    Not by rejecting prose - a scenario stem always passed - but by rejecting the answer
    text a scenario implies. `sympify('12 minutes')` fails, so the correct option matched
    nothing and the item was rejected for a mismatch its math did not have. Same family as
    `'x = 7'` and the typographic minus, unnoticed until the questions stopped being bare
    equations (D-191).

    The second half is the part that matters: stripping a unit must not stop the value
    being checked, or this would trade a false rejection for a false acceptance.
    """
    with_unit = _good_item(
        stem="A tank fills at 4 litres each minute. How long to add 12 litres?",
        equation="Eq(4*x, 12)",
        option_a="3 minutes",
        option_b="4 minutes",
        option_c="12 minutes",
        option_d="48 minutes",
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="Divide.", expression="12 / 4")],
            final_answer="3 minutes",
        ),
    )
    result = validate_authored_item(1, with_unit)
    assert result.passed, result.failures

    # Same units, wrong declared answer: still caught, so the unit did not become a
    # loophole that makes any option match.
    wrong = _good_item(
        stem="A tank fills at 4 litres each minute. How long to add 12 litres?",
        equation="Eq(4*x, 12)",
        option_a="3 minutes",
        option_b="4 minutes",
        option_c="12 minutes",
        option_d="48 minutes",
        correct_option="b",
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="Divide.", expression="12 / 4")],
            final_answer="4 minutes",
        ),
    )
    result = validate_authored_item(1, wrong)
    assert not result.passed
    assert any("does not match declared correct option" in f for f in result.failures)


def test_an_algebraic_answer_is_not_mistaken_for_a_united_value() -> None:
    """`'2x'` must not be read as `2` by the unit stripper - the reason it only runs
    after a direct parse has already failed, and only on suffixes of two letters or more.
    """
    from intellichoice_curriculum.authored_validation import _sympify

    assert _sympify("2x") is None
    assert str(_sympify("x")) == "x"
    assert _sympify("12 minutes") == 12
    assert _sympify("40 cm") == 40


def test_typographic_minus_distractor_is_no_longer_exempt_from_the_duplicate_check() -> None:
    """The gate was quieter, not just noisier, before the parse-site normalization.

    An option that failed to parse was skipped by `check_sympy_independent_solve`'s "no
    distractor also matches" arm entirely, so a distractor equal to the correct answer
    would pass unnoticed as long as it was written with a character SymPy rejects. The
    2026-08-05 run produced an item with exactly such a distractor ('−3'), which is how
    this was noticed.
    """
    item = _good_item(equation="Eq(x, 2 + 2)", option_b="−4", option_c="4")
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("more than one option matches" in f for f in result.failures)


def test_banned_wording_matches_words_not_substrings() -> None:
    """Substring matching rejected correct, harmless questions - and the words it hit are
    ones a math item is likely to contain.

    Measured on the first scenario run (D-191): a question about rolling a **die** was
    rejected. `'skill'` contains `'kill'` and `'studies'` contains `'die'`, so the check
    was a trap that got more likely to spring the more natural the language became. `die`
    is off the list entirely - it is the singular of dice, not a word about death.
    """
    for harmless in [
        "Roll a die and record the number that lands face up.",
        "This skill needs practice before the next unit.",
        "Ana studies for 40 minutes each evening.",
        "Choose the medium jar rather than the small one.",
    ]:
        item = _good_item(stem=harmless)
        result = validate_authored_item(1, item)
        assert not any("disallowed wording" in f for f in result.failures), harmless

    # "dies" added in D-223. The list carried "died"/"dying" but not the present tense, and
    # the gap surfaced from the *other* side: the shape half's negative controls only caught
    # it because that half was still substring-matching, so "dies" tripped on "die". Fixing
    # the substring bug there would have silently opened this hole here had the word not been
    # added at the same time.
    for banned in [
        "The plants died after a week.",
        "The character dies after four turns.",
        "That answer is stupid.",
    ]:
        item = _good_item(stem=banned)
        result = validate_authored_item(1, item)
        assert any("disallowed wording" in f for f in result.failures), banned


def test_leaked_answer_in_hint_rejected() -> None:
    item = _good_item(
        hint_ladder=[
            "The answer is 4, but think about why.",
            "Try counting up from 2 by 2 more.",
            "Add the two numbers together directly.",
        ]
    )
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("leak" in f for f in result.failures)


def test_hint_ladder_monotonicity_violation_rejected() -> None:
    item = _good_item(
        hint_ladder=[
            "Try counting up from 2. Add the two numbers together directly.",
            "Try counting up from 2.",
            "Add the two numbers together directly.",
        ]
    )
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("already reveals" in f for f in result.failures)


def test_monotonicity_check_covers_verbatim_containment_only() -> None:
    """Characterization, not aspiration: this pins the *gap* the name hides (D-251).

    `hint_ladder_monotonicity_violations` is `later.strip() in earlier` and nothing more, so a
    ladder that fails progression in any way other than verbatim repetition reads as clean.
    Both cases below are genuine progression failures and both return no violations.

    If a future change makes either of these fail, that is a widening of the rule into a
    heuristic and it must be a deliberate decision with a measurement behind it - not a
    silent tightening discovered by this test going red.
    """
    # A paraphrase of the same content across two rungs: nothing new is added, and no
    # substring of the later rung appears in the earlier one.
    paraphrased = [
        "Add the two numbers together directly.",
        "Simply sum both values.",
        "Combine 2 and 2 to finish.",
    ]
    assert hint_ladder_monotonicity_violations(paraphrased) == []

    # A reordered ladder - most revealing first, least revealing last - is backwards for a
    # student and invisible here, because containment is not ordering.
    reordered = [
        "Add the two numbers together directly.",
        "Try counting up from 2 by 2 more.",
        "Think about combining two small groups of objects.",
    ]
    assert hint_ladder_monotonicity_violations(reordered) == []


def test_hint_solution_answer_disagreement_rejected() -> None:
    item = _good_item(
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="e", expression="e")],
            final_answer="5",
        )
    )
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("final_answer" in f for f in result.failures)


def test_disallowed_wording_rejected() -> None:
    item = _good_item(stem="This is a dumb question: what is 2 + 2?")
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("disallowed wording" in f for f in result.failures)


def test_off_grade_readability_rejected() -> None:
    long_sentence = " ".join(["word"] * 40) + "?"
    item = _good_item(stem=long_sentence)
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("readability" in f for f in result.failures)


def test_html_or_link_rejected() -> None:
    item = _good_item(stem="Solve: what is 2 + 2? <script>alert(1)</script>")
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("HTML or a link" in f for f in result.failures)


def test_wrong_hint_ladder_length_rejected() -> None:
    # D-195 bounded `hint_ladder` in the schema, so a wrong-length ladder from a *model*
    # is now refused at construction (see the three schema tests at the end of this file)
    # and this fixture can no longer be built normally. The validator check is still
    # wanted and still tested, because the schema only guards items the Generator
    # produces: an item rebuilt from the YAML bank by `authored_bank.to_generated_item`
    # takes a different route in. `model_construct` skips validation, which is exactly the
    # "arrived without passing the model contract" case this second layer exists for.
    # `model_copy`, not `model_construct(**model_dump())`: dumping turns the nested
    # `canonical_solution` into a plain dict and the validator then trips over it, which
    # would make this test fail for a reason that has nothing to do with hints.
    item = _good_item().model_copy(update={"hint_ladder": ["only one hint"]})
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("hint_ladder has" in f for f in result.failures)


def test_out_of_range_difficulty_rejected() -> None:
    result = validate_authored_item(9, _good_item())
    assert not result.passed
    assert any("difficulty_label" in f for f in result.failures)


# --- D-195: the hint-ladder contract is structural, not only downstream --------------
# The first four-candidate pilot lost a candidate to a 4-level ladder *after* paying for
# the whole item. Bounding the field in the schema puts the rule in the tool's
# `inputSchema`, so a violation costs a bounded repair retry instead of the candidate.


def test_hint_ladder_accepts_exactly_three_levels() -> None:
    item = _good_item()
    assert len(item.hint_ladder) == 3


def test_hint_ladder_rejects_two_levels() -> None:
    with pytest.raises(ValidationError) as exc:
        _good_item(hint_ladder=["Only one hint.", "And a second."])
    assert "hint_ladder" in str(exc.value)


def test_hint_ladder_rejects_four_levels() -> None:
    # Candidate 1 of the first pilot, exactly: four hints where the contract says three.
    with pytest.raises(ValidationError) as exc:
        _good_item(
            hint_ladder=[
                "Think about combining two small groups.",
                "Try counting up from 2 by 2 more.",
                "Add the two numbers together directly.",
                "One more level than the contract allows.",
            ]
        )
    assert "hint_ladder" in str(exc.value)


# --- D-195: §6 checks, tested against the pilot's own defective content ---------------
# Each of these checks already existed. What was missing was a test proving it fires on
# the shape a real model actually produced, rather than on a hand-made counterexample.


def test_a_constant_equation_with_no_unknown_is_rejected() -> None:
    # Candidate 2's real equation. It has no variable to solve for, so nothing about the
    # student's answer can be derived from it - the "independent solve" would be a
    # comparison of the generator against itself, which is the hole D-191 closed.
    result = validate_authored_item(3, _good_item(equation="Eq((20 - 3) / 2, (25 - 7) / 2)"))
    assert not result.passed
    assert any("restates the answer" in f for f in result.failures)


def test_a_false_constant_equation_is_rejected() -> None:
    # The same candidate's equation is not merely unsolvable, it is false: 8.5 != 9.
    # SymPy collapses it to BooleanFalse, which is not an `Equality` either, so the same
    # check catches both - worth pinning, since a *true* tautology and a *false* one
    # arrive by different routes.
    result = validate_authored_item(3, _good_item(equation="Eq(2 + 2, 5)"))
    assert not result.passed
    assert any("restates the answer" in f for f in result.failures)


def test_an_equation_with_two_unknowns_is_rejected() -> None:
    result = validate_authored_item(3, _good_item(equation="Eq(a + b, 4)"))
    assert not result.passed
    assert any("unknowns, expected exactly one" in f for f in result.failures)


def test_a_canonical_answer_that_does_not_satisfy_the_equation_is_rejected() -> None:
    # The equation solves to 9 while the declared correct option and the canonical answer
    # both say 4. The item is internally consistent *except* against its own equation,
    # which is the only place the discrepancy can surface - and the reason the equation is
    # solved independently rather than trusted (D-191).
    result = validate_authored_item(3, _good_item(equation="Eq(x, 4 + 5)"))
    assert not result.passed
    assert any("does not match declared correct option" in f for f in result.failures)


def test_a_canonical_answer_disagreeing_with_the_correct_option_is_rejected() -> None:
    # The neighbouring failure, kept separate because a different check catches it: here
    # the equation and the options agree on 4 and only `canonical_solution.final_answer`
    # dissents, so the worked solution a student would be shown contradicts the key.
    result = validate_authored_item(
        1,
        _good_item(
            canonical_solution=SolutionResponse(
                steps=[SolutionStep(step_number=1, explanation="Add.", expression="2 + 2")],
                final_answer="5",
            )
        ),
    )
    assert not result.passed
    assert any("does not match the declared correct option" in f for f in result.failures)


def test_a_hint_leaking_the_answer_is_rejected() -> None:
    # Candidate 2's third hint contained the answer verbatim.
    result = validate_authored_item(
        3,
        _good_item(
            hint_ladder=[
                "Think about combining two small groups of objects.",
                "Try counting up from 2 by 2 more.",
                "The answer is 4, so pick that option.",
            ]
        ),
    )
    assert not result.passed
    assert any("hint_ladder[3]" in f for f in result.failures)


def test_a_stem_narrating_its_own_authoring_is_rejected() -> None:
    # Candidate 2's stem contained "The question is adjusted to ask for the number of
    # rides after...". It was caught only incidentally, as a 30-word sentence; a shorter
    # one would have shipped model-to-itself narration to a child.
    result = validate_authored_item(
        3, _good_item(stem="The question is adjusted to ask what 2 + 2 is.")
    )
    assert not result.passed
    assert any("authoring commentary" in f for f in result.failures)


def test_an_ordinary_adjustment_in_a_scenario_still_passes() -> None:
    # The counterexample that keeps the phrase list honest: a *recipe* being adjusted is
    # a legitimate math scenario, and matching the bare verb would have rejected it. The
    # phrases name the act of authoring, not the word "adjusted".
    result = validate_authored_item(
        1, _good_item(stem="The recipe was adjusted to serve 4 people. What is 2 + 2?")
    )
    assert result.passed, result.failures


# --- D-195 repeat pilot: a decimal in the scenario is not a leaked answer --------------
# `answer_text_leaked` treated a decimal point as a word boundary, so answer "8" matched
# the 8 inside "0.8". That rejected a correct, well-built item whose hint said "Jake
# starts 0.8 km from the park", and the same function guards runtime hints, where a false
# positive suppresses a legitimate hint. Single-digit answers in scenarios that use
# decimals are most of this topic, not a corner case.


def test_a_digit_inside_a_decimal_is_not_a_leaked_answer() -> None:
    hint = "Jake starts 0.8 km from the park and runs 0.05 km closer each minute."
    assert not answer_text_leaked(hint, "8")


def test_an_answer_followed_by_a_decimal_place_is_not_a_leak() -> None:
    assert not answer_text_leaked("the value is 8.5 km", "8")


def test_a_decimal_answer_is_still_caught_when_stated_in_full() -> None:
    assert answer_text_leaked("it costs 2.4 dollars", "2.4")


def test_a_genuine_leak_at_the_end_of_a_sentence_is_still_caught() -> None:
    # The `.` here is not followed by a digit, so it is punctuation, not a decimal point.
    assert answer_text_leaked("The answer is 8.", "8")
    assert answer_text_leaked("so g = 8 minutes", "8")


def test_the_earlier_boundary_fixes_are_not_regressed() -> None:
    # S30's negative-answer fix and the "4 inside 24" guard both still hold.
    assert answer_text_leaked("the value is -4", "-4")
    assert not answer_text_leaked("24 apples", "4")


def test_the_repeat_pilots_correct_item_now_survives_the_gate() -> None:
    """The whole item that was lost, rebuilt: Lena and Jake running toward a park.

    `Eq(1.2 - 0.1*m, 0.8 - 0.05*m)` solves to m = 8, which matches the declared option.
    Nothing about it was wrong - it was rejected because hint 2 mentioned "0.8 km".
    """
    item = _good_item(
        stem=(
            "Lena begins 1.2 km from the park and runs 0.1 km each minute. Jake begins "
            "0.8 km away and runs 0.05 km each minute. When are they equally far away?"
        ),
        option_a="12",
        option_b="2",
        option_c="4",
        option_d="8",
        correct_option="d",
        equation="Eq(1.2 - 0.1*m, 0.8 - 0.05*m)",
        hint_ladder=[
            "Think about how far each has left to run after a certain number of minutes.",
            "Lena starts 1.2 km from the park; Jake starts 0.8 km from the park.",
            "Write an equation setting Lena's distance equal to Jake's after m minutes.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Set the two remaining distances equal.",
                    expression="1.2 - 0.1*m = 0.8 - 0.05*m",
                )
            ],
            final_answer="8",
        ),
        proposed_difficulty=3,
        difficulty_rationale=(
            "Two moving objects, a variable on both sides, and decimal coefficients to "
            "carry through the arithmetic."
        ),
    )
    result = validate_authored_item(3, item)
    assert result.passed, result.failures


# --- D-201: an answer that coincides with a given quantity is not a leak ---------------
# Four correct items were destroyed by this before the rule existed. `answer_text_leaked`
# cannot tell "the answer is 4" from "he buys a 4-pack" - they are the same characters -
# so the rule is about what the student can already see.


def test_a_hint_repeating_a_number_the_stem_already_shows_is_not_a_leak() -> None:
    # The real juice-box item: Eq(3 + 4*t, 19) -> t = 4, and the stem says "4-pack".
    assert not answer_leaked_beyond_the_question(
        hint_text="Leo starts with 3 and adds 4 every trip, so after t trips he has 3 + 4t.",
        correct_answer_text="4",
        question_text="Leo has 3 juice boxes. He buys a 4-pack every trip. He wants 19 in total.",
    )


def test_a_hint_stating_an_answer_the_question_never_shows_is_still_a_leak() -> None:
    assert answer_leaked_beyond_the_question(
        hint_text="After working it through you will find it takes 7 weeks.",
        correct_answer_text="7",
        question_text="Mia has $18 and saves $6 each week. The bike costs $60.",
    )


def test_the_explicit_phrase_check_is_not_weakened_by_the_exemption() -> None:
    # "the answer is 4" must still fail even though 4 is a given - the exemption is about
    # repeating a visible value, never about being allowed to announce the answer.
    result = validate_authored_item(
        1,
        _good_item(
            stem="Liam buys a 4-pack of pens. What is 2 + 2?",
            hint_ladder=[
                "Think about combining two small groups.",
                "Try counting up from 2 by 2 more.",
                "The answer is 4, so pick that option.",
            ],
        ),
    )
    assert not result.passed
    assert any("explicit answer-leak phrase" in f for f in result.failures)


def test_the_real_item_this_gate_destroyed_now_passes() -> None:
    """`Eq(3*(x + 4) + 10, 34)` solves to 4, and the `+ 4` is inside its own equation.

    Two tier-5 candidates were rejected for this in one run - the fourth and fifth items
    lost to a check firing on a number the student is already looking at.
    """
    item = _good_item(
        stem="A club packs 3 boxes, each holding x badges plus 4 stickers, and adds 10 "
        "loose badges. Altogether there are 34 items. How many badges are in each box?",
        option_a="4",
        option_b="6",
        option_c="8",
        option_d="12",
        correct_option="a",
        equation="Eq(3*(x + 4) + 10, 34)",
        hint_ladder=[
            "How many items are in one box, if a box holds x badges?",
            "Each box holds x + 4 items, and there are 3 boxes plus 10 loose badges.",
            "Multiply out the bracket first, then gather the x terms.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Distribute, then collect like terms.",
                    expression="3*(x + 4) + 10 = 34",
                )
            ],
            final_answer="4",
        ),
        proposed_difficulty=5,
        difficulty_rationale=(
            "A bracket must be distributed before like terms can be combined, and the "
            "student must first decide that a box holds x + 4 items rather than x."
        ),
    )
    result = validate_authored_item(5, item)
    assert result.passed, result.failures
