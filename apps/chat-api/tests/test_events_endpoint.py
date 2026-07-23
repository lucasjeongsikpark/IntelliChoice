"""`GET /chat/events` (S18, plan §18-C2) - a deterministic, anonymous-OK listing
straight from `org_events`, no auth, no model call. Calls the route function directly
against a real, rollback-isolated Postgres session (same pattern `test_role_access.py`
uses for a pure service-layer function) rather than through `TestClient(app)` - this
endpoint has no interrupt/session-scoped state worth exercising at the HTTP layer, and
a full app lifespan would commit rows for real instead of rolling back.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from chat_api.routers.events import list_events
from intellichoice_db.models.org import OrgEvent
from intellichoice_db.repositories.org import OrgEventRepository

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)


def _event(event_external_id: str, *, starts_at: datetime, ends_at: datetime) -> OrgEvent:
    return OrgEvent(
        event_external_id=event_external_id,
        title=f"Zqxvevt {event_external_id}",
        description="",
        starts_at=starts_at,
        ends_at=ends_at,
        timezone="America/Chicago",
        audience="public",
        source_url="https://www.intellichoice.org/event/example/",
        content_hash="hash",
    )


def test_list_events_returns_only_upcoming_within_public_audience() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = OrgEventRepository(session)
            now = datetime.now(UTC)
            await repo.upsert_event(
                _event(
                    "zqxvevt-upcoming",
                    starts_at=now + timedelta(days=10),
                    ends_at=now + timedelta(days=10, hours=1),
                )
            )
            await repo.upsert_event(
                _event(
                    "zqxvevt-past",
                    starts_at=now - timedelta(days=10),
                    ends_at=now - timedelta(days=10, hours=-1),
                )
            )
            await session.flush()

            response = await list_events(db=session, window_days=90)
            titles = {e.title for e in response.events}
            assert "Zqxvevt zqxvevt-upcoming" in titles
            assert "Zqxvevt zqxvevt-past" not in titles

    asyncio.run(run())


def test_list_events_respects_window_days() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = OrgEventRepository(session)
            now = datetime.now(UTC)
            await repo.upsert_event(
                _event(
                    "zqxvevt-far-future",
                    starts_at=now + timedelta(days=200),
                    ends_at=now + timedelta(days=200, hours=1),
                )
            )
            await session.flush()

            response = await list_events(db=session, window_days=30)
            assert response.events == []

            response_wide = await list_events(db=session, window_days=365)
            assert any("zqxvevt-far-future" in e.title for e in response_wide.events)

    asyncio.run(run())
