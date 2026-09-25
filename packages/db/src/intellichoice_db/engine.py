import os
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_LOCAL_HOSTS = {None, "localhost", "127.0.0.1"}

# Dev-only hardcoded default, mirroring apps/learning-api/config.py (SPEC D-006 rationale):
# this is replaced by real settings-driven config when the app wiring lands, not tuned here.
DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"
)

# ---------------------------------------------------------------------------------------
# The Postgres connection budget (D-473, `STAGING-CONN-CEILING`).
#
# Every number here is a *maximum*, because bursts reach maximums: E1 (D-461) watched the
# ALB p95 step policy scale learning-api 2 -> 3 tasks at 50 VUs, and the third replica's
# pool crossed `db.t4g.micro`'s ceiling with `asyncpg.TooManyConnectionsError` - 2x HTTP
# 500 on `POST /answers`. Scale-out reduced availability. The pool used to be 10 + 10 per
# task, sized in S34 for ONE process; it is a per-task constant, so autoscaling multiplied
# it. The ceiling cannot be raised: this account's Free Tier restrictions reject any
# instance above `micro` outright (S32/D-084), and lowering the replica ceiling would
# throw away the +41% throughput the third replica measurably gave (E1). So the pool is
# what moves.
#
# Demand rule (ARCHITECTURE, D-348/D-356): a request holds one pooled connection for its
# transaction and an SSE stream holds none, so `pool_size ~ concurrent requests per task`.
# At E1's failing level (50 VUs / 3 tasks ~ 17 concurrent per task) a 10-connection pool
# queues the excess for up to `pool_timeout` (30s default) - fail-slow, where 10 + 10 failed
# hard. E1 also showed the service is CPU-bound (92-99% ECS CPU) well before it is
# connection-bound, so the smaller pool is not the throughput limiter.
#
# `test_engine_pool_budget.py` re-derives this arithmetic against the replica ceilings
# parsed from the terraform files, so a future `autoscaling_max_capacity` bump fails a test
# instead of silently re-opening the defect.
# ---------------------------------------------------------------------------------------

# `db.t4g.micro` (1 GiB): Postgres' default `LEAST({DBInstanceClassMemory/9531392}, 5000)`.
RDS_MAX_CONNECTIONS = 112
# Postgres' `superuser_reserved_connections` default; RDS's own `rdsadmin` role sits there.
RDS_SUPERUSER_RESERVED = 3
# Per API task, outside the SQLAlchemy pool: the D-335 relay's dedicated LISTEN and NOTIFY
# connections (`session_event_relay.py`) plus the single psycopg connection
# `AsyncPostgresSaver.from_conn_string` opens (it is one `AsyncConnection`, not a pool).
API_TASK_FIXED_CONNECTIONS = 2 + 1
# Two ops-task CLIs can overlap (the daily 18:00 `session-consolidate` and 18:10
# `chat-purge` schedules); each calls `create_engine()` bare and gets this same pool.
OPS_TASKS_CONCURRENT = 2

DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 5


def connection_budget(
    *,
    api_task_ceiling: int,
    pool_size: int = DEFAULT_POOL_SIZE,
    max_overflow: int = DEFAULT_MAX_OVERFLOW,
) -> tuple[int, int]:
    """Return `(worst_case_demand, available)` for `api_task_ceiling` API tasks in total
    (learning-api's maximum plus chat-api's maximum) at the given per-task pool shape.

    Pure arithmetic, exposed so the budget test and this module agree on one formula.
    """
    per_pool = pool_size + max_overflow
    demand = api_task_ceiling * (per_pool + API_TASK_FIXED_CONNECTIONS)
    demand += OPS_TASKS_CONCURRENT * per_pool
    available = RDS_MAX_CONNECTIONS - RDS_SUPERUSER_RESERVED
    return demand, available


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


def ssl_connect_args(database_url: str) -> dict[str, object]:
    """S34: real RDS's own default parameter group ships `rds.force_ssl=1`; local
    docker-compose Postgres neither needs nor supports SSL. Detected by host, not a new
    setting - shared by `create_engine` below and `packages/db/alembic/env.py` (which
    builds its own engine via `async_engine_from_config`, not `create_engine`, so needs
    this called separately - found live when the engine.py fix alone didn't stop a real
    migration-task failure against real RDS). asyncpg's `ssl` connect arg needs an
    actual Python `True`/`SSLContext`, not a URL query-string value (SQLAlchemy's
    asyncpg dialect passes query params through to asyncpg verbatim as strings, with no
    bool coercion for `ssl` specifically) - hence `connect_args`, not `?ssl=true` in the
    DSN itself.

    A bare `ssl=True` (found live, one deploy attempt later than the fix above) uses
    `ssl.create_default_context()`, which performs *full* certificate verification -
    RDS's certificate chains up to Amazon's own RDS CA, not one in this minimal image's
    system trust store, so every connection failed
    (`ssl.SSLCertVerificationError: self-signed certificate in certificate chain`).
    `check_hostname=False`/`CERT_NONE` matches the same posture `checkpoint_database_
    url`'s `?sslmode=require` already has for the psycopg/LangGraph-checkpoint path
    (encrypt the connection, don't verify the specific CA chain) - reasonable given this
    only ever connects over the private VPC network in the first place, and keeps both
    connection paths' security posture consistent rather than one being stricter than
    the other by accident.
    """
    if make_url(database_url).host not in _LOCAL_HOSTS:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return {"ssl": ctx}
    return {}


def create_engine(
    database_url: str | None = None,
    *,
    pool_size: int = DEFAULT_POOL_SIZE,
    max_overflow: int = DEFAULT_MAX_OVERFLOW,
) -> AsyncEngine:
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
    across every concurrent request this one process handles. S34 chose 10+10=20 as a
    deliberately moderate bump for one process and wrote: "revisit ... if RDS connection
    exhaustion is ever observed live". **It was, in E1 (D-461)** - the defaults are now
    `DEFAULT_POOL_SIZE + DEFAULT_MAX_OVERFLOW` under the connection budget documented
    above (D-473), and the two FastAPI apps pass their settings-driven values so a
    deployment can retune per service without a code change. `pool_pre_ping=True` is unrelated to
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
    return create_async_engine(
        resolved,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        connect_args=ssl_connect_args(resolved),
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A unit of work: commits on a clean exit, rolls back on an exception.

    **It used to do neither** (D-284 addendum, fixed in D-294). It yielded a session and
    closed it, so a caller that wrote without committing got a **no-op that reported
    success** - `set_active_status` flushes, so a one-off script printed
    `activated 26, retired 3` and rolled the whole thing back on the way out. The count
    came from the script's own loop, not from the database, and nothing said a word. It
    was caught only because the export that followed produced an empty diff.

    **Why commit-on-exit rather than a louder error.** Measured before changing it: all 66
    `session_scope` blocks in the repo already commit explicitly, so this changes the
    behaviour of exactly nothing that exists - the CLIs commit deliberately (`_settle`
    exists for that) and the tests commit because they assert across sessions. What it
    protects is the *ad-hoc* script, which is where the bug bit, where it is least likely
    to be noticed and most likely to be trusted. It also matches the convention the
    request path already sets: `get_db_session` in both apps commits after its yield.

    **Reads are unaffected.** SQLAlchemy autobegins a transaction for a `SELECT` too, so a
    read-only scope commits an empty transaction here - which is a no-op, not a write.

    The rollback is written out rather than left to `AsyncSession.__aexit__`, which would
    do it anyway: the whole defect was behaviour that had to be inferred instead of read.
    """
    async with session_factory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
        await session.commit()
