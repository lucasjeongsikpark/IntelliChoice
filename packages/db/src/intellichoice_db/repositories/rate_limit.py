"""Cross-task counter for SPEC §5.24.2's caller caps (AUD-C-27).

Holds a **session factory**, not a session, for the same reason
`CostReservationRepository` does: the request's own session does not commit until
FastAPI's dependency teardown, after the response, so a consumed attempt written on it
would be invisible to exactly the concurrent callers it needs to stop. A rate limiter
whose writes land after the response has no effect within the window it is enforcing.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from intellichoice_db.models.rate_limit import RateLimitEvent


class RateLimitRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def try_consume(
        self,
        *,
        scope: str,
        caller_key_hash: str,
        max_per_window: int,
        window: timedelta,
    ) -> bool:
        """Record one attempt and return whether it is within the cap.

        Serialized by a transaction-scoped advisory lock on (scope, caller), exactly as
        `CostReservationRepository.reserve` is and for the same reason: under READ
        COMMITTED, two concurrent callers counting before either commits both see the
        pre-insert total and both pass. The lock is held across a count, a prune and an
        insert - three fast statements on one index - and never across anything else.

        Keyed on `caller_key_hash`, so this repository never receives the caller key
        itself (see `intellichoice_db.models.rate_limit`).
        """
        cutoff = datetime.now(UTC) - window
        async with self._session_factory() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"{scope}:{caller_key_hash}"},
            )
            count = await self._count_since(
                session, scope=scope, caller_key_hash=caller_key_hash, cutoff=cutoff
            )
            if count >= max_per_window:
                # Commit rather than roll back: nothing was written, and this releases the
                # advisory lock now instead of holding it to teardown.
                await session.commit()
                return False

            # Prune this caller's own expired rows only. Deleting other keys' rows while
            # holding this key's lock would be cross-key contention for no benefit.
            await session.execute(
                delete(RateLimitEvent).where(
                    RateLimitEvent.scope == scope,
                    RateLimitEvent.caller_key_hash == caller_key_hash,
                    RateLimitEvent.created_at < cutoff,
                )
            )
            session.add(RateLimitEvent(scope=scope, caller_key_hash=caller_key_hash))
            await session.commit()
            return True

    async def attempts_since(
        self, *, scope: str, caller_key_hash: str, window: timedelta
    ) -> int:
        """Read-only, no lock - for tests and for answering "how close is this caller?"
        without consuming an attempt.
        """
        async with self._session_factory() as session:
            return await self._count_since(
                session,
                scope=scope,
                caller_key_hash=caller_key_hash,
                cutoff=datetime.now(UTC) - window,
            )

    @staticmethod
    async def _count_since(
        session, *, scope: str, caller_key_hash: str, cutoff: datetime
    ) -> int:
        stmt = select(func.count()).where(
            RateLimitEvent.scope == scope,
            RateLimitEvent.caller_key_hash == caller_key_hash,
            RateLimitEvent.created_at >= cutoff,
        )
        result = await session.execute(stmt)
        return int(result.scalar_one())
