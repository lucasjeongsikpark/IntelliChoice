"""SPEC §5.8.5 automated validation suite — deterministic/executable checks every
question variant must pass before its template is activated. Reusable by the S9
AI-generation pipeline, not just the S4 hand-authored loader.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from intellichoice_curriculum.authored_validation import disallowed_wording_found
from intellichoice_curriculum.content import CurriculumContent
from intellichoice_curriculum.generation import GeneratedVariant
from intellichoice_curriculum.templates.model import QuestionTemplateDef
from intellichoice_curriculum.templates.registry import CORRECT_OPTION_GENERATORS, SHAPES

MAX_ABSOLUTE_PARAMETER_VALUE = 999
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
_OPTION_LABELS = ("a", "b", "c", "d")


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
    """A coefficient in the question coincidentally matching the answer's digits is normal
    (e.g. "x + 7 = 14" can have answer 7); what must never happen is the stem literally
    stating the solved value, e.g. a template bug rendering "... x = 7 ..." into the
    question text. So the match is *anchored* to an assignment to x rather than looking for
    the answer anywhere — which is the difference between this and `answer_text_leaked`, and
    the reason the two cannot share one matcher.

    D-223: the anchor was there, but the match after it was a bare substring, so any answer
    that is a prefix of the number actually printed was read as a leak — "Solve for x:
    10x = -60" with answer "-6" contains "x = -6". Measured at **2.36% of the population
    `ai_pipeline` puts through this gate** (52 of 2 200), and on that path a failure returns
    `PipelineOutcome(status="rejected", cost_cents=total_cost)`: the generator call is
    already paid for and the item is binned before the solver calls. On the loader path it
    raises `CurriculumLoadError`, which fails the staging deploy's curriculum-load ops task
    (D-206) — latent only because the loader validates one fixed `seed=index` per template,
    so re-ordering the bank re-rolls it.

    The trailing assertions are `answer_text_leaked`'s, for the same reasons its docstring
    gives at length: not another alphanumeric (so "-6" does not match inside "-60"), not the
    integer part of a decimal, and — new here because `format_integer` calls `str()` on a
    `Fraction` — not the numerator of a fraction.

    The *leading* assertion is this check's own, and measurement is what found it: with the
    trailing guards alone the flag rate fell to 0.18% but did not reach zero, and every
    survivor looked like "Solve for x: 6(x + 2) + 1x = -2" with answer "-2" — where "1x = -2"
    is the equation's own right-hand side, which happens to equal the solution. An assignment
    a student could read the answer off is one whose "x" stands alone; a coefficient in front
    of it (`1x`, `6x`) makes it the equation being asked. Hence `(?<![0-9A-Za-z])`.

    Searching the whole rendered question is safe once the match is anchored this way. The old
    code searched only after the first ":" to dodge a collision with the "Solve for x:" prefix;
    an anchor requiring "=" cannot collide with a ":", and not skipping the prefix means a
    prefix that ever does state the answer is caught rather than ignored.
    """
    correct_text = _option_texts(variant)[_OPTION_LABELS.index(variant.correct_option)].strip()
    if not correct_text:
        return
    pattern = re.compile(
        rf"(?<![0-9A-Za-z])x\s*=\s*{re.escape(correct_text)}(?![0-9A-Za-z])(?!\.\d)(?!/\d)",
        re.IGNORECASE,
    )
    if pattern.search(variant.rendered_question):
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
    """Shares `authored_validation`'s matcher and list (D-223). It used to keep its own
    four-word tuple matched with `in`, i.e. the rule D-191 replaced on the authored side
    after substring matching destroyed a question about rolling a die — "skill" contains
    "kill", "studies" and "diet" contain "die". Unreachable today, because every shipped
    shape renders a bare equation with no prose to trip it; kept correct anyway, since
    "the same check, fixed in one copy only" is exactly what this session found twice.
    """
    for word in disallowed_wording_found(variant.rendered_question):
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
