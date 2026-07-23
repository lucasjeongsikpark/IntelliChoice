import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Dev-only hardcoded default, mirroring apps/learning-api/config.py (SPEC D-006 rationale):
# this is replaced by real settings-driven config when the app wiring lands, not tuned here.
DEFAULT_DATABASE_URL = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Callers that already have a real settings-derived URL (both FastAPI apps' own
    `main.py`) should keep passing it explicitly - unaffected by the env var below.
    Standalone CLI scripts (curriculum loader, knowledge ingest, etc.) call this bare,
    which previously always got the hardcoded localhost default with no way to point
    them at a real deployed database - found live via a real `ConnectionRefusedError`
    when curriculum-load ran against real RDS during S32/D-084's holistic testing.
    `DATABASE_URL` env var now overrides the hardcoded default for exactly those bare
    callers, mirroring `packages/db/alembic/env.py`'s identical fix for migrations.
    """
    resolved = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_async_engine(resolved)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
