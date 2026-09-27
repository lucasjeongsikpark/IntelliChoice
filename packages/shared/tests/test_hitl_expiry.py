"""The pending-approval TTL rule (HB-CHAT-F1): pure, so every boundary is pinned here and
the route tests only need to show the rule is wired, not re-derive it.
"""

import logging
from datetime import UTC, datetime, timedelta, timezone

import pytest
from intellichoice_shared.hitl_expiry import (
    EXPIRING_INTERRUPT_TYPES,
    PENDING_APPROVAL_TTL,
    pause_age,
    pause_expired,
)

STARTED = datetime(2026, 9, 27, 9, 30, tzinfo=UTC)
CREATED_AT = STARTED.isoformat()
ONE_SECOND = timedelta(seconds=1)


def test_the_ttl_is_twenty_four_hours_and_covers_exactly_the_external_action_types() -> None:
    assert PENDING_APPROVAL_TTL == timedelta(hours=24)
    assert EXPIRING_INTERRUPT_TYPES == {"email_approval", "calendar_action", "location_consent"}


@pytest.mark.parametrize("interrupt_type", sorted(EXPIRING_INTERRUPT_TYPES))
def test_an_external_action_pause_expires_one_second_past_the_ttl(interrupt_type: str) -> None:
    now = STARTED + PENDING_APPROVAL_TTL + ONE_SECOND
    assert pause_expired(CREATED_AT, now=now, interrupt_type=interrupt_type) is True


@pytest.mark.parametrize("interrupt_type", sorted(EXPIRING_INTERRUPT_TYPES))
def test_an_external_action_pause_is_live_one_second_under_the_ttl(interrupt_type: str) -> None:
    now = STARTED + PENDING_APPROVAL_TTL - ONE_SECOND
    assert pause_expired(CREATED_AT, now=now, interrupt_type=interrupt_type) is False


@pytest.mark.parametrize("interrupt_type", sorted(EXPIRING_INTERRUPT_TYPES))
def test_exactly_at_the_ttl_is_not_yet_older_than_it(interrupt_type: str) -> None:
    now = STARTED + PENDING_APPROVAL_TTL
    assert pause_expired(CREATED_AT, now=now, interrupt_type=interrupt_type) is False


@pytest.mark.parametrize("interrupt_type", ["child_selection", "intervention_choice"])
def test_a_selection_pause_never_expires(interrupt_type: str) -> None:
    now = STARTED + timedelta(days=10)
    assert pause_expired(CREATED_AT, now=now, interrupt_type=interrupt_type) is False


def test_a_missing_timestamp_fails_open_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="intellichoice_shared.hitl_expiry"):
        expired = pause_expired(
            None, now=STARTED + timedelta(days=10), interrupt_type="email_approval"
        )
    assert expired is False
    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == "hitl_pause_timestamp_invalid"
    assert record.reason == "missing"  # type: ignore[attr-defined]


def test_an_unparseable_timestamp_fails_open_and_warns_without_echoing_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="intellichoice_shared.hitl_expiry"):
        expired = pause_expired(
            "not-a-timestamp",
            now=STARTED + timedelta(days=10),
            interrupt_type="calendar_action",
        )
    assert expired is False
    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert record.reason == "unparseable"  # type: ignore[attr-defined]
    assert "not-a-timestamp" not in record.getMessage()


def test_a_non_expiring_type_never_parses_or_warns(caplog: pytest.LogCaptureFixture) -> None:
    """A selection pause with a bad timestamp is not an anomaly worth a warning - the rule
    never needed its age."""
    with caplog.at_level(logging.WARNING, logger="intellichoice_shared.hitl_expiry"):
        assert pause_expired(None, now=STARTED, interrupt_type="child_selection") is False
    assert caplog.records == []


def test_an_offset_timestamp_is_compared_as_the_instant_it_names() -> None:
    kst = timezone(timedelta(hours=9))
    created_at = STARTED.astimezone(kst).isoformat()
    assert pause_age(created_at, now=STARTED + ONE_SECOND) == ONE_SECOND


def test_a_naive_timestamp_is_read_as_utc() -> None:
    created_at = STARTED.replace(tzinfo=None).isoformat()
    assert pause_age(created_at, now=STARTED + ONE_SECOND) == ONE_SECOND


def test_a_pause_stamped_in_the_future_is_not_expired() -> None:
    """Clock skew between writer and reader yields a negative age, never an expiry."""
    created_at = (STARTED + timedelta(hours=1)).isoformat()
    assert pause_expired(created_at, now=STARTED, interrupt_type="email_approval") is False


def test_a_naive_now_is_a_caller_bug() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        pause_expired(CREATED_AT, now=STARTED.replace(tzinfo=None), interrupt_type="email_approval")
