"""SPEC §5.23/plan §18-C2: `GET /chat/events` - a deterministic, anonymous-OK listing
straight from `org_events` (public audience only, no auth, no model call) so a
frontend can show a calendar card without spending a chat turn on it. Shares its
classification logic with `calendar_extract`'s in-graph listing (`services.
calendar_events`), so this endpoint and a "what's coming up?" chat answer never
disagree about what counts as upcoming.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from intellichoice_db.repositories.org import OrgEventRepository
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.dependencies import get_db_session
from chat_api.services.calendar_events import list_upcoming_events
from chat_api.services.role_access import PUBLIC_AUDIENCE

router = APIRouter(prefix="/chat", tags=["chat-events"])

_MAX_WINDOW_DAYS = 365
_MAX_RESULTS = 50


class UpcomingEventResponse(BaseModel):
    title: str
    starts_at: str
    location: str | None = None


class EventsResponse(BaseModel):
    events: list[UpcomingEventResponse]


@router.get("/events", response_model=EventsResponse)
async def list_events(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    window_days: int = 90,
) -> EventsResponse:
    repo = OrgEventRepository(db)
    events = await repo.list_events(audiences=[PUBLIC_AUDIENCE])

    now = datetime.now(UTC)
    horizon = now + timedelta(days=max(1, min(window_days, _MAX_WINDOW_DAYS)))
    upcoming = [
        classified
        for classified in list_upcoming_events(events, now=now, limit=_MAX_RESULTS)
        if (classified.next_occurrence or classified.event.starts_at) <= horizon
    ]

    return EventsResponse(
        events=[
            UpcomingEventResponse(
                title=classified.event.title,
                starts_at=(classified.next_occurrence or classified.event.starts_at).isoformat(),
                location=classified.event.location,
            )
            for classified in upcoming
        ]
    )
