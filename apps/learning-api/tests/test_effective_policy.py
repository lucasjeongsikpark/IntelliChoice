"""AUD-L-16 (D-174 §6): the persisted policy snapshot governs assistance, rather than being
written and never read.

**These are masking tests, which is the point.** Asserting only "study allows hints, exams do
not" would pass just as well against the old hardcoded `phase == "study"` check — it did, for
many sessions. What distinguishes wired-up from documentation is that a snapshot **disagreeing**
with the constant is obeyed, and that is what most of this file measures. D-169's precedent:
wire it, state the inertness, test the masking.

Real Postgres via a rollback session (D-013 pattern); skips cleanly when Postgres is
unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from intellichoice_db.engine import create_engine
from intellichoice_db.models.assessment import AssessmentSession
from intellichoice_db.models.curriculum import Topic
from intellichoice_db.models.mastery import StudySession
from learning_api.services import exam_policy
from learning_api.services.effective_policy import effective_assistance_policy
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM assessment_sessions LIMIT 1"))
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


async def _seed_exam(session: AsyncSession, policy: dict | None) -> str:
    row = AssessmentSession(
        student_external_id="student-ext-1", session_type="pre_exam", policy=policy
    )
    session.add(row)
    await session.flush()
    return row.assessment_session_id


async def _seed_study(session: AsyncSession, intervention_policy: dict) -> str:
    topic = Topic(
        name="Effective policy topic", curriculum_version="test", grade_band="6-8"
    )
    session.add(topic)
    await session.flush()
    row = StudySession(
        student_external_id="student-ext-1",
        topic_id=topic.topic_id,
        target_skill_ids=[],
        starting_difficulty=2,
        maximum_attempts_per_skill=3,
        intervention_policy=intervention_policy,
    )
    session.add(row)
    await session.flush()
    return row.study_session_id


def test_a_study_snapshot_that_disables_hints_is_obeyed() -> None:
    """The load-bearing case. The constant says study allows hints; this session's own
    snapshot says it does not. If the snapshot were still unread, this returns True and the
    test fails - which is exactly how it failed before the fix.
    """
    assert exam_policy.get_policy("study").hints_allowed is True, "premise of this test"

    async def run() -> None:
        async with _rollback_session() as session:
            study_id = await _seed_study(session, {"hints_enabled": False})
            result = await effective_assistance_policy(
                session, {"phase": "study", "study_session_id": study_id}
            )
        assert result.hints_allowed is False, (
            "the study snapshot disabled hints and was ignored - the constant is still the "
            "mechanism (AUD-L-16)"
        )
        assert result.source == "study_snapshot"

    asyncio.run(run())


def test_an_exam_snapshot_that_enables_hints_is_obeyed() -> None:
    """The mirror image, and it matters for a different reason: it proves the exam arm reads
    the snapshot too rather than short-circuiting on the phase name.
    """
    assert exam_policy.get_policy("pre_exam").hints_allowed is False, "premise of this test"

    async def run() -> None:
        async with _rollback_session() as session:
            exam_id = await _seed_exam(session, {"hints_allowed": True})
            result = await effective_assistance_policy(
                session, {"phase": "pre_exam", "pre_assessment_session_id": exam_id}
            )
        assert result.hints_allowed is True
        assert result.source == "assessment_snapshot"

    asyncio.run(run())


def test_the_shipped_constants_and_the_snapshots_agree_today() -> None:
    """The inertness AUD-L-16's fix deliberately preserves: with the policies actually written
    at creation, every outcome is what the old phase check produced. A future reader seeing
    this file should not conclude behaviour changed.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            exam_id = await _seed_exam(
                session, exam_policy.get_policy("pre_exam").model_dump()
            )
            study_id = await _seed_study(session, {"hints_enabled": True})

            exam = await effective_assistance_policy(
                session, {"phase": "pre_exam", "pre_assessment_session_id": exam_id}
            )
            study = await effective_assistance_policy(
                session, {"phase": "study", "study_session_id": study_id}
            )
        assert exam.hints_allowed is False
        assert exam.source == "assessment_snapshot"
        assert study.hints_allowed is True
        assert study.source == "study_snapshot"

    asyncio.run(run())


def test_a_null_snapshot_falls_back_to_the_constant_and_says_so() -> None:
    """`AssessmentSession.policy` is nullable and its own comment records that pre-S22 rows were
    never backfilled, so this is a real path. The fallback must keep those sessions working, and
    it must be distinguishable from a snapshot that happens to hold the same value - otherwise
    "the snapshot decided" and "the snapshot was missing" look identical.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            exam_id = await _seed_exam(session, None)
            result = await effective_assistance_policy(
                session, {"phase": "pre_exam", "pre_assessment_session_id": exam_id}
            )
        assert result.hints_allowed is exam_policy.get_policy("pre_exam").hints_allowed
        assert result.source == "constant_fallback"

    asyncio.run(run())


def test_a_study_snapshot_missing_the_key_falls_back_rather_than_failing_open() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            study_id = await _seed_study(session, {})
            result = await effective_assistance_policy(
                session, {"phase": "study", "study_session_id": study_id}
            )
        assert result.source == "constant_fallback"

    asyncio.run(run())


@pytest.mark.parametrize("phase", ["created", "completed", "pre_exam_review", None])
def test_a_phase_with_no_session_refuses_without_touching_the_database(phase: str | None) -> None:
    """Fails closed (CLAUDE.md #5), and the old check's answer for these phases too. No id is
    in state, so nothing is queried - the assertion is on the source, which is what proves the
    refusal is deliberate rather than an accidental miss.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            result = await effective_assistance_policy(session, {"phase": phase})
        assert result.hints_allowed is False
        assert result.source == "phase_has_no_policy"

    asyncio.run(run())


def test_a_missing_session_row_falls_back_instead_of_raising() -> None:
    """A state id that no longer resolves (a purged or rolled-back session) must not 500 the
    chat route on its way to a 409.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            result = await effective_assistance_policy(
                session, {"phase": "study", "study_session_id": "does-not-exist"}
            )
        assert result.source == "constant_fallback"

    asyncio.run(run())
