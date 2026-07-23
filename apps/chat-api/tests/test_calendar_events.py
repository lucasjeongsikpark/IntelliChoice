"""Pure-function coverage for `chat_api.services.calendar_events` (S18, plan §18-C2) -
no Postgres needed, since these functions only ever operate on `OrgEvent` objects
already loaded by the caller. The real site's own event history is entirely historical
(confirmed live during S18 - see DECISIONS.md), so upcoming/recurring classification is
exercised here against synthetic events with a controlled `now`, the same posture prior
sessions used for other date-gated real content (D-018-style pattern).
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from chat_api.services.calendar_events import (
    classify_event,
    find_event_by_keywords,
    list_upcoming_events,
    to_calendar_event,
)
from intellichoice_db.models.org import OrgEvent

_TZ = ZoneInfo("America/Chicago")


def _event(
    event_external_id: str,
    title: str,
    *,
    starts_at: datetime,
    ends_at: datetime,
    status: str = "scheduled",
    recurrence_rule: str | None = None,
    location: str | None = None,
) -> OrgEvent:
    return OrgEvent(
        event_external_id=event_external_id,
        title=title,
        description="",
        starts_at=starts_at,
        ends_at=ends_at,
        timezone="America/Chicago",
        location=location,
        audience="public",
        registration_url=None,
        recurrence_rule=recurrence_rule,
        status=status,
        source_url="https://www.intellichoice.org/event/example/",
        content_hash="hash",
    )


def test_classify_event_future_event_is_upcoming() -> None:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    event = _event(
        "future",
        "Future Workshop",
        starts_at=datetime(2023, 6, 1, 18, 0, tzinfo=_TZ),
        ends_at=datetime(2023, 6, 1, 20, 0, tzinfo=_TZ),
    )
    result = classify_event(event, now=now)
    assert result.effective_status == "upcoming"
    assert result.next_occurrence is None


def test_classify_event_past_event_is_completed_even_if_stored_status_is_stale() -> None:
    now = datetime(2026, 7, 19, tzinfo=UTC)
    event = _event(
        "past",
        "Scholarship Banquet",
        starts_at=datetime(2023, 12, 10, 17, 0, tzinfo=_TZ),
        ends_at=datetime(2023, 12, 10, 20, 0, tzinfo=_TZ),
        status="scheduled",
    )
    result = classify_event(event, now=now)
    assert result.effective_status == "completed"


def test_classify_event_trusts_stored_canceled_regardless_of_dates() -> None:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    event = _event(
        "canceled",
        "Canceled Meetup",
        starts_at=datetime(2023, 6, 1, tzinfo=_TZ),
        ends_at=datetime(2023, 6, 1, 1, 0, tzinfo=_TZ),
        status="canceled",
    )
    result = classify_event(event, now=now)
    assert result.effective_status == "canceled"


def test_classify_event_trusts_stored_changed() -> None:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    event = _event(
        "changed",
        "Rescheduled Meetup",
        starts_at=datetime(2023, 6, 1, tzinfo=_TZ),
        ends_at=datetime(2023, 6, 1, 1, 0, tzinfo=_TZ),
        status="changed",
    )
    result = classify_event(event, now=now)
    assert result.effective_status == "changed"


def test_classify_event_recurring_with_future_occurrence_is_upcoming() -> None:
    now = datetime(2023, 7, 15, tzinfo=UTC)
    start = datetime(2023, 7, 10, 18, 0, tzinfo=_TZ)
    event = _event(
        "weekly-workshop",
        "Weekly SAT Workshop",
        starts_at=start,
        ends_at=start + timedelta(hours=2),
        recurrence_rule="FREQ=WEEKLY;COUNT=4",
    )
    result = classify_event(event, now=now)
    assert result.effective_status == "upcoming"
    assert result.next_occurrence is not None
    assert result.next_occurrence > now


def test_classify_event_recurring_with_no_future_occurrences_is_completed() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    start = datetime(2023, 7, 10, 18, 0, tzinfo=_TZ)
    event = _event(
        "weekly-workshop",
        "Weekly SAT Workshop",
        starts_at=start,
        ends_at=start + timedelta(hours=2),
        recurrence_rule="FREQ=WEEKLY;COUNT=4",
    )
    result = classify_event(event, now=now)
    assert result.effective_status == "completed"
    assert result.next_occurrence is None


def test_list_upcoming_events_filters_sorts_and_limits() -> None:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    later = _event(
        "later",
        "Later Event",
        starts_at=datetime(2023, 8, 1, tzinfo=_TZ),
        ends_at=datetime(2023, 8, 1, 1, 0, tzinfo=_TZ),
    )
    sooner = _event(
        "sooner",
        "Sooner Event",
        starts_at=datetime(2023, 2, 1, tzinfo=_TZ),
        ends_at=datetime(2023, 2, 1, 1, 0, tzinfo=_TZ),
    )
    past = _event(
        "past",
        "Past Event",
        starts_at=datetime(2022, 1, 1, tzinfo=_TZ),
        ends_at=datetime(2022, 1, 1, 1, 0, tzinfo=_TZ),
    )
    result = list_upcoming_events([later, sooner, past], now=now, limit=1)
    assert [c.event.event_external_id for c in result] == ["sooner"]

    result_all = list_upcoming_events([later, sooner, past], now=now)
    assert [c.event.event_external_id for c in result_all] == ["sooner", "later"]


def test_find_event_by_keywords_confident_single_match() -> None:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    banquet = _event(
        "banquet",
        "Scholarship Banquet",
        starts_at=datetime(2023, 6, 1, tzinfo=_TZ),
        ends_at=datetime(2023, 6, 1, 1, 0, tzinfo=_TZ),
    )
    workshop = _event(
        "workshop",
        "Summer SAT Workshop",
        starts_at=datetime(2023, 7, 1, tzinfo=_TZ),
        ends_at=datetime(2023, 7, 1, 1, 0, tzinfo=_TZ),
    )
    match = find_event_by_keywords(
        [banquet, workshop], "add the scholarship banquet to my calendar", now=now
    )
    assert match is not None
    assert match.event.event_external_id == "banquet"


def test_find_event_by_keywords_returns_none_when_ambiguous_or_no_match() -> None:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    workshop_a = _event(
        "workshop-a",
        "Summer SAT Workshop",
        starts_at=datetime(2023, 7, 1, tzinfo=_TZ),
        ends_at=datetime(2023, 7, 1, 1, 0, tzinfo=_TZ),
    )
    workshop_b = _event(
        "workshop-b",
        "Summer SAT Workshop Week 2",
        starts_at=datetime(2023, 7, 8, tzinfo=_TZ),
        ends_at=datetime(2023, 7, 8, 1, 0, tzinfo=_TZ),
    )
    # Both events tie on "summer sat workshop" overlap - too ambiguous to pick one.
    tie = find_event_by_keywords([workshop_a, workshop_b], "summer sat workshop", now=now)
    assert tie is None

    # No keyword overlap at all with any event title.
    no_match = find_event_by_keywords([workshop_a], "when is the parent meeting", now=now)
    assert no_match is None

    # A generic "what's coming up" style query has no distinguishing keywords either.
    generic = find_event_by_keywords([workshop_a], "what events are coming up", now=now)
    assert generic is None


def test_to_calendar_event_uses_stored_fields_and_org_event_provenance() -> None:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    event = _event(
        "banquet",
        "Scholarship Banquet",
        starts_at=datetime(2023, 12, 10, 17, 0, tzinfo=_TZ),
        ends_at=datetime(2023, 12, 10, 20, 0, tzinfo=_TZ),
        location="Main Hall",
    )
    classified = classify_event(event, now=now)
    calendar_event = to_calendar_event(classified)

    assert calendar_event.title == "Scholarship Banquet"
    assert calendar_event.start_datetime == datetime(2023, 12, 10, 17, 0, tzinfo=_TZ)
    assert calendar_event.end_datetime == datetime(2023, 12, 10, 20, 0, tzinfo=_TZ)
    assert calendar_event.timezone == "America/Chicago"
    assert calendar_event.location == "Main Hall"
    assert calendar_event.source_document_id == "org-event:banquet"
    assert calendar_event.source_page is None


def test_to_calendar_event_recurring_uses_next_occurrence_not_original_start() -> None:
    now = datetime(2023, 7, 15, tzinfo=UTC)
    start = datetime(2023, 7, 10, 18, 0, tzinfo=_TZ)
    event = _event(
        "weekly-workshop",
        "Weekly SAT Workshop",
        starts_at=start,
        ends_at=start + timedelta(hours=2),
        recurrence_rule="FREQ=WEEKLY;COUNT=4",
    )
    classified = classify_event(event, now=now)
    calendar_event = to_calendar_event(classified)

    assert calendar_event.start_datetime > start
    assert calendar_event.end_datetime - calendar_event.start_datetime == timedelta(hours=2)
