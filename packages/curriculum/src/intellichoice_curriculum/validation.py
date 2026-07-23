"""SPEC §5.8.5 automated validation suite — deterministic/executable checks every
question variant must pass before its template is activated. Reusable by the S9
AI-generation pipeline, not just the S4 hand-authored loader.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from intellichoice_curriculum.content import CurriculumContent
from intellichoice_curriculum.generation import GeneratedVariant
from intellichoice_curriculum.templates.model import QuestionTemplateDef
from intellichoice_curriculum.templates.registry import CORRECT_OPTION_GENERATORS, SHAPES

MAX_ABSOLUTE_PARAMETER_VALUE = 999
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
_OPTION_LABELS = ("a", "b", "c", "d")
_DISALLOWED_WORDING = ("kill", "die", "stupid", "dumb")


@dataclass
class ValidationResult:
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def fail(self, reason: str) -> None:
        self.failures.append(reason)


def _option_texts(variant: GeneratedVariant) -> list[str]:
    return [variant.option_a, variant.option_b, variant.option_c, variant.option_d]


def check_unique_options(variant: GeneratedVariant, result: ValidationResult) -> None:
    texts = _option_texts(variant)
    if len(set(texts)) != len(texts):
        result.fail("options are not all unique")


def check_exactly_one_correct_answer(
    template: QuestionTemplateDef, variant: GeneratedVariant, result: ValidationResult
) -> None:
    shape = SHAPES[template.solution_function]
    formatter = CORRECT_OPTION_GENERATORS[template.correct_option_generator]
    try:
        recomputed = formatter(shape.solve(variant.parameter_values))
    except (ZeroDivisionError, ValueError) as exc:
        result.fail(f"could not recompute solution: {exc}")
        return

    texts = _option_texts(variant)
    matches = [_OPTION_LABELS[i] for i, text in enumerate(texts) if text == recomputed]
    if len(matches) != 1:
        result.fail(f"expected exactly one option matching the solved answer, found {matches}")
    elif matches[0] != variant.correct_option:
        result.fail(
            f"correct_option={variant.correct_option!r} does not match solved option "
            f"{matches[0]!r}"
        )


def check_no_division_by_zero(
    template: QuestionTemplateDef, variant: GeneratedVariant, result: ValidationResult
) -> None:
    shape = SHAPES[template.solution_function]
    try:
        shape.solve(variant.parameter_values)
    except ZeroDivisionError:
        result.fail("solving the template divides by zero")


def check_values_in_range(variant: GeneratedVariant, result: ValidationResult) -> None:
    for name, value in variant.parameter_values.items():
        if abs(value) > MAX_ABSOLUTE_PARAMETER_VALUE:
            result.fail(f"parameter {name}={value} exceeds allowed magnitude")


def check_complete_wording(variant: GeneratedVariant, result: ValidationResult) -> None:
    question = variant.rendered_question
    if not question.strip():
        result.fail("rendered_question is empty")
    if "{" in question or "}" in question:
        result.fail("rendered_question has an unrendered placeholder")


def check_no_answer_leakage(variant: GeneratedVariant, result: ValidationResult) -> None:
    # A coefficient in the question coincidentally matching the answer's digits is
    # normal (e.g. "x + 7 = 14" can have answer 7); what must never happen is the
    # stem literally stating the solved value, e.g. a template bug that renders
    # "... x = 7 ..." into the question text itself.
    # Only check the equation body, not the "Solve for x:" instruction prefix — that
    # prefix's trailing "x:" would otherwise collide with a leading digit of a
    # coefficient right after it (e.g. "Solve for x: 5x = 25" is not a leak of "5").
    _, _, equation_body = variant.rendered_question.partition(":")
    correct_text = _option_texts(variant)[_OPTION_LABELS.index(variant.correct_option)]
    leak_patterns = (f"x = {correct_text}", f"x={correct_text}")
    if correct_text and any(pattern in equation_body for pattern in leak_patterns):
        result.fail("rendered_question leaks the correct answer text")


def check_no_duplicate_question(
    variant: GeneratedVariant, seen_questions: set[str], result: ValidationResult
) -> None:
    if variant.rendered_question in seen_questions:
        result.fail("duplicate rendered_question across templates")


def check_difficulty_rubric_compliance(
    template: QuestionTemplateDef, result: ValidationResult
) -> None:
    if not (MIN_DIFFICULTY <= template.difficulty_label <= MAX_DIFFICULTY):
        result.fail(f"difficulty_label {template.difficulty_label} out of range")
    if template.estimated_time_seconds <= 0:
        result.fail("estimated_time_seconds must be positive")


def check_topic_and_skill_alignment(
    template: QuestionTemplateDef, curriculum: CurriculumContent, result: ValidationResult
) -> None:
    if template.topic_id not in curriculum.topic_ids():
        result.fail(f"topic_id {template.topic_id!r} is not in the curriculum taxonomy")
        return
    skill_topic_ids = {s.skill_id: s.topic_id for s in curriculum.skills}
    if template.skill_id not in skill_topic_ids:
        result.fail(f"skill_id {template.skill_id!r} is not in the curriculum taxonomy")
    elif skill_topic_ids[template.skill_id] != template.topic_id:
        result.fail(
            f"skill {template.skill_id!r} does not belong to topic {template.topic_id!r}"
        )


def check_age_appropriate_wording(variant: GeneratedVariant, result: ValidationResult) -> None:
    lowered = variant.rendered_question.lower()
    for word in _DISALLOWED_WORDING:
        if word in lowered:
            result.fail(f"rendered_question contains disallowed wording: {word!r}")


def validate_variant(
    template: QuestionTemplateDef,
    variant: GeneratedVariant,
    curriculum: CurriculumContent,
    seen_questions: set[str] | None = None,
) -> ValidationResult:
    """Runs every SPEC §5.8.5 check against one generated variant of a template."""
    result = ValidationResult()
    check_unique_options(variant, result)
    check_exactly_one_correct_answer(template, variant, result)
    check_no_division_by_zero(template, variant, result)
    check_values_in_range(variant, result)
    check_complete_wording(variant, result)
    check_no_answer_leakage(variant, result)
    if seen_questions is not None:
        check_no_duplicate_question(variant, seen_questions, result)
    check_difficulty_rubric_compliance(template, result)
    check_topic_and_skill_alignment(template, curriculum, result)
    check_age_appropriate_wording(variant, result)
    return result
