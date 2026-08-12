"""The same story with different numbers, in a different topic (D-286).

Three collisions reached the shipped bank and no check could see them:

    g1_addition       "Liam has 9 stickers in his album. His friend gives him 6 more..."
    g2_word_problems  "Liam has 9 stickers in his album. His friend gives him 6 more..."

`rendered_question_exists` is global but needs the digits to match. The near-duplicate
embedding check compares meanings, but only within one `topic_id`. Between them sat this.

Both directions, per D-246 - the interesting question is not whether it catches the repeat
but whether it leaves alone the two things that legitimately look like one: a template
recurring inside its own topic, and two grades doing similar-but-distinct arithmetic.
"""

import asyncio

import pytest
from intellichoice_db.models.curriculum import Skill, Topic
from intellichoice_db.models.questions import QuestionTemplate, QuestionVariant
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.questions import QuestionRepository
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

# `rollback_session` binds to the real dev database, so a test asserting that *nothing*
# matches is only meaningful if its text cannot collide with content that actually shipped.
# The first draft used the real "Which of these numbers is the largest?" and failed by
# matching `authored-place_value-d1-200104` - the check working correctly on real data,
# reported as a test failure. Hence the nonce: these stems exist nowhere but here.
_NONCE = "zzq-dedup-fixture"
LIAM = (
    f"Liam has 9 {_NONCE} stickers in his album. His friend gives him 6 more stickers. "
    "How many now?"
)
TEMPLATE_STEM = f"Which of these {_NONCE} numbers is the largest?"


async def _seed(session: AsyncSession, *, name: str, stem: str, origin: str = "canonical") -> str:
    """One topic with one template and one variant. Returns the topic id."""
    curriculum = CurriculumRepository(session)
    questions = QuestionRepository(session)
    topic = await curriculum.create_topic(
        Topic(curriculum_version="v1", name=name, grade_band="1-2")
    )
    skill = await curriculum.create_skill(
        Skill(topic_id=topic.topic_id, name=f"{name}_skill")
    )
    template = await questions.create_template(
        QuestionTemplate(
            authoring_mode="authored",
            curriculum_version="v1",
            topic_id=topic.topic_id,
            skill_id=skill.skill_id,
            grade_band="1-2",
            difficulty_label=2,
            estimated_time_seconds=60,
            parameter_schema={},
            solution_function="solve_authored",
            correct_option_generator="gen_correct",
            stem=stem,
            answer_expression="Eq(x, 15)",
            generator_model="mock-generator",
            validation_status="approved",
            active_status="active",
        )
    )
    await questions.create_variant(
        QuestionVariant(
            question_template_id=template.question_template_id,
            random_seed=1,
            rendered_question=stem,
            option_a="15",
            option_b="3",
            option_c="14",
            option_d="16",
            correct_option="a",
            parameter_values={},
            origin=origin,
        )
    )
    return topic.topic_id


def test_the_same_story_in_another_topic_is_found() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            await _seed(session, name="Grade 1 Addition", stem=LIAM)
            other = await _seed(session, name="Grade 2 Word Problems", stem="unrelated stem")

            hit = await QuestionRepository(session).stem_skeleton_exists_in_another_topic(
                topic_id=other, rendered_question=LIAM
            )
            assert hit is not None

    asyncio.run(run())


def test_only_the_digits_need_differ() -> None:
    """The case the exact-match check misses, and the reason this exists at all."""

    async def run() -> None:
        async with rollback_session() as session:
            await _seed(session, name="Grade 1 Addition", stem=LIAM)
            other = await _seed(session, name="Grade 2 Addition", stem="unrelated stem")

            rewritten = LIAM.replace("9 stickers", "12 stickers").replace("6 more", "7 more")
            assert rewritten != LIAM
            hit = await QuestionRepository(session).stem_skeleton_exists_in_another_topic(
                topic_id=other, rendered_question=rewritten
            )
            assert hit is not None

    asyncio.run(run())


def test_a_template_repeating_inside_its_own_topic_is_left_alone() -> None:
    """`place_value_compare` asks "Which of these numbers is the largest?" twelve times and
    there is no other way to phrase it - the question lives in the options. Firing here
    would reject eleven correct items, which is why the check is scoped across topics."""

    async def run() -> None:
        async with rollback_session() as session:
            topic = await _seed(session, name="Place Value", stem=TEMPLATE_STEM)

            hit = await QuestionRepository(session).stem_skeleton_exists_in_another_topic(
                topic_id=topic, rendered_question=TEMPLATE_STEM
            )
            assert hit is None

    asyncio.run(run())


def test_a_different_story_in_another_topic_is_left_alone() -> None:
    """Two grades doing similar arithmetic is the curriculum spiral, not duplication. Only
    the *sentence* matters here - which is why this is digit-normalisation and not a cosine
    threshold, since an embedding would call these two close neighbours."""

    async def run() -> None:
        async with rollback_session() as session:
            await _seed(session, name="Grade 1 Addition", stem=LIAM)
            other = await _seed(session, name="Grade 2 Addition", stem="unrelated stem")

            different = (
                f"Maya has 9 {_NONCE} marbles in a jar. Her brother gives her 6 more marbles. "
                "How many now?"
            )
            hit = await QuestionRepository(session).stem_skeleton_exists_in_another_topic(
                topic_id=other, rendered_question=different
            )
            assert hit is None

    asyncio.run(run())


def test_a_runtime_variant_is_not_evidence() -> None:
    """S40/D-106's rule, which this query has to honour too: runtime variants are minted per
    serving, so counting them would make "is this a new question?" depend on how much the
    app has been used - the bug that recurred four times before D-106 scoped it."""

    async def run() -> None:
        async with rollback_session() as session:
            await _seed(session, name="Grade 1 Addition", stem=LIAM, origin="runtime")
            other = await _seed(session, name="Grade 2 Addition", stem="unrelated stem")

            hit = await QuestionRepository(session).stem_skeleton_exists_in_another_topic(
                topic_id=other, rendered_question=LIAM
            )
            assert hit is None, "a runtime variant was treated as an existing question"

    asyncio.run(run())
