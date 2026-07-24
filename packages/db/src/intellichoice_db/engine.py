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


def database_url_from_component_env_vars() -> str | None:
    """D-092: RDS's native `manage_master_user_password` (real auto-rotation, S33) makes
    the master password a Secrets-Manager-managed JSON secret, not a ready DSN string -
    ECS's `secrets` block can extract one JSON key per env var, but can't concatenate
    several into one URL, so the ops-task container (which every standalone CLI here
    runs through, via this function's env-var fallback) gets `DB_USERNAME`/`DB_PASSWORD`
    (secret-sourced) plus `DB_HOST`/`DB_PORT`/`DB_NAME` (plain, non-secret Terraform
    values) as five separate env vars instead. Checked before `DATABASE_URL` below -
    `None` (not all five present) falls through unchanged to the existing behavior.
    """
    username = os.environ.get("DB_USERNAME")
    password = os.environ.get("DB_PASSWORD")
    host = os.environ.get("DB_HOST")
    port = os.environ.get("DB_PORT")
    name = os.environ.get("DB_NAME")
    if not (username and password and host and port and name):
        return None
    return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{name}"


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Callers that already have a real settings-derived URL (both FastAPI apps' own
    `main.py`) should keep passing it explicitly - unaffected by the env vars below.
    Standalone CLI scripts (curriculum loader, knowledge ingest, etc.) call this bare,
    which previously always got the hardcoded localhost default with no way to point
    them at a real deployed database - found live via a real `ConnectionRefusedError`
    when curriculum-load ran against real RDS during S32/D-084's holistic testing.
    `DATABASE_URL` env var (or, since S33/D-092, the five-component fallback above)
    overrides the hardcoded default for exactly those bare callers, mirroring
    `packages/db/alembic/env.py`'s identical fix for migrations.

    S34: `pool_size`/`max_overflow` are explicit, not SQLAlchemy's bare defaults
    (5+10=15) - a real local k6 run of 150 concurrent learning sessions
    (load-tests/k6/learning_sessions.js) pushed average request latency to ~1.7s
    (SPEC §5.33.4 targets "near one second" P95) with a 15-connection ceiling shared
    across every concurrent request this one process handles. 10+10=20 is a deliberately
    moderate bump, not "as large as possible": staging's RDS instance is a Free Tier
    `db.t4g.micro` (T4g.micro ~1GB RAM caps Postgres' own `max_connections` around
    ~110, shared across *both* apps' pools plus each app's separate LangGraph
    `AsyncPostgresSaver` checkpoint pool, per `main.py`'s lifespan) - a much larger pool
    here risks exhausting that real, small ceiling instead of just being slow. Revisit
    together with the checkpoint pool's own sizing if RDS connection exhaustion is ever
    observed live (see DECISIONS.md's S34 entry). `pool_pre_ping=True` is unrelated to
    the sizing finding - added alongside it since S34 also ran a real DB-connection-loss
    drill (load-tests/drills/db_connection_loss.sh); without it, a connection that went
    stale while Postgres was down could be handed back out of the pool once Postgres
    returns, failing on first use instead of being detected and replaced by the pool
    itself.
    """
    resolved = (
        database_url
        or database_url_from_component_env_vars()
        or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    return create_async_engine(resolved, pool_size=10, max_overflow=10, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
