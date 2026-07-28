from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
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

    # `get_spend_cents_since` was removed in S42 (AUD-X-08). It summed `cost_cents` from
    # this table for the per-day chat ceiling, and that read was the defect: these rows
    # commit at request teardown, so concurrent turns each saw a stale total and each
    # received a full ceiling. The ceiling now reads `cost_reservations`, where a turn is
    # visible while it is still in flight. Deleted rather than left in place, because a
    # spend reader that no ceiling consults is how the next ceiling gets wired to the
    # wrong source. `cost_cents` stays on the row as the per-turn audit record.

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
