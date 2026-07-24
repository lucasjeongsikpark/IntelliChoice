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

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def ping_engine(engine: AsyncEngine, timeout_s: float = 3.0) -> bool:
    async def _ping() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_ping(), timeout=timeout_s)
        return True
    except Exception:
        return False
