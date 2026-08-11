"""A comma in an answer used to crash the gate rather than decide it (D-274).

Found by probing the Phase-R router against the forms the 3-5 wave needs, before authoring
any of it. `sympy.sympify('4,700')` returns the plain Python tuple `(4, 700)` - it neither
raises nor returns a `Basic` - so `_values_equal` called `.equals` on a tuple and every caller
died with `AttributeError` instead of returning a verdict. Two consequences, both tested here:

1. **The gate crashed** on an option written the way a grade-4 answer is naturally written.
   K-2 never reached four digits in an option, which is why the first three waves' worth of
   tests never touched it.
2. **The gate was order-dependent.** `answers_agree('4,700', '4700')` raised while the same
   pair reversed returned False - so which of the two solvers happened to be the first
   argument decided whether the run survived.

Both directions, per D-246: a separator-aware comparison that only ever says True is not a
fix, it is a hole. Free: pure SymPy, no model call, no database.
"""

import pytest
from intellichoice_curriculum.authored_validation import (
    _option_as_tuple,
    _option_as_value_set,
    _option_matches,
    _sympify,
    answers_agree,
    route_answer,
)


# --------------------------------------------------------------------------------------
# The crash itself
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["4,700", "34,281", "1,234,567", "(1, 2)", "3 or 4"],
)
def test_sympify_never_returns_a_non_value(text):
    """The annotation says `Basic | None`; before D-274 it could also return a tuple.

    This is the fix that makes every caller total. Whether the text *should* parse is the
    next test's question - this one only asserts nothing escapes as a non-value.
    """
    parsed = _sympify(text)
    assert parsed is None or hasattr(parsed, "equals")


@pytest.mark.parametrize(
    ("left", "right"),
    [("4,700", "4700"), ("4700", "4,700"), ("34,281", "34281"), ("1,234", "1234")],
)
def test_answers_agree_is_symmetric_across_a_separator(left, right):
    """The order-dependence is the reason this is a correctness bug and not cosmetics."""
    assert answers_agree(left, right) is True
    assert answers_agree(right, left) is True


@pytest.mark.parametrize(
    ("left", "right"),
    [("4,700", "4800"), ("34,281", "34,218"), ("1,234", "1,243")],
)
def test_a_separator_does_not_make_two_different_numbers_agree(left, right):
    """The other direction. Stripping formatting must not stop the comparison happening."""
    assert answers_agree(left, right) is False
    assert answers_agree(right, left) is False


# --------------------------------------------------------------------------------------
# Equations are a different language and must not be touched
# --------------------------------------------------------------------------------------


def test_an_equations_argument_commas_are_never_stripped():
    """The trap this fix had to avoid.

    In answer text a comma is formatting; in an equation it separates arguments. Stripping
    it there would rewrite `Max(340,218)` - a comparison of two numbers - into the single
    number 340218, silently changing the question the item asks. Written tight and spaced,
    both must still derive 340.
    """
    for equation in ("Eq(x, Max(340, 218))", "Eq(x, Max(340,218))"):
        derivation, error = route_answer(equation)
        assert derivation is not None, error
        assert derivation.payload == (340,)


# --------------------------------------------------------------------------------------
# Option matching, both directions
# --------------------------------------------------------------------------------------


def test_a_grouped_option_matches_the_derived_answer():
    derivation, error = route_answer("Eq(x, Max(34281, 34218, 34128))")
    assert derivation is not None, error
    assert _option_matches(derivation, "34,281") is True
    assert _option_matches(derivation, "34281") is True


@pytest.mark.parametrize("wrong", ["34,218", "34,128", "34,28", "3,4281"])
def test_a_grouped_distractor_is_still_rejected(wrong):
    """A separator must not turn a near-miss into a match - the D-246 direction."""
    derivation, error = route_answer("Eq(x, Max(34281, 34218, 34128))")
    assert derivation is not None, error
    assert _option_matches(derivation, wrong) is False


# --------------------------------------------------------------------------------------
# The overloaded comma: sets and tuples split on it, so the strip must precede the split
# --------------------------------------------------------------------------------------


def test_a_multi_root_answer_with_separators_stays_two_roots():
    assert _option_as_value_set("1,200 or -1,200") == frozenset(
        _option_as_value_set("1200 or -1200")
    )


@pytest.mark.parametrize(
    ("text", "expected_size"),
    [("3, -3", 2), ("100, 200", 2), ("3 or -3", 2), ("1,200 or -1,200", 2)],
)
def test_separator_stripping_does_not_merge_a_root_set(text, expected_size):
    stated = _option_as_value_set(text)
    assert stated is not None
    assert len(stated) == expected_size


def test_a_tuple_option_with_a_separator_keeps_its_component_count():
    assert _option_as_tuple("(1,200, 3)") == _option_as_tuple("(1200, 3)")
    assert _option_as_tuple("(2, 3)") is not None
    assert len(_option_as_tuple("(1,200, 3)") or ()) == 2


def test_the_ambiguous_tight_pair_fails_toward_rejection():
    """`'100,200'` is a thousands separator and a two-root set in the same six characters.

    No rule separates them, so this pins which way the ambiguity resolves and *why that is
    the acceptable direction*: it reads as one number, so a genuine two-root item written
    this way fails its gate and reaches a human as a review finding. The opposite default
    would let a one-number answer satisfy a two-root question silently.
    """
    stated = _option_as_value_set("100,200")
    assert stated is not None
    assert len(stated) == 1
