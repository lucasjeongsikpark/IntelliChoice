from intellichoice_curriculum.generation import VariantGenerationError, generate_variant
from intellichoice_curriculum.templates.linear_equations import LINEAR_EQUATIONS_TEMPLATES

_TWO_STEP_TEMPLATE = next(
    t for t in LINEAR_EQUATIONS_TEMPLATES if t.solution_function == "two_step"
)


def _generate(seed: int):
    return generate_variant(
        shape_key=_TWO_STEP_TEMPLATE.solution_function,
        parameter_schema=_TWO_STEP_TEMPLATE.parameter_schema,
        correct_option_generator=_TWO_STEP_TEMPLATE.correct_option_generator,
        distractor_generator_keys=_TWO_STEP_TEMPLATE.distractor_generators,
        seed=seed,
    )


def test_same_seed_produces_an_identical_variant() -> None:
    first = _generate(seed=42)
    second = _generate(seed=42)

    assert first == second


def test_different_seeds_usually_produce_different_variants() -> None:
    variants = {_generate(seed=s).rendered_question for s in range(20)}

    assert len(variants) > 1


def test_unknown_shape_raises() -> None:
    try:
        generate_variant(
            shape_key="not_a_real_shape",
            parameter_schema={},
            correct_option_generator="format_integer",
            distractor_generator_keys=[],
            seed=1,
        )
    except VariantGenerationError:
        return
    raise AssertionError("expected VariantGenerationError")
