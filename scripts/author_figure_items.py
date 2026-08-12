"""Author the family-C bank deterministically (D-279). Free: no model call, no database.

**Why a script and not the pipeline.** 34 taxonomy rows are questions whose subject is a
picture, and for those the picture has to be exactly right - a clock two minutes off is a
wrong question, not a stylistic problem. Every other family is generated because a model
writes better prose than a table does; here the content *is* the numbers, and a table
produces them correctly every time for nothing. This is the same reasoning that put
`place_value_compare`'s re-authoring in a script rather than a run.

It also sidesteps a contract change: the generator's structured-output schema never has to
carry a discriminated union, so nothing about the paid path moves.

Every item it writes goes through `validate_authored_item` with its figure before being
written, so a table entry that disagrees with its own question fails here rather than at
load. Run:

    uv run python scripts/author_figure_items.py            # writes the bank files
    uv run python scripts/author_figure_items.py --check    # validates, writes nothing
"""

import argparse
import pathlib
import sys

import yaml
from intellichoice_curriculum.authored_bank import AuthoredTemplateDef
from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_curriculum.content import load_curriculum
from intellichoice_shared.figures import (
    BarChartFigure,
    ClockFigure,
    CoordinateGridFigure,
    ShapeFigure,
)

BANK = pathlib.Path(__file__).resolve().parents[1] / "curriculum" / "internal_math" / "authored"
CURRICULUM_VERSION = load_curriculum().curriculum_version

# --------------------------------------------------------------------------------------
# Clock faces — `telling_time`
# --------------------------------------------------------------------------------------
# (hour, minute, distractor minutes) — the distractors are the mistakes a child actually
# makes reading a clock: the hands swapped, the minute hand read as a number rather than a
# count of five, and the nearest five-minute mark.
_CLOCKS = [
    (3, 0, [15, 30, 45], 1),
    (6, 30, [0, 15, 45], 1),
    (9, 15, [45, 0, 30], 2),
    (4, 45, [15, 30, 0], 2),
    (7, 20, [40, 25, 15], 3),
    (11, 50, [10, 45, 55], 4),
    (2, 35, [25, 40, 5], 4),
    (12, 25, [35, 20, 30], 5),
    # D-288: the serving floor is 2 approved items at EVERY difficulty (D-187 +
    # QUESTIONS_PER_DIFFICULTY), and this topic sat at d3:1, d5:1 - so no student could
    # open it at all. These two rows are what make telling_time servable.
    (8, 40, [20, 35, 45], 3),
    (1, 55, [5, 50, 45], 5),
]


def _clock_items() -> list[tuple[AuthoredTemplateDef, object]]:
    out = []
    for index, (hour, minute, wrong, tier) in enumerate(_CLOCKS):
        correct = f"{hour}:{minute:02d}"
        options = [correct] + [f"{hour}:{m:02d}" for m in wrong]
        # Rotate so the answer is not always option a (D-191's position-bias fix, applied
        # by hand here because there is no shuffle stage on this path).
        shift = index % 4
        rotated = options[-shift:] + options[:-shift] if shift else options
        label = "abcd"[rotated.index(correct)]
        out.append(
            (
                AuthoredTemplateDef(
                    question_template_id=f"figure-telling_time-d{tier}-{700100 + index}",
                    topic_id="telling_time",
                    skill_id="time_read_clock",
                    grade_band="1-2",
                    difficulty_label=tier,
                    rendered_question="What time does this clock show?",
                    stem="What time does this clock show?",
                    option_a=rotated[0],
                    option_b=rotated[1],
                    option_c=rotated[2],
                    option_d=rotated[3],
                    correct_option=label,
                    hint_ladder=[
                        "The short hand tells you the hour. Which number has it just passed?",
                        f"The short hand has passed {hour}, so the hour is {hour}.",
                        "The long hand counts minutes in fives. Count round from the 12 "
                        f"and you reach {minute}.",
                    ],
                    canonical_solution={
                        "steps": [
                            {
                                "step_number": 1,
                                "explanation": "Read the short hand for the hour.",
                                "expression": f"hour = {hour}",
                                "common_mistake": "reading the long hand as the hour",
                            },
                            {
                                "step_number": 2,
                                "explanation": "Count the long hand round in fives.",
                                "expression": f"minute = {minute}",
                                "common_mistake": None,
                            },
                        ],
                        "final_answer": correct,
                    },
                    estimated_time_seconds=45,
                    common_error_tags=["swapped_hands", "read_minute_as_number"],
                    generator_model="authored-figure-script",
                    random_seed=700100 + index,
                    answer_expression=None,
                    figure_spec=ClockFigure(hour=hour, minute=minute),
                    figure_reading="clock_time",
                ),
                None,
            )
        )
    return out


# --------------------------------------------------------------------------------------
# Bar charts — `data_graphs`
# --------------------------------------------------------------------------------------
# (title, categories, values, question kind, tier)
_CHARTS = [
    ("Books read this month", ["Ana", "Ben", "Cara", "Dan"], [12, 8, 15, 6], "most", 1),
    ("Goals scored", ["Lions", "Tigers", "Bears", "Wolves"], [7, 11, 4, 9], "most", 1),
    ("Cups sold", ["Mon", "Tue", "Wed", "Thu"], [24, 31, 18, 27], "least", 2),
    ("Trees planted", ["North", "South", "East", "West"], [45, 30, 60, 25], "difference", 3),
    ("Tickets sold", ["Fri", "Sat", "Sun"], [120, 185, 140], "total", 4),
    ("Rainfall in mm", ["Apr", "May", "Jun", "Jul"], [55, 40, 75, 20], "difference", 4),
    # D-288: data_graphs sat at d2:1, d3:1 and no d5 at all, below the 2-per-tier serving
    # floor. Four categories on the "least" row deliberately - three would trigger the
    # option-padding path, and a padded duplicate label fails `check_unique_options`.
    ("Stickers collected", ["Mia", "Noah", "Ori", "Pia"], [16, 9, 13, 11], "least", 2),
    ("Laps swum", ["Week 1", "Week 2", "Week 3", "Week 4"], [14, 22, 8, 17], "difference", 3),
    ("Cans recycled", ["Grade 3", "Grade 4", "Grade 5"], [135, 168, 149], "total", 5),
    ("Minutes practised", ["Mon", "Tue", "Wed", "Thu", "Fri"], [35, 50, 20, 45, 40], "difference", 5),
]


def _chart_items() -> list[tuple[AuthoredTemplateDef, object]]:
    out = []
    for index, (title, cats, values, kind, tier) in enumerate(_CHARTS):
        if kind == "most":
            stem = f"The chart shows {title.lower()}. Which one is the highest?"
            answer = cats[values.index(max(values))]
            options = list(cats)
            expression = f"Eq(x, Max({', '.join(str(v) for v in values)}))"
            # The answer is the LABEL, so the solution must end on the label too -
            # `check_hint_solution_answer_agreement` compares the two.
            final = answer
        elif kind == "least":
            stem = f"The chart shows {title.lower()}. Which one is the lowest?"
            answer = cats[values.index(min(values))]
            options = list(cats)
            expression = f"Eq(x, Min({', '.join(str(v) for v in values)}))"
            final = answer
        elif kind == "difference":
            top, bottom = max(values), min(values)
            stem = (
                f"The chart shows {title.lower()}. How much more is the highest than "
                f"the lowest?"
            )
            answer = str(top - bottom)
            options = [answer, str(top + bottom), str(top), str(bottom)]
            expression = f"Eq(x, {top} - {bottom})"
            final = answer
        else:  # total
            stem = f"The chart shows {title.lower()}. What is the total?"
            answer = str(sum(values))
            options = [answer, str(sum(values) - min(values)), str(max(values)), str(len(values))]
            expression = f"Eq(x, {' + '.join(str(v) for v in values)})"
            final = answer

        while len(options) < 4:
            options.append(f"{options[0]} ")
        options = options[:4]
        shift = index % 4
        rotated = options[-shift:] + options[:-shift] if shift else options
        label = "abcd"[rotated.index(answer)]
        out.append(
            (
                AuthoredTemplateDef(
                    question_template_id=f"figure-data_graphs-d{tier}-{710100 + index}",
                    topic_id="data_graphs",
                    skill_id="graph_read_bar_chart",
                    grade_band="2-3",
                    difficulty_label=tier,
                    rendered_question=stem,
                    stem=stem,
                    option_a=rotated[0],
                    option_b=rotated[1],
                    option_c=rotated[2],
                    option_d=rotated[3],
                    correct_option=label,
                    hint_ladder=[
                        "Look along the bottom to find each bar, then read its height.",
                        "Write down the height of every bar before comparing them.",
                        (
                            "Compare the heights you wrote down and pick out the one the "
                            "question asks about."
                            if kind in ("most", "least")
                            else "Find the tallest and shortest bars first, then do the "
                            "arithmetic the question asks for."
                        ),
                    ],
                    canonical_solution={
                        "steps": [
                            {
                                "step_number": 1,
                                "explanation": "Read the height of each bar from the scale.",
                                "expression": ", ".join(str(v) for v in values),
                                "common_mistake": "reading the label instead of the height",
                            },
                            {
                                "step_number": 2,
                                "explanation": "Compare or combine them as the question asks.",
                                "expression": expression,
                                "common_mistake": None,
                            },
                        ],
                        "final_answer": final,
                    },
                    estimated_time_seconds=60,
                    common_error_tags=["read_wrong_bar", "ignored_scale"],
                    generator_model="authored-figure-script",
                    random_seed=710100 + index,
                    answer_expression=None if kind in ("most", "least") else expression,
                    figure_reading=(
                        "chart_max_label"
                        if kind == "most"
                        else "chart_min_label"
                        if kind == "least"
                        else None
                    ),
                    figure_spec=BarChartFigure(
                        title=title,
                        axis_label="",
                        categories=cats,
                        values=[float(v) for v in values],
                    ),
                ),
                None,
            )
        )
    return out


# --------------------------------------------------------------------------------------
# Labelled shapes — `plane_figures`
# --------------------------------------------------------------------------------------
_SHAPES = [
    ("rectangle", [8.0, 5.0], "cm", "area", 1),
    ("rectangle", [12.0, 7.0], "cm", "perimeter", 2),
    ("triangle", [6.0, 8.0, 10.0], "cm", "perimeter", 2),
    ("triangle", [9.0, 12.0, 15.0], "cm", "right", 3),
    ("parallelogram", [10.0, 6.0], "cm", "area", 3),
    ("trapezoid", [8.0, 12.0, 5.0], "cm", "area", 4),
    ("circle", [7.0], "cm", "circumference", 4),
    ("circle", [5.0], "cm", "area", 5),
    # D-288: plane_figures sat at d1:1, d5:1, below the 2-per-tier serving floor. [9, 4]
    # rather than [6, 3] deliberately: a 6x3 rectangle's area and perimeter are both 18,
    # and the distractor set would collide with itself.
    ("rectangle", [9.0, 4.0], "cm", "area", 1),
    ("trapezoid", [6.0, 10.0, 4.0], "cm", "area", 5),
]


def _shape_items() -> list[tuple[AuthoredTemplateDef, object]]:
    out = []
    for index, (shape, sides, unit, kind, tier) in enumerate(_SHAPES):
        if kind == "area" and shape == "rectangle":
            value, expr = sides[0] * sides[1], f"Eq(x, {sides[0]:g} * {sides[1]:g})"
            stem = "The rectangle is labelled with its two side lengths. What is its area?"
            unit_text = f"square {unit}"
        elif kind == "perimeter" and shape == "rectangle":
            value = 2 * (sides[0] + sides[1])
            expr = f"Eq(x, 2 * ({sides[0]:g} + {sides[1]:g}))"
            stem = "The rectangle is labelled with its two side lengths. What is its perimeter?"
            unit_text = unit
        elif kind == "perimeter":
            value = sum(sides)
            expr = f"Eq(x, {' + '.join(f'{s:g}' for s in sides)})"
            stem = "The triangle is labelled with all three side lengths. What is its perimeter?"
            unit_text = unit
        elif kind == "right":
            value = sides[0] * sides[1] / 2
            expr = f"Eq(x, {sides[0]:g} * {sides[1]:g} / 2)"
            stem = (
                "The triangle has a right angle between its two shorter sides, which are "
                "labelled. What is its area?"
            )
            unit_text = f"square {unit}"
        elif kind == "area" and shape == "parallelogram":
            value, expr = sides[0] * sides[1], f"Eq(x, {sides[0]:g} * {sides[1]:g})"
            stem = "The parallelogram is labelled with its base and its height. What is its area?"
            unit_text = f"square {unit}"
        elif kind == "area" and shape == "trapezoid":
            value = (sides[0] + sides[1]) / 2 * sides[2]
            expr = f"Eq(x, ({sides[0]:g} + {sides[1]:g}) / 2 * {sides[2]:g})"
            stem = (
                "The trapezoid is labelled with its two parallel sides and its height. "
                "What is its area?"
            )
            unit_text = f"square {unit}"
        elif kind == "circumference":
            value = round(2 * 3.14 * sides[0], 2)
            expr = f"Eq(x, 2 * 3.14 * {sides[0]:g})"
            stem = (
                "The circle is labelled with its radius. What is its circumference? "
                "Use 3.14 for pi."
            )
            unit_text = unit
        else:  # circle area
            value = round(3.14 * sides[0] ** 2, 2)
            expr = f"Eq(x, 3.14 * {sides[0]:g}**2)"
            stem = "The circle is labelled with its radius. What is its area? Use 3.14 for pi."
            unit_text = f"square {unit}"

        answer = f"{value:g} {unit_text}"
        wrong = [value * 2, value / 2, value + sides[0]]
        options = [answer] + [f"{w:g} {unit_text}" for w in wrong]
        shift = index % 4
        rotated = options[-shift:] + options[:-shift] if shift else options
        label = "abcd"[rotated.index(answer)]
        out.append(
            (
                AuthoredTemplateDef(
                    question_template_id=f"figure-plane_figures-d{tier}-{720100 + index}",
                    topic_id="plane_figures",
                    skill_id="figure_measure_shape",
                    grade_band="4-5",
                    difficulty_label=tier,
                    rendered_question=stem,
                    stem=stem,
                    option_a=rotated[0],
                    option_b=rotated[1],
                    option_c=rotated[2],
                    option_d=rotated[3],
                    correct_option=label,
                    hint_ladder=[
                        "Read the labels on the figure before choosing what to calculate.",
                        f"The measurements shown are {', '.join(f'{s:g}' for s in sides)} {unit}.",
                        "Use the rule for this shape, then check the units of your answer.",
                    ],
                    canonical_solution={
                        "steps": [
                            {
                                "step_number": 1,
                                "explanation": "Read the labelled measurements from the figure.",
                                "expression": ", ".join(f"{s:g}" for s in sides),
                                "common_mistake": "using a length the figure does not label",
                            },
                            {
                                "step_number": 2,
                                "explanation": "Apply the rule for this shape.",
                                "expression": expr,
                                "common_mistake": None,
                            },
                        ],
                        "final_answer": answer,
                    },
                    estimated_time_seconds=90,
                    common_error_tags=["wrong_formula", "doubled_the_answer"],
                    generator_model="authored-figure-script",
                    random_seed=720100 + index,
                    answer_expression=expr,
                    figure_spec=ShapeFigure(
                        shape=shape, side_lengths=sides, unit=unit
                    ),
                ),
                None,
            )
        )
    return out


# --------------------------------------------------------------------------------------
# Coordinate grids — `coordinate_geometry`
# --------------------------------------------------------------------------------------
_GRIDS = [
    ([(3.0, 2.0)], ["P"], "name", 1),
    ([(-4.0, 1.0)], ["Q"], "name", 2),
    ([(2.0, -3.0)], ["R"], "name", 2),
    ([(1.0, 1.0), (5.0, 1.0)], ["A", "B"], "distance", 3),
    ([(-2.0, 4.0), (-2.0, -1.0)], ["C", "D"], "distance", 3),
    ([(0.0, 0.0), (4.0, 0.0), (4.0, 3.0)], ["X", "Y", "Z"], "hypotenuse", 5),
    # D-288: coordinate_geometry sat at d1:1, d5:1 with no d4 at all, below the 2-per-tier
    # serving floor. One vertical and one horizontal distance at d4, so the tier tests both
    # reading directions rather than the same one twice.
    ([(2.0, 5.0)], ["S"], "name", 1),
    ([(3.0, -2.0), (3.0, 4.0)], ["E", "F"], "distance", 4),
    ([(-3.0, -1.0), (2.0, -1.0)], ["G", "H"], "distance", 4),
    ([(0.0, 0.0), (6.0, 0.0), (6.0, 8.0)], ["K", "L", "M"], "hypotenuse", 5),
]


def _grid_items() -> list[tuple[AuthoredTemplateDef, object]]:
    out = []
    for index, (points, labels, kind, tier) in enumerate(_GRIDS):
        if kind == "name":
            (px, py) = points[0]
            answer = f"({px:g}, {py:g})"
            stem = f"What are the coordinates of point {labels[0]}?"
            options = [answer, f"({py:g}, {px:g})", f"({-px:g}, {py:g})", f"({px:g}, {-py:g})"]
            expr = f"Eq(x, {px:g} + {py:g})"
            final = answer
        elif kind == "distance":
            (x1, y1), (x2, y2) = points
            d = abs(x2 - x1) + abs(y2 - y1)
            answer = f"{d:g} units"
            stem = f"How far apart are points {labels[0]} and {labels[1]}?"
            options = [answer, f"{d * 2:g} units", f"{d / 2:g} units", f"{d + 1:g} units"]
            expr = f"Eq(x, {abs(x2 - x1):g} + {abs(y2 - y1):g})"
            final = answer
        else:  # hypotenuse
            (_, _), (x2, _), (_, y3) = points
            d = (x2**2 + y3**2) ** 0.5
            answer = f"{d:g} units"
            stem = (
                f"Points {labels[0]}, {labels[1]} and {labels[2]} form a right triangle. "
                f"How long is the side from {labels[0]} to {labels[2]}?"
            )
            options = [answer, f"{x2 + y3:g} units", f"{x2:g} units", f"{y3:g} units"]
            expr = f"Eq(x, sqrt({x2:g}**2 + {y3:g}**2))"
            final = answer

        shift = index % 4
        rotated = options[-shift:] + options[:-shift] if shift else options
        label = "abcd"[rotated.index(answer)]
        segments = [(i, i + 1) for i in range(len(points) - 1)]
        out.append(
            (
                AuthoredTemplateDef(
                    question_template_id=f"figure-coordinate_geometry-d{tier}-{730100 + index}",
                    topic_id="coordinate_geometry",
                    skill_id="coordinate_read_plot",
                    grade_band="6-7",
                    difficulty_label=tier,
                    rendered_question=stem,
                    stem=stem,
                    option_a=rotated[0],
                    option_b=rotated[1],
                    option_c=rotated[2],
                    option_d=rotated[3],
                    correct_option=label,
                    hint_ladder=[
                        "Start at the origin and read across before you read up or down.",
                        "The first number is how far across, the second is how far up.",
                        "Count the grid lines carefully, including any that are negative.",
                    ],
                    canonical_solution={
                        "steps": [
                            {
                                "step_number": 1,
                                "explanation": "Read each point off the grid, across then up.",
                                "expression": " ".join(
                                    f"({px:g}, {py:g})" for px, py in points
                                ),
                                "common_mistake": "reading up before across",
                            },
                            {
                                "step_number": 2,
                                "explanation": "Answer what the question asks about them.",
                                "expression": expr,
                                "common_mistake": None,
                            },
                        ],
                        "final_answer": final,
                    },
                    estimated_time_seconds=75,
                    common_error_tags=["swapped_coordinates", "miscounted_grid_lines"],
                    generator_model="authored-figure-script",
                    random_seed=730100 + index,
                    answer_expression=None if kind == "name" else expr,
                    figure_reading="point_coordinates" if kind == "name" else None,
                    figure_spec=CoordinateGridFigure(
                        points=points, point_labels=labels, segments=segments
                    ),
                ),
                None,
            )
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate only; write nothing")
    args = parser.parse_args()

    by_topic: dict[str, list[AuthoredTemplateDef]] = {}
    for definition, _ in [*_clock_items(), *_chart_items(), *_shape_items(), *_grid_items()]:
        by_topic.setdefault(definition.topic_id, []).append(definition)

    failures = 0
    for topic, definitions in sorted(by_topic.items()):
        for definition in definitions:
            result = validate_authored_item(
                definition.difficulty_label,
                definition.to_generated_item(),
                figure=definition.figure_spec,
                figure_reading=definition.figure_reading,
            )
            if not result.passed:
                failures += 1
                print(f"FAIL {definition.question_template_id}: {result.failures}")
        print(f"{topic:24s} {len(definitions):3d} items")

    if failures:
        print(f"\n{failures} item(s) failed the gate - nothing written")
        return 1
    if args.check:
        print("\nall items pass; --check so nothing written")
        return 0

    for topic, definitions in sorted(by_topic.items()):
        path = BANK / f"{topic}.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    # The loader reads this as a versioned bank file; the header shape has
                    # to match what `question-export` writes or the file will not parse.
                    "curriculum_version": CURRICULUM_VERSION,
                    "topic_id": topic,
                    "templates": [
                        d.model_dump(mode="json", exclude_none=False) for d in definitions
                    ],
                },
                sort_keys=False,
                width=100,
                allow_unicode=True,
            )
        )
        print(f"wrote {len(definitions):3d} items to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
