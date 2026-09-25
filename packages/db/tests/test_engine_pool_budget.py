"""D-473 (`STAGING-CONN-CEILING`): the per-task pool must fit the RDS connection ceiling
at the autoscaling maximum of *both* API services together.

E1 (D-461) found scale-out reducing availability: at 50 VUs learning-api scaled 2 -> 3
tasks and the third replica's 10 + 10 pool pushed total demand past `db.t4g.micro`'s
~112 `max_connections` (`asyncpg.TooManyConnectionsError`, 2x HTTP 500). The pool is a
per-task constant that autoscaling multiplies, so the fix is arithmetic, and arithmetic is
what this file pins - against the replica ceilings read from the terraform files rather
than a copied number, so raising `autoscaling_max_capacity` (the D-344 shape: a capacity
authored in one place and assumed in another) fails here instead of on staging.

The budget itself, and why the pool moved rather than the ceiling or the replicas, is
documented in `intellichoice_db.engine`.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from intellichoice_db.engine import (
    API_TASK_FIXED_CONNECTIONS,
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_POOL_SIZE,
    connection_budget,
    create_engine,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ECS_SERVICE_VARIABLES = _REPO_ROOT / "terraform/modules/ecs-service/variables.tf"
_STAGING_MAIN = _REPO_ROOT / "terraform/environments/staging/main.tf"
_API_SERVICE_MODULES = ("ecs_service_learning_api", "ecs_service_chat_api")

# Headroom for what the budget does not model: `rdsadmin`'s own sessions, an operator's
# psql, the UD-2 read-only session, Alembic during a deploy.
_MIN_HEADROOM = 8


def _module_default_max_capacity() -> int:
    text = _ECS_SERVICE_VARIABLES.read_text()
    block = re.search(r'variable\s+"autoscaling_max_capacity"\s*\{(.*?)\n\}', text, flags=re.DOTALL)
    assert block, "autoscaling_max_capacity variable not found in the ecs-service module"
    default = re.search(r"^\s*default\s*=\s*(\d+)", block.group(1), flags=re.MULTILINE)
    assert default, "autoscaling_max_capacity has no numeric default"
    return int(default.group(1))


def _staging_module_block(module_name: str) -> str:
    text = _STAGING_MAIN.read_text()
    start = text.find(f'module "{module_name}"')
    assert start >= 0, f"module {module_name} not found in staging main.tf"
    end = text.find("\nmodule ", start + 1)
    return text[start : end if end >= 0 else len(text)]


def _staging_max_capacity(module_name: str) -> int:
    """The service's effective ceiling: an uncommented `autoscaling_max_capacity = N` in its
    staging module block, else the module default. Comment lines are skipped so D-344's
    retracted-and-explained override does not read as live."""
    block = _staging_module_block(module_name)
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        match = re.match(r"autoscaling_max_capacity\s*=\s*(\d+)", stripped)
        if match:
            return int(match.group(1))
    return _module_default_max_capacity()


def api_task_ceiling() -> int:
    return sum(_staging_max_capacity(name) for name in _API_SERVICE_MODULES)


def test_terraform_replica_ceilings_are_readable() -> None:
    # Guards the parser, not the number: if the terraform shape changes such that the
    # budget test below would silently compute against 0 tasks, this fails first.
    assert _module_default_max_capacity() >= 1
    assert api_task_ceiling() >= 2


def test_default_pool_fits_the_rds_ceiling_at_max_replicas() -> None:
    demand, available = connection_budget(api_task_ceiling=api_task_ceiling())
    assert demand + _MIN_HEADROOM <= available, (
        f"worst-case demand {demand} + headroom {_MIN_HEADROOM} exceeds the {available} "
        f"non-superuser slots on db.t4g.micro at {api_task_ceiling()} API tasks - "
        "re-derive the budget in intellichoice_db.engine before changing pool or capacity"
    )


def test_the_pre_d473_pool_would_not_have_fit() -> None:
    # The regression this file exists for: S34's 10 + 10 per task, at the same ceilings.
    demand, available = connection_budget(
        api_task_ceiling=api_task_ceiling(), pool_size=10, max_overflow=10
    )
    assert demand > available


def test_fixed_per_task_connections_match_the_code_paths() -> None:
    # relay LISTEN + relay NOTIFY (session_event_relay.py) + one AsyncPostgresSaver
    # connection (`from_conn_string` opens a single AsyncConnection, not a pool).
    assert API_TASK_FIXED_CONNECTIONS == 3


def _pool_shape(
    pool_size: int = DEFAULT_POOL_SIZE, max_overflow: int = DEFAULT_MAX_OVERFLOW
) -> tuple[int, int]:
    # No connection is opened: SQLAlchemy's pool is lazy, so this reads configuration only.
    async def read() -> tuple[int, int]:
        engine = create_engine(pool_size=pool_size, max_overflow=max_overflow)
        try:
            pool = engine.pool
            return pool.size(), pool._max_overflow  # type: ignore[attr-defined]
        finally:
            await engine.dispose()

    return asyncio.run(read())


def test_bare_create_engine_uses_the_budget_defaults() -> None:
    assert _pool_shape() == (DEFAULT_POOL_SIZE, DEFAULT_MAX_OVERFLOW)


def test_create_engine_honours_explicit_pool_shape() -> None:
    assert _pool_shape(pool_size=2, max_overflow=1) == (2, 1)
