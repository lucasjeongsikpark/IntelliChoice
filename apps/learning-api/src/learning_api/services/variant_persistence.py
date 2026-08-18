"""Shared variant-generation + persistence step used by both the pre/post-exam builder
and the study-plan builder (SPEC §5.8.1, §5.8.6 generation; §5.13.1 parallel-form seed).
"""

import logging
import random

from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_RUNTIME,
    QuestionTemplate,
    QuestionVariant,
)
from intellichoice_db.repositories.questions import QuestionRepository

_MAX_REGENERATION_ATTEMPTS = 20
_MAX_SEED = 2**31 - 1

OPTION_KEYS = ("a", "b", "c", "d")
# 4! = 24 orders, one of which is the identity. A handful of redraws is plenty to avoid it;
# the bound exists so a pathological RNG cannot spin here rather than because it is expected
# to be reached.
_MAX_PERMUTATION_ATTEMPTS = 12


def _permute_options(*, canonical_variant: QuestionVariant, seed: int) -> tuple[list[str], str]:
    """Return `canonical_variant`'s four options in a new order, plus the remapped answer key.

    Seeded from `seed`, which the caller has already drawn from the session RNG, so this
    stays inside the deterministic core (CLAUDE.md non-negotiable #2): the same session seed
    reproduces the same order. It draws from a *private* `Random` rather than the session
    RNG so that adding this step did not shift any later draw and change existing exams.

    The identity order is rejected because "differs in option order" is the property being
    bought; returning the original order would satisfy the type and not the requirement.
    """
    options = [
        canonical_variant.option_a,
        canonical_variant.option_b,
        canonical_variant.option_c,
        canonical_variant.option_d,
    ]
    rng = random.Random(seed)
    order = list(range(len(options)))
    original_index = OPTION_KEYS.index(canonical_variant.correct_option)
    # Rejecting the identity order alone left ~22% of draws keeping the *correct answer*
    # on the same letter, which is the position memory ("I picked C") the docstring
    # promises to remove - a shuffled distractor doesn't help if the answer didn't move.
    # So the draw must also move the correct option. P(reject) per draw ≈ 0.25, so twelve
    # bounded attempts fail with probability ~0.25^12; the fallthrough serves the last
    # draw rather than crashing, and the caller logs whether the answer actually moved.
    for _ in range(_MAX_PERMUTATION_ATTEMPTS):
        rng.shuffle(order)
        if order != sorted(order) and order.index(original_index) != original_index:
            break
    # `order[j]` is which original option now sits at position `j`, so the answer key moves
    # to wherever the originally-correct option landed.
    return [options[i] for i in order], OPTION_KEYS[order.index(original_index)]


class StaticVariantUnavailableError(Exception):
    """A template whose content is stored rather than computed was asked to render
    without its canonical variant - see `build_variant_row`.
    """


logger = logging.getLogger(__name__)


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

    **Every servable template is served from its canonical variant** (D-226). This used to
    branch: a template whose `solution_function` named a registered shape was *generated*
    from a seed instead. That branch had been unreachable since D-210 made `_servable()`
    require `authoring_mode == "authored"`, and the shape registry it keyed on no longer
    exists. `canonical_variant` is therefore required rather than conditional, and its
    absence is a programming error rather than a content shape - see `_static_variant_row`
    for what serving one means and what it costs.
    """
    if canonical_variant is None:
        raise StaticVariantUnavailableError(
            f"template {template.question_template_id!r} was asked to render with no "
            f"canonical variant; every servable template stores its content (D-226)"
        )
    return _static_variant_row(
        template=template,
        rng=rng,
        canonical_variant=canonical_variant,
        avoid_rendered_question=avoid_rendered_question,
    )


def _static_variant_row(
    *,
    template: QuestionTemplate,
    rng: random.Random,
    canonical_variant: QuestionVariant,
    avoid_rendered_question: str | None,
) -> QuestionVariant:
    """Serve a stored item: copy the canonical variant's content into a fresh runtime row.

    **This is where the post-exam's parallel form is partly given up** (D-189, the user's
    call). An authored template has exactly one rendering, so when the post-exam asks for
    "the same template, a rendering that isn't the pre-exam's", there is no other rendering
    to give and the student sees the same stem and numbers twice.

    D-189 accepted that **on the condition that the repeat rate be measurable rather than
    assumed**. It has now been measured on staging (2026-08-07, a full journey driven
    through the deployed UI): with D-210's authored-only bank, **10 of 10** post-exam items
    repeated the pre-exam - stems, numeric parameters *and* option order all identical. So
    the rate is 100%, not the rare fallback the generated path had.

    What that measurement changes here is narrow and deliberate. Re-rendering with different
    numbers is still content work D-189 costed and rejected, so it is untouched. But SPEC
    §5.13.1 names **three** axes the post-exam must differ in - numerical parameters, option
    order, and seed - and option order needs no new content, no schema change and no human
    review. Serving the same four options in the same four positions was giving up an axis
    that was free. It is now permuted, which removes pure position memory ("I picked C")
    from the gain measurement. Numerical parameters remain D-189's open trade.

    Verified safe before doing it: the authored bank contains no reference to an option
    letter in any stem, hint or worked solution, so no text can disagree with the new order.
    Only the post-exam path permutes - the pre-exam and the study planner pass
    `avoid_rendered_question=None` and are byte-for-byte unchanged.

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
    options = [
        canonical_variant.option_a,
        canonical_variant.option_b,
        canonical_variant.option_c,
        canonical_variant.option_d,
    ]
    correct_option = canonical_variant.correct_option
    if (
        avoid_rendered_question is not None
        and canonical_variant.rendered_question == avoid_rendered_question
    ):
        options, correct_option = _permute_options(canonical_variant=canonical_variant, seed=seed)
        logger.info(
            "static_variant_repeats_rendering",
            extra={
                "question_template_id": template.question_template_id,
                "topic_id": template.topic_id,
                "skill_id": template.skill_id,
                "difficulty_label": template.difficulty_label,
                # So the log still distinguishes "same question entirely" from "same
                # question, re-ordered options" once this has been running a while.
                # Measured, not asserted: a constant `True` here could not have caught
                # `_permute_options`'s bounded-attempts fallthrough serving the original
                # order (D-216).
                "options_permuted": [
                    canonical_variant.option_a,
                    canonical_variant.option_b,
                    canonical_variant.option_c,
                    canonical_variant.option_d,
                ]
                != options,
                "correct_letter_moved": correct_option != canonical_variant.correct_option,
            },
        )
    return QuestionVariant(
        origin=VARIANT_ORIGIN_RUNTIME,
        question_template_id=template.question_template_id,
        random_seed=seed,
        rendered_question=canonical_variant.rendered_question,
        option_a=options[0],
        option_b=options[1],
        option_c=options[2],
        option_d=options[3],
        correct_option=correct_option,
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

    The canonical-variant read costs exactly one query (D-189). It used to be conditional
    on `renders_from_canonical_variant`, which D-226 removed along with the shape templates
    that were its only False case.
    """
    canonical_variant = await question_repo.get_variant_for_template(template.question_template_id)
    return await question_repo.create_variant(
        build_variant_row(
            template=template,
            rng=rng,
            avoid_rendered_question=avoid_rendered_question,
            canonical_variant=canonical_variant,
        )
    )
