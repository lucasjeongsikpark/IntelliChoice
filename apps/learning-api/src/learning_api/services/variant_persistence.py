"""Shared variant-generation + persistence step used by both the pre/post-exam builder
and the study-plan builder (SPEC §5.8.1, §5.8.6 generation; §5.13.1 parallel-form seed).
"""

import random
from typing import cast

from intellichoice_curriculum.generation import generate_variant
from intellichoice_curriculum.templates.registry import ParameterSchema
from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_RUNTIME,
    QuestionTemplate,
    QuestionVariant,
)
from intellichoice_db.repositories.questions import QuestionRepository

_MAX_REGENERATION_ATTEMPTS = 20
_MAX_SEED = 2**31 - 1


async def generate_and_store_variant(
    *,
    question_repo: QuestionRepository,
    template: QuestionTemplate,
    rng: random.Random,
    avoid_rendered_question: str | None = None,
) -> QuestionVariant:
    """Generates one variant of `template`. When `avoid_rendered_question` is set (the
    post-exam parallel-form case, SPEC §5.13.2 "do not reuse the exact same question
    variant"), retries with a new seed until the rendering differs, up to a bound.
    """
    candidate = generate_variant(
        shape_key=template.solution_function,
        parameter_schema=cast(ParameterSchema, template.parameter_schema),
        correct_option_generator=template.correct_option_generator,
        distractor_generator_keys=template.distractor_generators,
        seed=rng.randint(0, _MAX_SEED),
    )
    attempts = 1
    while (
        avoid_rendered_question is not None
        and candidate.rendered_question == avoid_rendered_question
        and attempts < _MAX_REGENERATION_ATTEMPTS
    ):
        candidate = generate_variant(
            shape_key=template.solution_function,
            parameter_schema=cast(ParameterSchema, template.parameter_schema),
            correct_option_generator=template.correct_option_generator,
            distractor_generator_keys=template.distractor_generators,
            seed=rng.randint(0, _MAX_SEED),
        )
        attempts += 1

    return await question_repo.create_variant(
        QuestionVariant(
            # One row per question served, so this is the unbounded population and must
            # never enter SPEC §5.8.3's dedup check (D-106). Matches the column default;
            # stated anyway because this is the write site that made the difference.
            origin=VARIANT_ORIGIN_RUNTIME,
            question_template_id=template.question_template_id,
            random_seed=candidate.random_seed,
            rendered_question=candidate.rendered_question,
            option_a=candidate.option_a,
            option_b=candidate.option_b,
            option_c=candidate.option_c,
            option_d=candidate.option_d,
            correct_option=candidate.correct_option,
            parameter_values=candidate.parameter_values,
        )
    )
