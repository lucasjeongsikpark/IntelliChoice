"""Answer families, and the skill config that used to be Python (D-274).

Three things are pinned here, and the first is the one that matters:

1. **A family decides the number rules, and both families are scored both ways.** A
   `rational` family that accepts everything would be indistinguishable from deleting the
   check, which is the D-246 failure mode: a gate measured only on what should pass reads
   as perfect. So every case below also asserts what the family must still reject.
2. **The whole-number test is about the number, not the SymPy type.** `Float(12.0)` is a
   whole number and `is_Integer` says otherwise.
3. **The authoring plan is derived from the taxonomy, not written beside the pipeline.**
   A skill added to `skills.yaml` is generatable without a source edit, which is the whole
   point of the move.

Free: no model call, no database.
"""

import pathlib

import pytest
from intellichoice_curriculum import ai_pipeline
from intellichoice_curriculum.ai_pipeline import validate_equation_design
from intellichoice_curriculum.authored_validation import _is_whole_number, _sympify
from intellichoice_curriculum.content import ANSWER_FAMILIES, load_curriculum
from intellichoice_shared.bedrock import EquationDesignResponse


def _design(equation: str, final_answer: str) -> EquationDesignResponse:
    return EquationDesignResponse(
        reasoning="fixture",
        scenario_sketch="fixture",
        unknown_meaning="fixture",
        equation=equation,
        final_answer=final_answer,
        answer_units="",
    )


# --------------------------------------------------------------------------------------
# The whole-number predicate
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "whole"),
    [
        ("12", True),
        ("2568", True),
        ("-3", True),
        # The case that made the old check wrong: an even division of decimals.
        ("12.0", True),
        ("6.15", False),
        ("5/8", False),
        ("7.75", False),
        # A fraction that reduces to an integer is whole, however it was written.
        ("24/2", True),
    ],
)
def test_whole_number_asks_about_the_number_not_the_sympy_type(text, whole):
    value = _sympify(text)
    assert value is not None
    assert _is_whole_number(value) is whole


def test_the_old_predicate_and_the_new_one_disagree_on_exactly_the_reported_case():
    """Kept as the regression witness: `Eq(x, 8.4 / 0.7)` solves to 12 and was rejected.

    Asserting the disagreement rather than only the new behaviour, so that if someone
    "simplifies" this back to `is_Integer` the test says what breaks and why.
    """
    value = _sympify("12.0")
    assert value is not None
    assert value.is_Integer is False
    assert _is_whole_number(value) is True


# --------------------------------------------------------------------------------------
# The families, both directions
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("equation", "answer"),
    [
        ("Eq(x, 428 * 6)", "2568"),
        ("Eq(x, 4536 / 8)", "567"),
        ("Eq(x, Max(34281, 34218))", "34281"),
        # An even decimal division: whole in value, Float in type. Counting must accept it.
        ("Eq(x, 8.4 / 0.7)", "12"),
    ],
)
def test_counting_accepts_a_whole_positive_answer(equation, answer):
    assert validate_equation_design(
        _design(equation, answer), target_difficulty=3, family=ANSWER_FAMILIES["counting"]
    ) == []


@pytest.mark.parametrize(
    ("equation", "answer"),
    [
        ("Eq(x, 3.75 + 2.4)", "6.15"),
        ("Eq(x, Rational(1,4) + Rational(3,8))", "5/8"),
        ("Eq(x, 12.50 - 4.75)", "7.75"),
    ],
)
def test_counting_still_rejects_a_fractional_answer(equation, answer):
    """The direction that keeps the family from being a licence.

    This is the behaviour the constant had, and it stays the default - a counting skill
    that produces 12/5 games is still a real defect.
    """
    failures = validate_equation_design(
        _design(equation, answer), target_difficulty=3, family=ANSWER_FAMILIES["counting"]
    )
    assert failures
    assert "not a whole number" in failures[0]


@pytest.mark.parametrize(
    ("equation", "answer"),
    [
        ("Eq(x, 3.75 + 2.4)", "6.15"),
        ("Eq(x, Rational(1,4) + Rational(3,8))", "5/8"),
        ("Eq(x, 12.50 - 4.75)", "7.75"),
        ("Eq(x, 2.5 * 1.4)", "3.5"),
    ],
)
def test_rational_accepts_what_counting_refuses(equation, answer):
    assert validate_equation_design(
        _design(equation, answer), target_difficulty=3, family=ANSWER_FAMILIES["rational"]
    ) == []


@pytest.mark.parametrize(
    ("equation", "answer"),
    [
        ("Eq(x, 4.5 - 7.25)", "-2.75"),
        ("Eq(x, Rational(1,4) - Rational(3,8))", "-1/8"),
    ],
)
def test_rational_still_rejects_a_negative_answer(equation, answer):
    """`rational` relaxes *one* rule. A negative amount of money is still wrong."""
    failures = validate_equation_design(
        _design(equation, answer), target_difficulty=3, family=ANSWER_FAMILIES["rational"]
    )
    assert failures
    assert "not positive" in failures[0]


def test_a_wrong_final_answer_is_caught_under_every_family():
    """The family must not be able to switch off the checks that are genuinely universal."""
    for family in ANSWER_FAMILIES.values():
        failures = validate_equation_design(
            _design("Eq(x, 3.75 + 2.4)", "6.25"), target_difficulty=3, family=family
        )
        assert any("final_answer" in f for f in failures), family.name


def test_the_default_family_is_the_behaviour_the_constant_had():
    """Every caller that does not pass a family keeps exactly its old behaviour."""
    assert validate_equation_design(
        _design("Eq(x, 428 * 6)", "2568"), target_difficulty=3
    ) == []
    assert validate_equation_design(_design("Eq(x, 3.75 + 2.4)", "6.15"), target_difficulty=3)


# --------------------------------------------------------------------------------------
# The bank the constant already contradicted
# --------------------------------------------------------------------------------------


def test_every_shipped_fraction_item_passes_its_own_skills_family():
    """The measurement that made this a defect rather than a limitation.

    26 of the 184 shipped items answer with a fraction, and the design gate required a
    positive whole number - so the pipeline could not have regenerated 14% of its own bank.
    This asserts the topic's skills now declare a family that admits them.
    """
    content = load_curriculum()
    for skill in content.skills_for_topic("fraction_operations"):
        assert skill.answer_family == "rational", skill.skill_id
        assert skill.family.whole_numbers_only is False


# --------------------------------------------------------------------------------------
# The config now has one home
# --------------------------------------------------------------------------------------


def test_the_authoring_plan_is_derived_from_the_taxonomy():
    content = load_curriculum()
    assert ai_pipeline.TOPIC_SKILL_DIFFICULTIES == content.generation_plan()
    assert ai_pipeline.TOPIC_SKILL_DIFFICULTIES, "a derived plan that is empty is a load bug"


def test_no_hand_written_skill_registry_remains_in_the_pipeline_source():
    """The duplication this move removed, pinned so it cannot come back quietly.

    A dict literal keyed by skill id is exactly what drifted from `skills.yaml`; reading
    the source is crude but it is the only thing that catches a *new* one.
    """
    source = pathlib.Path(ai_pipeline.__file__).read_text()
    assert "TOPIC_SKILL_DIFFICULTIES: dict[str, dict[str, list[int]]] = {\n" not in source
    assert "SKILL_STRUCTURES: dict[str, str] = {\n    \"" not in source


def test_every_authorable_skill_declares_a_structure():
    """A slot with tiers but no structure is the D-200 collision waiting to happen.

    Two skills told only their tier were handed the identical equation, and the both-sides
    slot got an equation with the variable on one side.
    """
    content = load_curriculum()
    missing = [
        s.skill_id for s in content.skills if s.difficulty_tiers and not s.structure
    ]
    assert missing == []


def test_every_skill_declares_a_known_family_and_on_scale_tiers():
    content = load_curriculum()
    for skill in content.skills:
        assert skill.answer_family in ANSWER_FAMILIES, skill.skill_id
        assert all(t in range(1, 6) for t in skill.difficulty_tiers), skill.skill_id
