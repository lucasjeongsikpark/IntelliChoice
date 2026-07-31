#!/usr/bin/env python
"""Read §2.6 criterion 6's evidence — scheduled jobs running unattended — per job.

**Why this is a script.** Criterion 6 is the gate's last open item and it is read by hand.
The hand reading has now been wrong twice, in opposite directions, and both times the
error was in the *instrument* rather than in the jobs:

  1. D-135 §3 read `InvocationAttemptCount` in 86,400-second buckets, which are offset from
     `--start-time` and so straddle calendar days. It concluded there had been no firings on
     07-30 or 07-31 — i.e. that the clock was broken — when the truth was that one bucket
     spanned two days and 07-31's runs were still in the future.
  2. The same read recorded per-job firing counts "from Scheduler's own metrics". **Scheduler
     publishes no per-schedule dimension** (see `_METRIC_DIMENSION`), so those counts cannot
     have come from where they say. Their *values* were right for the two daily jobs and
     wrong for the weekly one, which is the failure mode of an inference that looks like a
     measurement: it is right until the case where it matters.

Both errors are the kind a script can hold still. D-114 §3 requires criterion 6 be read
**per job**, so per-job attribution is this script's central problem, and everything below
exists to make the attribution honest or refuse to make it.

**What it reads, in order, and why more than one source.**

  - **The schedules themselves**, live, from EventBridge Scheduler: expression, timezone,
    state, and `CreationDate`. Nothing about the cadence is remembered — the expected
    firing instants are *computed* from the expression and the creation time, which is the
    check that found D-135's second error. `memory-consolidate` was created 2026-07-27
    02:48:30Z, eight hours *after* Sunday 07-26's 18:30Z slot, so it could not have fired
    that Sunday: its first firing is 08-02 and its second is 08-09.
  - **`AWS/Scheduler` `InvocationAttemptCount`** at 300-second resolution, which is the
    only source that counts *schedule* firings rather than task runs. The ops-task log
    group also carries manual `make` invocations and cannot be used alone.
  - **The ops-task log group**, per job, for the line the job prints when it does its work.
    This is the AUD-F-15 distinction — that finding was a job that fired and died on
    `127.0.0.1` — so a firing count is not evidence that anything ran.

**The attribution method, stated because it is not obvious and it is fragile.**
`AWS/Scheduler` carries only a `ScheduleGroup` dimension, so the metric is the *sum over
every schedule in the group*, including schedules that have since been deleted. Per-job
attribution is possible here only because the three enabled crons fire at three distinct
minutes — 18:10, 18:30, 18:50 UTC — so a datapoint's 5-minute bucket identifies the job.
That is a property of this configuration, not a general fact, so the script **asserts it**
(`_check_attributable`) and refuses to attribute anything if two enabled schedules could
land in one bucket. Firings that match no enabled schedule are **reported, never dropped**:
the two on 2026-07-27 at 02:50Z and 03:20Z are D-105 §5's deliberate failure tests of the
notification path, and a count that silently absorbed them would overstate every job.

**Structural guards, in the style of `scan_xray_pii.py` — a read that cannot fail is
worthless:**

  1. **The log confirmation runs a positive control.** A per-job filter returning nothing is
     ambiguous between "the job never ran" and "the filter is wrong". So an unfiltered query
     over the same window and log group runs first; if *it* comes back empty the run aborts
     as INVALID rather than reporting three jobs as never having run. This is exactly how
     `memory-consolidate`'s zero was established as real.
  2. **Timestamps are printed in UTC, always, with the `Z`.** Both the AWS CLI and boto3
     hand back local-time datetimes, which is the raw material of D-135's first error.
  3. **Absent is not zero.** Scheduler does not publish zeros for its error metrics, so
     "empty" and "no errors" are the same observation from CloudWatch and are reported as
     `no datapoints` — with the attempt metric alongside as proof the namespace works.
  4. **Expected firings are computed, and misses are named.** Every expected instant since
     each schedule's creation is generated and matched; a missing one is printed with its
     UTC time rather than folded into a count.
  5. **The verdict is per job and the exit code follows the weakest one**, so the 08-02-style
     read is a command with an answer rather than a judgement call over a console.

**What it deliberately does not do.** It does not decide criterion 6. It reports, per job,
how many days of unattended operation are evidenced and what is still missing; whether that
clears "≥ 1 week" for a weekly job that has fired once is a stated reading, and D-135 §4's
instruction to quote the reading with the tick still applies. Neither purge job has ever
deleted a row and neither can until ~2026-10-20, so a clean run here evidences that the
schedules fire and the jobs execute — not that the retention promise deletes correctly.

Usage (read-only; needs credentials for the staging account):

    make scheduler-evidence
    uv run python scripts/read_scheduler_evidence.py --profile jeongsik-staging-admin
    uv run python scripts/read_scheduler_evidence.py --days 21
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import boto3

# EventBridge Scheduler's metrics carry the schedule *group* and nothing finer. There is no
# `ScheduleName` dimension to ask for - confirmed against `list-metrics` on this account,
# which returns exactly two series: one with this dimension and one with none at all.
_METRIC_DIMENSION = "ScheduleGroup"
_NAMESPACE = "AWS/Scheduler"
_ATTEMPT_METRIC = "InvocationAttemptCount"
# Read together so an all-empty error result can be shown to be meaningful rather than
# merely absent. Scheduler publishes no zeros, so every one of these is normally missing.
_ERROR_METRICS = (
    "TargetErrorCount",
    "TargetErrorThrottledCount",
    "InvocationDroppedCount",
    "InvocationThrottleCount",
    "InvocationsFailedToBeSentToDeadLetterCount",
)

# 300 s is the finest resolution CloudWatch retains for 63 days, and it is fine enough to
# separate 18:10 / 18:30 / 18:50. `GetMetricStatistics` caps a response at 1440 datapoints,
# which is exactly 5 days at this period - so windows are chunked below that.
_PERIOD_SECONDS = 300
_CHUNK = timedelta(days=4)

# The line each job prints when it has actually done its work, not merely started. Chosen
# from the CLIs' own output rather than from a job name, because a name appears in a log
# stream whether or not the process got as far as its database.
_WORK_LINE = {
    "chat-purge": "tutor_chat_messages row(s) older than",
    "retention-purge": "semantic_memory row(s) older than",
    "memory-consolidate": "Consolidation run complete",
}
_OPS_LOG_GROUP = "/ecs/intellichoice-staging-ops-task"

# "Unattended for ≥ 1 week" needs both a span and a recurrence: one datapoint cannot
# evidence a repeat, however long ago it was.
_WEEK = timedelta(days=7)
_MIN_FIRINGS = 2


def _z(moment: datetime) -> str:
    """UTC, with the Z, every time (guard 2)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%SZ")


@dataclass
class Schedule:
    name: str
    short: str
    expression: str
    timezone: str
    enabled: bool
    created: datetime
    # None when the expression is not one of the two shapes this understands. An
    # unparsed expression is reported as unreadable, never assumed to be daily.
    minute: int | None = None
    hour: int | None = None
    weekday: int | None = None  # Monday=0, as `datetime.weekday()` numbers them
    parse_error: str | None = None

    @property
    def bucket(self) -> tuple[int, int] | None:
        """The 5-minute bucket this schedule fires into, which is its identity in the
        group-level metric. `None` when the expression could not be read.
        """
        if self.minute is None or self.hour is None:
            return None
        return (self.hour, self.minute - self.minute % 5)

    def expected(self, until: datetime) -> list[datetime]:
        """Every instant this schedule should have fired between creation and `until`."""
        if self.minute is None or self.hour is None:
            return []
        out: list[datetime] = []
        day = self.created.astimezone(UTC).date()
        last = until.astimezone(UTC).date()
        while day <= last:
            moment = datetime(day.year, day.month, day.day, self.hour, self.minute, tzinfo=UTC)
            fires_today = self.weekday is None or day.weekday() == self.weekday
            # `>` and not `>=`: a schedule created at 02:48 has not fired at 02:48.
            if fires_today and moment > self.created and moment <= until:
                out.append(moment)
            day += timedelta(days=1)
        return out


@dataclass
class JobReading:
    schedule: Schedule
    firings: list[datetime] = field(default_factory=list)
    missed: list[datetime] = field(default_factory=list)
    work_lines: list[datetime] = field(default_factory=list)

    @property
    def unattended(self) -> timedelta:
        """Elapsed unattended operation, measured from *enablement* rather than from the
        first firing: the clock criterion 6 cares about starts when nobody has to touch it
        again, and for a weekly job those differ by up to six days.
        """
        if not self.firings:
            return timedelta(0)
        return max(self.firings) - self.schedule.created

    @property
    def verdict(self) -> tuple[bool, str]:
        if not self.schedule.enabled:
            return True, "DISABLED - outside criterion 6 (D-105 §4)"
        if self.schedule.parse_error:
            return False, f"UNREADABLE - {self.schedule.parse_error}"
        if not self.firings:
            return False, "NO FIRINGS - never run unattended"
        problems = []
        if self.missed:
            problems.append(f"{len(self.missed)} expected firing(s) missing")
        if not self.work_lines:
            problems.append("fired but no work line in the ops log (the AUD-F-15 shape)")
        if len(self.firings) < _MIN_FIRINGS:
            problems.append(f"only {len(self.firings)} firing - a repeat is not evidenced")
        if self.unattended < _WEEK:
            short = _WEEK - self.unattended
            problems.append(
                f"{self.unattended.days}d of ≥7d "
                f"({short.days}d {short.seconds // 3600}h short)"
            )
        if problems:
            return False, "NOT YET - " + "; ".join(problems)
        return (
            True,
            f"MET - {self.unattended.days}d unattended, "
            f"{len(self.firings)} firings, 0 errors",
        )


def _parse_expression(schedule: Schedule) -> None:
    """Read `cron(M H * * ? *)` and `cron(M H ? * DOW *)`, and nothing else.

    Deliberately narrow. `rate(...)`, step values and multi-value fields all exist and none
    is in use here; a parser that guessed at them would produce an expected-firing list that
    looks authoritative and is wrong, which is the failure this whole script is a reaction
    to. Anything else is reported unreadable and the job is marked NOT YET.
    """
    expression = schedule.expression.strip()
    if not expression.startswith("cron(") or not expression.endswith(")"):
        schedule.parse_error = f"not a cron expression: {expression!r}"
        return
    fields = expression[5:-1].split()
    if len(fields) != 6:
        schedule.parse_error = f"expected 6 cron fields, got {len(fields)}: {expression!r}"
        return
    minute, hour, day_of_month, month, day_of_week, year = fields
    if not (minute.isdigit() and hour.isdigit()):
        schedule.parse_error = f"non-literal minute/hour, unsupported: {expression!r}"
        return
    if month != "*" or year != "*":
        schedule.parse_error = f"month/year restrictions unsupported: {expression!r}"
        return
    if schedule.timezone.upper() != "UTC":
        # Everything downstream compares against UTC metric timestamps. A non-UTC schedule
        # is readable but would need DST-aware expansion, so refuse rather than drift.
        schedule.parse_error = f"non-UTC schedule timezone {schedule.timezone!r}"
        return

    names = {"SUN": 6, "MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5}
    if day_of_month in ("*", "?") and day_of_week in ("*", "?"):
        schedule.weekday = None  # daily
    elif day_of_week.upper() in names:
        schedule.weekday = names[day_of_week.upper()]
    else:
        schedule.parse_error = f"unsupported day fields ({day_of_month!r}, {day_of_week!r})"
        return
    schedule.minute, schedule.hour = int(minute), int(hour)


def _read_schedules(session: boto3.Session, prefix: str) -> list[Schedule]:
    client = session.client("scheduler")
    out: list[Schedule] = []
    for page in client.get_paginator("list_schedules").paginate():
        for summary in page["Schedules"]:
            if not summary["Name"].startswith(prefix):
                continue
            detail = client.get_schedule(Name=summary["Name"], GroupName=summary["GroupName"])
            schedule = Schedule(
                name=detail["Name"],
                short=detail["Name"][len(prefix) :].lstrip("-"),
                expression=detail["ScheduleExpression"],
                timezone=detail.get("ScheduleExpressionTimezone", "UTC"),
                enabled=detail["State"] == "ENABLED",
                created=detail["CreationDate"].astimezone(UTC),
            )
            _parse_expression(schedule)
            out.append(schedule)
    return sorted(out, key=lambda s: (not s.enabled, s.short))


def _align(moment: datetime) -> datetime:
    """Floor to a `_PERIOD_SECONDS` boundary on the wall clock.

    **This is D-135's bug, and it reproduced inside this script before the fix.**
    CloudWatch lays its buckets out from `StartTime` (floored to the minute), not from the
    clock, so a window starting at 19:36 puts 18:10's firing into a bucket *labelled*
    18:06 - and this script identifies a job by its bucket. The first run attributed zero
    firings to `chat-purge` while its work lines sat in the log, i.e. the same class of
    false negative as reading daily buckets offset from midnight, three orders of magnitude
    smaller. Aligning the window makes a bucket label mean what it says.
    """
    floored = moment.replace(second=0, microsecond=0)
    return floored - timedelta(minutes=floored.minute % (_PERIOD_SECONDS // 60))


def _windows(start: datetime, end: datetime) -> Iterator[tuple[datetime, datetime]]:
    """Chunks below `GetMetricStatistics`' 1440-datapoint cap (guard on the API, not on us:
    it rejects the request outright rather than truncating, which is the good failure).

    `_CHUNK` is a whole number of days and so a whole number of periods, which is what keeps
    every chunk aligned once the first one is.
    """
    cursor = _align(start)
    while cursor < end:
        yield cursor, min(cursor + _CHUNK, end)
        cursor += _CHUNK


def _read_firings(
    session: boto3.Session, group: str, start: datetime, end: datetime
) -> list[datetime]:
    cloudwatch = session.client("cloudwatch")
    firings: list[datetime] = []
    for window_start, window_end in _windows(start, end):
        response = cloudwatch.get_metric_statistics(
            Namespace=_NAMESPACE,
            MetricName=_ATTEMPT_METRIC,
            Dimensions=[{"Name": _METRIC_DIMENSION, "Value": group}],
            StartTime=window_start,
            EndTime=window_end,
            Period=_PERIOD_SECONDS,
            Statistics=["Sum"],
        )
        for point in response["Datapoints"]:
            count = int(point["Sum"])
            # A bucket with two firings is one datapoint; repeat it so the count survives.
            firings.extend([point["Timestamp"].astimezone(UTC)] * count)
    return sorted(firings)


def _read_errors(
    session: boto3.Session, group: str, start: datetime, end: datetime
) -> dict[str, float | None]:
    """Each error metric's total, or `None` for "no datapoints" (guard 3)."""
    cloudwatch = session.client("cloudwatch")
    out: dict[str, float | None] = {}
    for metric in _ERROR_METRICS:
        total: float | None = None
        for window_start, window_end in _windows(start, end):
            response = cloudwatch.get_metric_statistics(
                Namespace=_NAMESPACE,
                MetricName=metric,
                Dimensions=[{"Name": _METRIC_DIMENSION, "Value": group}],
                StartTime=window_start,
                EndTime=window_end,
                Period=_PERIOD_SECONDS,
                Statistics=["Sum"],
            )
            for point in response["Datapoints"]:
                total = (total or 0.0) + point["Sum"]
        out[metric] = total
    return out


def _any_event(logs: object, start_ms: int, end_ms: int) -> bool:
    """Whether the ops log group carries any event at all in the window."""
    token = None
    while True:
        kwargs: dict[str, object] = {
            "logGroupName": _OPS_LOG_GROUP,
            "startTime": start_ms,
            "endTime": end_ms,
        }
        if token:
            kwargs["nextToken"] = token
        page = logs.filter_log_events(**kwargs)  # type: ignore[attr-defined]
        if page["events"]:
            return True
        token = page.get("nextToken")
        if not token:
            return False


def _read_work_lines(
    session: boto3.Session, start: datetime, end: datetime, jobs: list[str]
) -> dict[str, list[datetime]] | None:
    """Per-job work lines from the ops log group, behind a positive control (guard 1).

    Returns `None` when the control fails, which the caller must treat as INVALID rather
    than as three jobs having never run.
    """
    logs = session.client("logs")
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    # The control has to paginate too, and finding that out was the point of writing it.
    # `filter_log_events` returns pages *as it scans streams*, so a page can legitimately be
    # empty while carrying a `nextToken` - the first version of this control asked for
    # `limit=1` and got an empty page back from a log group that demonstrably has events,
    # i.e. it would have declared every run INVALID. Same shape as D-102's zero-hit scan.
    if not _any_event(logs, start_ms, end_ms):
        return None

    out: dict[str, list[datetime]] = {}
    for job in jobs:
        needle = _WORK_LINE.get(job)
        if needle is None:
            out[job] = []
            continue
        found: list[datetime] = []
        token = None
        while True:
            kwargs = {
                "logGroupName": _OPS_LOG_GROUP,
                "startTime": start_ms,
                "endTime": end_ms,
                "filterPattern": f'"{needle}"',
            }
            if token:
                kwargs["nextToken"] = token
            # Paginated to exhaustion on purpose: D-102's log scan reported zero hits for
            # strings that were present because it read only the first page.
            page = logs.filter_log_events(**kwargs)
            found.extend(
                datetime.fromtimestamp(event["timestamp"] / 1000, UTC) for event in page["events"]
            )
            token = page.get("nextToken")
            if not token:
                break
        out[job] = sorted(found)
    return out


def _check_attributable(schedules: list[Schedule]) -> list[str]:
    """Two enabled schedules in one 5-minute bucket make the group metric unattributable."""
    seen: dict[tuple[int, int], str] = {}
    clashes: list[str] = []
    for schedule in schedules:
        if not schedule.enabled or schedule.bucket is None:
            continue
        other = seen.get(schedule.bucket)
        if other:
            hour, minute = schedule.bucket
            clashes.append(f"{schedule.short} and {other} both fire into {hour:02d}:{minute:02d}Z")
        seen[schedule.bucket] = schedule.short
    return clashes


def _attribute(
    schedules: list[Schedule], firings: list[datetime], end: datetime
) -> tuple[dict[str, JobReading], list[datetime]]:
    by_bucket = {s.bucket: s for s in schedules if s.enabled and s.bucket is not None}
    readings = {s.short: JobReading(schedule=s) for s in schedules}

    unattributed: list[datetime] = []
    for firing in firings:
        bucket = (firing.hour, firing.minute - firing.minute % 5)
        owner = by_bucket.get(bucket)
        if owner is None:
            unattributed.append(firing)
        else:
            readings[owner.short].firings.append(firing)

    for schedule in schedules:
        if not schedule.enabled:
            continue
        observed = readings[schedule.short].firings
        # A firing can land a few seconds either side of its slot; match on the bucket.
        seen_buckets = {(f.hour, f.minute - f.minute % 5, f.date()) for f in observed}
        for moment in schedule.expected(end):
            key = (moment.hour, moment.minute - moment.minute % 5, moment.date())
            if key not in seen_buckets:
                readings[schedule.short].missed.append(moment)
    return readings, unattributed


def _report(
    readings: dict[str, JobReading],
    unattributed: list[datetime],
    errors: dict[str, float | None],
    work: dict[str, list[datetime]] | None,
    start: datetime,
    end: datetime,
) -> int:
    print(f"\n{'=' * 88}")
    print("criterion 6 evidence - scheduled jobs running unattended, read per job (D-114 §3)")
    print(f"window {_z(start)} .. {_z(end)}   all times UTC")
    print(f"{'=' * 88}")

    if work is None:
        print(
            f"\nINVALID: the positive control found no events at all in {_OPS_LOG_GROUP}\n"
            "  over this window. That is a broken query or the wrong log group, not three\n"
            "  jobs that never ran (guard 1). No conclusion follows; fix the read first."
        )
        return 2

    for job, reading in readings.items():
        schedule = reading.schedule
        state = "ENABLED" if schedule.enabled else "DISABLED"
        print(f"\n{job}  [{state}]  {schedule.expression} {schedule.timezone}")
        print(f"  created            {_z(schedule.created)}")
        if schedule.parse_error:
            print(f"  expression         UNREADABLE - {schedule.parse_error}")
        elif schedule.enabled:
            expected = schedule.expected(end)
            print(
                f"  firings            {len(reading.firings)} observed"
                f" / {len(expected)} expected since creation"
            )
            if reading.firings:
                print(
                    f"  first / last       {_z(min(reading.firings))}"
                    f" / {_z(max(reading.firings))}"
                )
                days = reading.unattended
                print(
                    f"  unattended for     {days.days}d {days.seconds // 3600}h"
                    f"  (from creation to last firing)"
                )
            for moment in reading.missed:
                print(f"  MISSED             {_z(moment)}")
            lines = work.get(job, [])
            last = f", last {_z(max(lines))}" if lines else ""
            print(f"  work lines in log  {len(lines)}{last}")

        ok, note = reading.verdict
        print(f"  verdict            {'✅' if ok else '❌'} {note}")

    print(f"\n{'-' * 88}")
    if unattributed:
        print(
            f"{len(unattributed)} firing(s) matched no enabled schedule's slot. Reported, not\n"
            "dropped: the group-level metric also counts schedules that were since deleted\n"
            "(D-105 §5's deliberate failure tests of the notification path, 2026-07-27)."
        )
        for moment in unattributed:
            print(f"  unattributed       {_z(moment)}")

    published = [f"{k}={v:g}" for k, v in errors.items() if v is not None]
    print(
        "\nerror metrics       "
        + (", ".join(published) if published else "no datapoints on any of the five")
    )
    print(
        "                    Scheduler publishes no zeros, so 'no datapoints' and 'no errors'\n"
        "                    are the same observation from CloudWatch (guard 3). The attempt\n"
        "                    metric is populated, which is what shows the namespace works."
    )

    enabled = [r for r in readings.values() if r.schedule.enabled]
    failing = [r for r in enabled if not r.verdict[0]]
    print(f"\n{'=' * 88}")
    if failing:
        weakest = max(failing, key=lambda r: (_WEEK - r.unattended))
        print(
            f"criterion 6 NOT MET. {len(failing)} of {len(enabled)} enabled job(s) short;\n"
            f"the weakest binds it (D-114 §3): {weakest.schedule.short} - {weakest.verdict[1]}"
        )
        print(
            "\nQuote the reading with the tick (D-135 §4): this evidences that the schedules\n"
            "fire unattended and the jobs execute cleanly. It does NOT evidence that the\n"
            "retention promise deletes correctly - neither purge job has ever deleted a row\n"
            "and neither can until ~2026-10-20."
        )
        return 1
    print(f"criterion 6 MET on all {len(enabled)} enabled job(s).")
    print(
        "\nQuote the reading with the tick (D-135 §4): this evidences that the schedules fire\n"
        "unattended and the jobs execute cleanly, NOT that the retention promise deletes\n"
        "correctly - neither purge job has ever deleted a row and neither can until ~2026-10-20."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default="",
        help=(
            "AWS profile. Leave empty when credentials are already in the environment - "
            "which is how `make scheduler-evidence` calls this, because boto3 cannot read "
            "the CLI's own login cache (the same gotcha `make scan-traces` documents)."
        ),
    )
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--days", type=int, default=21, help="lookback window (default 21)")
    parser.add_argument("--prefix", default="intellichoice-staging", help="schedule name prefix")
    parser.add_argument("--group", default="default", help="schedule group")
    args = parser.parse_args()

    session = (
        boto3.Session(profile_name=args.profile, region_name=args.region)
        if args.profile
        else boto3.Session(region_name=args.region)
    )
    end = datetime.now(UTC)
    start = end - timedelta(days=args.days)

    schedules = _read_schedules(session, args.prefix)
    if not schedules:
        print(f"FAIL: no schedules found with prefix {args.prefix!r}", file=sys.stderr)
        return 2

    clashes = _check_attributable(schedules)
    if clashes:
        print(
            "FAIL: per-job attribution is impossible. AWS/Scheduler carries only a\n"
            f"{_METRIC_DIMENSION} dimension, so firings are separated by their 5-minute\n"
            "bucket - and these enabled schedules share one:",
            file=sys.stderr,
        )
        for clash in clashes:
            print(f"  {clash}", file=sys.stderr)
        print(
            "Move one schedule's minute, or read criterion 6 from the ops log group alone\n"
            "(which mixes in manual invocations and needs its own argument).",
            file=sys.stderr,
        )
        return 2

    # Firings are only attributable from each schedule's creation onward, but the window is
    # read whole so that firings from deleted schedules still surface.
    firings = _read_firings(session, args.group, start, end)
    readings, unattributed = _attribute(schedules, firings, end)
    errors = _read_errors(session, args.group, start, end)
    work = _read_work_lines(session, start, end, list(readings))
    if work is not None:
        for job, lines in work.items():
            readings[job].work_lines = lines
    return _report(readings, unattributed, errors, work, start, end)


if __name__ == "__main__":
    raise SystemExit(main())
