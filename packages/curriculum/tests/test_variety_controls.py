"""What the first real 3-5 run repeated, and what now stops it (D-275).

The `decimals` wave accepted 17 of 17 candidates with zero rejections at any gate — and
every one of these defects was in that output. A gate measured only by its pass rate would
have called the run a success, which is the point of writing them down as tests:

1. **11 of 17 stems were about cutting ribbon.** Lena, Emma, Ava, Lila and Maya all cutting
   ribbon. `avoid_equations` told the design call which *numbers* were taken and nothing
   about the setting, so the model varied exactly what it was asked to vary.
2. **`Eq(x, 6.3 / 0.9)` was authored at tier 4 and again at tier 5.** The accumulator was
   keyed on `(skill, tier)`, and a skill's tiers differ in how demanding the numbers are,
   not in which numbers exist — so it could not see its own duplicate one tier away.
3. **Two of three skills never produced the answer kind they exist for.**
   `decimal_multiply` authored `2.5 * 12` (answer 30); `decimal_divide` authored six "how
   many whole pieces fit" items, four with whole answers.

Free: no model call, no database.
"""

import re

import pytest
from intellichoice_adapters.bedrock.mock_provider import _equation_design_json
from intellichoice_curriculum.content import load_curriculum

# --------------------------------------------------------------------------------------
# 2. The accumulator key
# --------------------------------------------------------------------------------------


def test_the_used_equation_accumulator_is_keyed_on_the_skill_not_the_tier():
    """Reading the source, because the key is a dict annotation rather than behaviour.

    Crude, and it is the only thing that catches a revert to `(skill, tier)` — which is
    what shipped a duplicate calculation across two tiers of one skill.
    """
    import pathlib

    from intellichoice_curriculum import pipeline_cli

    source = pathlib.Path(pipeline_cli.__file__).read_text()
    assert "used_equations: dict[str, list[str]]" in source
    assert "used_equations: dict[tuple[str, int], list[str]]" not in source
    assert "used_equations.get(slot.skill_id" in source


# --------------------------------------------------------------------------------------
# 1. Scenario memory reaches the design call and changes what it proposes
# --------------------------------------------------------------------------------------


def test_the_design_stub_varies_its_setting_with_the_scenarios_it_is_told_to_avoid():
    """The double has to be able to do the thing production is now relied on to do.

    A mock returning one setting forever was a faithful stand-in while nothing told the
    model what had been used. Once the runner does, it stops being faithful — the same
    reasoning D-273 applied to `avoid_equations`.
    """
    seen = set()
    for used in range(4):
        design = _equation_design_json(
            {"target_difficulty": 2, "avoid_scenarios": ["prior"] * used}
        )
        seen.add(design["scenario_sketch"])
    assert len(seen) == 4, seen


def test_scenarios_and_equations_vary_independently():
    """Varying the setting must not silently change the numbers, or a run avoiding a
    scenario would re-roll arithmetic that was already verified."""
    a = _equation_design_json({"target_difficulty": 3, "avoid_scenarios": []})
    b = _equation_design_json({"target_difficulty": 3, "avoid_scenarios": ["x", "y"]})
    assert a["equation"] == b["equation"]
    assert a["scenario_sketch"] != b["scenario_sketch"]


@pytest.mark.parametrize("field", ["avoid_equations", "avoid_scenarios"])
def test_the_design_payload_carries_both_avoid_lists(field):
    from intellichoice_shared.bedrock import EquationDesignPayload

    assert field in EquationDesignPayload.model_fields


def test_the_anchor_names_the_used_scenarios_rather_than_asking_for_variety():
    """D-252 measured a prompt clause protecting one field at 0 of 52 preserved. The fix
    for repetition is telling the model what is taken, not asking it to be varied."""
    import pathlib

    from intellichoice_curriculum import ai_pipeline

    source = pathlib.Path(ai_pipeline.__file__).read_text()
    assert "These settings are already used by this skill" in source
    assert "avoid_scenarios" in source


# --------------------------------------------------------------------------------------
# 3. A skill whose structure permits the thing that hid it
# --------------------------------------------------------------------------------------


def test_decimal_multiply_requires_both_factors_to_be_decimals():
    """`2.5 * 12` satisfied "at least one factor is a decimal" and answers 30.

    The old wording admitted the easier skill *and* an answer that is not a decimal, so
    the topic's whole reason for having the `rational` family went unexercised.
    """
    skill = load_curriculum().skill("decimal_multiply")
    assert skill is not None
    assert "BOTH factors are decimals" in skill.structure


def test_decimal_divide_rules_out_the_framing_that_forces_an_even_division():
    skill = load_curriculum().skill("decimal_divide")
    assert skill is not None
    assert "quotient is itself a decimal" in skill.structure
    assert "how many whole pieces" in skill.structure


def test_every_rational_skill_states_that_its_answer_is_not_whole():
    """The general form of the two above, so a third `rational` skill cannot ship with a
    structure that silently permits whole answers.

    Deliberately a keyword check rather than a judgement: it fails loudly when someone adds
    a `rational` skill without saying anything about the answer, which is the state both
    decimal skills were in.
    """
    content = load_curriculum()
    vague = []
    for skill in content.skills:
        if skill.answer_family != "rational" or not skill.difficulty_tiers:
            continue
        if not re.search(
            r"decimal|fraction|Rational|cents|amount|not be rounded|quotient",
            skill.structure,
        ):
            vague.append(skill.skill_id)
    assert vague == []


# --------------------------------------------------------------------------------------
# 4. The pipeline and the loader must agree about what a valid item is
# --------------------------------------------------------------------------------------


def _item(**overrides):
    from intellichoice_shared.bedrock import (
        AuthoredGeneratedItemResponse,
        SolutionResponse,
        SolutionStep,
    )

    base = dict(
        stem="A car travels 9.45 kilometers and uses 2.5 liters of fuel. "
        "What is the fuel efficiency in kilometers per liter?",
        option_a="11.95 kilometers per liter",
        option_b="3.78 kilometers per liter",
        option_c="37.8 kilometers per liter",
        option_d="23.625 kilometers per liter",
        correct_option="b",
        hint_ladder=[
            "What operation compares distance to fuel used?",
            "Divide the distance by the litres of fuel.",
            "Work out that division carefully.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Divide distance by fuel used.",
                    expression="x = 9.45 / 2.5",
                    common_mistake=None,
                )
            ],
            final_answer="3.78 kilometers per liter",
        ),
        estimated_time_seconds=60,
        misconception_tags=["added_instead_of_divided"],
        proposed_difficulty=4,
        difficulty_rationale="two decimals; the quotient is itself a decimal",
        required_prerequisites=["dividing decimals"],
        equation="Eq(x, 9.45 / 2.5)",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def test_the_loader_rejects_an_item_with_no_equation():
    """D-191's rule, still enforced where bank files are read."""
    from intellichoice_curriculum.authored_validation import validate_authored_item

    result = validate_authored_item(4, _item(equation=None))
    assert result.passed is False
    assert any("equation is missing" in f for f in result.failures)
    assert validate_authored_item(4, _item()).passed is True


def test_the_pipeline_path_requires_the_equation_the_loader_requires():
    """The disagreement this closes, pinned at the pipeline end (D-275).

    The second `decimals` run produced 1 of 21 candidates with `equation: null` - optional
    on the response model, and nothing on the generation path asked for it. That row
    reached `pending`, so a human would have reviewed an item the bank load then refuses.

    Source-level, because exercising the branch needs a gateway and a database; the point
    is that the check exists on that path at all, which is what was missing.
    """
    import pathlib

    from intellichoice_curriculum import ai_pipeline

    source = pathlib.Path(ai_pipeline.__file__).read_text()
    assert "if not item.equation:" in source
    assert "equation_present" in source
    # Before the solvers: an item that cannot pass the loader should not be paid for three
    # more times first.
    # The *call*, not the definition - `def solver_objections` sits near the top of the
    # module, so searching for the bare name compares against the wrong offset.
    assert source.index("if not item.equation:") < source.index("objections = solver_objections(")
