"""Extracts events from the org's Tribe Events Calendar REST API
(`/wp-json/tribe/events/v1/events`) - confirmed live during S18 to be richer and more
reliable than HTML-scraping the `/events/` listing page, which only ever renders a
fixed date window. Every event in the real dataset turned out to be historical (most
recent: 2025-05-10) - the org's public calendar hasn't been kept current since - so
recurrence and cancellation handling is exercised only via synthetic test data, not real
scraped rows (see DECISIONS.md).

The API's own `timezone`/`timezone_abbr` fields report a bare UTC offset (`"UTC+0"`),
confirmed live to be a WordPress site-timezone misconfiguration, not a real IANA zone
`.ics` generation can use - so it's never trusted. No event in the real dataset carries
venue data, so there's no per-event signal for a more specific zone than the org's own
headquarters (Dallas-founded, most branches in Texas).
"""

import hashlib
import html

from intellichoice_webcontent.records import EventRecord

_DEFAULT_TIMEZONE = "America/Chicago"


def _content_hash(*parts: str | None) -> str:
    joined = "|".join(p or "" for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def extract_events(raw_events: list[dict]) -> list[EventRecord]:
    records: list[EventRecord] = []
    for raw in raw_events:
        slug = raw.get("slug")
        raw_title = raw.get("title")
        starts_at = raw.get("start_date")
        ends_at = raw.get("end_date")
        if not slug or not raw_title or not starts_at or not ends_at:
            continue
        # WordPress serves post titles/descriptions as HTML-entity-encoded text (e.g.
        # "&#8211;" for an en dash) - confirmed live during S18 (several real event
        # titles use it) - unescaped before this ever reaches a rendered document.
        title = html.unescape(raw_title)

        location = None
        venues = raw.get("venue") or []
        if venues:
            venue = venues[0]
            location = venue.get("address") or venue.get("venue")

        description = html.unescape(raw.get("description") or "")
        records.append(
            EventRecord(
                event_external_id=slug,
                title=title,
                description=description,
                starts_at=starts_at,
                ends_at=ends_at,
                timezone=_DEFAULT_TIMEZONE,
                location=location,
                registration_url=raw.get("website") or None,
                recurrence_rule=None,
                source_url=raw.get("url", ""),
                content_hash=_content_hash(title, starts_at, ends_at, description, location),
            )
        )
    return records
