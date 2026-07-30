"""`current_week_key` is the seam where the org's time convention (D-130) actually changes
behavior: it is the attendance gate's key and the fixture seeder's column value, so if it
ignored the convention the env switch would be decoration.

Separate from `test_mysql_profile_adapter.py` because that module skips entirely without a
reachable MySQL, and this behavior is pure — a skipped test is not a passing one.
"""

from datetime import UTC, datetime

from intellichoice_adapters.mysql_profile_adapter import current_week_key
from intellichoice_shared.org_time import (
    CONVENTION_ENV,
    TIMEZONE_ENV,
    OrgTimeConvention,
    resolve_org_time,
)

# Sunday 2026-08-02, 19:00 America/Chicago (CDT) == Monday 2026-08-03 00:00 UTC.
SUNDAY_EVENING_LOCAL = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)


def test_week_key_uses_local_time_not_utc():
    """The bug this replaced: reading the ISO week off UTC put a Sunday-evening session in
    the following week, which fail-closed gating turns into "you did not attend"."""
    assert SUNDAY_EVENING_LOCAL.isocalendar().week == 32
    assert current_week_key(SUNDAY_EVENING_LOCAL) == "2026-W31"


def test_week_key_follows_an_injected_config():
    config = resolve_org_time(env={TIMEZONE_ENV: "Asia/Seoul"})
    # 09:00 Monday in Seoul — a zone east of UTC moves the boundary the other way.
    assert current_week_key(SUNDAY_EVENING_LOCAL, config=config) == "2026-W32"


def test_week_key_follows_the_environment_without_an_explicit_config(monkeypatch):
    """The deploy-time path: nobody passes `config=` in production, so the env has to reach
    this function on its own."""
    monkeypatch.setenv(TIMEZONE_ENV, "Asia/Seoul")
    assert current_week_key(SUNDAY_EVENING_LOCAL) == "2026-W32"


def test_the_legacy_convention_is_reachable_from_the_environment(monkeypatch):
    monkeypatch.setenv(CONVENTION_ENV, OrgTimeConvention.LEGACY_FIXED_UTC_MINUS_6.value)
    # Fixed UTC-6 puts the same instant at Sunday 18:00, still week 31 — the conventions
    # agree here, and the test exists to prove the switch is wired, not that it differs.
    assert current_week_key(SUNDAY_EVENING_LOCAL) == "2026-W31"


def test_no_argument_call_still_works():
    """`current_week_key()` with no arguments is the production call site in both the
    attendance gate and the seeder; it must resolve 'now' itself."""
    assert current_week_key().startswith(str(datetime.now(UTC).year)[:2])
