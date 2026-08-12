"""Family-C figures, and the two properties that make one safe to ship (D-279).

A figure is the only part of an item not derived from the verified equation, so it gets two
checks and both are scored in both directions:

1. **Coupling** - every number in the figure appears in the item. A clock showing 3:45 next
   to a stem about 4:15 is a defect no other check can see.
2. **Reading** - for a question the figure *answers*, the figure is what verifies it.
   `check_sympy_independent_solve` cannot: "what time does this clock show" has no
   arithmetic, so `derive_answer` yields a number while the option says "3:45" - exactly
   the mismatch that made `Museum B` fail in the 3-5 wave.

Free: no model call, no database.
"""

import pytest
from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)
from intellichoice_shared.figures import (
    BarChartFigure,
    ClockFigure,
    CoordinateGridFigure,
    figure_derived_answer,
    figure_numbers_missing_from_item,
)

CLOCK = ClockFigure(hour=3, minute=45)
CHART = BarChartFigure(categories=["Ana", "Ben", "Cara"], values=[12.0, 8.0, 15.0])


def _item(**overrides) -> AuthoredGeneratedItemResponse:
    base = dict(
        stem="What time does this clock show?",
        option_a="3:45",
        option_b="9:15",
        option_c="4:45",
        option_d="3:15",
        correct_option="a",
        hint_ladder=[
            "The short hand tells you the hour.",
            "The short hand has passed 3.",
            "The long hand counts in fives.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Read the short hand for the hour.",
                    expression="hour = 3",
                    common_mistake=None,
                )
            ],
            final_answer="3:45",
        ),
        estimated_time_seconds=45,
        misconception_tags=["swapped_hands"],
        proposed_difficulty=2,
        difficulty_rationale="the minute hand is on a quarter mark",
        required_prerequisites=["counting in fives"],
        equation=None,
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


# --------------------------------------------------------------------------------------
# 1. Coupling
# --------------------------------------------------------------------------------------


def test_a_figure_whose_numbers_are_in_the_item_is_coupled_to_it():
    assert figure_numbers_missing_from_item(CLOCK, item_text="3:45 and 9:15") == []


def test_a_figure_carrying_numbers_the_item_never_mentions_is_caught():
    """The defect this exists for: a clock that does not match its own question.

    Both numbers are reported, not just the first - a reviewer fixing this needs to know
    the whole figure is wrong rather than one field of it.
    """
    assert figure_numbers_missing_from_item(CLOCK, item_text="4:15 and 9:20") == [3.0, 45.0]


def test_the_gate_rejects_an_item_whose_figure_disagrees_with_it():
    """Every option changed, so nothing in the item mentions 3 or 45 any more.

    Written that way deliberately: an earlier draft of this test left "3:15" and "4:45"
    among the options, which *do* contain 3 and 45, so the coupling check passed and the
    item failed for an unrelated reason - a test that would have gone green against a
    deleted check.
    """
    result = validate_authored_item(
        2,
        _item(
            option_a="7:20",
            option_b="8:10",
            option_c="9:50",
            option_d="6:20",
            correct_option="a",
            canonical_solution=SolutionResponse(
                steps=[
                    SolutionStep(
                        step_number=1,
                        explanation="Read the short hand for the hour.",
                        expression="hour = 7",
                        common_mistake=None,
                    )
                ],
                final_answer="7:20",
            ),
            hint_ladder=["The short hand.", "It has passed 7.", "Count in fives."],
        ),
        figure=CLOCK,
    )
    assert result.passed is False
    assert any("appear nowhere in the question" in f for f in result.failures), result.failures


def test_a_whole_valued_float_matches_the_integer_an_author_writes():
    """The spec holds 12.0; the question says "12"."""
    assert figure_numbers_missing_from_item(CHART, item_text="12 8 15") == []


# --------------------------------------------------------------------------------------
# 2. Reading — the figure as the source of truth
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("figure", "reading", "expected"),
    [
        (CLOCK, "clock_time", "3:45"),
        (CHART, "chart_max_label", "Cara"),
        (CHART, "chart_min_label", "Ben"),
        (
            CoordinateGridFigure(points=[(3.0, 2.0)], point_labels=["P"]),
            "point_coordinates",
            "(3, 2)",
        ),
    ],
)
def test_a_figure_determines_its_own_answer(figure, reading, expected):
    assert figure_derived_answer(figure, reading) == expected


def test_a_reading_a_figure_cannot_answer_returns_none_rather_than_guessing():
    assert figure_derived_answer(CLOCK, "chart_max_label") is None
    assert figure_derived_answer(CHART, "clock_time") is None


def test_the_gate_accepts_an_item_whose_option_states_what_the_figure_reads():
    assert validate_authored_item(2, _item(), figure=CLOCK, figure_reading="clock_time").passed


def test_the_gate_rejects_an_item_whose_option_disagrees_with_the_figure():
    """The other direction. A reading that only ever says yes is not a check."""
    result = validate_authored_item(
        2,
        _item(correct_option="d"),  # says 3:15; the clock says 3:45
        figure=CLOCK,
        figure_reading="clock_time",
    )
    assert result.passed is False
    assert any("the figure reads" in f for f in result.failures)


def test_the_gate_rejects_two_options_stating_what_the_figure_reads():
    result = validate_authored_item(
        2,
        _item(option_b="3:45"),
        figure=CLOCK,
        figure_reading="clock_time",
    )
    assert result.passed is False
    assert any("more than one option" in f for f in result.failures)


def test_a_reading_declared_without_a_figure_fails_closed():
    result = validate_authored_item(2, _item(), figure=None, figure_reading="clock_time")
    assert result.passed is False
    assert any("has no figure" in f for f in result.failures)


def test_a_reading_the_figure_kind_cannot_answer_fails_closed():
    result = validate_authored_item(
        2, _item(), figure=CLOCK, figure_reading="chart_max_label"
    )
    assert result.passed is False
    assert any("does not apply" in f for f in result.failures)


def test_a_reading_replaces_the_equation_rather_than_weakening_the_gate():
    """An item with a reading has no equation, and must not therefore skip everything.

    The two answer-derivation checks are exchanged, not dropped - every other check still
    runs, which this proves by failing one of them on an item whose reading is correct.
    """
    result = validate_authored_item(
        2,
        _item(option_b="3:45 ", hint_ladder=["a", "b", "c"], option_c="3:45"),
        figure=CLOCK,
        figure_reading="clock_time",
    )
    assert result.passed is False


def test_an_item_with_no_figure_is_gated_exactly_as_before():
    """Every item authored before figures existed passes both parameters as None."""
    result = validate_authored_item(
        3,
        _item(
            stem="A car travels 9.45 km on 2.5 litres. What is its efficiency?",
            option_a="3.78 km per litre",
            option_b="11.95 km per litre",
            option_c="37.8 km per litre",
            option_d="23.625 km per litre",
            correct_option="a",
            canonical_solution=SolutionResponse(
                steps=[
                    SolutionStep(
                        step_number=1,
                        explanation="Divide distance by fuel.",
                        expression="x = 9.45 / 2.5",
                        common_mistake=None,
                    )
                ],
                final_answer="3.78 km per litre",
            ),
            equation="Eq(x, 9.45 / 2.5)",
        ),
    )
    assert result.passed, result.failures


# --------------------------------------------------------------------------------------
# 3. The authored bank
# --------------------------------------------------------------------------------------


def test_every_figure_item_in_the_bank_passes_its_own_gate():
    """The bank files the authoring script wrote, re-checked from disk.

    Figure skills carry no `difficulty_tiers` on purpose, so no paid run can schedule them -
    these items are authored, and this is what stands in for a generation gate.
    """
    import glob
    import pathlib

    import yaml
    from intellichoice_curriculum.authored_bank import AuthoredTemplateDef

    root = pathlib.Path(__file__).resolve().parents[3]
    checked = 0
    for topic in ("telling_time", "data_graphs", "plane_figures", "coordinate_geometry"):
        matches = glob.glob(str(root / f"curriculum/internal_math/authored/{topic}.yaml"))
        assert matches, f"{topic}.yaml is missing"
        for path in matches:
            for raw in yaml.safe_load(open(path))["templates"]:
                definition = AuthoredTemplateDef.model_validate(raw)
                assert definition.figure_spec is not None, definition.question_template_id
                result = validate_authored_item(
                    definition.difficulty_label,
                    definition.to_generated_item(),
                    figure=definition.figure_spec,
                    figure_reading=definition.figure_reading,
                )
                assert result.passed, (definition.question_template_id, result.failures)
                checked += 1
    assert checked >= 28


def test_no_figure_skill_is_schedulable_by_a_paid_run():
    from intellichoice_curriculum.content import load_curriculum

    content = load_curriculum()
    plan = content.generation_plan()
    for topic in ("telling_time", "data_graphs", "plane_figures", "coordinate_geometry"):
        assert topic not in plan, f"{topic} would be scheduled by a paid run"
