from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.assessment import (
    AssessmentAttempt,
    AssessmentItem,
    AssessmentItemState,
    AssessmentSession,
    BlockedSession,
)


class AssessmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(self, session_row: AssessmentSession) -> AssessmentSession:
        self._session.add(session_row)
        await self._session.flush()
        return session_row

    async def add_item(self, item: AssessmentItem) -> AssessmentItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def record_attempt(self, attempt: AssessmentAttempt) -> AssessmentAttempt:
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def record_attempt_if_first(self, attempt: AssessmentAttempt) -> AssessmentAttempt | None:
        """Insert, or return `None` if this item already has an attempt (AUD-L-10).

        The insert runs inside a SAVEPOINT so that losing the race leaves the surrounding
        request transaction usable - an `IntegrityError` on the outer transaction would
        poison every later statement in the same request, which for the answer path
        includes the item-status write and the graph's own bookkeeping.
        """
        try:
            async with self._session.begin_nested():
                self._session.add(attempt)
                await self._session.flush()
        except IntegrityError as exc:
            if "uq_assessment_attempts_session_variant" in str(exc.orig):
                return None
            raise
        return attempt

    async def create_blocked_session(self, blocked: BlockedSession) -> BlockedSession:
        self._session.add(blocked)
        await self._session.flush()
        return blocked

    async def get_session(self, assessment_session_id: str) -> AssessmentSession | None:
        return await self._session.get(AssessmentSession, assessment_session_id)

    async def get_items(self, assessment_session_id: str) -> list[AssessmentItem]:
        stmt = (
            select(AssessmentItem)
            .where(AssessmentItem.assessment_session_id == assessment_session_id)
            .order_by(AssessmentItem.display_order)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_attempts(self, assessment_session_id: str) -> list[AssessmentAttempt]:
        stmt = select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_session_id == assessment_session_id
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_attempt_by_idempotency_key(
        self, assessment_session_id: str, question_variant_id: str, idempotency_key: str
    ) -> AssessmentAttempt | None:
        stmt = select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_session_id == assessment_session_id,
            AssessmentAttempt.question_variant_id == question_variant_id,
            AssessmentAttempt.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_blocked_sessions_for_student(self, student_id: str) -> list[BlockedSession]:
        """SPEC §5.14.3 parent dashboard - weeks where the attendance gate stopped the
        session before any score was recorded, newest first.
        """
        stmt = (
            select(BlockedSession)
            .where(BlockedSession.student_external_id == student_id)
            .order_by(BlockedSession.blocked_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_item_state(self, item_state: AssessmentItemState) -> AssessmentItemState:
        self._session.add(item_state)
        await self._session.flush()
        return item_state

    async def get_item_states(self, assessment_session_id: str) -> list[AssessmentItemState]:
        stmt = (
            select(AssessmentItemState)
            .join(
                AssessmentItem,
                AssessmentItemState.assessment_item_id == AssessmentItem.assessment_item_id,
            )
            .where(AssessmentItem.assessment_session_id == assessment_session_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_item_state(self, assessment_item_id: str) -> AssessmentItemState | None:
        stmt = select(AssessmentItemState).where(
            AssessmentItemState.assessment_item_id == assessment_item_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def set_item_status(self, assessment_item_id: str, status: str) -> AssessmentItemState:
        """Sets `status` and opportunistically stamps `first_viewed_at` on first touch -
        there's no dedicated "view" event yet, so the first skip/flag/answer that reaches
        this item is treated as the first view (SPEC §5.9/§5.13, plan §18-L3).
        """
        state = await self.get_item_state(assessment_item_id)
        assert state is not None
        state.status = status
        if state.first_viewed_at is None:
            state.first_viewed_at = datetime.now()
        await self._session.flush()
        return state

    async def add_item_time(
        self, assessment_item_id: str, elapsed_ms: int
    ) -> AssessmentItemState:
        """S23 autosave tick: accumulates `elapsed_ms` into `time_spent_ms` (never
        overwrites - a student can revisit an item multiple times via nav-bar jump) and
        stamps `first_viewed_at` on first touch, same semantics as `set_item_status`.
        Does not touch `status` - viewing time alone isn't a skip/flag/answer action.
        """
        state = await self.get_item_state(assessment_item_id)
        assert state is not None
        state.time_spent_ms += elapsed_ms
        if state.first_viewed_at is None:
            state.first_viewed_at = datetime.now()
        await self._session.flush()
        return state

    async def mark_finalized(self, assessment_session_id: str, at: datetime) -> AssessmentSession:
        session_row = await self.get_session(assessment_session_id)
        assert session_row is not None
        session_row.finalized_at = at
        session_row.status = "completed"
        session_row.completed_at = at
        await self._session.flush()
        return session_row

    async def get_student_assessment_summary(self, student_id: str) -> list[AssessmentSession]:
        """SPEC §5.26.1 predefined method. Full scoring/aggregation (weighted bootstrap
        score, gain) lands in S5; this proves the parameterized-query shape the runtime
        must use instead of NL2SQL.
        """
        stmt = (
            select(AssessmentSession)
            .where(AssessmentSession.student_external_id == student_id)
            .order_by(AssessmentSession.started_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
