"""The dedup gap that 86% acceptance hid (D-273, C1 wave K-2).

The first generated wave produced 55 items at 86% acceptance, and every one read well on its
own. Counted by their *arithmetic* rather than their prose, 27 of the 55 shared a number set
with another item and four separate items were `9 + 9`. All of them passed dedup, because
dedup asked about the story twice - exact stem text, then stem-embedding distance - and about
the mathematics never.

Both directions, per D-246: the check must collide on the same sum told two ways, and must
NOT collide on genuinely different sums that happen to share digits.

Free: pure string and regex work, no model call, no database.
"""

import pytest
from intellichoice_curriculum.authored_validation import arithmetic_identity


@pytest.mark.parametrize(
    ("first", "second"),
    [
        # The exact collisions measured in the wave.
        ("Eq(x, 4 + 5)", "Eq(x, 5 + 4)"),
        ("Eq(x, 4 + 5)", "x = 5 + 4"),  # both written forms, one identity
        ("Eq(x, 9 + 9)", "x = 9 + 9"),
        ("Eq(x, 7 + 6)", "x = 7 + 6"),
        ("Eq(x, 35 + 24)", "Eq(x, 24 + 35)"),
        ("x = 2456 + 1378", "x = 2456 + 1378"),
        ("Eq(x, 9 - 7)", "Eq(x, 9 - 7)"),
    ],
)
def test_the_same_sum_told_two_ways_is_one_identity(first, second):
    assert arithmetic_identity(first) == arithmetic_identity(second)


@pytest.mark.parametrize(
    ("first", "second", "why"),
    [
        ("Eq(x, 9 + 9)", "Eq(x, 9 - 9)", "same numbers, different operation"),
        ("Eq(x, 4 + 5)", "Eq(x, 4 + 6)", "different operand"),
        ("Eq(x, 15 + 9 - 6)", "Eq(x, 15 + 9)", "an extra step is a different question"),
        ("Eq(x, 35 + 28)", "Eq(x, 3 + 5 + 28)", "different decomposition"),
        # The direction that matters most: a false collision costs a good candidate.
        ("Eq(x, 12 - 3 - 4)", "Eq(x, 12 - 34)", "digits regrouped is not the same sum"),
    ],
)
def test_different_calculations_do_not_collide(first, second, why):
    assert arithmetic_identity(first) != arithmetic_identity(second), why


def test_only_a_digitless_equation_returns_none():
    """Written asserting that a symbolic expression returns None, which was wrong: it was my
    assumption, not the code's behaviour. `(x - 3)*(x + 3)` contains the digits 3 and 3, so
    it has an identity like anything else.

    **The limit that mistake exposed, stated rather than hidden.** For `value` items the
    digits are the operands and the identity means what it says. For `symbolic` items they
    are coefficients, so two genuinely different expressions with the same coefficients and
    operators would collide - `Eq(x, 3*x + 3)` and a rearrangement of it, say. That is a
    false positive costing one candidate, which is the cheap direction, and no symbolic
    content exists yet (family B is grades 9-12, unseeded). Revisit when the 9-12 wave runs
    rather than pre-emptively weakening a check that is currently exact for what it guards.
    """
    assert arithmetic_identity("(x - 3)*(x + 3)") == (("3", "3"), ("*", "+", "-"))
    assert arithmetic_identity("") is None
    assert arithmetic_identity("Eq(a, b)") is None


def test_it_catches_what_the_measured_wave_actually_shipped():
    """The evidence this check was written from, pinned so a regression is visible.

    These are real `answer_expression` values from the wave, in the multiplicities they
    appeared. If the identity ever stops collapsing them, the 27-of-55 duplication returns.
    """
    wave = [
        "Eq(x, 4 + 5)",
        "Eq(x, 5 + 4)",
        "x = 5 + 4",
        "Eq(x, 9 + 9)",
        "Eq(x, 9 + 9)",
        "Eq(x, 9 + 9)",
        "x = 9 + 9",
    ]
    identities = {arithmetic_identity(equation) for equation in wave}
    # Seven items, two genuinely distinct calculations.
    assert len(identities) == 2
