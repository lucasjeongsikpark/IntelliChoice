"""Turn-scoped cancellation for in-flight chat turns (D-402).

**Holds a session factory, not a session** - the same shape and the same reason as
`CostReservationRepository`. The cancellation has to be visible to a transaction that is
*already open*: the running turn holds the per-session advisory lock in its own
transaction-scoped session, and it has to observe a row committed by a different request after
that transaction began. A short, independently-committed transaction per operation makes that
true without depending on the ambient isolation level, and keeps the check off the turn's own
session so a cancellation lookup can never interact with the lock it is trying to release.
"""

import logging
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from intellichoice_db.models.chat_turn_cancellation import ChatTurnCancellation

logger = logging.getLogger(__name__)

# How long a cancellation row may sit unobserved before it is swept. Comfortably longer than
# `chat_turn_deadline_s` (50s), so a row can never be pruned out from under a turn that is still
# entitled to see it, and short enough that the table is empty at rest.
STALE_AFTER = timedelta(minutes=15)


class ChatTurnCancellationRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def request(self, *, chat_session_id: str, client_turn_id: str) -> None:
        """Record that this turn should stop, and sweep this session's stale rows.

        Idempotent: a visitor pressing Stop twice writes one row. `ON CONFLICT DO NOTHING`
        rather than an upsert, because the first request's `requested_at` is the one that
        matters for pruning - refreshing it on every repeat would let a client hold a row alive
        indefinitely.

        The sweep is here rather than in a scheduled job because it is bounded work on an index
        this query already touches, and because the alternative is a new nightly job to delete
        rows that are only ever a few bytes. A cancellation that raced its own turn's completion
        has nobody to observe and delete it, so without this the table would only grow.
        """
        async with self._session_factory() as session:
            await session.execute(
                pg_insert(ChatTurnCancellation)
                .values(chat_session_id=chat_session_id, client_turn_id=client_turn_id)
                .on_conflict_do_nothing(index_elements=["chat_session_id", "client_turn_id"])
            )
            await session.execute(
                delete(ChatTurnCancellation).where(
                    ChatTurnCancellation.chat_session_id == chat_session_id,
                    ChatTurnCancellation.requested_at < func.now() - STALE_AFTER,
                )
            )
            await session.commit()

    async def is_requested(self, *, chat_session_id: str, client_turn_id: str) -> bool:
        """Primary-key lookup, called at each of the turn's checkpoint boundaries.

        Cheap by design: the graph's super-steps are seconds apart and each one already does
        real database work, so one indexed existence check per boundary is not measurable beside
        a Bedrock call. Returning `False` on an error would be the wrong direction - see
        `consume`'s note on which way this fails.
        """
        async with self._session_factory() as session:
            found = await session.scalar(
                select(ChatTurnCancellation.client_turn_id).where(
                    ChatTurnCancellation.chat_session_id == chat_session_id,
                    ChatTurnCancellation.client_turn_id == client_turn_id,
                )
            )
            return found is not None

    async def consume(self, *, chat_session_id: str, client_turn_id: str) -> None:
        """Delete the row once the turn has acted on it.

        Called by the turn that stops, so the request is not re-observed by a *retry* of the
        same turn id - "Ask again" reuses the id, and a row left behind would cancel the retry
        the moment it started, which reads to the visitor as Stop having jammed the
        conversation.
        """
        async with self._session_factory() as session:
            await session.execute(
                delete(ChatTurnCancellation).where(
                    ChatTurnCancellation.chat_session_id == chat_session_id,
                    ChatTurnCancellation.client_turn_id == client_turn_id,
                )
            )
            await session.commit()
