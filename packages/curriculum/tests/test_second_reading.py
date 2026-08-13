"""The second reading of a verified model (D-281), scored in both directions.

**What this exists for, measured.** The 6-8/9-12 re-run accepted **0 of 28** candidates
across all three inequality skills. The rejected items were not wrong:

    stem     "A collector has 12 cards and receives 6 each month. She wants at least 54.
              What is the smallest number of months?"
    equation "12 + 6*m >= 54"
    answer   "7 months"

`route_answer` reads an inequality as the `interval` model and derived `Interval(7, oo)`,
then compared a solution *set* against the string "7 months". Both are honest readings of
one correctly-modelled inequality; the gate admitted only the first, so a threshold word
problem - the ordinary way to ask an inequality - could not be accepted at all.

**Why this is not a loosening.** The second reading runs only when the first matches
nothing, and it must match exactly one option, which is the same bar the first reading
clears. An open boundary yields nothing at all rather than an off-by-one guess. The tests
below score the direction that matters: that a *wrong* answer is still rejected, that the
off-by-one distractor these items carry is never accepted, and that an item the gate
already accepted is untouched.

Free: pure SymPy, no model call, no database.
"""

import pytest
import sympy
from intellichoice_curriculum import authored_validation as av
from intellichoice_curriculum.authored_validation import (
    _student_notation,
    validate_authored_item,
)
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)


def _item(**overrides) -> AuthoredGeneratedItemResponse:
    base = dict(
        stem=(
            "A collector has 12 trading cards and receives 6 new cards each month. She "
            "wants at least 54 cards. What is the smallest number of months she needs?"
        ),
        option_a="7 months",
        option_b="6 months",
        option_c="8 months",
        option_d="42 months",
        correct_option="a",
        hint_ladder=[
            "Start from the cards she already has.",
            "Subtract those from the goal.",
            "Divide what is left by the monthly rate.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Subtract the starting cards, then divide by the rate.",
                    expression="12 + 6*m >= 54",
                    common_mistake=None,
                )
            ],
            final_answer="7 months",
        ),
        estimated_time_seconds=60,
        misconception_tags=["off_by_one"],
        proposed_difficulty=3,
        difficulty_rationale="two steps and an inequality",
        required_prerequisites=["dividing whole numbers"],
        equation="12 + 6*m >= 54",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def _failures(item: AuthoredGeneratedItemResponse) -> list[str]:
    return validate_authored_item(3, item).failures


# --------------------------------------------------------------------------------------
# 1. The direction that was broken: a correct item is accepted
# --------------------------------------------------------------------------------------


def test_a_threshold_question_is_accepted_from_its_inequality():
    assert validate_authored_item(3, _item()).passed, _failures(_item())


def test_an_at_most_question_reads_the_other_boundary():
    """`<=` puts the finite endpoint on the right, and the answer is the largest value."""
    item = _item(
        stem=(
            "A club charges a $20 joining fee and $5 for each sticker pack. A student has "
            "$70 to spend. What is the greatest number of packs the student can buy?"
        ),
        option_a="10 packs",
        option_b="9 packs",
        option_c="11 packs",
        option_d="14 packs",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Subtract the fee, then divide by the price of a pack.",
                    expression="5*x + 20 <= 70",
                    common_mistake=None,
                )
            ],
            final_answer="10 packs",
        ),
        equation="5*x + 20 <= 70",
    )
    assert validate_authored_item(3, item).passed, _failures(item)


def test_a_bare_polynomial_is_read_as_solve_when_nothing_else_fits():
    """The other ambiguous form: no relation, but the stem asks for the roots."""
    item = _item(
        stem=(
            "A water balloon is launched from a platform. Its height in metres is "
            "h = -2t^2 + 10t - 12, where t is the time in seconds. At what two times is "
            "the balloon at ground level?"
        ),
        option_a="2 seconds and 3 seconds",
        option_b="1 second and 6 seconds",
        option_c="2 seconds only",
        option_d="5 seconds",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Set the height to zero and factorise.",
                    expression="-2*t**2 + 10*t - 12 = 0",
                    common_mistake=None,
                )
            ],
            final_answer="2 seconds and 3 seconds",
        ),
        misconception_tags=["sign_error"],
        equation="-2*t**2 + 10*t - 12",
    )
    assert validate_authored_item(3, item).passed, _failures(item)


# --------------------------------------------------------------------------------------
# 2. The direction that matters: wrong answers are still rejected
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("correct_option", "why"),
    [
        ("b", "6 months - one month short of the goal"),
        ("c", "8 months - the off-by-one these items are built to catch"),
        ("d", "42 months - forgot to divide by the monthly rate"),
    ],
)
def test_the_boundary_reading_never_accepts_a_distractor(correct_option, why):
    """The whole risk of a second reading is that it says yes to more things.

    Each of these is one plausible slip away from the real answer, and the second reading
    derives 7 - so declaring any of them correct must still fail.
    """
    failures = _failures(_item(correct_option=correct_option))
    assert failures, f"declaring {why} correct was accepted"
    assert any("does not match" in f for f in failures), failures


def test_a_strict_inequality_declines_rather_than_guessing_an_off_by_one():
    """`m > 7` does not admit 7, and its smallest whole value is 8 - so the gate says
    nothing rather than picking one. Guessing here would accept an off-by-one, which is
    exactly the distractor in these items."""
    failures = _failures(_item(equation="6*m > 42"))
    assert failures
    assert any("does not match" in f for f in failures), failures


def test_an_unbounded_solution_set_yields_no_value():
    """`m >= 0` for a quantity that is never negative has a boundary, but `-oo` is not a
    number a student writes - the infinite side must never become an answer."""
    failures = _failures(_item(equation="-6*m <= 42"))
    assert failures, "an interval whose only finite boundary is the wrong side passed"


def test_an_expression_that_solves_to_nothing_stays_rejected():
    failures = _failures(_item(equation="2*m + 1"))
    assert failures


# --------------------------------------------------------------------------------------
# 3. The second reading must not disturb what already worked
# --------------------------------------------------------------------------------------


def test_an_item_whose_first_reading_matches_is_untouched():
    """A plain equation still routes to `value` and passes exactly as before."""
    item = _item(
        stem="A number multiplied by 6 and increased by 12 gives 54. What is the number?",
        option_a="7",
        option_b="6",
        option_c="8",
        option_d="42",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Subtract 12, then divide by 6.",
                    expression="Eq(6*n + 12, 54)",
                    common_mistake=None,
                )
            ],
            final_answer="7",
        ),
        equation="Eq(6*n + 12, 54)",
    )
    assert validate_authored_item(3, item).passed, _failures(item)


def test_an_item_asking_for_the_set_itself_still_passes_on_the_first_reading():
    """The reading that was always supported. It must not be traded away for the new one -
    the second reading exists because *both* questions are askable, not to replace one."""
    item = _item(
        stem="Solve for m: 12 + 6m is at least 54. Which describes all the values of m?",
        option_a="m >= 7",
        option_b="m <= 7",
        option_c="m > 7",
        option_d="m >= 42",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Subtract 12 from both sides, then divide by 6.",
                    expression="12 + 6*m >= 54",
                    common_mistake=None,
                )
            ],
            final_answer="m >= 7",
        ),
        equation="12 + 6*m >= 54",
    )
    assert validate_authored_item(3, item).passed, _failures(item)


def test_an_ambiguous_item_matching_two_options_is_still_rejected():
    """Two options stating the boundary is ambiguity, not a reason to pick the declared
    one - the second reading has to clear the same uniqueness bar as the first."""
    failures = _failures(_item(option_b="7 months"))
    assert failures


# --------------------------------------------------------------------------------------
# 5. D-297: the gate demanded a notation it could not read
# --------------------------------------------------------------------------------------


def _symbolic_item(**overrides) -> AuthoredGeneratedItemResponse:
    """A factoring item whose options carry powers as superscripts, which is what D-288's
    readability check requires of every student-facing field."""
    base = dict(
        stem=(
            "A designer models a panel's area with the expression x cubed plus two x "
            "squared plus three x plus six. Which factored form is equivalent?"
        ),
        option_a="(x² + 2)(x + 3)",
        option_b="(x + 1)(x² + 6)",
        option_c="(x + 2)(x² + 3)",
        option_d="(x + 6)(x² + 1)",
        correct_option="c",
        hint_ladder=[
            "Group the first two terms and the last two terms.",
            "Take the common factor out of each group.",
            "The two groups should leave the same bracket behind.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Group the terms in pairs, then factor each pair.",
                    expression="x**3 + 2*x**2 + 3*x + 6",
                    common_mistake=None,
                )
            ],
            final_answer="(x + 2)(x² + 3)",
        ),
        estimated_time_seconds=90,
        misconception_tags=["mismatched_grouping"],
        proposed_difficulty=3,
        difficulty_rationale="grouping and a common factor",
        required_prerequisites=["factoring by grouping"],
        equation="x**3 + 2*x**2 + 3*x + 6",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def test_a_superscript_power_in_a_symbolic_option_is_read_as_a_power():
    """D-288 tells the generator to write `x²` and refuses `x**2`; the symbolic arm then
    could not parse `x²` at all, so it rejected the item and blamed the answer key. Measured
    over stored rejections: 8 of 38 recovered, and the ambiguous ones stayed rejected.
    """
    assert validate_authored_item(3, _symbolic_item()).passed, _failures(_symbolic_item())


def test_a_wrong_symbolic_key_written_with_superscripts_is_still_rejected():
    """The precision half. Reading the notation must not make a wrong key acceptable."""
    failures = _failures(_symbolic_item(correct_option="b"))
    assert failures
    assert any("does not match" in f for f in failures), failures


def test_two_options_equal_under_the_superscript_reading_are_still_ambiguous():
    """The six items this reading turns from "the key is wrong" into "two options match"
    must stay rejected - what improves is the reason, not the verdict. `x(x² + 2x + 3) + 6`
    is the same polynomial as `(x + 2)(x² + 3)`, so an item offering both is ambiguous.
    """
    failures = _failures(_symbolic_item(option_a="x(x² + 2x + 3) + 6"))
    assert failures
    assert any("more than one option" in f for f in failures), failures


def test_a_partially_factored_distractor_does_not_make_a_shipped_item_ambiguous():
    """The regression the first version of D-297 caused, pinned so it cannot come back.

    `alg2_polynomial_factor` asks for a *complete* factorisation, so its best distractor is
    an incomplete one - and `3x(x² + 4x + 3)` is algebraically **equal** to
    `3x(x + 1)(x + 3)`. The stem's word "completely" is what separates them and no
    equivalence check can see a word. Applying the superscript reading unconditionally gave
    two shipped, correct items a second matching option and the bank's own loader began
    refusing them; scoping it to the D-281 seam (consulted only when the first reading
    matched nothing) leaves them alone, because their first reading already matches exactly
    one option.
    """
    item = _symbolic_item(
        equation="3*x**3 + 12*x**2 + 9*x",
        option_a="3x(x² + 4x + 3)",
        option_b="3x(x + 1)(x + 3)",
        option_c="x(x + 1)(x + 3)",
        option_d="3x(x + 2)(x + 2)",
        correct_option="b",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Take out the common factor, then factor what is left.",
                    expression="3*x**3 + 12*x**2 + 9*x",
                    common_mistake=None,
                )
            ],
            final_answer="3x(x + 1)(x + 3)",
        ),
    )
    assert validate_authored_item(3, item).passed, _failures(item)


# --------------------------------------------------------------------------------------
# 6. D-298: the same contradiction on the value arm, and this one failed silently
# --------------------------------------------------------------------------------------


def _surd_item(**overrides) -> AuthoredGeneratedItemResponse:
    base = dict(
        stem=(
            "A square patio covers 98 square feet. Written in simplest radical form, how "
            "long is each side in feet?"
        ),
        option_a="49√2",
        option_b="7√2",
        option_c="14√2",
        option_d="9 feet",
        correct_option="b",
        hint_ladder=[
            "The side length is the square root of the area.",
            "Look for a perfect square that divides 98.",
            "98 is 49 times 2, and 49 is a perfect square.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Split the area into a perfect square times what is left.",
                    expression="x = sqrt(98)",
                    common_mistake=None,
                )
            ],
            final_answer="7√2",
        ),
        estimated_time_seconds=70,
        misconception_tags=["kept_the_perfect_square_inside"],
        proposed_difficulty=3,
        difficulty_rationale="simplifying a surd into a coefficient and a radical",
        required_prerequisites=["perfect squares"],
        equation="Eq(x, sqrt(98))",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def test_a_coefficient_in_front_of_a_radical_is_read_as_multiplication():
    """`7√2` is how anyone writes a surd, and D-288's readability check asks for exactly
    that. `sympy.sympify` cannot do the implicit multiplication, so `alg2_irrational` took
    0 of 2 and the rejection blamed an answer key that was right.
    """
    assert validate_authored_item(3, _surd_item()).passed, _failures(_surd_item())


def test_a_radical_option_parses_as_a_number_and_not_as_a_symbol():
    """The reason D-298 was worse than D-297: it failed *silently*.

    `sympy.sympify('√2')` returns `Symbol('√2')` - not a number, never equal to one, and it
    raises nothing. A first attempt at this fix only inserted the missing `*`, on the
    strength of `_sympify('√2')` printing `√2`, which is SymPy pretty-printing that symbol.
    So the transform has to produce `sqrt(...)`, and this pins it.
    """
    parsed = sympy.sympify(_student_notation("7√2"))
    assert parsed.is_number, f"{parsed!r} is not a number"
    assert parsed == 7 * sympy.sqrt(2)


def test_an_unsimplified_radical_equal_to_the_answer_is_ambiguous_not_wrong():
    """`4√8` and `8√2` are the same number, so an item offering both cannot be graded - the
    stem's "simplest radical form" is what separates them and no value check sees a phrase.
    The third skill with this shape, after `alg2_polynomial_factor` (D-297) and
    `g6_fractions` (lowest terms). It stays rejected; the reason becomes true.
    """
    item = _surd_item(
        equation="Eq(x, sqrt(128))",
        option_a="64√2",
        option_b="8√2",
        option_c="16√2",
        option_d="4√8",
        correct_option="b",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Split the area into a perfect square times what is left.",
                    expression="x = sqrt(128)",
                    common_mistake=None,
                )
            ],
            final_answer="8√2",
        ),
    )
    failures = _failures(item)
    assert failures
    assert any("more than one option" in f for f in failures), failures


def test_a_wrong_surd_is_still_rejected():
    """The precision half: reading the notation must not make a wrong key acceptable."""
    failures = _failures(_surd_item(correct_option="c"))
    assert failures
    assert any("does not match" in f for f in failures), failures


def test_two_options_stating_the_answer_under_the_FIRST_reading_are_rejected():
    """The exactly-one bar on the *first* reading, which had no test at all (found D-299).

    Every existing ambiguity test here reaches `len(matches) > 1` through a *second* reading
    - the boundary, the prose interval, the student notation. So a change that truncated the
    first reading's match list to one entry passed the entire suite while letting a genuinely
    ungradeable item through. Discovered by deliberately breaking `matching_options` after
    extracting it, which is the only reason it is covered now.
    """
    item = _item(
        stem=(
            "A shop sells notebooks in packs of 6. A teacher buys 7 packs for her class. "
            "How many notebooks does she have in total?"
        ),
        equation="Eq(x, 6 * 7)",
        option_a="42 notebooks",
        option_b="42.0 notebooks",
        option_c="13 notebooks",
        option_d="36 notebooks",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Multiply the number of packs by the pack size.",
                    expression="x = 6 * 7",
                    common_mistake=None,
                )
            ],
            final_answer="42 notebooks",
        ),
    )
    failures = _failures(item)
    assert failures, "two options stating 42 must not be gradeable"
    assert any("more than one option" in f for f in failures), failures


# --------------------------------------------------------------------------------------
# 7. D-303: what counts as one sentence, for the readability ceiling
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected", "why"),
    [
        ("A cat sat. A dog ran.", 2, "the ordinary case"),
        ("The recipe needs 2.5 cups of flour today.", 1, "a decimal is not a sentence end"),
        ("She paid $3.50 for 1.5 kg of apples.", 1, "two decimals, still one sentence"),
        ('3 say "Try Again." What is the probability?', 2, "the period sits inside the quote"),
        ("then p(c) = 0.\n\nAn engineer models it.", 2, "a sentence may end in a digit"),
        ("Divide 756 by 6. The answer is 126.", 2, "so may both of them"),
        ("Is it 4? Yes! Done.", 3, "? and ! end sentences too"),
    ],
)
def test_the_readability_ceiling_agrees_about_what_a_sentence_is(text, expected, why):
    """Every one of these was wrong in some draft of `_sentences`, which is why they are here.

    The shipped version before D-303 was `re.split(r"[.!?]", text)` and split decimals, so a
    long sentence became short fragments and cleared the 30-word ceiling. My first replacement
    required whitespace after the period and so read `say "Try Again." What is...` as one
    48-word sentence; my second added a no-digit-before rule and so refused to end a sentence
    at `= 0.`, which is how half of a mathematics explanation ends.
    """
    assert len(av._sentences(text)) == expected, why


def test_a_long_sentence_full_of_decimals_no_longer_clears_the_ceiling():
    """The hole D-303 closed, as the sentence that demonstrated it.

    33 words carrying six decimals. The old splitter saw seven fragments of 4-6 words and
    passed it; spelled out without decimals the same sentence was rejected at 51 words, which
    is the inconsistency that made this a defect rather than a preference.

    Measured before fixing: **0 of 9,552** bank sentences actually exploited it, so this
    protects future content rather than repairing existing content.
    """
    padded = (
        "The recipe needs 2.5 cups of flour and 3.5 cups of sugar and 1.5 spoons of salt "
        "and 4.5 grams of yeast and 6.5 millilitres of water and 7.5 pinches of pepper today"
    )
    assert len(padded.split()) > 30
    assert len(av._sentences(padded)) == 1, "one sentence, however many decimals it carries"


def test_the_gate_itself_applies_the_corrected_sentence_rule():
    """The wiring, not just the helper - and the reason this test exists is a near miss.

    The parametrised cases above call `_sentences` directly, so they pass whether or not
    `check_age_appropriate_wording` actually uses it: reverting the call site to
    `re.split(r"[.!?]", text)` left all of them green. A rule nothing routes through is not
    enforced, which is the same lesson `matching_options` taught in D-299.
    """
    long_decimal_sentence = (
        "A baker measures 2.5 cups of flour and 3.5 cups of sugar and 1.5 spoons of salt "
        "and 4.5 grams of yeast and 6.5 millilitres of water and 7.5 pinches of pepper, "
        "so how many months of savings are needed?"
    )
    assert len(long_decimal_sentence.split()) > 30
    failures = _failures(_item(stem=long_decimal_sentence))
    assert any("readability ceiling" in f for f in failures), failures


# --------------------------------------------------------------------------------------
# 7. D-309: the same contradiction a third time, on the exponential family, and this one
#    shut a skill out completely - `calc_differential_equations` held 0 items and every
#    answer it can have is `Ce^(kt)`.
#
#        check_math_notation_is_readable  rejects any option containing `*`   (D-288)
#        the answer comparison            parses `3*exp(4*t)`, raises on `3e^(4t)`
#
#    so no exponential answer could pass both rules. The caret was never the problem -
#    `sympify` converts `^` to `**` already, which is why `x^2 - 9` has always matched - and
#    the `e` is: `3e**(4t)` parses as `3*e**(4*t)` with `e` a free Symbol, so it never raises
#    and never matches. D-298's silent trap in a third costume.
# --------------------------------------------------------------------------------------


def _exponential_item(**overrides) -> AuthoredGeneratedItemResponse:
    base = dict(
        stem=(
            "A culture grows so that its rate of change is four times its current size, and "
            "it starts at 3 grams. Which function gives its size after t hours?"
        ),
        option_a="3e^(4t)",
        option_b="4e^(3t)",
        option_c="3e^(t/4)",
        option_d="12e^t",
        correct_option="a",
        hint_ladder=[
            "A rate of change proportional to the amount is exponential growth.",
            "The constant of proportionality becomes the coefficient of t in the exponent.",
            "The starting amount is the coefficient in front.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Separate the variables and integrate both sides.",
                    expression="dy/dt = 4y",
                    common_mistake=None,
                )
            ],
            final_answer="3e^(4t)",
        ),
        estimated_time_seconds=110,
        misconception_tags=["swapped_the_coefficient_and_the_rate"],
        proposed_difficulty=4,
        difficulty_rationale="separating variables and applying the initial condition",
        required_prerequisites=["integrating an exponential"],
        equation="3*exp(4*t)",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def test_an_exponential_written_the_way_a_student_reads_it_is_accepted():
    """The whole point: the notation D-288 *requires* now matches, where it previously did not
    and the rejection blamed a correct answer key."""
    item = _exponential_item()
    assert validate_authored_item(4, item).passed, _failures(item)


def test_the_same_answer_written_for_sympy_is_rejected_by_the_readability_rule():
    """The other half of the contradiction, asserted so nobody 'fixes' this by telling the
    generator to write stars. `3*exp(4*t)` matches the equation and D-288 refuses it."""
    failures = _failures(_exponential_item(option_a="3*exp(4*t)"))
    assert any("programmer notation" in f for f in failures), failures


@pytest.mark.parametrize(
    "wrong",
    ["4e^(4t)", "3e^(5t)", "3e^(-4t)", "12e^(4t)", "3e^(4t) + 1", "e^(4t)"],
)
def test_a_wrong_exponential_is_still_rejected(wrong):
    """The direction that matters. Reading a notation must not turn into accepting anything
    shaped like it - D-246's lesson, and D-298's fix needed exactly this control to catch a
    version that only inserted a star."""
    item = _exponential_item(option_a=wrong)
    assert not validate_authored_item(4, item).passed, wrong


def test_the_caret_was_never_the_missing_piece():
    """Recorded because I nearly fixed the wrong half. `sympify` already converts `^` to `**`,
    so a caret power has matched since long before this - and a caret-ONLY pattern matched
    nothing on the symbolic arm, because `_normalize_math_text` rewrites `^` to `**` before the
    student reading runs. The pattern accepts both forms for that reason."""
    derivation = av.route_answer("(x - 3)*(x + 3)")[0]
    assert derivation is not None
    assert av._option_matches(derivation, "x^2 - 9")
    exponential = av.route_answer("3*exp(4*t)")[0]
    assert exponential is not None
    for written in ("3e^(4t)", "3e**(4t)", "3e^(4*t)"):
        assert av._option_matches(exponential, written, student_notation=True), written
        assert not av._option_matches(exponential, written), written


def test_an_identifier_containing_an_e_is_not_read_as_an_exponential():
    """`time**2` and `degrees**2` must survive the reading untouched, or a units-carrying
    option would silently become an exponential."""
    for text in ("time^2", "the^2", "degrees^2", "1e5"):
        assert "exp(" not in av._student_notation(av._normalize_math_text(text)), text
