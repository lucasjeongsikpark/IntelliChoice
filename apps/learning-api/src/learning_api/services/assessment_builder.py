"""Builds the fixed pre/post-exam question sets (SPEC §5.9.1-§5.9.2, §5.13.1-§5.13.2).

Once built, the set is fixed - `assessment_items` is never regenerated, only graded
against (§5.9.2). The post-exam reuses the exact same `question_template_id` per slot
as the pre-exam ("same template family") with a freshly generated variant.
"""

import random

from intellichoice_db.models.assessment import (
    AssessmentItem,
    AssessmentItemState,
    AssessmentSession,
)
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.questions import QuestionRepository

from learning_api.services import exam_policy
from learning_api.services.variant_persistence import build_variant_row

DIFFICULTIES = (1, 2, 3, 4, 5)
QUESTIONS_PER_DIFFICULTY = 2
# D-302: the exam's length, which is what a topic must now be able to fill. It is exactly
# what the per-difficulty rule used to imply (2 x 5), so no exam changes length.
#
# **Why the rule moved from "2 at every tier" to "10 in total."** The old precondition made a
# topic unopenable if any single tier was short, and D-301 measured that a third of serving
# items carry the slot's tier over a judge disagreement. Once the judge's tier is stored
# (D-302), 214 items move down and 116 up, which empties the top tiers: openable topics would
# have gone 26 -> 12. Measured under this rule instead: **33 of 33**, with no topic short of
# 10 items. The user's decision was to follow the judge, accept an uneven and biased tier
# distribution, and fill the question count.
#
# The consequence, stated because it is a real product change: a topic with no tier-5 content
# now serves an easier exam than one that has it, so exam difficulty varies by topic and not
# only by student.
EXAM_QUESTION_COUNT = QUESTIONS_PER_DIFFICULTY * len(DIFFICULTIES)


class AssessmentBuildError(Exception):
    """Not enough approved templates exist for a topic/difficulty to build a fixed set."""


async def _store_items(
    *,
    assessment_repo: AssessmentRepository,
    assessment_session_id: str,
    question_variant_ids: list[str],
) -> list[AssessmentItem]:
    """Writes a whole exam's items and their state rows in two round-trips, not two per
    item (AUD-F-31).

    `display_order` is the position in `question_variant_ids`, so the caller controls the
    order and this function never re-sorts it.

    Two flushes rather than one because `assessment_item_id` is assigned by the flush, not
    by the constructor - the state rows cannot be built until the items have been written.
    It costs the same two statements either way.
    """
    items = await assessment_repo.add_items(
        [
            AssessmentItem(
                assessment_session_id=assessment_session_id,
                question_variant_id=question_variant_id,
                display_order=display_order,
            )
            for display_order, question_variant_id in enumerate(question_variant_ids)
        ]
    )
    # SPEC §5.9/§5.13: every item starts unseen. The policy lives here, not in the
    # repository, which only knows how to write the two tables in one round-trip each.
    await assessment_repo.create_item_states(
        [
            AssessmentItemState(assessment_item_id=item.assessment_item_id, status="unseen")
            for item in items
        ]
    )
    return items


async def build_pre_exam(
    *,
    question_repo: QuestionRepository,
    assessment_repo: AssessmentRepository,
    student_external_id: str,
    topic_id: str,
    rng: random.Random,
) -> AssessmentSession:
    """AUD-F-31: batched. Every variant is rendered in memory first, then the whole exam is
    written in two flushes instead of three round-trips per item.

    The RNG is consumed in exactly the order the unbatched version consumed it - per
    difficulty, `rng.sample` then one `build_variant_row` per sampled template - because
    that order *is* the exam's identity for a given seed (CLAUDE.md non-negotiable #2).
    Only the I/O moved out of the loop; the generation sequence did not.
    """
    policy = exam_policy.get_policy("pre_exam")
    session_row = await assessment_repo.create_session(
        AssessmentSession(
            student_external_id=student_external_id,
            session_type="pre_exam",
            topic_id=topic_id,
            policy=policy.model_dump(),
            time_limit_seconds=policy.time_limit_seconds,
        )
    )

    templates_by_difficulty = await question_repo.get_active_questions_by_difficulty(
        topic_id, DIFFICULTIES
    )
    # Read before the loop, from the whole candidate pool rather than the sampled subset
    # (D-189). Sampling first and then reading would batch more tightly but would reorder
    # the RNG draws - `rng.sample` and `build_variant_row` interleave per difficulty, and
    # that order is what makes a fixed seed reproduce a fixed exam. A topic with no
    # statically-rendered templates issues no extra statement at all.
    canonical_variants = await question_repo.get_canonical_variants(
        [
            template.question_template_id
            for templates in templates_by_difficulty.values()
            for template in templates
        ]
    )
    available = sum(len(templates_by_difficulty[d]) for d in DIFFICULTIES)
    if available < EXAM_QUESTION_COUNT:
        raise AssessmentBuildError(
            f"topic {topic_id} has only {available} approved templates across every "
            f"difficulty, need {EXAM_QUESTION_COUNT}"
        )

    variant_rows = []
    taken: set[str] = set()

    def _draw(template) -> None:
        taken.add(template.question_template_id)
        variant_rows.append(
            build_variant_row(
                template=template,
                rng=rng,
                canonical_variant=canonical_variants.get(template.question_template_id),
            )
        )

    # Pass 1 is the old loop with `len(templates)` as a ceiling, and that is deliberate: for a
    # topic holding QUESTIONS_PER_DIFFICULTY at every tier it draws exactly what it always
    # drew, in the same order, so a seeded exam is byte-identical and the pinned pre-exam
    # capture does not move. Only a topic that used to be *refused* takes a different path.
    for difficulty in DIFFICULTIES:
        templates = templates_by_difficulty[difficulty]
        for template in rng.sample(templates, min(QUESTIONS_PER_DIFFICULTY, len(templates))):
            _draw(template)

    # Pass 2 tops the exam up to its full length from whichever tiers have surplus, easiest
    # first. Reached only when a tier was short, so it cannot perturb pass 1's draws.
    for difficulty in DIFFICULTIES:
        if len(variant_rows) >= EXAM_QUESTION_COUNT:
            break
        surplus = [
            t for t in templates_by_difficulty[difficulty] if t.question_template_id not in taken
        ]
        wanted = min(EXAM_QUESTION_COUNT - len(variant_rows), len(surplus))
        for template in rng.sample(surplus, wanted):
            _draw(template)

    stored_variants = await question_repo.create_variants(variant_rows)
    await _store_items(
        assessment_repo=assessment_repo,
        assessment_session_id=session_row.assessment_session_id,
        question_variant_ids=[v.question_variant_id for v in stored_variants],
    )

    return session_row


async def build_post_exam(
    *,
    question_repo: QuestionRepository,
    assessment_repo: AssessmentRepository,
    student_external_id: str,
    pre_assessment_session_id: str,
    rng: random.Random,
) -> AssessmentSession:
    """SPEC §5.13.1-§5.13.2: one post-exam slot per pre-exam slot, same template family,
    a freshly rendered variant.

    Batched the same way as `build_pre_exam` (AUD-F-31), and for the same reason: the
    per-item reads of the pre-exam's variants and their templates were N+1, and the writes
    were three round-trips per item. The iteration order over `pre_items` is unchanged, so
    each slot still draws from the RNG in the same sequence.
    """
    pre_items = await assessment_repo.get_items(pre_assessment_session_id)
    pre_session = await assessment_repo.get_session(pre_assessment_session_id)
    assert pre_session is not None
    policy = exam_policy.get_policy("post_exam")
    session_row = await assessment_repo.create_session(
        AssessmentSession(
            student_external_id=student_external_id,
            session_type="post_exam",
            topic_id=pre_session.topic_id,
            policy=policy.model_dump(),
            time_limit_seconds=policy.time_limit_seconds,
        )
    )

    pre_variants = await question_repo.get_variants(
        [item.question_variant_id for item in pre_items]
    )
    templates = await question_repo.get_templates(
        [variant.question_template_id for variant in pre_variants.values()]
    )

    canonical_variants = await question_repo.get_canonical_variants(
        [template.question_template_id for template in templates.values()]
    )
    variant_rows = []
    for pre_item in pre_items:
        pre_variant = pre_variants.get(pre_item.question_variant_id)
        assert pre_variant is not None
        template = templates.get(pre_variant.question_template_id)
        assert template is not None
        # SPEC §5.13.2: same template family, a rendering that isn't the pre-exam's -
        # except for a statically-rendered template, which has only the one rendering and
        # therefore repeats it here by design (D-189). `_static_variant_row` logs each
        # such repeat so the rate is measurable.
        variant_rows.append(
            build_variant_row(
                template=template,
                rng=rng,
                avoid_rendered_question=pre_variant.rendered_question,
                canonical_variant=canonical_variants.get(template.question_template_id),
            )
        )

    stored_variants = await question_repo.create_variants(variant_rows)
    await _store_items(
        assessment_repo=assessment_repo,
        assessment_session_id=session_row.assessment_session_id,
        question_variant_ids=[v.question_variant_id for v in stored_variants],
    )

    return session_row
