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
from learning_api.services.variant_persistence import generate_and_store_variant

DIFFICULTIES = (1, 2, 3, 4, 5)
QUESTIONS_PER_DIFFICULTY = 2


class AssessmentBuildError(Exception):
    """Not enough approved templates exist for a topic/difficulty to build a fixed set."""


async def _add_item(
    *,
    assessment_repo: AssessmentRepository,
    assessment_session_id: str,
    question_variant_id: str,
    display_order: int,
) -> AssessmentItem:
    item = await assessment_repo.add_item(
        AssessmentItem(
            assessment_session_id=assessment_session_id,
            question_variant_id=question_variant_id,
            display_order=display_order,
        )
    )
    await assessment_repo.create_item_state(
        AssessmentItemState(assessment_item_id=item.assessment_item_id, status="unseen")
    )
    return item


async def build_pre_exam(
    *,
    question_repo: QuestionRepository,
    assessment_repo: AssessmentRepository,
    student_external_id: str,
    topic_id: str,
    rng: random.Random,
) -> AssessmentSession:
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

    display_order = 0
    for difficulty in DIFFICULTIES:
        templates = await question_repo.get_active_questions(topic_id, difficulty)
        if len(templates) < QUESTIONS_PER_DIFFICULTY:
            raise AssessmentBuildError(
                f"topic {topic_id} difficulty {difficulty} has only {len(templates)} "
                f"approved templates, need {QUESTIONS_PER_DIFFICULTY}"
            )
        for template in rng.sample(templates, QUESTIONS_PER_DIFFICULTY):
            variant_row = await generate_and_store_variant(
                question_repo=question_repo, template=template, rng=rng
            )
            await _add_item(
                assessment_repo=assessment_repo,
                assessment_session_id=session_row.assessment_session_id,
                question_variant_id=variant_row.question_variant_id,
                display_order=display_order,
            )
            display_order += 1

    return session_row


async def build_post_exam(
    *,
    question_repo: QuestionRepository,
    assessment_repo: AssessmentRepository,
    student_external_id: str,
    pre_assessment_session_id: str,
    rng: random.Random,
) -> AssessmentSession:
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

    for display_order, pre_item in enumerate(pre_items):
        pre_variant = await question_repo.get_variant(pre_item.question_variant_id)
        assert pre_variant is not None
        template = await question_repo.get_template(pre_variant.question_template_id)
        assert template is not None

        variant_row = await generate_and_store_variant(
            question_repo=question_repo,
            template=template,
            rng=rng,
            avoid_rendered_question=pre_variant.rendered_question,
        )
        await _add_item(
            assessment_repo=assessment_repo,
            assessment_session_id=session_row.assessment_session_id,
            question_variant_id=variant_row.question_variant_id,
            display_order=display_order,
        )

    return session_row
