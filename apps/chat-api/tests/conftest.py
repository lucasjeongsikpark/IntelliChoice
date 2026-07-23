import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from intellichoice_db.engine import create_engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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
