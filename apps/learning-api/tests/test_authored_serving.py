"""D-189: serving authored (statically-rendered) templates through the exam builders.

D-188 found this by approving five authored templates and watching 34 tests fail with
`VariantGenerationError: unknown shape 'authored'` — the builders rendered every served
question through `generate_variant(shape_key=template.solution_function)` and an authored
template has no shape. The pipeline had been able to *produce* authored items since S20,
but nothing had ever approved one, so producing-vs-serving had never been exercised.

The exam here is deliberately **mixed**: difficulty 1 is served entirely from authored
content and difficulties 2-5 from the shape bank. That is the realistic shape of the bank
after A6-C, and it exercises both rendering paths in a single build — a topic of purely
authored content would not have caught a regression in the generated path.

Real Postgres via a rollback session (D-013), same pattern as `test_select_topic_sql_shape`.
"""

import asyncio
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_CANONICAL,
    VARIANT_ORIGIN_RUNTIME,
    QuestionTemplate,
    QuestionVariant,
)
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.questions import QuestionRepository
from learning_api.services.assessment_builder import build_post_exam, build_pre_exam
from learning_api.services.variant_persistence import (
    StaticVariantUnavailableError,
    _permute_options,
    build_variant_row,
    renders_from_canonical_variant,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TOPIC_ID = "linear_equations"
STUDENT_ID = "authored-serving-test-student"
SEED = 20260805
AUTHORED_DIFFICULTY = 1
# `build_pre_exam` needs QUESTIONS_PER_DIFFICULTY templates at each difficulty, and this
# test replaces difficulty 1's bank entirely, so it must supply at least that many.
AUTHORED_COUNT = 2


@asynccontextmanager
async def _rollback_session() -> AsyncIterator[AsyncSession]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()


def _authored_stem(index: int) -> str:
    return f"Authored serving fixture {index}: solve for x: x + {index} = {index + 4}"


async def _replace_one_difficulty_with_authored_content(session: AsyncSession) -> list[str]:
    """Deactivate difficulty 1's shape templates and put authored ones in their place.

    Rolled back with the session, so it never leaves the shared dev database in a state
    where an authored template is approved — which is exactly what made D-188's 34
    failures show up in unrelated test files.
    """
    repo = QuestionRepository(session)
    existing = await repo.get_active_questions(TOPIC_ID, difficulty=AUTHORED_DIFFICULTY)
    assert existing, "fixture assumes the seeded shape bank is present"
    skill_id = existing[0].skill_id
    curriculum_version = existing[0].curriculum_version
    grade_band = existing[0].grade_band
    await session.execute(
        text(
            "update question_templates set active_status = 'retired' "
            "where topic_id = :topic_id and difficulty_label = :difficulty"
        ),
        {"topic_id": TOPIC_ID, "difficulty": AUTHORED_DIFFICULTY},
    )

    template_ids = []
    for index in range(AUTHORED_COUNT):
        template = await repo.create_template(
            QuestionTemplate(
                question_template_id=f"authored-serving-fixture-{index}",
                curriculum_version=curriculum_version,
                topic_id=TOPIC_ID,
                skill_id=skill_id,
                grade_band=grade_band,
                difficulty_label=AUTHORED_DIFFICULTY,
                question_type="multiple_choice",
                parameter_schema={},
                solution_function="authored",
                correct_option_generator="authored",
                distractor_generators=[],
                common_error_tags=[],
                estimated_time_seconds=30,
                generator_model="test",
                review_model_versions={},
                stem=_authored_stem(index),
                hint_ladder=["one", "two", "three"],
                canonical_solution={"steps": [], "final_answer": "4"},
                authoring_mode="authored",
                validation_status="approved",
                active_status="active",
            )
        )
        await repo.create_variant(
            QuestionVariant(
                origin=VARIANT_ORIGIN_CANONICAL,
                question_template_id=template.question_template_id,
                random_seed=index,
                rendered_question=_authored_stem(index),
                option_a="4",
                option_b="5",
                option_c="6",
                option_d="3",
                correct_option="a",
                parameter_values={},
            )
        )
        template_ids.append(template.question_template_id)
    await session.flush()
    return template_ids


def _run(scenario) -> None:  # type: ignore[no-untyped-def]
    try:
        asyncio.run(_ensure_curriculum())
    except OSError as exc:  # pragma: no cover - D-008: skip when Postgres is unreachable
        pytest.skip(f"Postgres unreachable: {exc}")
    asyncio.run(scenario())


async def _ensure_curriculum() -> None:
    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            await load_curriculum_and_templates(session)
            await session.commit()
    finally:
        await engine.dispose()


def test_an_authored_template_is_served_from_its_canonical_variant() -> None:
    """The failure D-188 measured: this build used to raise `VariantGenerationError`."""

    async def scenario() -> None:
        async with _rollback_session() as session:
            authored_ids = await _replace_one_difficulty_with_authored_content(session)
            question_repo = QuestionRepository(session)
            assessment_repo = AssessmentRepository(session)

            pre_exam = await build_pre_exam(
                question_repo=question_repo,
                assessment_repo=assessment_repo,
                student_external_id=STUDENT_ID,
                topic_id=TOPIC_ID,
                rng=random.Random(SEED),
            )
            items = await assessment_repo.get_items(pre_exam.assessment_session_id)
            variants = await question_repo.get_variants(
                [item.question_variant_id for item in items]
            )
            served_authored = [
                variant
                for variant in variants.values()
                if variant.question_template_id in authored_ids
            ]
            assert len(served_authored) == AUTHORED_COUNT

            # Served from the reviewed content, verbatim - not regenerated, not blank.
            assert {variant.rendered_question for variant in served_authored} == {
                _authored_stem(index) for index in range(AUTHORED_COUNT)
            }
            for variant in served_authored:
                assert variant.correct_option == "a"
                assert variant.option_a == "4"
                # A serving, not the canonical row: it must stay out of the §5.8.3 dedup
                # population, or every showing would make the item look like a duplicate
                # of itself (D-106's accumulation bug, reintroduced through a new door).
                assert variant.origin == VARIANT_ORIGIN_RUNTIME

            # The other difficulties still came from the shape bank, so this build
            # exercised both paths rather than replacing one with the other.
            assert len(items) > len(served_authored)

    _run(scenario)


def test_the_post_exam_repeats_an_authored_stem_but_reorders_its_options() -> None:
    """The accepted trade-off and its one recovered axis, both pinned.

    SPEC §5.13.2 asks the post-exam for a rendering that is not the pre-exam's, and an
    authored template has exactly one to give. D-189's call was to serve it again rather
    than to exclude authored content from exams, *conditional on the repeat rate being
    measured*. It was measured on staging 2026-08-07 by driving a full journey through the
    deployed UI: 10 of 10 post-exam items repeated, stems and numbers and option order
    alike. 100%, not the rare fallback the generated path had.

    So this asserts both halves of where that leaves us. The stem and its numbers still
    repeat - that is D-189's open trade and re-rendering them is content work. But SPEC
    §5.13.1 lists **option order** as its own axis, and that one costs nothing to honour,
    so the four options now come back in a different order with the answer key moved to
    follow. Without it the gain measurement was also rewarding pure position memory.
    """

    async def scenario() -> None:
        async with _rollback_session() as session:
            authored_ids = await _replace_one_difficulty_with_authored_content(session)
            question_repo = QuestionRepository(session)
            assessment_repo = AssessmentRepository(session)

            pre_exam = await build_pre_exam(
                question_repo=question_repo,
                assessment_repo=assessment_repo,
                student_external_id=STUDENT_ID,
                topic_id=TOPIC_ID,
                rng=random.Random(SEED),
            )
            post_exam = await build_post_exam(
                question_repo=question_repo,
                assessment_repo=assessment_repo,
                student_external_id=STUDENT_ID,
                pre_assessment_session_id=pre_exam.assessment_session_id,
                rng=random.Random(SEED + 1),
            )

            async def served(assessment_session_id: str) -> dict[str, QuestionVariant]:
                items = await assessment_repo.get_items(assessment_session_id)
                variants = await question_repo.get_variants(
                    [item.question_variant_id for item in items]
                )
                return {
                    variant.question_template_id: variant
                    for variant in variants.values()
                    if variant.question_template_id in authored_ids
                }

            pre_served = await served(pre_exam.assessment_session_id)
            post_served = await served(post_exam.assessment_session_id)
            assert set(pre_served) == set(post_served) == set(authored_ids)

            def options(variant: QuestionVariant) -> list[str]:
                return [
                    variant.option_a,
                    variant.option_b,
                    variant.option_c,
                    variant.option_d,
                ]

            def answer_text(variant: QuestionVariant) -> str:
                return options(variant)["abcd".index(variant.correct_option)]

            for template_id in authored_ids:
                before, after = pre_served[template_id], post_served[template_id]
                # The text repeats - this is the trade-off, stated.
                assert after.rendered_question == before.rendered_question
                # But it is a distinct row, which is what §5.13.2 forbids reusing.
                assert after.question_variant_id != before.question_variant_id
                # SPEC §5.13.1's option-order axis: the same four options, genuinely
                # re-ordered rather than merely re-emitted.
                assert sorted(options(after)) == sorted(options(before))
                assert options(after) != options(before)
                # And the answer key moved with them. This is the assertion that would
                # catch a permutation applied to the options but not to `correct_option`,
                # which would silently mis-grade every post-exam.
                assert answer_text(after) == answer_text(before)
                # D-216: the *letter* itself must change, not just the distractors around
                # it - rejecting only the identity order left ~22% of draws keeping the
                # correct answer on the same letter, which is exactly the position memory
                # ("I picked C") the permutation exists to remove.
                assert after.correct_option != before.correct_option

    _run(scenario)


def test_the_option_permutation_always_moves_the_correct_letter() -> None:
    """`_permute_options` over many seeds: never the identity order, and the correct
    answer never stays on its original letter. Property-tested directly because the
    flow-level test above only exercises the handful of seeds one exam build draws.
    """
    canonical = QuestionVariant(
        origin=VARIANT_ORIGIN_CANONICAL,
        question_template_id="t-permute",
        random_seed=0,
        rendered_question="stem",
        option_a="alpha",
        option_b="beta",
        option_c="gamma",
        option_d="delta",
        correct_option="c",
        parameter_values={},
    )
    originals = ["alpha", "beta", "gamma", "delta"]
    for seed in range(2000):
        permuted, correct_option = _permute_options(canonical_variant=canonical, seed=seed)
        assert sorted(permuted) == sorted(originals)
        assert permuted != originals
        # The answer text survives the move; the letter never stays put.
        assert permuted["abcd".index(correct_option)] == "gamma"
        assert correct_option != "c"


def test_building_without_a_canonical_variant_raises_rather_than_serving_nothing() -> None:
    """A statically-rendered template with nothing behind it must not render silently.

    `build_variant_row` cannot read the database - it is the pure half, split out for
    AUD-F-31's batched writes - so a caller that forgets to supply the canonical variant
    would otherwise be one `None` away from serving an empty question to a student.
    """

    async def scenario() -> None:
        async with _rollback_session() as session:
            authored_ids = await _replace_one_difficulty_with_authored_content(session)
            repo = QuestionRepository(session)
            template = await repo.get_template(authored_ids[0])
            assert template is not None
            assert renders_from_canonical_variant(template)

            with pytest.raises(StaticVariantUnavailableError):
                build_variant_row(template=template, rng=random.Random(SEED))

    _run(scenario)
