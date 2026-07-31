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

    Suppressing here instead removes the spans at the source, which is the only place
    that knows this query is a health check rather than real work. `excluded_urls` stays
    in `tracing.py` so no *server* span is created either; the two together are what make
    `/readyz` cost nothing.
    """

    async def _ping() -> None:
        # Suppression is set inside the coroutine, not around `wait_for`, so it applies in
        # the task that actually executes the query - OTel context does not propagate
        # outward from an awaited task to its parent, and a suppression attached to the
        # wrong context silently does nothing.
        with suppress_instrumentation():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_ping(), timeout=timeout_s)
        return True
    except Exception:
        return False
