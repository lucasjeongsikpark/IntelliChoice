"""SPEC §5.23.4 / §5.31.2's ".ics syntax" executable evaluator."""

from datetime import datetime

import pytest
from intellichoice_adapters.ics import (
    InvalidCalendarEventError,
    generate_ics,
    validate_event,
    validate_ics_text,
)
from intellichoice_shared.calendar import CalendarEvent


def _event(**overrides: object) -> CalendarEvent:
    defaults: dict[object, object] = {
        "title": "Fall Parent Meeting",
        "start_datetime": datetime(2026, 11, 26, 9, 0),
        "end_datetime": datetime(2026, 11, 26, 10, 0),
        "timezone": "America/Los_Angeles",
        "location": "Main Branch",
        "description": "Discussion; agenda includes\nnew items, budget, and schedule.",
        "source_document_id": "doc-academic-calendar",
        "source_page": 1,
    }
    defaults.update(overrides)
    return CalendarEvent(**defaults)  # type: ignore[arg-type]


def test_generated_ics_round_trips_and_validates() -> None:
    text = generate_ics(_event())
    result = validate_ics_text(text)
    assert result.passed, result.failures


def test_generated_ics_has_required_properties() -> None:
    text = generate_ics(_event())
    assert "DTSTART" in text
    assert "DTEND" in text
    assert "UID" in text
    assert "DTSTAMP" in text


def test_two_calls_produce_distinct_uids() -> None:
    first = generate_ics(_event())
    second = generate_ics(_event())

    def _uid(text: str) -> str:
        return next(line for line in text.splitlines() if line.startswith("UID:"))

    assert _uid(first) != _uid(second)


def test_title_with_special_characters_escapes_and_round_trips() -> None:
    event = _event(title="Meeting, Part 1; Q&A session\nwith notes")
    text = generate_ics(event)
    result = validate_ics_text(text)
    assert result.passed, result.failures
    # Line folding/escaping proof: the raw unescaped title never appears as its own
    # unfolded physical line (commas/semicolons/newlines must be escaped by the library).
    assert "Meeting, Part 1; Q&A session\nwith notes" not in text


def test_invalid_timezone_raises_before_generating_any_text() -> None:
    event = _event(timezone="Not/A/Real/Zone")
    with pytest.raises(InvalidCalendarEventError):
        generate_ics(event)


def test_end_before_start_raises() -> None:
    event = _event(
        start_datetime=datetime(2026, 11, 26, 10, 0),
        end_datetime=datetime(2026, 11, 26, 9, 0),
    )
    with pytest.raises(InvalidCalendarEventError):
        generate_ics(event)


def test_validate_event_matches_generate_ics_validation() -> None:
    """`validate_event` lets a caller reject an unusable event before ever previewing
    it to a user, without needing to actually generate `.ics` text first."""
    with pytest.raises(InvalidCalendarEventError):
        validate_event(_event(timezone="Not/A/Real/Zone"))
    # A valid event doesn't raise.
    validate_event(_event())


def test_validate_ics_text_rejects_unparseable_text() -> None:
    result = validate_ics_text("this is not a calendar file")
    assert not result.passed
    assert result.failures


def test_validate_ics_text_rejects_missing_vevent() -> None:
    empty_calendar = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//\nEND:VCALENDAR\n"
    result = validate_ics_text(empty_calendar)
    assert not result.passed
    assert "no VEVENT component" in result.failures
