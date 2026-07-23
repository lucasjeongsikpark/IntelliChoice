from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.tutor_chat import TutorChatMessage


class TutorChatMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, message: TutorChatMessage) -> TutorChatMessage:
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_for_student_in_window(
        self, student_external_id: str, start: datetime, end: datetime
    ) -> list[TutorChatMessage]:
        """S25 (plan §9): lets the consolidation worker fetch a chat turn's
        already-redacted message text by `message_id` (the id a `chat_turn` learning
        event references, never the text itself - see `services.memory_events`) for the
        one Bedrock call this project sends PII-redacted student text to besides chat
        itself (D-074).
        """
        stmt = select(TutorChatMessage).where(
            TutorChatMessage.student_external_id == student_external_id,
            TutorChatMessage.created_at >= start,
            TutorChatMessage.created_at < end,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_spend_cents_since(self, student_external_id: str, since: datetime) -> float:
        """Sum of `cost_cents` for this student's chat turns at or after `since` - the
        per-day cost-ceiling check reads this before every Bedrock-calling dispatch
        branch (SPEC §5.25.1 per-session budget's sibling: a per-*day* ceiling, since
        chat is the first surface a student can trigger LLM spend repeatedly across many
        sessions in one day).
        """
        stmt = select(func.coalesce(func.sum(TutorChatMessage.cost_cents), 0.0)).where(
            TutorChatMessage.student_external_id == student_external_id,
            TutorChatMessage.created_at >= since,
        )
        result = await self._session.execute(stmt)
        return float(result.scalar_one())

    async def purge_older_than(self, cutoff: datetime) -> int:
        """SPEC §15's 90-day retention - deletes every turn older than `cutoff`,
        regardless of student. Returns the number of rows removed.
        """
        result = cast(
            CursorResult,
            await self._session.execute(
                delete(TutorChatMessage).where(TutorChatMessage.created_at < cutoff)
            ),
        )
        return result.rowcount or 0
