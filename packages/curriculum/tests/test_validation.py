"""One test per SPEC §5.8.5 check, each using a deliberately broken fixture so a
regression in the validation suite itself would be caught (not just a broken
template)."""

import dataclasses
import random

import pytest
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.generation import (
    GeneratedVariant,
    VariantGenerationError,
    generate_variant,
)
from intellichoice_curriculum.loader import TEMPLATE_BANKS
from intellichoice_curriculum.templates.model import QuestionTemplateDef
from intellichoice_curriculum.validation import (
    ValidationResult,
    check_age_appropriate_wording,
    check_no_answer_leakage,
    validate_variant,
)

CURRICULUM = load_curriculum()


def _template(**overrides) -> QuestionTemplateDef:
    base = dict(
        topic_id="linear_equations",
        skill_id="linear_one_step",
        grade_band="6-7",
        difficulty_label=1,
        parameter_schema={"b": {"min": 1, "max": 9}, "x": {"min": 1, "max": 9, "exclude": [0]}},
        solution_function="one_step_add",
        correct_option_generator="format_integer",
        distractor_generators=["distractor_sign_flip", "distractor_off_by_one"],
        estimated_time_seconds=25,
    )
    base.update(overrides)
    return QuestionTemplateDef.model_validate(base)


def _variant(**overrides) -> GeneratedVariant:
    # x + 3 = 10 -> x = 7
    base = GeneratedVariant(
        random_seed=1,
        rendered_question="Solve for x: x + 3 = 10",
        option_a="7",
        option_b="6",
        option_c="-7",
        option_d="9",
        correct_option="a",
        parameter_values={"b": 3, "c": 10},
    )
    return dataclasses.replace(base, **overrides)


def test_valid_variant_passes_every_check() -> None:
    result = validate_variant(_template(), _variant(), CURRICULUM, seen_questions=set())
    assert result.passed, result.failures


def test_duplicate_options_fail() -> None:
    result = validate_variant(_template(), _variant(option_b="7"), CURRICULUM)
    assert not result.passed
    assert any("unique" in f for f in result.failures)


def test_correct_option_pointing_at_wrong_value_fails() -> None:
    # option_a is still "7" (the real answer) but correct_option now points at "6".
    result = validate_variant(_template(), _variant(correct_option="b"), CURRICULUM)
    assert not result.passed
    assert any("does not match" in f for f in result.failures)


def test_more_than_one_option_matching_the_answer_fails() -> None:
    result = validate_variant(_template(), _variant(option_b="7"), CURRICULUM)
    assert not result.passed
    assert any("exactly one option" in f for f in result.failures)


def test_division_by_zero_fails() -> None:
    template = _template(solution_function="one_step_mul")
    variant = _variant(parameter_values={"a": 0, "c": 0})
    result = validate_variant(template, variant, CURRICULUM)
    assert not result.passed
    assert any("divide" in f for f in result.failures)


def test_value_out_of_range_fails() -> None:
    result = validate_variant(
        _template(), _variant(parameter_values={"b": 3, "c": 100_000}), CURRICULUM
    )
    assert not result.passed
    assert any("magnitude" in f for f in result.failures)


def test_incomplete_wording_fails() -> None:
    result = validate_variant(
        _template(), _variant(rendered_question="Solve for x: x + {b} = {c}"), CURRICULUM
    )
    assert not result.passed
    assert any("placeholder" in f for f in result.failures)


def test_empty_wording_fails() -> None:
    result = validate_variant(_template(), _variant(rendered_question="   "), CURRICULUM)
    assert not result.passed
    assert any("empty" in f for f in result.failures)


def test_answer_leakage_fails() -> None:
    result = validate_variant(
        _template(), _variant(rendered_question="Solve for x: x + 3 = 10, x = 7"), CURRICULUM
    )
    assert not result.passed
    assert any("leaks" in f for f in result.failures)


def test_duplicate_question_fails() -> None:
    variant = _variant()
    result = validate_variant(
        _template(), variant, CURRICULUM, seen_questions={variant.rendered_question}
    )
    assert not result.passed
    assert any("duplicate" in f for f in result.failures)


def test_difficulty_out_of_range_fails() -> None:
    result = validate_variant(_template(difficulty_label=6), _variant(), CURRICULUM)
    assert not result.passed
    assert any("difficulty_label" in f for f in result.failures)


def test_nonpositive_estimated_time_fails() -> None:
    result = validate_variant(_template(estimated_time_seconds=0), _variant(), CURRICULUM)
    assert not result.passed
    assert any("estimated_time_seconds" in f for f in result.failures)


def test_skill_not_belonging_to_topic_fails() -> None:
    result = validate_variant(
        _template(topic_id="fraction_operations"), _variant(), CURRICULUM
    )
    assert not result.passed
    assert any("does not belong to topic" in f for f in result.failures)


def test_unknown_skill_fails() -> None:
    result = validate_variant(_template(skill_id="not_a_real_skill"), _variant(), CURRICULUM)
    assert not result.passed
    assert any("not in the curriculum taxonomy" in f for f in result.failures)


def test_age_inappropriate_wording_fails() -> None:
    result = validate_variant(
        _template(),
        _variant(rendered_question="Solve for x: this problem is so dumb, x + 3 = 10"),
        CURRICULUM,
    )
    assert not result.passed
    assert any("disallowed wording" in f for f in result.failures)


# --- D-223: the two text checks, scored in both directions -----------------------------
#
# Called directly rather than through `validate_variant`, because a labelled case is a
# *text* case: it pairs a rendering with an answer, and has no shape to recompute from, so
# `check_exactly_one_correct_answer` would reject every one of them for the wrong reason.
# `scripts/measure_shape_gate.py` scores the same two directions over the real generated
# populations; these pin the individual cases that measurement was built to explain.


def _leak_flagged(rendered_question: str, correct_text: str) -> bool:
    result = ValidationResult()
    check_no_answer_leakage(
        _variant(
            rendered_question=rendered_question,
            option_a=correct_text,
            option_b=f"{correct_text} b",
            option_c=f"{correct_text} c",
            option_d=f"{correct_text} d",
            correct_option="a",
        ),
        result,
    )
    return not result.passed


@pytest.mark.parametrize(
    ("rendered_question", "correct_text", "why"),
    [
        ("Solve for x: x + 3 = 10, x = 7", "7", "the solved value appended to the stem"),
        ("Solve for x: 2x = 14 (x=7)", "7", "no spaces around the ="),
        ("Solve for x: 2x = 14  (x  =  7)", "7", "extra spaces around the ="),
        ("Solve for x: 2x = -14, x = -7", "-7", "a negative answer"),
        ("Solve for x: 4x = 2, x = 1/2", "1/2", "a fraction answer"),
        ("Solve for x: x - 1 = 11, so x = 12.", "12", "a sentence-final period"),
    ],
)
def test_a_stated_solution_is_a_leak_in_every_format(
    rendered_question: str, correct_text: str, why: str
) -> None:
    """The direction that must never weaken. A fix aimed at false positives can always
    reach zero by never firing, so the loosening below is only meaningful next to this.
    """
    assert _leak_flagged(rendered_question, correct_text), why


@pytest.mark.parametrize(
    ("rendered_question", "correct_text", "why"),
    [
        ("Solve for x: 11x = -55", "-5", "the case D-222 found live"),
        ("Solve for x: 10x = -60", "-6", "answer is a prefix of the printed number"),
        ("Solve for x: 2x = 70", "7", "answer is a prefix of a positive number"),
        ("Solve for x: x + 5 = 12.5", "12", "answer is a decimal's integer part"),
        ("Solve for x: 2x = 11/2", "11", "answer is a fraction's numerator"),
        ("Solve for x: 6(x + 2) + 1x = -2", "-2", "the equation's own right-hand side"),
        ("Solve for x: x + 7 = 14", "7", "answer equals a given coefficient"),
        ("Solve for x: 5x = 25", "5", "the 'Solve for x:' prefix collision"),
    ],
)
def test_a_coincidence_is_not_a_leak(
    rendered_question: str, correct_text: str, why: str
) -> None:
    """Every case here is a correct, servable question. Before D-223 four of them were
    rejected, which on `ai_pipeline`'s path bins a generator call that has already been
    paid for (2.36% of that population, measured).
    """
    assert not _leak_flagged(rendered_question, correct_text), why


def test_no_variant_of_any_shipped_shape_is_flagged_as_a_leak() -> None:
    """The population test, small enough to live in the suite. `scripts/measure_shape_gate.py`
    runs the same sweep wider and prints what it flags; this only has to fail if a future
    edit reintroduces a systematic false positive.

    A flag here is not a hypothetical: on `loader.py`'s path it raises `CurriculumLoadError`,
    and the staging deploy runs the loader as an ops task on every deploy (D-206).
    """
    rng = random.Random(11)
    flagged = []
    for templates in TEMPLATE_BANKS.values():
        for template in templates:
            for _ in range(20):
                try:
                    variant = generate_variant(
                        shape_key=template.solution_function,
                        parameter_schema=template.parameter_schema,
                        correct_option_generator=template.correct_option_generator,
                        distractor_generator_keys=template.distractor_generators,
                        seed=rng.randint(0, 10**6),
                    )
                except VariantGenerationError:
                    continue
                if _leak_flagged(
                    variant.rendered_question,
                    str(getattr(variant, f"option_{variant.correct_option}")),
                ):
                    flagged.append(variant.rendered_question)
    assert not flagged, f"shipped shapes render questions the leak check rejects: {flagged[:5]}"


@pytest.mark.parametrize(
    "rendered_question",
    [
        "A number cube (die) is rolled and lands on 4. Solve for x: x + 4 = 11",
        "Maya studies for x hours a week. Solve for x: 3x = 12",
        "Her skill at chess improves by x points. Solve for x: x + 5 = 20",
        "The diet plan adds x grams. Solve for x: 2x = 8",
    ],
)
def test_a_word_merely_containing_a_disallowed_word_is_not_flagged(rendered_question: str) -> None:
    """This half of the gate kept its own four-word tuple matched with `in`, i.e. the rule
    D-191 replaced on the authored side after it destroyed a question about rolling a die.
    Both halves now call `disallowed_wording_found`, so a correction to one reaches the other.
    """
    result = ValidationResult()
    check_age_appropriate_wording(_variant(rendered_question=rendered_question), result)
    assert result.passed, result.failures


@pytest.mark.parametrize(
    "rendered_question",
    [
        "A soldier killed x enemies. Solve for x: x + 1 = 4",
        "That is a stupid way to solve for x: x + 1 = 4",
        "The character dies after x turns. Solve for x: x + 1 = 4",
    ],
)
def test_disallowed_wording_is_still_flagged(rendered_question: str) -> None:
    result = ValidationResult()
    check_age_appropriate_wording(_variant(rendered_question=rendered_question), result)
    assert not result.passed
