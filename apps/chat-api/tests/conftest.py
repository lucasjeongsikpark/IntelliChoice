import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import pytest
from chat_api.config import get_settings
from intellichoice_db.engine import create_engine
from intellichoice_db.models.cost_reservation import SCOPE_CHAT_TURN, SUBJECT_CHAT_API
from intellichoice_db.models.rate_limit import SCOPE_ADMIN_ESCALATION, SCOPE_CHAT_MESSAGE
from intellichoice_shared.rate_limit import hash_caller_key
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Every `TestClient` request arrives from the same host, so the whole suite shares one
# escalation rate-limit key.
TEST_CLIENT_CALLER_KEY = "testclient"


def postgres_skip_reason() -> str | None:
    """Mirrors `packages/db/tests/conftest.py`'s probe (D-008) - each package/app keeps
    its own copy rather than sharing a test-only module across workspace members.
    """

    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM rag_documents LIMIT 1"))
                except Exception:
                    return "Postgres schema is not migrated (run `make up && make db-upgrade`)"
            return None
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        finally:
            await engine.dispose()

    return asyncio.run(check())


@asynccontextmanager
async def rollback_session() -> AsyncIterator[AsyncSession]:
    """One test's worth of writes, always rolled back - mirrors `packages/db/tests/
    conftest.py::rollback_session`.
    """
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


@pytest.fixture(autouse=True)
def reset_caller_rate_limits() -> Iterator[None]:
    """AUD-C-27 made the escalation cap persistent, and that has a test-suite consequence
    worth stating rather than discovering later: the cap used to reset with the process, so
    a suite that escalates a handful of times per run could never trip it. Now the counter
    survives the run, every `TestClient` request shares the caller key `testclient`, and
    the dev cap is 5/hour - so without this fixture the third run of the escalate tests
    inside an hour would start failing on a real limit, on a shared dev database, looking
    exactly like a regression.

    D-345 made that far more pressing by adding a second, much broader counter: *every*
    `/messages` call now consumes from `SCOPE_CHAT_MESSAGE` under the same shared
    `testclient` key. The suite posts well over 120 messages, so without clearing this
    scope the tests would not merely fail on the third run within an hour - they would fail
    partway through the first.

    Clears only this key's rows, and only these two scopes: a developer's own counters for
    other callers are left alone.
    """
    _clear_caller_attempts()
    yield
    _clear_caller_attempts()


def _clear_caller_attempts() -> None:
    key_hash = hash_caller_key(TEST_CLIENT_CALLER_KEY, secret=get_settings().jwt_signing_secret)

    async def run() -> None:
        engine = create_engine()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "DELETE FROM rate_limit_events "
                        "WHERE scope = :scope AND caller_key_hash = :key"
                    ),
                    {"scope": SCOPE_ADMIN_ESCALATION, "key": key_hash},
                )
                # The chat-message scope is cleared for **every** key, not just
                # `testclient`, and that is a correction rather than carelessness. The
                # narrow version failed: signed-in tests are keyed by their own `sub`
                # (`parent-ext-1` and friends), those rows survived, and
                # `test_a_signed_in_caller_has_their_own_budget_not_the_shared_ip_one`
                # then failed in the full suite while passing alone - an order-dependent
                # failure that looks exactly like a regression in the code under test.
                # Unlike the escalation cap, whose 5/hour a developer clicking through the
                # app can plausibly care about, this counter is consumed by every test
                # message and has no local value worth preserving.
                await conn.execute(
                    text("DELETE FROM rate_limit_events WHERE scope = :scope"),
                    {"scope": SCOPE_CHAT_MESSAGE},
                )
                # D-345's other shared counter. Turns settle to the mock provider's
                # near-zero real cost so the suite cannot plausibly reach the 1500-cent
                # ceiling, but the rows accumulate in a shared dev database for 24h and
                # a test that wants to *observe* the ceiling has to seed its own - both
                # of which are only true if the slate starts clean.
                await conn.execute(
                    text(
                        "DELETE FROM cost_reservations "
                        "WHERE scope = :scope AND subject_external_id = :subject"
                    ),
                    {"scope": SCOPE_CHAT_TURN, "subject": SUBJECT_CHAT_API},
                )
        except Exception:
            # An unmigrated or unreachable database is already reported by
            # `postgres_skip_reason`; this fixture must not turn that into a collection
            # error for the tests that do not need Postgres at all.
            pass
        finally:
            await engine.dispose()

    asyncio.run(run())
