"""AUD-C-27: the counter that makes SPEC §5.24.2's caller caps mean what they say.

Like `test_cost_reservation.py` and for the same reason, these cannot use
`rollback_session`: the point of `RateLimitRepository` is that it commits on its own
connection so a consumed attempt is visible to other callers. Each test cleans up by key.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.models.rate_limit import SCOPE_ADMIN_ESCALATION
from intellichoice_db.repositories.rate_limit import RateLimitRepository
from sqlalchemy import text

from .conftest import postgres_skip_reason

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

CALLER = "rate-limit-test-caller-hash"
OTHER_CALLER = "rate-limit-test-other-hash"
OTHER_SCOPE = "rate_limit_test_other_scope"
WINDOW = timedelta(hours=1)


async def _cleanup() -> None:
    engine = create_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM rate_limit_events WHERE caller_key_hash = ANY(:keys)"),
                {"keys": [CALLER, OTHER_CALLER]},
            )
    finally:
        await engine.dispose()


async def _backdate_oldest(caller_key_hash: str, age: timedelta) -> None:
    engine = create_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE rate_limit_events SET created_at = :at
                    WHERE event_id = (
                        SELECT event_id FROM rate_limit_events
                        WHERE caller_key_hash = :key ORDER BY created_at LIMIT 1
                    )
                    """
                ),
                {"at": datetime.now(UTC) - age, "key": caller_key_hash},
            )
    finally:
        await engine.dispose()


def _run(coro_factory) -> None:
    async def wrapped() -> None:
        engine = create_engine()
        try:
            repo = RateLimitRepository(create_session_factory(engine))
            await _cleanup()
            try:
                await coro_factory(repo)
            finally:
                await _cleanup()
        finally:
            await engine.dispose()

    asyncio.run(wrapped())


def test_the_cap_is_shared_across_repository_instances() -> None:
    """**The assertion `InMemoryRateLimiter` cannot pass, and the whole reason this table
    exists.** Two repository instances stand in for two ECS tasks: separate objects,
    separate connections, one database. Before AUD-C-27 each task held its own dict, so
    the deployed cap of 5 measured 8 on the real system.
    """

    async def body(first: RateLimitRepository) -> None:
        engine = create_engine()
        try:
            second = RateLimitRepository(create_session_factory(engine))
            granted = 0
            # Alternate between the two "tasks", the way an ALB spreads one caller.
            for attempt in range(6):
                repo = first if attempt % 2 == 0 else second
                if await repo.try_consume(
                    scope=SCOPE_ADMIN_ESCALATION,
                    caller_key_hash=CALLER,
                    max_per_window=3,
                    window=WINDOW,
                ):
                    granted += 1
            assert granted == 3
        finally:
            await engine.dispose()

    _run(body)


def test_concurrent_attempts_cannot_exceed_the_cap() -> None:
    """The arm the advisory lock exists for. A read-then-act count passes the sequential
    test above and still lets ten simultaneous callers through - the same property
    `test_cost_reservation.test_concurrent_reservations_cannot_exceed_the_ceiling` pins
    for the spend ledger.
    """

    async def body(repo: RateLimitRepository) -> None:
        results = await asyncio.gather(
            *(
                repo.try_consume(
                    scope=SCOPE_ADMIN_ESCALATION,
                    caller_key_hash=CALLER,
                    max_per_window=3,
                    window=WINDOW,
                )
                for _ in range(10)
            )
        )
        assert sum(results) == 3, results
        assert (
            await repo.attempts_since(
                scope=SCOPE_ADMIN_ESCALATION, caller_key_hash=CALLER, window=WINDOW
            )
            == 3
        )

    _run(body)


def test_attempts_are_scoped_by_surface_caller_and_window() -> None:
    """A cap another surface's traffic, another caller's traffic, or last hour's traffic
    can trip would block legitimate use - the three axes that make a counter a rate limit
    rather than a global switch.
    """

    async def body(repo: RateLimitRepository) -> None:
        assert await repo.try_consume(
            scope=SCOPE_ADMIN_ESCALATION,
            caller_key_hash=CALLER,
            max_per_window=1,
            window=WINDOW,
        )
        # Same caller, different surface: unaffected.
        assert await repo.try_consume(
            scope=OTHER_SCOPE, caller_key_hash=CALLER, max_per_window=1, window=WINDOW
        )
        # Different caller, same surface: unaffected.
        assert await repo.try_consume(
            scope=SCOPE_ADMIN_ESCALATION,
            caller_key_hash=OTHER_CALLER,
            max_per_window=1,
            window=WINDOW,
        )
        # Same caller, same surface, cap reached.
        assert not await repo.try_consume(
            scope=SCOPE_ADMIN_ESCALATION,
            caller_key_hash=CALLER,
            max_per_window=1,
            window=WINDOW,
        )

        # And the window releases it. Backdating past the window is what proves the
        # earlier refusal came from the count rather than from anything sticky.
        await _backdate_oldest(CALLER, timedelta(hours=2))
        assert await repo.try_consume(
            scope=SCOPE_ADMIN_ESCALATION,
            caller_key_hash=CALLER,
            max_per_window=1,
            window=WINDOW,
        )

    _run(body)


def test_an_expired_attempt_is_pruned_rather_than_accumulating() -> None:
    """No retention job covers this table, so `try_consume` prunes the key it already
    holds a lock on. Without this, a caller who returns every hour forever leaves a row
    per attempt behind forever.
    """

    async def body(repo: RateLimitRepository) -> None:
        assert await repo.try_consume(
            scope=SCOPE_ADMIN_ESCALATION,
            caller_key_hash=CALLER,
            max_per_window=5,
            window=WINDOW,
        )
        await _backdate_oldest(CALLER, timedelta(hours=2))
        assert await repo.try_consume(
            scope=SCOPE_ADMIN_ESCALATION,
            caller_key_hash=CALLER,
            max_per_window=5,
            window=WINDOW,
        )

        engine = create_engine()
        try:
            async with engine.connect() as conn:
                total = await conn.execute(
                    text("SELECT count(*) FROM rate_limit_events WHERE caller_key_hash = :key"),
                    {"key": CALLER},
                )
                # Two attempts, one of them expired and deleted by the second call.
                assert total.scalar_one() == 1
        finally:
            await engine.dispose()

    _run(body)
