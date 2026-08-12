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
from intellichoice_curriculum.authored_validation import validate_authored_item
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
