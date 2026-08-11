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


def test_a_skill_whose_point_is_a_non_whole_answer_says_so_in_its_structure():
    """The general form of the two above — narrowed in D-277, because it was over-reaching.

    The defect it exists to catch is `decimal_multiply`: a structure that admitted the
    *easier* whole-answer version of the skill, so the topic's whole reason for having the
    `rational` family went unexercised (0 of 2 items had a non-whole answer).

    It first applied to **every** `rational` skill, which is wrong. `rational` means a
    non-whole answer is *permitted*, not that it is the point — `g6_wp_average` computes a
    mean that is often a whole number, and `geo_area` from whole side lengths usually is.
    Requiring those to promise a fraction would push authors toward contrived numbers.

    So it binds where non-wholeness *is* the skill: the decimal and fraction topics, and
    rounding, whose upper tiers round decimals. Those are exactly the skills where a
    whole-answer item means the skill was not exercised at all.
    """
    content = load_curriculum()
    must_state = [
        s
        for s in content.skills
        if s.difficulty_tiers
        and (s.topic_id in {"decimals", "g6_fractions"} or s.skill_id == "number_rounding")
    ]
    assert must_state, "the guard selected no skills - did a topic get renamed?"
    vague = [
        s.skill_id
        for s in must_state
        if not re.search(r"decimal|fraction|Rational|quotient|not be rounded", s.structure)
    ]
    assert vague == []
