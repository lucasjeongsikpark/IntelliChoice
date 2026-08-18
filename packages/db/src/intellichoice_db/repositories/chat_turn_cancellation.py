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
        """Record that this turn should stop, and sweep **every** stale row while here.

        Idempotent: a visitor pressing Stop twice writes one row. `ON CONFLICT DO NOTHING`
        rather than an upsert, because the first request's `requested_at` is the one that
        matters for pruning - refreshing it on every repeat would let a client hold a row alive
        indefinitely.

        The sweep is here rather than in a scheduled job because the alternative is a new nightly
        job to delete rows that are only ever a few bytes. A cancellation that raced its own
        turn's completion has nobody to observe and delete it, so without this the table would
        only grow.

        **The sweep is global, and D-416 made it so after a live probe.** It used to be scoped to
        `chat_session_id`, which reaped a session's own leftovers and nothing else. `POST
        /chat/sessions` persists nothing - it returns a bare uuid4 (D-345: *"a session id costs
        nothing until a message spends against it"*) - so this endpoint cannot tell a real session
        from an invented id, and it must not try: a visitor pressing Stop on their **first** turn
        is cancelling a session that has no checkpoint yet, so refusing to write without one would
        silently restore the defect D-402 exists to fix.

        What that leaves is an anonymous caller able to insert a row per fabricated
        `(uuid, turn id)` pair, each of which a per-session sweep could never reach because that
        id never returns. Measured on the deployed edge: `POST .../turns/probe/cancel` for an
        invented session answered 202. Unscoping the `WHERE` closes it without touching the
        authorization path - **any** Stop press now reaps **all** expired rows, so the table is
        bounded by 15 minutes of insert traffic rather than by callers being well behaved.

        No index on `requested_at`, deliberately: this table is meant to hold approximately zero
        rows, its whole content is younger than `STALE_AFTER`, and an index to help a sequential
        scan over a handful of rows would cost more to maintain than it saves. If it ever holds
        enough rows for that to be wrong, the sweep working is what will have kept it small.

        `STALE_AFTER` is 15 minutes against a 50s server-side turn deadline, so a row this
        deletes cannot belong to a turn still running.
        """
        async with self._session_factory() as session:
            await session.execute(
                pg_insert(ChatTurnCancellation)
                .values(chat_session_id=chat_session_id, client_turn_id=client_turn_id)
                .on_conflict_do_nothing(index_elements=["chat_session_id", "client_turn_id"])
            )
            await session.execute(
                delete(ChatTurnCancellation).where(
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
