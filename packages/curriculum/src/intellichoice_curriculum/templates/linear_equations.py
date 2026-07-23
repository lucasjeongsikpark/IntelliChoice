"""Hand-authored seed templates for the linear_equations topic (SPEC §5.8.1, D-003).

10 templates per difficulty (50 total), each difficulty tier built from the skill
ladder in curriculum/internal_math/skills.yaml. Every template reuses one of the
shapes registered in templates/registry.py with different numeric ranges — the
shape math guarantees an exact integer answer, and the shared distractor set models
three common error types (sign flip, off-by-one, magnitude error).

The full 100-per-topic volume target (SPEC §5.8.1) and the other two seeded topics
are filled in later by the S9 AI-generation pipeline; this is the deterministic
seed bank that unblocks S5/S6.
"""

from intellichoice_curriculum.templates.model import QuestionTemplateDef

_DISTRACTOR_GENERATORS = ["distractor_sign_flip", "distractor_off_by_one", "distractor_scaled"]
_COMMON_ERROR_TAGS = ["sign_error", "off_by_one", "magnitude_error"]


def _tpl(
    *,
    skill_id: str,
    difficulty: int,
    shape: str,
    parameter_schema: dict,
    estimated_time_seconds: int,
) -> QuestionTemplateDef:
    return QuestionTemplateDef(
        topic_id="linear_equations",
        skill_id=skill_id,
        grade_band="6-7",
        difficulty_label=difficulty,
        parameter_schema=parameter_schema,
        generation_constraints={
            "x_is_integer": True,
            "unique_distractors": True,
            "no_division_by_zero": True,
        },
        solution_function=shape,
        correct_option_generator="format_integer",
        distractor_generators=_DISTRACTOR_GENERATORS,
        common_error_tags=_COMMON_ERROR_TAGS,
        estimated_time_seconds=estimated_time_seconds,
    )


def _bounds(min_: int, max_: int, exclude: list[int] | None = None) -> dict:
    spec: dict = {"min": min_, "max": max_}
    if exclude:
        spec["exclude"] = exclude
    return spec


# --- Difficulty 1: linear_one_step -------------------------------------------
_DIFFICULTY_1 = [
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_add",
        parameter_schema={"b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=25,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_add",
        parameter_schema={"b": _bounds(10, 20), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=25,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_sub",
        parameter_schema={"b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=25,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_sub",
        parameter_schema={"b": _bounds(10, 20), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=25,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_mul",
        parameter_schema={"a": _bounds(2, 9, [0, 1]), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=30,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_mul",
        parameter_schema={"a": _bounds(-9, -2), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=30,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_add",
        parameter_schema={"b": _bounds(1, 20), "x": _bounds(-9, -1)},
        estimated_time_seconds=30,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_sub",
        parameter_schema={"b": _bounds(1, 20), "x": _bounds(-9, -1)},
        estimated_time_seconds=30,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_mul",
        parameter_schema={"a": _bounds(2, 12, [0, 1]), "x": _bounds(-9, -1)},
        estimated_time_seconds=30,
    ),
    _tpl(
        skill_id="linear_one_step",
        difficulty=1,
        shape="one_step_mul",
        parameter_schema={"a": _bounds(-12, -2), "x": _bounds(-9, -1)},
        estimated_time_seconds=30,
    ),
]


# --- Difficulty 2: linear_two_step -------------------------------------------
_DIFFICULTY_2 = [
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step",
        parameter_schema={"a": _bounds(2, 9, [0]), "b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=40,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step_sub_b",
        parameter_schema={"a": _bounds(2, 9, [0]), "b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=40,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step",
        parameter_schema={"a": _bounds(-9, -2), "b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=40,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step_sub_b",
        parameter_schema={"a": _bounds(-9, -2), "b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=40,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step",
        parameter_schema={"a": _bounds(2, 9, [0]), "b": _bounds(10, 20), "x": _bounds(-9, -1)},
        estimated_time_seconds=45,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step_sub_b",
        parameter_schema={"a": _bounds(2, 9, [0]), "b": _bounds(10, 20), "x": _bounds(-9, -1)},
        estimated_time_seconds=45,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step",
        parameter_schema={
            "a": _bounds(2, 12, [0]),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=45,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step_sub_b",
        parameter_schema={
            "a": _bounds(2, 12, [0]),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=45,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step",
        parameter_schema={
            "a": _bounds(-12, -2),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=45,
    ),
    _tpl(
        skill_id="linear_two_step",
        difficulty=2,
        shape="two_step_sub_b",
        parameter_schema={
            "a": _bounds(-12, -2),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=45,
    ),
]


# --- Difficulty 3: linear_neg_frac_coeff -------------------------------------
_DIFFICULTY_3 = [
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="frac_coeff",
        parameter_schema={
            "d": _bounds(2, 4, [0, 1]),
            "b": _bounds(1, 9),
            "x_over_d": _bounds(1, 9, [0]),
        },
        estimated_time_seconds=50,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="neg_coeff",
        parameter_schema={"a": _bounds(2, 6, [0]), "b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=50,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="frac_coeff",
        parameter_schema={
            "d": _bounds(2, 4, [0, 1]),
            "b": _bounds(10, 20),
            "x_over_d": _bounds(-9, -1),
        },
        estimated_time_seconds=50,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="neg_coeff",
        parameter_schema={"a": _bounds(2, 6, [0]), "b": _bounds(10, 20), "x": _bounds(-9, -1)},
        estimated_time_seconds=50,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="frac_coeff",
        parameter_schema={
            "d": _bounds(2, 6, [0, 1]),
            "b": _bounds(1, 9),
            "x_over_d": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=55,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="neg_coeff",
        parameter_schema={"a": _bounds(2, 9, [0]), "b": _bounds(1, 9), "x": _bounds(-9, 9, [0])},
        estimated_time_seconds=55,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="frac_coeff",
        parameter_schema={
            "d": _bounds(3, 6, [0, 1]),
            "b": _bounds(1, 20),
            "x_over_d": _bounds(1, 9, [0]),
        },
        estimated_time_seconds=55,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="neg_coeff",
        parameter_schema={"a": _bounds(3, 9, [0]), "b": _bounds(1, 20), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=55,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="frac_coeff",
        parameter_schema={
            "d": _bounds(2, 5, [0, 1]),
            "b": _bounds(1, 9),
            "x_over_d": _bounds(-9, -1),
        },
        estimated_time_seconds=55,
    ),
    _tpl(
        skill_id="linear_neg_frac_coeff",
        difficulty=3,
        shape="neg_coeff",
        parameter_schema={"a": _bounds(2, 9, [0]), "b": _bounds(1, 9), "x": _bounds(-9, -1)},
        estimated_time_seconds=55,
    ),
]


# --- Difficulty 4: linear_both_sides -----------------------------------------
_DIFFICULTY_4 = [
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides",
        parameter_schema={
            "a": _bounds(2, 9, [0]),
            "d": _bounds(2, 9, [0]),
            "b": _bounds(1, 9),
            "x": _bounds(1, 9, [0]),
        },
        estimated_time_seconds=60,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides_alt",
        parameter_schema={
            "a": _bounds(2, 9, [0]),
            "d": _bounds(2, 9, [0]),
            "b": _bounds(1, 9),
            "x": _bounds(1, 9, [0]),
        },
        estimated_time_seconds=60,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides",
        parameter_schema={
            "a": _bounds(-9, -2),
            "d": _bounds(2, 9, [0]),
            "b": _bounds(1, 9),
            "x": _bounds(1, 9, [0]),
        },
        estimated_time_seconds=60,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides_alt",
        parameter_schema={
            "a": _bounds(-9, -2),
            "d": _bounds(2, 9, [0]),
            "b": _bounds(1, 9),
            "x": _bounds(1, 9, [0]),
        },
        estimated_time_seconds=60,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides",
        parameter_schema={
            "a": _bounds(2, 9, [0]),
            "d": _bounds(-9, -2),
            "b": _bounds(1, 20),
            "x": _bounds(-9, -1),
        },
        estimated_time_seconds=65,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides_alt",
        parameter_schema={
            "a": _bounds(2, 9, [0]),
            "d": _bounds(-9, -2),
            "b": _bounds(1, 20),
            "x": _bounds(-9, -1),
        },
        estimated_time_seconds=65,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides",
        parameter_schema={
            "a": _bounds(2, 12, [0]),
            "d": _bounds(2, 12, [0]),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=65,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides_alt",
        parameter_schema={
            "a": _bounds(2, 12, [0]),
            "d": _bounds(2, 12, [0]),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=65,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides",
        parameter_schema={
            "a": _bounds(-12, -2),
            "d": _bounds(2, 12, [0]),
            "b": _bounds(1, 9),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=65,
    ),
    _tpl(
        skill_id="linear_both_sides",
        difficulty=4,
        shape="both_sides_alt",
        parameter_schema={
            "a": _bounds(-12, -2),
            "d": _bounds(2, 12, [0]),
            "b": _bounds(1, 9),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=65,
    ),
]


# --- Difficulty 5: linear_distribute -----------------------------------------
_DIFFICULTY_5 = [
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_simple",
        parameter_schema={"a": _bounds(2, 9, [0]), "b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=70,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_combine",
        parameter_schema={
            "a": _bounds(2, 6, [0]),
            "d": _bounds(1, 6, [0]),
            "b": _bounds(1, 9),
            "x": _bounds(1, 9, [0]),
        },
        estimated_time_seconds=75,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_simple",
        parameter_schema={"a": _bounds(-9, -2), "b": _bounds(1, 9), "x": _bounds(1, 9, [0])},
        estimated_time_seconds=70,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_combine",
        parameter_schema={
            "a": _bounds(2, 6, [0]),
            "d": _bounds(-6, -1),
            "b": _bounds(1, 9),
            "x": _bounds(1, 9, [0]),
        },
        estimated_time_seconds=75,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_simple",
        parameter_schema={"a": _bounds(2, 9, [0]), "b": _bounds(1, 20), "x": _bounds(-9, -1)},
        estimated_time_seconds=75,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_combine",
        parameter_schema={
            "a": _bounds(2, 9, [0]),
            "d": _bounds(1, 9, [0]),
            "b": _bounds(1, 20),
            "x": _bounds(-9, -1),
        },
        estimated_time_seconds=80,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_simple",
        parameter_schema={
            "a": _bounds(2, 12, [0]),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=80,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_combine",
        parameter_schema={
            "a": _bounds(2, 9, [0]),
            "d": _bounds(-9, -1),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=80,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_simple",
        parameter_schema={
            "a": _bounds(-12, -2),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=80,
    ),
    _tpl(
        skill_id="linear_distribute",
        difficulty=5,
        shape="distribute_combine",
        parameter_schema={
            "a": _bounds(-9, -2),
            "d": _bounds(2, 9, [0]),
            "b": _bounds(1, 20),
            "x": _bounds(-9, 9, [0]),
        },
        estimated_time_seconds=80,
    ),
]


LINEAR_EQUATIONS_TEMPLATES: list[QuestionTemplateDef] = (
    _DIFFICULTY_1 + _DIFFICULTY_2 + _DIFFICULTY_3 + _DIFFICULTY_4 + _DIFFICULTY_5
)
