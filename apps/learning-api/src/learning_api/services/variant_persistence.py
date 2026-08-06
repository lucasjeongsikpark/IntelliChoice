"""Shared variant-generation + persistence step used by both the pre/post-exam builder
and the study-plan builder (SPEC §5.8.1, §5.8.6 generation; §5.13.1 parallel-form seed).
"""

import logging
import random
from typing import cast

from intellichoice_curriculum.generation import SHAPES, generate_variant
from intellichoice_curriculum.templates.registry import ParameterSchema
from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_RUNTIME,
    QuestionTemplate,
    QuestionVariant,
)
from intellichoice_db.repositories.questions import QuestionRepository

_MAX_REGENERATION_ATTEMPTS = 20
_MAX_SEED = 2**31 - 1


class StaticVariantUnavailableError(Exception):
    """A template whose content is stored rather than computed was asked to render
    without its canonical variant - see `build_variant_row`.
    """


logger = logging.getLogger(__name__)


def renders_from_canonical_variant(template: QuestionTemplate) -> bool:
    """True when `template`'s content is stored rather than computed.

    S20's authored templates carry `solution_function="authored"`, a
    `parameter_schema` of `{}` and no distractor generators: the item is a fixed piece of
    text with one canonical `QuestionVariant`, not a parameterized shape. Keyed on the
    shape registry rather than on `authoring_mode` so the predicate stays about what can
    actually be rendered - a future authored template registered as a real shape would
    correctly take the generated path.
    """
    return template.solution_function not in SHAPES


def build_variant_row(
    *,
    template: QuestionTemplate,
    rng: random.Random,
    avoid_rendered_question: str | None = None,
    canonical_variant: QuestionVariant | None = None,
) -> QuestionVariant:
    """The pure half of `generate_and_store_variant`: renders one variant of `template`
    and returns an unpersisted row.

    Split out for AUD-F-31 so a builder producing a whole exam can render every variant
    first and then write them in one batch. The RNG is consumed here and only here, so a
    caller that keeps its loop order keeps its exam identical - which is the property the
    deterministic core requires (CLAUDE.md non-negotiable #2).

    `canonical_variant` is required for a statically-rendered template and ignored
    otherwise; see `_static_variant_row` for what "serving" one means and what it costs.
    """
    if renders_from_canonical_variant(template):
        if canonical_variant is None:
            raise StaticVariantUnavailableError(
                f"template {template.question_template_id!r} has solution_function="
                f"{template.solution_function!r}, which has no shape to render from, and "
                f"no canonical variant was supplied to serve instead"
            )
        return _static_variant_row(
            template=template,
            rng=rng,
            canonical_variant=canonical_variant,
            avoid_rendered_question=avoid_rendered_question,
        )
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

    return QuestionVariant(
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


def _static_variant_row(
    *,
    template: QuestionTemplate,
    rng: random.Random,
    canonical_variant: QuestionVariant,
    avoid_rendered_question: str | None,
) -> QuestionVariant:
    """Serve a stored item: copy the canonical variant's content into a fresh runtime row.

    **This is where the post-exam's parallel form is knowingly given up** (D-189, the
    user's call). An authored template has exactly one rendering, so when the post-exam
    asks for "the same template, a rendering that isn't the pre-exam's", there is no other
    rendering to give and the student sees the identical question twice.

    Two reasons that is acceptable rather than a regression. SPEC §5.13.2 forbids reusing
    the same question *variant*, and this does mint a new row per serving. And the
    generated path already gives up: `build_variant_row` retries a bounded number of times
    and then returns the colliding rendering anyway, so "the post-exam may repeat an item"
    was already reachable, just rarely. What changes is that it becomes systematic for
    authored content, which is why the collision is logged rather than passed over - the
    frequency should be measurable before anyone decides it is fine.

    The RNG is still drawn from so that a caller's per-item consumption does not depend on
    which kind of template it happened to sample; the value is recorded as the row's seed
    for provenance, and is not used to render anything.
    """
    seed = rng.randint(0, _MAX_SEED)
    if (
        avoid_rendered_question is not None
        and canonical_variant.rendered_question == avoid_rendered_question
    ):
        logger.info(
            "static_variant_repeats_rendering",
            extra={
                "question_template_id": template.question_template_id,
                "topic_id": template.topic_id,
                "skill_id": template.skill_id,
                "difficulty_label": template.difficulty_label,
            },
        )
    return QuestionVariant(
        origin=VARIANT_ORIGIN_RUNTIME,
        question_template_id=template.question_template_id,
        random_seed=seed,
        rendered_question=canonical_variant.rendered_question,
        option_a=canonical_variant.option_a,
        option_b=canonical_variant.option_b,
        option_c=canonical_variant.option_c,
        option_d=canonical_variant.option_d,
        correct_option=canonical_variant.correct_option,
        parameter_values=canonical_variant.parameter_values,
    )


async def generate_and_store_variant(
    *,
    question_repo: QuestionRepository,
    template: QuestionTemplate,
    rng: random.Random,
    avoid_rendered_question: str | None = None,
) -> QuestionVariant:
    """Generates one variant of `template` and persists it immediately. When
    `avoid_rendered_question` is set (the post-exam parallel-form case, SPEC §5.13.2 "do
    not reuse the exact same question variant"), retries with a new seed until the
    rendering differs, up to a bound.

    The one-at-a-time form, still correct for callers that mint a single variant (the
    study planner's per-item selection). Exam builders use `build_variant_row` plus a
    batched write instead - see AUD-F-31.

    The canonical-variant read is conditional so the common path keeps its statement
    count: a shape template needs no extra query, and a statically-rendered one costs
    exactly one (D-189).
    """
    canonical_variant = (
        await question_repo.get_variant_for_template(template.question_template_id)
        if renders_from_canonical_variant(template)
        else None
    )
    return await question_repo.create_variant(
        build_variant_row(
            template=template,
            rng=rng,
            avoid_rendered_question=avoid_rendered_question,
            canonical_variant=canonical_variant,
        )
    )
