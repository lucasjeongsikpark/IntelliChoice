"""RFC 5545 `.ics` generation and validation (SPEC §5.23.4, §5.31.2's ".ics syntax"
executable evaluator), built on the `icalendar` library rather than hand-rolled
line-folding/escaping - a well-maintained, widely-used dependency handles that
correctly by construction. This module only supplies correct inputs (a fresh UID/
DTSTAMP per call, a validated timezone, UTC-normalized instants) and validates the
result; each SPEC §5.23.4 rule is its own small pure function, mirroring
`intellichoice_curriculum.validation`'s "one check per rule" shape.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from icalendar import Calendar, Event
from icalendar.cal import Component
from intellichoice_shared.calendar import CalendarEvent


class InvalidCalendarEventError(Exception):
    """Raised before any `.ics` text is generated - an unusable `CalendarEvent` never
    reaches the serializer."""


def _validate_timezone(event: CalendarEvent) -> ZoneInfo:
    try:
        return ZoneInfo(event.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidCalendarEventError(f"unknown timezone {event.timezone!r}") from exc


def _validate_datetimes(event: CalendarEvent) -> None:
    if event.end_datetime <= event.start_datetime:
        raise InvalidCalendarEventError("end_datetime must be after start_datetime")


def _to_utc(dt: datetime, tz: ZoneInfo) -> datetime:
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=tz)
    return aware.astimezone(UTC)


def validate_event(event: CalendarEvent) -> None:
    """Public entry point for the two pre-serialization checks `generate_ics` itself
    runs - lets a caller (e.g. `chat_api.services.calendar`'s extraction step) reject an
    unusable `CalendarEvent` before ever previewing it to a user, not only at the point
    of actually generating a `.ics` file.
    """
    _validate_timezone(event)
    _validate_datetimes(event)


def generate_ics(event: CalendarEvent) -> str:
    """Datetimes are normalized to UTC (RFC 5545's "form 2" UTC time, a `Z`-suffixed
    instant) rather than embedding a `VTIMEZONE` block - an unambiguous, always-valid
    representation that doesn't depend on generating a timezone-database-derived
    component. `event.timezone` is still validated as a real IANA name first (SPEC's
    own "Timezone" rule) even though the serialized instant itself is UTC.
    """
    tz = _validate_timezone(event)
    _validate_datetimes(event)

    calendar = Calendar()
    calendar.add("prodid", "-//IntelliChoice//chat.intellichoice.org//")
    calendar.add("version", "2.0")

    vevent = Event()
    vevent.add("uid", f"{uuid4()}@intellichoice.org")
    vevent.add("dtstamp", datetime.now(UTC))
    vevent.add("summary", event.title)
    vevent.add("dtstart", _to_utc(event.start_datetime, tz))
    vevent.add("dtend", _to_utc(event.end_datetime, tz))
    if event.location:
        vevent.add("location", event.location)
    vevent.add("description", event.description)
    calendar.add_component(vevent)

    return calendar.to_ical().decode("utf-8")


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    failures: list[str]


def _check_has_dtstart(vevent: Component) -> str | None:
    return None if vevent.get("dtstart") is not None else "missing DTSTART"


def _check_has_dtend(vevent: Component) -> str | None:
    return None if vevent.get("dtend") is not None else "missing DTEND"


def _check_has_uid(vevent: Component) -> str | None:
    return None if vevent.get("uid") else "missing UID"


def _check_has_dtstamp(vevent: Component) -> str | None:
    return None if vevent.get("dtstamp") is not None else "missing DTSTAMP"


_PER_EVENT_CHECKS = (_check_has_dtstart, _check_has_dtend, _check_has_uid, _check_has_dtstamp)


def validate_ics_text(text: str) -> ValidationResult:
    """Parses `text` back through `icalendar`'s own decoder first - a malformed
    line-fold or an unescaped comma/semicolon/newline would fail to parse at all, so a
    successful `from_ical` call is itself the escaping/line-folding proof - then checks
    each required property is present, plus no duplicate `UID`s across events.
    """
    failures: list[str] = []
    try:
        calendar = Calendar.from_ical(text)
    except ValueError as exc:
        return ValidationResult(passed=False, failures=[f"unparseable: {exc}"])

    vevents = [component for component in calendar.walk() if component.name == "VEVENT"]
    if not vevents:
        return ValidationResult(passed=False, failures=["no VEVENT component"])

    for vevent in vevents:
        for check in _PER_EVENT_CHECKS:
            failure = check(vevent)
            if failure:
                failures.append(failure)

    uids = [str(vevent.get("uid")) for vevent in vevents]
    if len(uids) != len(set(uids)):
        failures.append("duplicate UID across events")

    return ValidationResult(passed=not failures, failures=failures)
