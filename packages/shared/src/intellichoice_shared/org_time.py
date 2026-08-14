"""The organization's local-time convention — a placeholder with a switch, not a decision.

**Why this module exists.** Attendance gating (SPEC §5.6.2) hangs off "which week is it",
and that question has no answer without knowing what local time the organization keeps.
The existing `icrest` system stores session times in UTC and its reports convert them with
a **hard-coded UTC−6** written literally into three queries — which is US Central *Standard*
time, so it is an hour early from mid-March to early November. Two conventions are therefore
defensible, and choosing between them is an operational call belonging to the org, not an
engineering one (see Message A in [S42_ORG_ASKS.md](../../../../docs/S42_ORG_ASKS.md)):

1. **`local_dst_aware`** — real local time in a named IANA zone, DST included. Correct, but
   in summer it disagrees by an hour with what the org's own reports display.
2. **`legacy_fixed_utc_minus_6`** — mimic the existing reports exactly. Always consistent
   with what staff already read, and both are an hour early in summer.

**The default is provisional and says so.** `local_dst_aware` + `America/Chicago`, chosen
because it is correct by construction and because the alternative exists only to mirror a
display bug. `America/Chicago` itself is *inferred from the `-6` in someone else's code*,
which is not the same as knowing. Until the org confirms, `ORG_TIME_CONFIRMED` stays false
and both apps log the unconfirmed convention at startup — an assumption that announces
itself, because the failure mode here is the one this project keeps meeting: a default that
was reasonable when written, hardening silently into a decision nobody made.

**Switching, once confirmed** — set environment variables, deploy, done. No code change:

    ORG_TIMEZONE=America/Chicago            # or whatever the org confirms
    ORG_TIME_CONVENTION=local_dst_aware     # or legacy_fixed_utc_minus_6
    ORG_TIME_CONFIRMED=true                 # silences the startup warning

**Deliberately not prefixed per app.** Every other setting is `LEARNING_`/`CHAT_`-scoped;
these three are not, because the two apps disagreeing about what week it is would be a real
defect — learning-api gating on week N while chat reports week N+1 — and there is no scenario
where one organization is in two timezones. One variable, both apps, no way to skew them.

**Scope note.** This decides the *week boundary* used for attendance, which is the part that
changes behavior. It does not yet cover which sessions the org actually runs: a Sunday-evening
session is Monday in UTC, so it lands in the *next* ISO week under a naive UTC reading. That is
why the week key is computed in local time here rather than in UTC, and why the org ask needs
one more sentence about session scheduling than it currently has.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

TIMEZONE_ENV = "ORG_TIMEZONE"
CONVENTION_ENV = "ORG_TIME_CONVENTION"
CONFIRMED_ENV = "ORG_TIME_CONFIRMED"

# Provisional until the org manager confirms. See the module docstring.
DEFAULT_TIMEZONE = "America/Chicago"

# The offset `icrest`'s reports hard-code. Named rather than inlined so a reader of the
# `legacy` branch can see it is someone else's constant being deliberately reproduced.
LEGACY_FIXED_OFFSET_HOURS = -6


class OrgTimeConvention(StrEnum):
    """How UTC instants become the organization's local calendar."""

    LOCAL_DST_AWARE = "local_dst_aware"
    LEGACY_FIXED_UTC_MINUS_6 = "legacy_fixed_utc_minus_6"


class InvalidOrgTimeConfigError(ValueError):
    """Raised when the environment asks for a convention or zone that does not exist.

    Fails loudly at resolution rather than falling back to the default: a typo'd
    `ORG_TIMEZONE` silently reverting to Chicago is how a confirmed decision gets undone
    by a deploy, which is exactly what this module exists to prevent.
    """


@dataclass(frozen=True)
class OrgTimeConfig:
    convention: OrgTimeConvention
    timezone_name: str
    confirmed: bool

    def tzinfo(self) -> timezone | ZoneInfo:
        if self.convention is OrgTimeConvention.LEGACY_FIXED_UTC_MINUS_6:
            return timezone(timedelta(hours=LEGACY_FIXED_OFFSET_HOURS))
        return ZoneInfo(self.timezone_name)

    def local(self, instant: datetime | None = None) -> datetime:
        """The organization's local wall-clock time for a UTC instant."""
        instant = instant or datetime.now(UTC)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        return instant.astimezone(self.tzinfo())

    def week_key(self, instant: datetime | None = None) -> str:
        """`YYYY-Www`, the ISO week of the *local* date — the attendance gate's key."""
        iso = self.local(instant).isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def display_time_zone(self) -> str:
        """An IANA id a **browser** can pass to `Intl`/`toLocaleDateString`.

        Exists so the frontend never holds its own copy of the zone. Before this, every
        date on the student dashboard was formatted with `toLocaleDateString()` and no
        `timeZone`, i.e. in *the viewer's* zone — so a parent reading the same chart from
        another country saw the org's days shifted, and a late-evening session could show
        on the wrong date entirely. The value is served from here (D-324), which keeps this
        module's own rule intact: one variable, both apps, **no way to skew them**.

        **Not simply `timezone_name`,** and that is the whole reason this is a method.
        Under the legacy convention the effective zone is a fixed UTC−6 and
        `timezone_name` is unused, so returning it would silently display DST-aware
        Chicago time while every server-side calculation used the fixed offset — the two
        conventions disagreeing by an hour for eight months of the year, which is the
        exact bug `legacy_fixed_utc_minus_6` exists to reproduce faithfully.

        The `Etc/GMT` sign is **inverted** by POSIX convention: `Etc/GMT+6` is UTC−6, not
        UTC+6. Derived from `LEGACY_FIXED_OFFSET_HOURS` rather than written as a literal,
        so the sign flip happens once, here, next to the comment explaining it.
        """
        if self.convention is OrgTimeConvention.LEGACY_FIXED_UTC_MINUS_6:
            return f"Etc/GMT{-LEGACY_FIXED_OFFSET_HOURS:+d}"
        return self.timezone_name

    def local_date_key(self, instant: datetime) -> str:
        """`YYYY-MM-DD` for the org's **local** calendar day, for bucketing by day.

        Bucketing on `instant.date()` buckets on the *UTC* day, which is a different day
        for every session that runs after 7pm Central. Measured on the dashboard's
        accuracy trend: an attempt at 02:00 UTC is 21:00 the previous evening in Chicago,
        so a student's Thursday-evening work landed in Friday's bucket and both days'
        accuracy numbers were wrong (D-324). Any per-day aggregate a human reads has to
        agree with the day that human was in.
        """
        return self.local(instant).date().isoformat()

    def describe(self) -> str:
        state = "confirmed with the org" if self.confirmed else "PROVISIONAL, unconfirmed"
        if self.convention is OrgTimeConvention.LEGACY_FIXED_UTC_MINUS_6:
            where = f"fixed UTC{LEGACY_FIXED_OFFSET_HOURS:+d} (matching icrest's reports)"
        else:
            where = f"{self.timezone_name} (DST-aware)"
        return f"{where} — {state}"


def resolve_org_time(env: dict[str, str] | None = None) -> OrgTimeConfig:
    """Read the convention from the environment. Pure, and takes `env` for testability."""
    source = os.environ if env is None else env

    raw_convention = source.get(CONVENTION_ENV) or OrgTimeConvention.LOCAL_DST_AWARE.value
    try:
        convention = OrgTimeConvention(raw_convention)
    except ValueError as exc:
        valid = ", ".join(c.value for c in OrgTimeConvention)
        raise InvalidOrgTimeConfigError(
            f"{CONVENTION_ENV}={raw_convention!r} is not a known convention (expected one of: "
            f"{valid})"
        ) from exc

    timezone_name = source.get(TIMEZONE_ENV) or DEFAULT_TIMEZONE
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidOrgTimeConfigError(
            f"{TIMEZONE_ENV}={timezone_name!r} is not a known IANA timezone"
        ) from exc

    confirmed = (source.get(CONFIRMED_ENV) or "").strip().lower() in ("1", "true", "yes")
    return OrgTimeConfig(convention=convention, timezone_name=timezone_name, confirmed=confirmed)


def log_org_time_convention(config: OrgTimeConfig | None = None) -> OrgTimeConfig:
    """Announce the convention once at startup; WARNING while it is still provisional.

    Called from both apps' `lifespan`. The level is the point: an unconfirmed assumption
    that decides whether a student is let into their weekly exam should be visible in every
    deploy's logs, not discoverable only by reading this file.
    """
    config = config or resolve_org_time()
    message = "org time convention: %s"
    if config.confirmed:
        logger.info(message, config.describe())
    else:
        logger.warning(message, config.describe())
    return config
