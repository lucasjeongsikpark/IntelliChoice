"""U7/D-331: the durable summary a learning session never had.

The test that matters most here is `test_every_orphan_field_survives`. D-331's enumeration found
five `LearningState` fields with no durable home, and the whole reason this table exists is to hold
them. A future refactor that quietly drops one would otherwise reintroduce exactly the data loss
the enumeration was run to prevent, and nothing else in the suite would notice.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from intellichoice_db.models.learning_session import LearningSession
from intellichoice_db.repositories.learning_session import LearningSessionRepository

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

# The five fields D-331 found with no durable home anywhere, plus `phase`, the half-case.
ORPHAN_FIELDS = {
    "week_id": "2026-W33",
    "parent_external_id": "parent-ext-77",
    "bedrock_spend_cents": 4.25,
    "attendance_status": "UNKNOWN",
    "attendance_resolution": "absence_acknowledged",
    "phase": "completed",
}

ACTIVITY = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

# **Deliberately not `student-ext-1`.** `rollback_session` isolates this test's *writes*, not its
# reads: `list_for_student` still sees every committed row. The first version of this file used
# `student-ext-1`, passed in isolation, and failed in the full suite the moment the reconciler had
# been run against the dev database - which had put 1,374 real rows under that id. A test that
# only holds while a table is empty is not testing what it claims to.
STUDENT = "learning-session-repo-test-student"


def _summary(session_id: str, **overrides: object) -> LearningSession:
    fields: dict[str, object] = {
        "learning_session_id": session_id,
        "student_external_id": STUDENT,
        "user_external_id": "user-ext-1",
        "user_role": "student",
        "topic_id": "topic-fractions",
        "pre_assessment_session_id": "pre-1",
        "study_session_id": "study-1",
        "post_assessment_session_id": "post-1",
        "blocked_session_id": None,
        "last_activity_at": ACTIVITY,
        **ORPHAN_FIELDS,
        **overrides,
    }
    return LearningSession(**fields)


def test_every_orphan_field_survives() -> None:
    """**The regression test proper.** Each of the five fields with no other durable home must
    round-trip. Asserted field by field rather than on the object, so a failure names the field
    that was lost instead of reporting that two objects differ."""

    async def run() -> None:
        async with rollback_session() as session:
            repo = LearningSessionRepository(session)
            await repo.upsert(_summary("thread-orphans"))
            stored = await repo.get("thread-orphans")

            assert stored is not None
            for field, expected in ORPHAN_FIELDS.items():
                assert getattr(stored, field) == expected, f"{field} was not preserved"

    asyncio.run(run())


def test_upsert_twice_writes_one_row_and_refreshes_it() -> None:
    """Falsification check #4 of the U7 design, at the repository level: the reconciler is
    expected to re-run over threads it has already seen, so a second pass must update in place
    rather than conflict or duplicate."""

    async def run() -> None:
        async with rollback_session() as session:
            repo = LearningSessionRepository(session)
            await repo.upsert(_summary("thread-twice", phase="study"))
            later = ACTIVITY + timedelta(days=1)
            await repo.upsert(
                _summary("thread-twice", phase="completed", last_activity_at=later)
            )

            rows = await repo.list_for_student(STUDENT)
            assert [r.learning_session_id for r in rows] == ["thread-twice"]
            assert rows[0].phase == "completed"
            assert rows[0].last_activity_at == later

    asyncio.run(run())


def test_upsert_does_not_erase_a_recorded_checkpoint_deletion() -> None:
    """`checkpoint_deleted_at` records a fact about the scaffolding, and a later consolidation
    pass has nothing new to say about it. If `upsert` included it in the update set, the next run
    after a deletion would write `None` back over it and the job would lose its own record of what
    it had already cleaned up - which is how a deletion job stops being idempotent."""

    async def run() -> None:
        async with rollback_session() as session:
            repo = LearningSessionRepository(session)
            await repo.upsert(_summary("thread-deleted"))

            deleted_at = datetime(2026, 9, 1, tzinfo=UTC)
            stored = await repo.get("thread-deleted")
            assert stored is not None
            stored.checkpoint_deleted_at = deleted_at
            await session.flush()

            await repo.upsert(_summary("thread-deleted", phase="completed"))
            await session.refresh(stored)
            assert stored.checkpoint_deleted_at == deleted_at

    asyncio.run(run())


def test_known_activity_reports_what_the_reconciler_can_skip() -> None:
    """The incremental filter. Without this the daily job calls `aget_tuple` once per thread
    forever, which at the projected scale is tens of thousands of reads to learn nothing."""

    async def run() -> None:
        async with rollback_session() as session:
            repo = LearningSessionRepository(session)
            await repo.upsert(_summary("thread-known"))

            known = await repo.known_activity()
            assert known["thread-known"] == ACTIVITY

    asyncio.run(run())


def test_a_session_with_no_student_yet_is_still_recordable() -> None:
    """A thread exists from its first turn, before `resolve_student` has run. Those abandoned
    "who is this?" threads are a real share of checkpoint storage (D-331 §1.2), so the summary must
    be able to describe one rather than requiring a student that never arrived."""

    async def run() -> None:
        async with rollback_session() as session:
            repo = LearningSessionRepository(session)
            await repo.upsert(
                _summary(
                    "thread-anonymous",
                    student_external_id=None,
                    parent_external_id=None,
                    topic_id=None,
                    phase="created",
                )
            )
            stored = await repo.get("thread-anonymous")
            assert stored is not None
            assert stored.student_external_id is None
            assert stored.phase == "created"

    asyncio.run(run())
