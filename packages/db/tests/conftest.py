import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from intellichoice_db.engine import create_engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def postgres_skip_reason() -> str | None:
    """Mirrors the MySQL skip-if-unreachable probe (see DECISIONS.md D-008): returns None
    when round-trip tests can run, otherwise a reason pytest can show.
    """

    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM topics LIMIT 1"))
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
    """One repository call per test runs inside a transaction that is always rolled back,
    so round-trip tests never need a separate test database or leave data behind.
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
