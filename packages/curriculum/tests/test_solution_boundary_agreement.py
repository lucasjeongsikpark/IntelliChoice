"""`canonical_solution.final_answer` against a threshold option (D-293), both directions.

**Measured.** In one C1 Phase 3 depth run, six candidates died with:

    canonical_solution.final_answer 'x >= 10' does not match the declared correct
    option 'at least 10 boxes'

Every one an inequality skill. D-281 taught `check_sympy_independent_solve` that a solution
set and the boundary a student writes are both honest readings of one verified inequality;
`check_hint_solution_answer_agreement` does its own comparison and never learned it, so an
item that now clears the equation check is rejected by the solution-text check instead.

**The restraint is D-281's, unchanged**: only a closed boundary yields a value, and the
boundary is compared by value - so `x > 10` still fails and the off-by-one distractor these
items carry ("11 boxes") is still rejected. The fix is in the check rather than in
`answers_agree`, because that helper is shared with the serving path.

Free: pure SymPy, no model call, no database.
"""

from intellichoice_curriculum.authored_validation import (
    AuthoredValidationResult,
    check_hint_solution_answer_agreement,
)
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)


def _item(
    *, final_answer: str, correct: str = "at least 10 boxes"
) -> AuthoredGeneratedItemResponse:
    return AuthoredGeneratedItemResponse(
        stem=(
            "A shop packs 12 pens per box and needs at least 120 pens for an order. What is "
            "the smallest number of boxes the shop must pack?"
        ),
        option_a=correct,
        option_b="at least 11 boxes",
        option_c="at least 9 boxes",
        option_d="at least 120 boxes",
        correct_option="a",
        hint_ladder=[
            "Work out how many pens one box holds.",
            "Compare that with the number the order needs.",
            "Divide the order size by the box size.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Divide the pens needed by the pens per box.",
                    expression="12*b >= 120",
                    common_mistake=None,
                )
            ],
            final_answer=final_answer,
        ),
        estimated_time_seconds=60,
        misconception_tags=["off_by_one"],
        proposed_difficulty=3,
        difficulty_rationale="one inequality and a division",
        required_prerequisites=["dividing whole numbers"],
        equation="12*b >= 120",
    )


def _failures(item: AuthoredGeneratedItemResponse) -> list[str]:
    result = AuthoredValidationResult()
    check_hint_solution_answer_agreement(item, result)
    return result.failures


# --------------------------------------------------------------------------------------
# 1. The direction that was broken
# --------------------------------------------------------------------------------------


def test_a_closed_inequality_agrees_with_the_boundary_the_option_states():
    assert _failures(_item(final_answer="x >= 10")) == []


def test_the_other_boundary_direction_agrees_with_its_own_prose():
    assert _failures(_item(final_answer="x <= 10", correct="at most 10 boxes")) == []


def test_the_two_directions_are_not_interchangeable():
    """Written as a recall test first, and it was wrong: `x <= 10` must NOT agree with
    "at least 10". The prose reading distinguishes the directions, which is the property
    that makes admitting prose safe at all."""
    assert _failures(_item(final_answer="x <= 10", correct="at least 10 boxes")) != []


def test_the_boundary_value_agrees_with_a_plain_option():
    """The other option shape in the real rejections: `'x <= 10'` against `'10 movies'`.

    Here the solution *set* cannot match the option at all - only the boundary value can,
    which is the reading D-281 added and this check did not have.
    """
    assert _failures(_item(final_answer="x <= 10", correct="10 boxes")) == []


def test_a_plain_answer_still_agrees():
    """The path that always worked must not be disturbed."""
    assert _failures(_item(final_answer="10 boxes", correct="10 boxes")) == []


# --------------------------------------------------------------------------------------
# 2. The precision side
# --------------------------------------------------------------------------------------


def test_an_open_boundary_is_still_refused():
    """`x > 10` admits 11, not 10 - D-281's rule, and the off-by-one is what these items test."""
    assert _failures(_item(final_answer="x > 10")) != []


def test_the_wrong_boundary_is_still_refused():
    assert _failures(_item(final_answer="x >= 11")) != []


def test_an_unrelated_answer_is_still_refused():
    assert _failures(_item(final_answer="120 pens")) != []


def test_the_wrong_strictness_is_still_refused():
    """`x > 10` and "at least 10" are different claims, and the prose reading knows it."""
    assert _failures(_item(final_answer="x > 10", correct="at least 10 boxes")) != []
