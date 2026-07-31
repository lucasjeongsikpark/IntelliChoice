"""The org's time convention is a placeholder with a switch (D-130), so these tests pin
both the default and the switch — a placeholder nobody can flip safely is just a hardcode
with a comment on it.

The Sunday cases are the reason the module exists: attendance gating keys off the ISO week,
ISO weeks start Monday, and Sunday evening in Central is already Monday in UTC. Reading the
week off UTC therefore filed a Sunday session into the *next* week, and with fail-closed
gating ("unknown attendance is not present") that blocks a student who actually attended.
"""

from datetime import UTC, datetime

import pytest
from intellichoice_shared.org_time import (
    CONFIRMED_ENV,
    CONVENTION_ENV,
    DEFAULT_TIMEZONE,
    TIMEZONE_ENV,
    InvalidOrgTimeConfigError,
    OrgTimeConvention,
    log_org_time_convention,
    resolve_org_time,
)

LEGACY = OrgTimeConvention.LEGACY_FIXED_UTC_MINUS_6.value


def test_default_is_the_documented_provisional_one_and_marks_itself_unconfirmed():
    config = resolve_org_time(env={})
    assert config.convention is OrgTimeConvention.LOCAL_DST_AWARE
    assert config.timezone_name == DEFAULT_TIMEZONE
    assert config.confirmed is False
    assert "PROVISIONAL" in config.describe()


def test_confirming_flips_the_flag_and_the_description():
    config = resolve_org_time(env={CONFIRMED_ENV: "true"})
    assert config.confirmed is True
    assert "PROVISIONAL" not in config.describe()
    assert "confirmed with the org" in config.describe()


@pytest.mark.parametrize("raw", ["true", "TRUE", "yes", "1"])
def test_confirmed_accepts_the_spellings_a_human_would_type(raw: str):
    assert resolve_org_time(env={CONFIRMED_ENV: raw}).confirmed is True


@pytest.mark.parametrize("raw", ["", "false", "no", "0", "maybe"])
def test_anything_else_is_not_confirmed(raw: str):
    """Fail closed on the flag too: only an affirmative silences the warning."""
    assert resolve_org_time(env={CONFIRMED_ENV: raw}).confirmed is False


def test_switching_the_convention_is_an_env_change_only():
    config = resolve_org_time(env={CONVENTION_ENV: LEGACY})
    assert config.convention is OrgTimeConvention.LEGACY_FIXED_UTC_MINUS_6
    assert "fixed UTC-6" in config.describe()


def test_switching_the_timezone_is_an_env_change_only():
    config = resolve_org_time(env={TIMEZONE_ENV: "Asia/Seoul"})
    assert config.timezone_name == "Asia/Seoul"
    assert config.local(datetime(2026, 7, 30, 0, 0, tzinfo=UTC)).hour == 9


@pytest.mark.parametrize(
    "env",
    [
        {CONVENTION_ENV: "local"},
        {CONVENTION_ENV: "utc"},
        {TIMEZONE_ENV: "America/Chicagoo"},
        {TIMEZONE_ENV: "UTC-6"},
    ],
)
def test_a_bad_value_raises_instead_of_falling_back_to_the_default(env: dict[str, str]):
    """The failure mode this guards is specific: a typo'd zone silently reverting to the
    provisional default would undo a *confirmed* decision at deploy time, invisibly."""
    with pytest.raises(InvalidOrgTimeConfigError):
        resolve_org_time(env=env)


# --- The week boundary, which is the part that changes behavior --------------------------


def test_sunday_evening_central_stays_in_its_own_week():
    """2026-08-02 is a Sunday. 19:00 Central (CDT, UTC-5) is 2026-08-03 00:00 UTC — Monday.
    A UTC reading calls that week 32; the org's Sunday is still week 31."""
    instant = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
    assert instant.isocalendar().week == 32  # the old, UTC-based answer
    assert resolve_org_time(env={}).week_key(instant) == "2026-W31"


def test_monday_morning_central_is_the_new_week():
    """The boundary has to move, not just shift: Monday 08:00 Central is week 32."""
    instant = datetime(2026, 8, 3, 13, 0, tzinfo=UTC)
    assert resolve_org_time(env={}).week_key(instant) == "2026-W32"


def test_dst_aware_and_legacy_agree_outside_the_disputed_hour():
    """The two conventions differ by exactly one hour, so they answer the same for all but
    a one-hour window per day. Recording that keeps the switch from looking scarier than it
    is: it is not a wholesale re-dating of history."""
    instant = datetime(2026, 7, 15, 18, 0, tzinfo=UTC)  # 13:00 CDT / 12:00 fixed-offset
    dst_aware = resolve_org_time(env={})
    legacy = resolve_org_time(env={CONVENTION_ENV: LEGACY})
    assert dst_aware.week_key(instant) == legacy.week_key(instant)
    assert dst_aware.local(instant).hour - legacy.local(instant).hour == 1


def test_the_conventions_disagree_inside_the_disputed_hour():
    """00:00-00:59 local in summer is the window where even the *date* differs, which is
    the whole reason the org has to choose rather than the code guessing."""
    instant = datetime(2026, 7, 16, 5, 30, tzinfo=UTC)  # 00:30 CDT, 23:30 fixed-offset
    dst_aware = resolve_org_time(env={})
    legacy = resolve_org_time(env={CONVENTION_ENV: LEGACY})
    assert dst_aware.local(instant).date() != legacy.local(instant).date()


def test_winter_is_identical_under_both_conventions():
    """Central Standard Time *is* UTC-6, so outside DST the legacy convention is correct
    and the choice is genuinely free. Worth pinning: it explains why nobody noticed."""
    instant = datetime(2026, 1, 15, 18, 0, tzinfo=UTC)
    dst_aware = resolve_org_time(env={})
    legacy = resolve_org_time(env={CONVENTION_ENV: LEGACY})
    assert dst_aware.local(instant) == legacy.local(instant)


def test_a_naive_instant_is_read_as_utc_not_as_local_time():
    """Every stored timestamp in both systems is UTC. Interpreting a naive datetime as
    local would shift attendance by the offset — silently, and only for callers that
    happened to pass a naive value."""
    naive = datetime(2026, 8, 3, 0, 0)
    aware = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
    config = resolve_org_time(env={})
    assert config.week_key(naive) == config.week_key(aware) == "2026-W31"


# --- The startup announcement -----------------------------------------------------------


def test_unconfirmed_convention_logs_at_warning(caplog):
    """An assumption that decides whether a student reaches their exam should be visible in
    every deploy's logs, not only in the module that defines it."""
    config = resolve_org_time(env={})
    with caplog.at_level("INFO"):
        log_org_time_convention(config)
    assert [r.levelname for r in caplog.records] == ["WARNING"]
    assert "PROVISIONAL" in caplog.text


def test_confirmed_convention_drops_to_info(caplog):
    config = resolve_org_time(env={CONFIRMED_ENV: "true"})
    with caplog.at_level("INFO"):
        log_org_time_convention(config)
    assert [r.levelname for r in caplog.records] == ["INFO"]
