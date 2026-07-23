"""One test per SPEC §5.8.5 check, each using a deliberately broken fixture so a
regression in the validation suite itself would be caught (not just a broken
template)."""

import dataclasses

from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.generation import GeneratedVariant
from intellichoice_curriculum.templates.model import QuestionTemplateDef
from intellichoice_curriculum.validation import validate_variant

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
