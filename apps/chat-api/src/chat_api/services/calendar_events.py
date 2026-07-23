"""Deterministic event lookup/classification against the real `org_events` table
(SPEC §5.23 rewired for S18, plan §18-C2) - `calendar_extract` tries this path first,
with the existing LLM+RAG chunk extraction (`services/calendar.py`) kept as a fallback
for calendar content that hasn't been migrated into the structured table. No LLM call
is involved anywhere in this module - CLAUDE.md non-negotiable #2 (no runtime NL2SQL);
matching a query to an event is plain keyword overlap, and date classification is plain
arithmetic against `now`.

Status classification never trusts a possibly-stale stored `"upcoming"`/`"completed"`
value - only a stored `"canceled"`/`"changed"` designation (which nothing but a human
can set today, see `OrgEvent`'s own docstring) is taken as-is. Everything else is
recomputed against `now` every time, so a past event is never described as upcoming
regardless of when the row was last synced.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from dateutil.rrule import rrulestr
from intellichoice_db.models.org import OrgEvent
from intellichoice_shared.calendar import CalendarEvent

# Effective status shown to a caller - a superset of `OrgEvent.status`'s stored values
# ("scheduled" never surfaces directly; it always resolves to "upcoming"/"completed").
EventStatus = str

_STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "when",
    "what",
    "where",
    "add",
    "it",
    "to",
    "my",
    "for",
    "of",
    "on",
    "in",
    "at",
    "and",
    "coming",
    "up",
    "next",
    "event",
    "events",
    "calendar",
    "schedule",
    "about",
    "this",
    "that",
}


@dataclass(frozen=True)
class ClassifiedEvent:
    event: OrgEvent
    effective_status: EventStatus  # "upcoming" | "completed" | "canceled" | "changed"
    # Populated only when `event.recurrence_rule` still has a future occurrence -
    # the *displayed* start time for a recurring event, distinct from its original
    # `event.starts_at` (the very first occurrence, which may be long past).
    next_occurrence: datetime | None = None


def classify_event(event: OrgEvent, *, now: datetime) -> ClassifiedEvent:
    if event.status in ("canceled", "changed"):
        return ClassifiedEvent(event=event, effective_status=event.status)

    if event.recurrence_rule:
        rule = rrulestr(event.recurrence_rule, dtstart=event.starts_at)
        next_start = rule.after(now, inc=True)
        if next_start is not None:
            return ClassifiedEvent(
                event=event, effective_status="upcoming", next_occurrence=next_start
            )
        return ClassifiedEvent(event=event, effective_status="completed")

    if event.ends_at >= now:
        return ClassifiedEvent(event=event, effective_status="upcoming")
    return ClassifiedEvent(event=event, effective_status="completed")


def list_upcoming_events(
    events: list[OrgEvent], *, now: datetime, limit: int = 10
) -> list[ClassifiedEvent]:
    classified = [classify_event(event, now=now) for event in events]
    upcoming = [c for c in classified if c.effective_status == "upcoming"]
    upcoming.sort(key=lambda c: c.next_occurrence or c.event.starts_at)
    return upcoming[:limit]


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS and len(t) > 2}


def find_event_by_keywords(
    events: list[OrgEvent], query: str, *, now: datetime
) -> ClassifiedEvent | None:
    """Confident single-match keyword overlap between the query and each event's
    title - deliberately conservative: ambiguous (a tie) or weak (no overlap at all)
    matches return `None` so the caller falls back to RAG+LLM extraction or a generic
    listing rather than silently guessing which event the user meant.
    """
    query_tokens = _tokens(query)
    if not query_tokens:
        return None

    scored: list[tuple[int, OrgEvent]] = []
    for event in events:
        overlap = len(query_tokens & _tokens(event.title))
        if overlap > 0:
            scored.append((overlap, event))

    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return classify_event(scored[0][1], now=now)


def to_calendar_event(classified: ClassifiedEvent) -> CalendarEvent:
    """Converts a structured `org_events` row into the existing `CalendarEvent` shape
    so `calendar_action`'s interrupt/`.ics`/Google-calendar handling (unchanged, D-038's
    RAG-chunk provenance pattern) works identically regardless of source. There is no
    `RagDocument` behind a structured event, so `source_document_id` is a stand-in
    natural-key reference (`"org-event:<slug>"`) - still a real, resolvable identifier,
    just not a RAG document id.
    """
    event = classified.event
    starts_at = classified.next_occurrence or event.starts_at
    duration = event.ends_at - event.starts_at
    return CalendarEvent(
        title=event.title,
        start_datetime=starts_at,
        end_datetime=starts_at + duration,
        timezone=event.timezone,
        location=event.location,
        description=event.description,
        source_document_id=f"org-event:{event.event_external_id}",
        source_page=None,
    )
