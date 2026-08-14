"""ROADMAP S28 (SPEC §5.14.2-§5.14.4, plan §12, §18-L9) - `services/dashboard.py`'s
aggregation correctness against seeded rows, and `DashboardRepository`'s SQL date-range
filtering. Real Postgres via a rollback session (D-013 pattern) - skips cleanly when
Postgres is unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from intellichoice_db.engine import create_engine
from intellichoice_db.models.assessment import (
    AssessmentAttempt,
    AssessmentItem,
    AssessmentItemState,
    AssessmentSession,
)
from intellichoice_db.models.curriculum import Skill, Topic
from intellichoice_db.models.mastery import (
    LearningGain,
    Mastery,
    StudyAttempt,
    StudyItem,
    StudySession,
)
from intellichoice_db.models.questions import QuestionTemplate, QuestionVariant
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.dashboard import DashboardRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_db.repositories.study import StudyRepository
from intellichoice_shared.org_time import resolve_org_time
from learning_api.services.dashboard import _accuracy_trend, build_dashboard
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM student_reports LIMIT 1"))
                except Exception:
                    return "Postgres schema is not migrated (run `make up && make db-upgrade`)"
            return None
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        finally:
            await engine.dispose()

    return asyncio.run(check())


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


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)

STUDENT_ID = "dashboard-test-student-1"


async def _seed_variant(
    session: AsyncSession, questions: QuestionRepository, *, topic_id: str, skill_id: str, seed: int
) -> QuestionVariant:
    template = await questions.create_template(
        QuestionTemplate(
            curriculum_version="v1",
            topic_id=topic_id,
            skill_id=skill_id,
            grade_band="6-8",
            difficulty_label=2,
            difficulty_confidence=0.9,
            parameter_schema={"a": "int"},
            solution_function="solve_linear",
            correct_option_generator="gen_correct",
            estimated_time_seconds=60,
            generator_model="mock-generator",
            validation_status="approved",
            active_status="active",
        )
    )
    return await questions.create_variant(
        QuestionVariant(
            question_template_id=template.question_template_id,
            random_seed=seed,
            rendered_question=f"2x + {seed} = 11",
            option_a="4",
            option_b="5",
            option_c="6",
            option_d="7",
            correct_option="a",
            parameter_values={"a": seed},
        )
    )


async def _seed(session: AsyncSession, *, in_range_at: datetime, out_of_range_at: datetime) -> None:
    curriculum = CurriculumRepository(session)
    questions = QuestionRepository(session)
    study = StudyRepository(session)
    assessment = AssessmentRepository(session)
    mastery_repo = MasteryRepository(session)

    topic = await curriculum.create_topic(
        Topic(curriculum_version="v1", name="Linear Equations", grade_band="6-8")
    )
    skill = await curriculum.create_skill(
        Skill(topic_id=topic.topic_id, name="two_step_equations")
    )

    await mastery_repo.upsert_mastery(
        Mastery(
            student_external_id=STUDENT_ID,
            skill_id=skill.skill_id,
            raw_accuracy=0.6,
            weighted_score=0.6,
        )
    )

    gain_pre_session = await assessment.create_session(
        AssessmentSession(student_external_id=STUDENT_ID, session_type="pre_exam")
    )
    gain_post_session = await assessment.create_session(
        AssessmentSession(student_external_id=STUDENT_ID, session_type="post_exam")
    )

    # One LearningGain in range, one out of range - only the in-range row's
    # skill_level_gain should reach the pre/post-by-skill chart.
    for at, gain_value in [(in_range_at, 0.3), (out_of_range_at, 0.1)]:
        gain = LearningGain(
            student_external_id=STUDENT_ID,
            pre_assessment_session_id=gain_pre_session.assessment_session_id,
            post_assessment_session_id=gain_post_session.assessment_session_id,
            pre_raw_score=4.0,
            post_raw_score=7.0,
            raw_gain=3.0,
            weighted_gain=gain_value,
            skill_level_gain={
                skill.skill_id: {"pre_accuracy": 0.4, "post_accuracy": 0.8, "gain": 0.4}
            },
            difficulty_transition={},
            independent_correct_rate=0.5,
            hint_dependency=0.2,
            solution_dependency=0.1,
            unresolved_skills=[],
            response_time_change_ms=-500,
        )
        gain.computed_at = at
        await mastery_repo.record_learning_gain(gain)

    study_session = await study.create_study_session(
        StudySession(
            student_external_id=STUDENT_ID,
            topic_id=topic.topic_id,
            target_skill_ids=[skill.skill_id],
            starting_difficulty=1,
            maximum_attempts_per_skill=3,
        )
    )

    # Two study attempts: one in range (hint used, correct, difficulty 2), one out of
    # range (no assistance, incorrect, difficulty 3) - only the in-range one should
    # reach the usage/difficulty/accuracy aggregates.
    for at, difficulty, is_correct, hint_used in [
        (in_range_at, 2, True, True),
        (out_of_range_at, 3, False, False),
    ]:
        variant = await _seed_variant(
            session, questions, topic_id=topic.topic_id, skill_id=skill.skill_id, seed=difficulty
        )
        item = await study.add_item(
            StudyItem(
                study_session_id=study_session.study_session_id,
                question_variant_id=variant.question_variant_id,
                display_order=1,
                target_skill_id=skill.skill_id,
                skill_id=skill.skill_id,
                difficulty=difficulty,
            )
        )
        attempt = StudyAttempt(
            student_external_id=STUDENT_ID,
            study_session_id=study_session.study_session_id,
            question_variant_id=item.question_variant_id,
            selected_option="a",
            is_correct=is_correct,
            hint_used=hint_used,
        )
        attempt.responded_at = at
        await study.record_attempt(attempt)

    # One assessment session with one in-range attempt (10 minutes) and one out-of-range
    # attempt (5 minutes) - only the in-range minutes should reach `time_spent_minutes`.
    # The item-state rows deliberately carry `time_spent_ms=0`: that is AUD-L-14's live
    # shape (S36 measured 140 item-state rows summing to 0 ms), and asserting a non-zero
    # `time_spent_minutes` beside them proves the dashboard reads the attempts' required
    # `response_time_ms`, not the fire-and-forget telemetry.
    assessment_session = await assessment.create_session(
        AssessmentSession(student_external_id=STUDENT_ID, session_type="pre_exam")
    )
    for at, response_time_ms in [(in_range_at, 600_000), (out_of_range_at, 300_000)]:
        variant = await _seed_variant(
            session, questions, topic_id=topic.topic_id, skill_id=skill.skill_id, seed=100
        )
        assessment_item = await assessment.add_item(
            AssessmentItem(
                assessment_session_id=assessment_session.assessment_session_id,
                question_variant_id=variant.question_variant_id,
                display_order=1,
            )
        )
        item_state = AssessmentItemState(
            assessment_item_id=assessment_item.assessment_item_id, time_spent_ms=0
        )
        item_state.updated_at = at
        await assessment.create_item_state(item_state)

        exam_attempt = AssessmentAttempt(
            student_external_id=STUDENT_ID,
            assessment_session_id=assessment_session.assessment_session_id,
            question_variant_id=assessment_item.question_variant_id,
            selected_option="a",
            correct_option="a",
            is_correct=True,
            response_time_ms=response_time_ms,
            idempotency_key=f"key-{at.isoformat()}",
        )
        exam_attempt.submitted_at = at
        await assessment.record_attempt(exam_attempt)


def test_dashboard_date_range_filtering_excludes_rows_outside_window() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            now = datetime.now(UTC)
            in_range_at = now - timedelta(days=5)
            out_of_range_at = now - timedelta(days=60)
            await _seed(session, in_range_at=in_range_at, out_of_range_at=out_of_range_at)

            data = await build_dashboard(
                student_id=STUDENT_ID,
                start=now - timedelta(days=10),
                end=now,
                dashboard_repo=DashboardRepository(session),
                mastery_repo=MasteryRepository(session),
                curriculum_repo=CurriculumRepository(session),
            )

            # Mastery is current-state, not date-filtered - always present.
            assert len(data.mastery_by_skill) == 1
            assert data.mastery_by_skill[0].weighted_score == 0.6

            # Only the in-range LearningGain contributes.
            assert len(data.gains_over_time) == 1
            assert data.gains_over_time[0].weighted_gain == 0.3

            # Only the in-range study attempt contributes to usage/difficulty.
            assert data.usage.total_attempts == 1
            assert data.usage.hint_count == 1
            assert data.usage.independent_count == 0
            assert len(data.difficulty_progression) == 1
            assert data.difficulty_progression[0].difficulty == 2
            assert data.difficulty_progression[0].skill_name == "two_step_equations"

            # Accuracy trend combines study + assessment attempts, in-range only.
            assert len(data.accuracy_trend) == 1
            assert data.accuracy_trend[0].accuracy == 1.0
            assert data.accuracy_trend[0].attempts == 2

            # Only the in-range attempt's 600_000ms of `response_time_ms` (10 minutes)
            # contributes - and the item-state rows all hold 0, so a non-zero value here
            # is what proves the source is the attempts (AUD-L-14).
            assert data.time_spent_minutes == 10.0
            assert data.attempts_count == 2

    asyncio.run(run())


def test_dashboard_with_no_range_includes_everything() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            now = datetime.now(UTC)
            in_range_at = now - timedelta(days=5)
            out_of_range_at = now - timedelta(days=60)
            await _seed(session, in_range_at=in_range_at, out_of_range_at=out_of_range_at)

            data = await build_dashboard(
                student_id=STUDENT_ID,
                start=None,
                end=None,
                dashboard_repo=DashboardRepository(session),
                mastery_repo=MasteryRepository(session),
                curriculum_repo=CurriculumRepository(session),
            )

            assert len(data.gains_over_time) == 2
            assert data.usage.total_attempts == 2
            assert data.attempts_count == 4
            assert data.time_spent_minutes == 15.0

    asyncio.run(run())


# --- Which day an attempt is counted against (D-324) ------------------------------------
#
# Pure-function tests, deliberately not seeded ones: the defect is entirely in how an
# instant becomes a date key, and a rollback-session test would need real rows on both
# sides of a timezone boundary to say the same thing at fifty times the cost.


def _study_row(responded_at: datetime, *, is_correct: bool) -> tuple:
    """`_accuracy_trend` reads exactly two attributes off a study row."""
    return (SimpleNamespace(responded_at=responded_at, is_correct=is_correct), object())


def test_accuracy_trend_buckets_a_late_evening_attempt_under_the_org_day() -> None:
    """**The bug, stated as a test.** 02:00 UTC on the 8th is 21:00 Central on the 7th. The
    previous version bucketed on `.date()` - the UTC day - so a student who worked Friday
    evening saw that work counted against Saturday, and *both* days' accuracy described
    something that never happened. The two attempts here are on the same Central evening and
    must therefore form **one** point, not two."""
    org_time = resolve_org_time(env={})
    rows = [
        _study_row(datetime(2026, 8, 8, 1, 30, tzinfo=UTC), is_correct=True),  # 20:30 CDT 8/7
        _study_row(datetime(2026, 8, 8, 2, 30, tzinfo=UTC), is_correct=False),  # 21:30 CDT 8/7
    ]

    points = _accuracy_trend(rows, [], org_time)

    assert len(points) == 1, "one Central evening is one day"
    assert points[0].date.date().isoformat() == "2026-08-07"
    assert points[0].attempts == 2
    assert points[0].accuracy == 0.5


def test_accuracy_trend_dates_carry_a_timezone_so_the_client_cannot_reread_them_locally() -> None:
    """A naive datetime on the wire is re-interpreted by `new Date(...)` as the *viewer's*
    local time, which shifts the label by the viewer's offset - the same class of defect as
    formatting with a bare `toLocaleDateString()`. Emitting an aware value removes the
    ambiguity rather than relying on every consumer to guess right."""
    points = _accuracy_trend(
        [_study_row(datetime(2026, 8, 7, 15, 0, tzinfo=UTC), is_correct=True)],
        [],
        resolve_org_time(env={}),
    )
    assert points[0].date.tzinfo is not None
    assert points[0].date.utcoffset() is not None


def test_accuracy_trend_separates_two_genuinely_different_org_days() -> None:
    """The other direction, so the fix cannot pass by collapsing everything into one bucket
    (the failure mode a "one point" assertion alone would accept)."""
    points = _accuracy_trend(
        [
            _study_row(datetime(2026, 8, 7, 15, 0, tzinfo=UTC), is_correct=True),
            _study_row(datetime(2026, 8, 9, 15, 0, tzinfo=UTC), is_correct=True),
        ],
        [],
        resolve_org_time(env={}),
    )
    assert [p.date.date().isoformat() for p in points] == ["2026-08-07", "2026-08-09"]
