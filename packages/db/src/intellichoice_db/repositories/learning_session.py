"""Reads and writes the durable learning-session summary (U7, D-331)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.learning_session import LearningSession

# Everything the reconciler projects from checkpoint state. `learning_session_id` is the conflict
# target and `consolidated_at` is server-defaulted, so neither belongs here.
_PROJECTED_COLUMNS = (
    "student_external_id",
    "parent_external_id",
    "user_external_id",
    "user_role",
    "week_id",
    "topic_id",
    "phase",
    "attendance_status",
    "attendance_resolution",
    "pre_assessment_session_id",
    "study_session_id",
    "post_assessment_session_id",
    "blocked_session_id",
    "bedrock_spend_cents",
    "last_activity_at",
)


class LearningSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, summary: LearningSession) -> None:
        """Insert, or refresh an existing summary in place.

        **Idempotent by construction, which is falsification check #4 in the U7 design.** A
        reconciler that ran twice must not produce two rows or a different second result, and the
        honest way to get that is a primary-key conflict clause rather than a read-then-write the
        next concurrent run could interleave with.

        **`checkpoint_deleted_at` is deliberately not refreshed.** It records a fact about the
        scaffolding, not about the session, and a later consolidation pass has nothing new to say
        about it. Overwriting it with `None` here would silently un-record a completed deletion.
        """
        values = {c: getattr(summary, c) for c in _PROJECTED_COLUMNS}
        stmt = (
            pg_insert(LearningSession)
            .values(learning_session_id=summary.learning_session_id, **values)
            .on_conflict_do_update(index_elements=["learning_session_id"], set_=values)
        )
        await self._session.execute(stmt)

    async def get(self, learning_session_id: str) -> LearningSession | None:
        stmt = select(LearningSession).where(
            LearningSession.learning_session_id == learning_session_id
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_student(self, student_external_id: str) -> list[LearningSession]:
        """The read this table was built to make possible: a student's session history, still
        answerable after the checkpoints behind it are gone."""
        stmt = (
            select(LearningSession)
            .where(LearningSession.student_external_id == student_external_id)
            .order_by(LearningSession.last_activity_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def known_activity(self) -> dict[str, datetime]:
        """`{learning_session_id: last_activity_at}` for every summary already stored.

        Lets the reconciler skip threads whose checkpoint has not advanced since the last run, so a
        daily job costs one `aget_tuple` per *changed* thread rather than per thread. Returned
        whole rather than queried per-thread: at the scale this table reaches, one round trip beats
        thousands.
        """
        stmt = select(LearningSession.learning_session_id, LearningSession.last_activity_at)
        return {row[0]: row[1] for row in (await self._session.execute(stmt)).all()}
