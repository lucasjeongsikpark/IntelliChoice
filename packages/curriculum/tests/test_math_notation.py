"""No `*` reaches a student as mathematics (D-288), scored in both directions.

The frontend renders stems and options as raw strings - `RichText` covers tutor text only -
so 36 shipped option lines showed students `(x + 1)*(x + 12)` and `6*t + 5` as programmer
notation. The content was rewritten by hand; this check is what keeps the next wave from
re-shipping it, and these tests are what keep the check honest:

- the failing direction, with the remedy stated in the message (D-283's lesson - a repair
  loop fed "contains '*'" can only guess; one fed the replacement forms can act)
- the passing direction for every rewritten form (`6t`, `(x + 1)(x + 3)`, `4 × 8`, `x²`)
- the exemption: `step.expression` renders inside `<code>` and keeps its stars

Free: no model call, no database.
"""

import glob
import pathlib

import pytest
import yaml
from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)


def _item(**overrides) -> AuthoredGeneratedItemResponse:
    base = dict(
        stem="A car travels at a steady speed. Its distance is 6t km after t hours. What is "
        "its distance after adding a 5 km detour?",
        option_a="6t + 5",
        option_b="6t",
        option_c="11t",
        option_d="6t + 11",
        correct_option="a",
        hint_ladder=[
            "Start from the distance the car covers on its own.",
            "The detour adds a fixed amount, not a rate.",
            "Add the detour once, at the end.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Add the fixed detour to the distance expression.",
                    expression="d = 6*t + 5",  # the exempt field, starred on purpose
                    common_mistake=None,
                )
            ],
            final_answer="6t + 5",
        ),
        estimated_time_seconds=60,
        misconception_tags=["added_rate_instead_of_constant"],
        proposed_difficulty=2,
        difficulty_rationale="one expression, one constant",
        required_prerequisites=["writing expressions"],
        equation="6*t + 5",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


# --------------------------------------------------------------------------------------
# 1. The failing direction - and the message carries the remedy
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("option_a", "6*t + 5"),
        ("option_b", "(x + 1)*(x + 3)"),
        ("stem", "The distance is 6*t km after t hours. What is 6*t when t is 3?"),
    ],
)
def test_programmer_notation_in_student_text_is_rejected(field, value):
    result = validate_authored_item(2, _item(**{field: value}))
    assert not result.passed
    assert any("programmer notation" in f and "×" in f for f in result.failures), (
        result.failures
    )


def test_a_starred_hint_is_rejected():
    result = validate_authored_item(
        2, _item(hint_ladder=["Start from 6*t.", "The detour is fixed.", "Add it once."])
    )
    assert not result.passed
    assert any("hint_ladder[0]" in f for f in result.failures), result.failures


def test_a_starred_final_answer_is_rejected():
    # final_answer renders raw in the solution panel, and the agreement check compares it
    # to option text - so a starred final_answer would either show a student the star or
    # force the option to carry one too.
    item = _item(option_a="6*t + 5")
    item.canonical_solution.final_answer = "6*t + 5"
    result = validate_authored_item(2, item)
    assert not result.passed


# --------------------------------------------------------------------------------------
# 2. The passing direction - every rewritten form
# --------------------------------------------------------------------------------------


def test_natural_notation_passes():
    """The exact forms the 64 rewritten fields now use."""
    result = validate_authored_item(2, _item())
    assert result.passed, result.failures


def test_the_multiplication_sign_and_superscripts_pass():
    item = _item(
        hint_ladder=[
            "Simplify 9/4 × 8 first.",
            "Powers write as superscripts, like 2⁵ or x².",
            "Then add the detour.",
        ]
    )
    result = validate_authored_item(2, item)
    assert result.passed, result.failures


def test_the_expression_field_keeps_its_stars():
    """`step.expression` renders inside <code>, where `d = 6*t + 5` is the honest form.
    The fixture already stars it; this pins that the exemption is real by construction."""
    result = validate_authored_item(2, _item())
    assert result.passed, result.failures


# --------------------------------------------------------------------------------------
# 3. The shipped bank holds the rule
# --------------------------------------------------------------------------------------


def test_no_shipped_student_text_contains_a_star():
    """The census for this rule. The loader gates on insert/update only, so an unchanged
    item never re-gates - this sweep is what proves the whole bank complies, not the load."""
    root = pathlib.Path(__file__).resolve().parents[3]
    offenders: list[str] = []
    checked = 0
    for path in sorted(glob.glob(str(root / "curriculum/internal_math/authored/*.yaml"))):
        for template in yaml.safe_load(pathlib.Path(path).read_text())["templates"]:
            solution = template.get("canonical_solution") or {}
            fields = [
                template.get("stem"),
                template.get("context_block"),
                template.get("rendered_question"),
                *(template.get(f"option_{o}") for o in "abcd"),
                *(template.get("hint_ladder") or []),
                *(s.get("explanation") for s in solution.get("steps") or []),
                solution.get("final_answer"),
            ]
            checked += 1
            for value in fields:
                if value and "*" in value:
                    offenders.append(f"{template['question_template_id']}: {value[:70]}")
    assert checked >= 600, f"only {checked} templates swept - did the glob match?"
    assert offenders == [], offenders
