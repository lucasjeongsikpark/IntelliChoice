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
