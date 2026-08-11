"""The answer-model router, scored in both directions (D-273, C1 Phase R).

**Both directions, deliberately.** D-246 is the precedent: a hint-leak rule measured only on
items that should pass read as a perfect detector, and measuring the other direction showed it
was a coin-flip gate. A verifier that accepts the right answer proves nothing on its own - the
question is whether it *rejects* a wrong one. Every model below is tested with a correct option
and with a wrong option that is close enough to be tempting.

Free: pure SymPy, no model call, no database.
"""

import pytest
from intellichoice_curriculum.authored_validation import (
    DerivedAnswer,
    _option_matches,
    derive_answer,
    route_answer,
)


def _route(equation: str) -> DerivedAnswer:
    derivation, error = route_answer(equation)
    assert derivation is not None, f"{equation!r} was rejected: {error}"
    return derivation


# --------------------------------------------------------------------------------------
# Which model each form routes to
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("equation", "expected_model"),
    [
        ("Eq(3*x + 2, 11)", "value"),
        ("3*x + 2 = 11", "value"),
        # The form that makes comparison questions expressible. It is `value` because the
        # answer *is* a value - the point is that `Max` does the selecting, so the item
        # models "which is larger" without being reshaped into "how many more".
        ("Eq(x, Max(34, 43))", "value"),
        ("Eq(x, gcd(12, 18))", "value"),
        ("Eq(x**2, 9)", "multi_root"),
        ("x**2 = 9", "multi_root"),
        ("3*x + 2 > 11", "interval"),
        ("x >= 4", "interval"),
        ("Eq(x + y, 10); Eq(x - y, 2)", "tuple"),
        ("(x - 3)*(x + 3)", "symbolic"),
        ("2*x", "symbolic"),
    ],
)
def test_each_written_form_routes_to_its_answer_model(equation, expected_model):
    assert _route(equation).model == expected_model


@pytest.mark.parametrize(
    ("equation", "reason"),
    [
        # Hole 1 (D-273): passes `derive_answer` and verifies nothing.
        ("Eq(x, 43)", "states the answer"),
        ("43 = x", "states the answer"),
        ("Eq(4, 4)", "restates the answer"),
        ("43", "bare value"),
        # A system written as one equation cannot be solved for either unknown.
        ("Eq(x + y, 10)", "2 unknowns"),
        ("nonsense((", "did not parse"),
    ],
)
def test_forms_no_model_can_verify_are_rejected_not_skipped(equation, reason):
    """Fail closed. An item whose answer nothing can check must not reach a student on the
    strength of nobody having checked it.
    """
    derivation, error = route_answer(equation)
    assert derivation is None
    assert error and reason in error


def test_the_vacuous_form_is_rejected_without_banning_the_form_it_resembles():
    """The one that took a wrong attempt to get right.

    `Eq(x, 43)` and `Eq(x, Max(34, 43))` **parse to the identical expression** - SymPy folds
    `Max` while parsing, and `evaluate=False` does not stop it. A check written against the
    parsed value therefore rejects both, banning the exact form that makes comparison
    questions expressible. The check reads the source text for that reason.
    """
    assert route_answer("Eq(x, 43)")[0] is None
    assert _route("Eq(x, Max(34, 43))").payload == (43,)
    assert _route("Eq(x, gcd(12, 18))").payload == (6,)


# --------------------------------------------------------------------------------------
# Each model accepts the right answer AND rejects a wrong one
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("equation", "correct", "wrong"),
    [
        ("Eq(3*x + 2, 11)", "3", "4"),
        ("Eq(x, Max(34, 43))", "43", "34"),
        ("Eq(x**2, 9)", "3 or -3", "3"),  # one root of two is a wrong answer, not a partial one
        ("Eq(x**2, 9)", "3, -3", "3 or 9"),
        ("3*x + 2 > 11", "x > 3", "x >= 3"),  # the boundary is the whole difficulty
        ("x >= 4", "x >= 4", "x > 4"),
        ("Eq(x + y, 10); Eq(x - y, 2)", "(6, 4)", "(4, 6)"),  # order is the answer
        ("Eq(x + y, 10); Eq(x - y, 2)", "x = 6, y = 4", "x = 6, y = 5"),
        ("(x - 3)*(x + 3)", "x**2 - 9", "x**2 + 9"),
        ("(x - 3)*(x + 3)", "(x + 3)*(x - 3)", "(x - 3)**2"),
    ],
)
def test_every_model_accepts_the_answer_and_rejects_a_near_miss(equation, correct, wrong):
    derivation = _route(equation)
    assert _option_matches(derivation, correct), f"{correct!r} should match {equation!r}"
    assert not _option_matches(derivation, wrong), f"{wrong!r} should NOT match {equation!r}"


def test_symbolic_accepts_an_equivalent_rearrangement():
    """`(x-3)(x+3)` and `x**2 - 9` are one answer written two ways. Equivalence, not string
    equality, is the only comparison that does not reject an author for factoring.
    """
    derivation = _route("(x - 3)*(x + 3)")
    for equivalent in ("x**2 - 9", "-9 + x**2", "(x + 3)*(x - 3)"):
        assert _option_matches(derivation, equivalent)


def test_an_unparseable_option_never_counts_as_a_match():
    """The direction that matters: a distractor nobody can parse must not be silently
    exempt from the "no other option also matches" arm. D-188 found the old gate was
    *quieter* for exactly this reason.
    """
    for equation in ("Eq(3*x + 2, 11)", "Eq(x**2, 9)", "3*x + 2 > 11", "(x - 3)*(x + 3)"):
        assert not _option_matches(_route(equation), "??? not maths ???")


def test_multi_root_requires_every_root_not_merely_a_subset():
    """"3" is not a partially-correct answer to `x**2 = 9`; it is a wrong one, and it is the
    distractor a student who forgets the negative root will pick.
    """
    derivation = _route("Eq(x**2, 9)")
    assert _option_matches(derivation, "-3 or 3")
    assert not _option_matches(derivation, "3")
    assert not _option_matches(derivation, "3 or -3 or 9")


def test_the_whole_shipped_bank_still_routes_as_value_and_matches_its_own_key():
    """The regression that matters most: the bank was authored against the single-value
    gate, and this phase must add models rather than move any of it.

    The count is asserted rather than the shape alone, so a topic silently vanishing from
    the export shows up here. It moved 130 -> 184 when C1's K-2 wave landed (54 generated
    items across six new topics; a 55th was rejected for two options carrying the same
    value written two ways).
    """
    import glob
    import pathlib

    import yaml

    root = pathlib.Path(__file__).resolve().parents[3]
    checked = 0
    for path in sorted(glob.glob(str(root / "curriculum/internal_math/authored/*.yaml"))):
        for template in yaml.safe_load(open(path))["templates"]:
            derivation, error = route_answer(template["answer_expression"])
            assert derivation is not None, f"{template['question_template_id']}: {error}"
            assert derivation.model == "value"
            options = {label: template[f"option_{label}"] for label in "abcd"}
            matching = [k for k, v in options.items() if _option_matches(derivation, v)]
            assert matching == [template["correct_option"]], template["question_template_id"]
            checked += 1
    assert checked == 184


# --------------------------------------------------------------------------------------
# The parser must return a verdict for every input, including ones SymPy answers oddly
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["None", "True", "False", "...", ""])
def test_a_non_value_parse_is_rejected_rather_than_raised(text):
    """`parse_expr` does not only raise or return a `Basic` (D-275).

    Handed `'None'`, `'True'` or `'...'` it returns the plain Python object, which has no
    `.free_symbols` - so `route_answer` died with `AttributeError` instead of returning
    `(None, reason)`, in a function documented as fail-closed. Found while analysing the
    first real 3-5 wave, on a row whose `answer_expression` was NULL.

    **Third occurrence of this class**, which is why the fix is in `_parse_side` rather
    than at the call site that reported it: Phase R's `TokenError` escaping `derive_answer`
    and D-274's `sympify('4,700')` returning a tuple were the first two, each patched where
    it surfaced. All ten callers already wrap the parser in `except _PARSE_ERRORS`, so
    fixing the parser fixes every route at once.
    """
    for fn in (route_answer, derive_answer):
        value, error = fn(text)
        assert value is None, f"{fn.__name__} accepted {text!r}"
        assert error


@pytest.mark.parametrize(
    ("equation", "expected"),
    [
        ("Eq(x, 428 * 6)", "value"),
        # The missing-factor form the second `decimals` run introduced. It has to keep
        # working: the fix touches the parser every route shares.
        ("Eq(2.5 * x, 8.75)", "value"),
        ("x**2 = 9", "multi_root"),
        ("3*x + 2 > 11", "interval"),
        ("x**2 - 9", "symbolic"),
    ],
)
def test_real_equations_are_unaffected_by_the_non_value_guard(equation, expected):
    derivation, error = route_answer(equation)
    assert derivation is not None, error
    assert derivation.model == expected
