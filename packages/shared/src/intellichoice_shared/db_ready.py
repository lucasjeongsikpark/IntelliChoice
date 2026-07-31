"""S34: `/readyz` DB-connectivity check, deliberately separate from `/healthz`.

`/healthz` is a pure liveness probe (no dependency checks) - it stays that way, used by
both the Docker `HEALTHCHECK` instruction and any external uptime monitor, so a transient
DB blip never looks like "the container itself is broken" and triggers a container
restart that wouldn't fix anything. `/readyz` is what the ALB target group should health-
check instead: it actually pings Postgres/MySQL, so a real DB outage makes the ALB stop
routing user traffic to a task that can only 500 on every DB-touching request, returning a
clean 503 instead. Found via S34's own local DB-connection-loss drill (`/healthz` never
reflected the outage, so the live ALB config would have kept routing to a broken task).
"""

import asyncio

from opentelemetry.instrumentation.utils import suppress_instrumentation
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def ping_engine(engine: AsyncEngine, timeout_s: float = 3.0) -> bool:
    """Pings `engine` with `SELECT 1`, emitting **no telemetry** (AUD-F-30).

    The suppression is the whole point of this docstring, because removing it does not
    break anything visible. `/readyz` is polled by the ALB every 15s per task and pings
    two engines, and those spans were ~97% of every trace this project ever recorded.

    **Excluding `/readyz` from FastAPI instrumentation alone made this worse, measured:**
    trace volume went *up* 3.4x (320 -> 1,095 per idle 10 minutes). Dropping the server
    span does not drop its children - it **orphans** them, and each orphaned `SELECT 1`
    becomes its own root segment, i.e. its own trace. So one health-check trace became
    two, and the new ones carry no HTTP URL at all, which is strictly worse for reading a
    scan's denominator: they cannot even be attributed to a route.

    **The suppression that actually matters is at the `/readyz` handler**, not here:
    per-query suppression is what failed the second time. This function suppressed itself
    and chat-api's corpus-provenance check - on the same handler, added later for an
    unrelated reason - kept emitting. Both apps' handlers now wrap their whole body, so
    anything added inside them is covered by construction. `excluded_urls` in `tracing.py`
    stops the *server* span; those two together are what make `/readyz` cost nothing.

    The suppression is kept here as well, because a health-check ping should not be traced
    whoever calls it, and this is the only place that knows the query is a liveness probe
    rather than work. It is belt-and-braces, not the mechanism.
    """

    async def _ping() -> None:
        # Redundant when the caller already suppressed - and a caller's suppression *does*
        # reach in here, verified rather than assumed: `asyncio.wait_for` creates a Task,
        # and a Task copies the current contextvars at creation, so an outer
        # `suppress_instrumentation()` applies inside. (Propagation is inward only;
        # changes made in here would not escape to the caller.)
        with suppress_instrumentation():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_ping(), timeout=timeout_s)
        return True
    except Exception:
        return False
