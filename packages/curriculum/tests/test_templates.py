from collections import Counter

from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.generation import generate_variant
from intellichoice_curriculum.templates.linear_equations import LINEAR_EQUATIONS_TEMPLATES
from intellichoice_curriculum.validation import validate_variant

CURRICULUM = load_curriculum()


def test_fifty_templates_ten_per_difficulty() -> None:
    assert len(LINEAR_EQUATIONS_TEMPLATES) == 50
    counts = Counter(t.difficulty_label for t in LINEAR_EQUATIONS_TEMPLATES)
    assert counts == {1: 10, 2: 10, 3: 10, 4: 10, 5: 10}


def test_every_template_targets_linear_equations() -> None:
    for template in LINEAR_EQUATIONS_TEMPLATES:
        assert template.topic_id == "linear_equations"


def test_every_loaded_template_passes_the_validation_suite() -> None:
    """SPEC §5.8.5 / S4 'Done when': every template's generated variant passes
    every automated check, with no duplicate rendered questions across the bank.
    """
    seen_questions: set[str] = set()
    failures = []

    for index, template in enumerate(LINEAR_EQUATIONS_TEMPLATES):
        variant = generate_variant(
            shape_key=template.solution_function,
            parameter_schema=template.parameter_schema,
            correct_option_generator=template.correct_option_generator,
            distractor_generator_keys=template.distractor_generators,
            seed=index,
        )
        result = validate_variant(template, variant, CURRICULUM, seen_questions)
        seen_questions.add(variant.rendered_question)
        if not result.passed:
            failures.append((index, template.solution_function, result.failures))

    assert not failures, failures
