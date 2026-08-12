"""A solution set stated the way a child reads it (D-282), scored in both directions.

`_option_as_solution_set` needed a `<` or `>` before it would read anything, so the gate
could check `'x > 10'` and not `'more than 10 hours'`. An item whose options were written in
the age-appropriate language SPEC §5.10.3 asks for was rejected as **wrong**, not as
unreadable — so the gate was quietly paying the generator to write algebra at children.
Measured on the 6-12 wave: 6 correct items rejected for this alone.

The risk of reading English is reading it *backwards*, and one phrase makes that concrete:
"no more than 10" contains "more than 10". Getting that wrong would accept an item stating
exactly the opposite bound, which is worse than not reading the phrase at all — so the
ordering is pinned here rather than left to the arrangement of the table.

Free: pure SymPy, no model call, no database.
"""

import pytest
import sympy
from intellichoice_curriculum.authored_validation import (
    _option_as_solution_set,
    route_answer,
    validate_authored_item,
)
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)

N = sympy.Integer(10)


# --------------------------------------------------------------------------------------
# 1. Each phrase, and the boundary strictness it carries
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        ("more than 10 hours", sympy.Interval.open(N, sympy.oo)),
        ("greater than 10", sympy.Interval.open(N, sympy.oo)),
        ("over 10 days", sympy.Interval.open(N, sympy.oo)),
        ("fewer than 10 hours", sympy.Interval.open(-sympy.oo, N)),
        ("less than 10", sympy.Interval.open(-sympy.oo, N)),
        ("under 10 minutes", sympy.Interval.open(-sympy.oo, N)),
        ("at least 10 weeks", sympy.Interval(N, sympy.oo)),
        ("a minimum of 10 packs", sympy.Interval(N, sympy.oo)),
        ("at most 10 boxes", sympy.Interval(-sympy.oo, N)),
        ("up to 10 guests", sympy.Interval(-sympy.oo, N)),
        # Capitalisation is how these actually arrive: "More than 25 days".
        ("More Than 10 Hours", sympy.Interval.open(N, sympy.oo)),
    ],
)
def test_a_phrase_reads_as_its_solution_set(option, expected):
    assert _option_as_solution_set(option) == expected


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        ("no more than 10 hours", sympy.Interval(-sympy.oo, N)),
        ("no fewer than 10 hours", sympy.Interval(N, sympy.oo)),
        ("no less than 10", sympy.Interval(N, sympy.oo)),
        ("no greater than 10", sympy.Interval(-sympy.oo, N)),
    ],
)
def test_a_negated_phrase_is_not_read_as_the_phrase_it_contains(option, expected):
    """The failure this pins: "no more than 10" contains "more than 10", and reading it as
    the latter would accept an item stating the exact opposite bound."""
    assert _option_as_solution_set(option) == expected


def test_strict_and_inclusive_bounds_stay_distinct():
    """The commonest real mistake in inequality work. A gate that blurred it would be worse
    than no gate, so "more than 10" must never equal "at least 10"."""
    assert _option_as_solution_set("more than 10") != _option_as_solution_set("at least 10")
    assert _option_as_solution_set("fewer than 10") != _option_as_solution_set("at most 10")


# --------------------------------------------------------------------------------------
# 2. What is deliberately not read
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "option",
    [
        "between 5 and 10 hours",  # two numbers: which bound is which is not recoverable
        "more than a few hours",  # no number at all
        "10 hours",  # a value, not a set - must stay the `value` model's business
        "the battery lasts a long time",
        "",
    ],
)
def test_an_unreadable_option_returns_none_rather_than_guessing(option):
    assert _option_as_solution_set(option) is None


def test_mathematics_is_never_reinterpreted_as_english():
    """`'x > 10'` parses symbolically and must keep doing so - the prose reading is only
    reached when there is no relational operator at all, so nothing that works today can
    change meaning (the ordering rule D-280 and D-191 both follow)."""
    assert _option_as_solution_set("x > 10") == sympy.Interval.open(N, sympy.oo)
    assert _option_as_solution_set("x >= 10 weeks") == sympy.Interval(N, sympy.oo)


# --------------------------------------------------------------------------------------
# 3. Through the gate, both directions
# --------------------------------------------------------------------------------------


def _item(**overrides) -> AuthoredGeneratedItemResponse:
    base = dict(
        stem=(
            "A phone battery starts at 50% and drops 3% each hour. For how long does the "
            "battery stay above 20%?"
        ),
        option_a="fewer than 10 hours",
        option_b="more than 10 hours",
        option_c="fewer than 15 hours",
        option_d="at most 10 hours",
        correct_option="a",
        hint_ladder=[
            "Start from the charge it begins with.",
            "Work out how much it may drop in total.",
            "Divide that by the hourly rate.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Subtract the floor, then divide by the hourly drop.",
                    expression="50 - 3*h > 20",
                    common_mistake=None,
                )
            ],
            final_answer="fewer than 10 hours",
        ),
        estimated_time_seconds=60,
        misconception_tags=["strict_vs_inclusive"],
        proposed_difficulty=3,
        difficulty_rationale="an inequality with a rate",
        required_prerequisites=["dividing whole numbers"],
        equation="50 - 3*h > 20",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def test_the_equation_and_the_english_option_agree():
    derivation, error = route_answer("50 - 3*h > 20")
    assert derivation is not None, error
    assert derivation.payload == sympy.Interval.open(-sympy.oo, N)


def test_an_item_answered_in_a_childs_words_is_accepted():
    result = validate_authored_item(3, _item())
    assert result.passed, result.failures


@pytest.mark.parametrize(
    ("correct_option", "why"),
    [
        ("b", "'more than 10 hours' - the set inverted"),
        ("c", "'fewer than 15 hours' - the right shape, the wrong number"),
        ("d", "'at most 10 hours' - inclusive where the answer is strict"),
    ],
)
def test_the_wrong_set_is_still_rejected(correct_option, why):
    """Reading English must not mean accepting any English. Option (d) is the one that
    matters most: it differs from the answer only in whether the boundary is included."""
    result = validate_authored_item(3, _item(correct_option=correct_option))
    assert not result.passed, f"declaring {why} correct was accepted"
