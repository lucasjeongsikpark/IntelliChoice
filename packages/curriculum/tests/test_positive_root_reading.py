"""The positive-root second reading (C1 Phase 3), scored in both directions.

**What this exists for, measured.** The Phase 3 serving-floor batch opened on `algebra_1`
difficulty 1 and took **0 of 3**, all three identical:

    stem     "A square garden has an area of 64 square metres. What is the side length?"
    equation "Eq(x**2, 64)"
    answer   "8 metres"

`route_answer` reads that as the `multi_root` model and derives `{8, -8}`, then compares a
solution *set* against the value a student writes. Exactly D-281's interval defect in a
second answer model. `alg1_square_roots` had never produced an accepted tier-1 item, and
difficulty 1 is the tier that kept the whole `algebra_1` topic under the serving floor.

**Why this is not a loosening**, and the tests below are ordered by which claim they defend:

- it runs only when the first reading matched nothing, and must match exactly one option -
  the same bar the first reading clears;
- exactly one root must be positive, so a genuine two-solution quadratic declines;
- **no option may match a non-positive root.** An abstract "solve x**2 = 81" offers -9 as a
  distractor *because* ±9 is its honest answer, and there "9" alone is a wrong key. A
  measurement item never offers "-9 metres". The item's own options carry the domain
  constraint, so nothing is asked of a model and no stem text is parsed for units.

Measured over the stored rejections: 4 recovered, 6 declined, **3 of those declines are the
option guard alone**, 0 items rejected for other reasons become acceptable.

Free: pure SymPy, no model call, no database.
"""

from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)


def _item(**overrides) -> AuthoredGeneratedItemResponse:
    base = dict(
        stem=(
            "A square garden has an area of 64 square metres. What is the side length of "
            "the garden?"
        ),
        option_a="8 metres",
        option_b="16 metres",
        option_c="32 metres",
        option_d="4 metres",
        correct_option="a",
        hint_ladder=[
            "The area of a square is its side length times itself.",
            "Ask which number multiplied by itself gives the area.",
            "A side length is a distance, so it is a positive number.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="A square's area is the side times itself, so take the "
                    "square root of the area.",
                    expression="x**2 = 64",
                    common_mistake=None,
                )
            ],
            final_answer="8 metres",
        ),
        estimated_time_seconds=60,
        misconception_tags=["confuses_area_and_side"],
        proposed_difficulty=1,
        difficulty_rationale="one square root of a perfect square",
        required_prerequisites=["perfect squares"],
        equation="Eq(x**2, 64)",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def _failures(item: AuthoredGeneratedItemResponse) -> list[str]:
    return validate_authored_item(1, item).failures


# --------------------------------------------------------------------------------------
# 1. The direction that was broken: a measured quantity is accepted
# --------------------------------------------------------------------------------------


def test_a_square_side_is_accepted_from_its_area_equation():
    item = _item()
    assert validate_authored_item(1, item).passed, _failures(item)


def test_the_bare_form_of_the_same_equation_is_accepted_too():
    """The generator writes `x**2 = 64` as often as `Eq(x**2, 64)`; both route the same."""
    item = _item(equation="x**2 = 64")
    assert validate_authored_item(1, item).passed, _failures(item)


# --------------------------------------------------------------------------------------
# 2. The precision side: the option guard, which is what makes the rule safe
# --------------------------------------------------------------------------------------


def test_an_abstract_equation_offering_the_negative_root_stays_rejected():
    """`solve x**2 = 64` with -8 among the options: the answer is BOTH roots.

    This is the case the whole guard exists for. Nothing about the equation distinguishes
    it from the garden above - only the options do, and offering -8 as a choice is the
    item saying that the negative root is in play.
    """
    item = _item(
        stem="Solve for x: x squared equals 64.",
        option_a="8",
        option_b="-8",
        option_c="8 and -8",
        option_d="4096",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Take the square root of both sides.",
                    expression="x**2 = 64",
                    common_mistake=None,
                )
            ],
            final_answer="8",
        ),
    )
    assert not validate_authored_item(1, item).passed


def test_a_quadratic_with_two_positive_roots_declines_rather_than_picking_one():
    item = _item(
        stem="A rectangle's length is 9 metres more than nothing and its area factors to "
        "zero at two widths. Which width is a solution?",
        option_a="4 metres",
        option_b="6 metres",
        option_c="9 metres",
        option_d="20 metres",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Factor the quadratic and read its roots.",
                    expression="x**2 - 9*x + 20 = 0",
                    common_mistake=None,
                )
            ],
            final_answer="4 metres",
        ),
        equation="Eq(x**2 - 9*x + 20, 0)",
    )
    assert not validate_authored_item(1, item).passed


def test_a_wrong_key_is_still_rejected_when_the_reading_applies():
    """The reading recovers the *item*, never the *key*: 8 is the side, 16 is not."""
    item = _item(correct_option="b")
    assert not validate_authored_item(1, item).passed


def test_the_squared_distractor_is_not_accepted_as_the_side():
    """64 itself among the options must not match the derived root."""
    item = _item(option_b="64 metres", correct_option="b")
    assert not validate_authored_item(1, item).passed


# --------------------------------------------------------------------------------------
# 3. It must not touch what already worked
# --------------------------------------------------------------------------------------


def test_an_item_whose_first_reading_matches_is_untouched():
    """Options naming both roots: the multi_root reading matches, so no second reading runs."""
    item = _item(
        stem="Solve for x: x squared equals 64.",
        option_a="8 and -8",
        option_b="8",
        option_c="-8",
        option_d="16",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Take the square root of both sides, keeping both signs.",
                    expression="x**2 = 64",
                    common_mistake=None,
                )
            ],
            final_answer="8 and -8",
        ),
    )
    assert validate_authored_item(1, item).passed, _failures(item)


def test_a_linear_equation_is_unaffected():
    item = _item(
        stem="A number multiplied by 4 gives 32. What is the number?",
        option_a="8",
        option_b="4",
        option_c="32",
        option_d="128",
        correct_option="a",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Divide both sides by 4.",
                    expression="4*x = 32",
                    common_mistake=None,
                )
            ],
            final_answer="8",
        ),
        equation="Eq(4*x, 32)",
    )
    assert validate_authored_item(1, item).passed, _failures(item)
