from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    """SPEC §5.23.2's exact field list, plus the two provenance fields it already
    names (`source_document_id`/`source_page`) - always backend-derived from the real
    `RagChunk`/`RagDocument` row the extraction cited, never trusted from the model's
    own claim (D-038's "model proposes, code re-derives" pattern). No PII: title/
    location/description come from public organizational documents, not a person.
    """

    title: str
    start_datetime: datetime
    end_datetime: datetime
    timezone: str
    location: str | None = None
    description: str = ""
    source_document_id: str
    source_page: int | None = None


class CalendarTransport(Protocol):
    """Google Calendar MCP stand-in (SPEC §5.23.3), called only through the MCP tool
    registry as the `calendar.create_event` tool - mirrors `EmailTransport`'s shape.
    """

    async def create_event(self, event: CalendarEvent) -> str: ...
