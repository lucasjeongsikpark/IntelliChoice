#!/usr/bin/env python
"""Scan live CloudWatch log events for PII (SPEC §5.30, §2.6 gate criterion 9).

Criterion 9 covers logs as well as traces, and until this script the two stores had very
different evidence: `scan_xray_pii.py` is repeatable and self-checking, while the log half
rested on S38's one-off CLI pipeline over *guest* traffic. D-104 §4 is the reason that gap
matters rather than being a formality - the same SSE request was sanitized in the access log
and not in the trace, so **a PII floor is per-store and is not inherited**. The corollary runs
in this direction too: a log scan from before authenticated traffic existed says nothing about
authenticated traffic.

Deliberately built on the trace scanner's parts rather than beside them:

* **The patterns and the matcher are imported, not re-written.** A second hand-rolled detector
  would need its own proof, and D-104 §8 records three measurement instruments in one session
  that were wrong before the system they measured was. This one inherits a matcher that walks
  JSON-in-string (log lines *are* JSON here) and the same positive control.
* **Truncation is a failure, not a footnote.** S38's first log scan reported zero hits for
  strings that were demonstrably present, because `filter-log-events --max-items` paginates and
  only the first page was read (D-102). Logs Insights caps a query at 10,000 returned records,
  which is the same bug wearing a different hat, so the window is walked in slices and any
  slice that comes back at the cap fails the run instead of quietly under-reporting.
* **Zero events scanned is an explicit FAIL**, for the reason the trace scanner has the same
  guard: "no PII in logs" over an empty window is true and worthless.

Usage:
    uv run python scripts/scan_logs_pii.py [--minutes 60]
    uv run python scripts/scan_logs_pii.py --start 2026-07-30T21:38:00Z --end 2026-07-30T21:40:00Z
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_xray_pii import (  # noqa: E402
    SHAPE_PATTERNS,
    Findings,
    Hit,
    _fixture_patterns,
    _match,
    positive_control,
)

LOG_GROUPS = [
    "/ecs/intellichoice-staging-learning-api",
    "/ecs/intellichoice-staging-chat-api",
    "/ecs/intellichoice-staging-ops-task",
]

# Logs Insights returns at most this many records for a `fields`-style query. Hitting it means
# the slice was truncated, which is the S38 false negative - so it fails the run.
INSIGHTS_RECORD_LIMIT = 10_000


# Three excuses, and the correction that produced all of them (2026-08-24).
#
# **This list was empty and its own comment overstated why, and it is now measured wrong three
# times over - on the same too-small window every time.** The comment read that over 2,774 real
# log events across all three groups "no pattern fired at all", and drew the stronger claim that
# nothing needed excusing. It even named the exception it expected to need and then reported not
# needing: "uvicorn's bind address, Container Insights' network fields" for
# `shape:pii-field-name`. Both halves of that were window size, not evidence. Run over the 8-day
# window the scheduled workflow actually uses - 319,726 log events, 288 slices - the scanner
# exits 1 with 131 hits across two patterns, and **not one of them is PII**:
#
#   branch-latitude:39.85   86 hits: 78 ISO-8601 timestamps, 8 access-log durations
#   shape:pii-field-name    45 hits, one distinct line, the collector's own bind address
#
# Those splits are enumerated, not sampled. This script prints three examples per pattern, and
# reading the classes off those three examples got the first count wrong: the timestamps are the
# common case and the durations were hiding behind them. Every number here comes from a separate
# read of all 86 hits with their paths (43 log lines over 8 days contain the string "39.85" at
# all, so the set is small and was walked entirely).
#
# 1. **`branch-latitude:39.85` on a timestamp.** The fixture branch latitude is `39.8500`, so
#    `_fixture_patterns` builds `(?<![\d.])39\.85\d*(?![\d.])`. That guard is boundary-aware
#    for the case it was written against - X-Ray's epoch `start_time` (`1785093039.8546414`,
#    where the preceding character is a digit) is correctly refused. An ISO timestamp puts a `:`
#    there instead, so `:39.853559+` passes it. The seconds field lands in [39.85, 39.86) once
#    every 6,000 lines, which is exactly why 2,774 events could not contain one and the 8-day
#    window holds 86. The trace scanner never saw this because X-Ray timestamps are epoch
#    floats: **this is the log store's own false positive**, D-104 §4's rule (a floor is
#    per-store and is not inherited) arriving from the other direction.
#
# 2. **`shape:pii-field-name` on the OTel collector's bind address.** Over the same 8 days the
#    pattern has exactly **one** distinct excerpt, 45 occurrences, all
#    `Serving metrics {"address": "localhost:8888", "metrics level": "Normal"}`. The pattern
#    fires on the field *name*; the value is what makes it not a person's address.
#
# 3. **`branch-latitude:39.85` on the access log's own latency.** 8 hits, 4 log lines,
#    `{... "status_code": 200, "duration_ms": 39.85}`. A request that took 39.85 ms.
#
# **The root cause under all three, stated so the fourth one is expected rather than surprising.**
# `str(39.8500)` is `"39.85"` - the fixture branch latitude carries only two decimals, which makes
# it an *ordinary number*. It collides with ISO timestamp seconds, with a 2-decimal millisecond
# duration, and in principle with any other 2-decimal value this system logs. `SHAPE_PATTERNS`'
# own `shape:coordinate-pair` already encodes the insight, requiring `\.\d{3,}`; the sibling
# branch (39.7817 / -89.6501) has four decimals and produced **zero** false positives across the
# same 319,726 events. A precision floor on the fixture-derived patterns was considered and
# **rejected**: it does not fix the timestamp class (`:39.853559` has trailing digits and matches
# either way) and it would lose the most likely real leak for this fixture, the exact value
# `39.85`. The durable remedy, if a fourth class ever appears, is to give this fixture latitude
# four decimals like its sibling - which is a deliberate decision about load-bearing fixture data
# and deliberately not taken here.
#
# All three are excused here rather than by loosening the shared matcher in `scan_xray_pii.py`,
# which is criterion 9's *trace* evidence too. Each shape is narrow in the direction that matters:
#
# * The timestamp shape needs the full ISO time context - a `THH:MM:` prefix **and** a timezone
#   suffix - so a real coordinate never wears both: `{"latitude": 39.85}`, `{"lat": "39.8500"}`
#   and `39.85, -89.69` all still exit 1.
# * The bind-address shape needs the value to be **loopback**, not the collector's log prose
#   (which a collector upgrade could reword). `{"address": "123 Main St, Springfield"}` and
#   `{"display_name": "Kim"}` still exit 1 - and so would a collector that started binding
#   `0.0.0.0`, deliberately: failing toward review is the right direction for a PII gate, and a
#   further entry is then a decision somebody makes.
# * The duration shape is the one that needed the **path**, and it is why `LogExcuse` exists at
#   all - see its docstring. An excerpt rule cannot express it without also excusing a real
#   `{"latitude": 39.85}`, whose JSON-walked excerpt is the identical bare `39.85`.
#
# All three are pinned in both directions by
# `packages/adapters/tests/test_log_pii_scanner_allowlist.py` (D-221), per constraint rather than
# per entry, because an excuse nothing scores can widen later without anything noticing.
#
# Anything added must obey the trace scanner's rules: one pattern, one narrow path or shape,
# counted and printed rather than silently dropped. An allowlist that grows to cover a real leak
# is the failure mode this comment exists to slow down.
@dataclass(frozen=True)
class LogExcuse:
    """One non-PII fact, and the shapes it takes in this log store.

    **`path` exists because its absence was itself the defect.** The trace scanner excuses by
    *path* (`_allowlisted(pattern_name, path)`), and this scanner was written to excuse by
    *excerpt* instead. That divergence looked like a detail and is not: one log line produces two
    hits - the raw message and the JSON-walked field - and only the raw one carries surrounding
    context. For `"duration_ms": 39.85` the JSON-walked hit's excerpt is the bare string `39.85`,
    identical to what a genuine `{"latitude": 39.85}` leak produces, so no excerpt rule can
    separate them. The field the value came from can. This converges the two scanners on the
    semantics the trace half has had all along.

    Each constraint is a *sufficient* shape of the same fact rather than an additional
    requirement, because the two hits from one line carry different evidence. That is only safe
    while every constraint is independently narrow enough to be a statement about infrastructure,
    which is what `test_log_pii_scanner_allowlist.py` scores in both directions - per constraint,
    not just per entry.
    """

    pattern: str
    path: re.Pattern[str] | None = None
    excerpt: re.Pattern[str] | None = None

    def excuses(self, hit: Hit) -> bool:
        if hit.pattern != self.pattern:
            return False
        if self.path is not None and self.path.search(hit.path):
            return True
        return self.excerpt is not None and self.excerpt.search(hit.excerpt)


LOG_ALLOWLIST: list[LogExcuse] = [
    LogExcuse(
        "branch-latitude:39.85",
        excerpt=re.compile(r"T\d{2}:\d{2}:39\.85\d*(?:Z|[+-]\d{2}:\d{2})"),
    ),
    LogExcuse("shape:pii-field-name", excerpt=re.compile(r'"address": "localhost:\d+"')),
    LogExcuse(
        "branch-latitude:39.85",
        # The JSON-walked half: anchored, so it names one field and cannot reach `.latitude`.
        path=re.compile(r"\.duration_ms$"),
        # The raw-line half: the field name has to be immediately before the value.
        excerpt=re.compile(r'"duration_ms": 39\.85\d*'),
    ),
]


@dataclass
class Slice:
    group: str
    start: datetime
    end: datetime
    events: int
    truncated: bool
    unqueryable: str | None = None


def _run_query(logs, group: str, start: datetime, end: datetime) -> tuple[list[str], bool]:
    """Return the raw messages in one window for one group, and whether it was truncated."""
    query = logs.start_query(
        logGroupName=group,
        startTime=int(start.timestamp()),
        endTime=int(end.timestamp()),
        queryString="fields @message | sort @timestamp asc",
        limit=INSIGHTS_RECORD_LIMIT,
    )
    query_id = query["queryId"]
    while True:
        result = logs.get_query_results(queryId=query_id)
        if result["status"] in ("Complete", "Failed", "Cancelled", "Timeout"):
            break
        time.sleep(1.0)
    if result["status"] != "Complete":
        raise RuntimeError(f"Logs Insights query {result['status']} for {group}")
    messages = [
        field["value"]
        for row in result.get("results", [])
        for field in row
        if field.get("field") == "@message"
    ]
    return messages, len(messages) >= INSIGHTS_RECORD_LIMIT


def scan(
    start: datetime, end: datetime, slice_minutes: int, profile: str, region: str
) -> tuple[Findings, list[Slice], list[str]]:
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        session = boto3.Session(region_name=region)
    else:
        session = boto3.Session(profile_name=profile, region_name=region)
    logs = session.client("logs")

    patterns = _fixture_patterns() + SHAPE_PATTERNS
    findings = Findings()
    slices: list[Slice] = []
    missing: list[str] = []

    existing = set()
    for page in logs.get_paginator("describe_log_groups").paginate():
        existing.update(g["logGroupName"] for g in page.get("logGroups", []))

    for group in LOG_GROUPS:
        if group not in existing:
            missing.append(group)
            continue
        cursor = start
        while cursor < end:
            stop = min(cursor + timedelta(minutes=slice_minutes), end)
            try:
                messages, truncated = _run_query(logs, group, cursor, stop)
            except ClientError as exc:
                # A window older than the group's retention (or older than the group itself)
                # is rejected outright rather than returning zero rows. That distinction is
                # the whole point: "the store had nothing" and "I could not read the store"
                # must not both come out as CLEAN, so the slice is recorded as unqueryable
                # and the run fails below.
                code = exc.response.get("Error", {}).get("Code", "ClientError")
                slices.append(Slice(group, cursor, stop, 0, False, unqueryable=code))
                cursor = stop
                continue
            slices.append(Slice(group, cursor, stop, len(messages), truncated))
            for message in messages:
                findings.scanned_segments += 1
                _match(patterns, message, findings)
            cursor = stop
    return findings, slices, missing


def _apply_log_allowlist(findings: Findings) -> list[Hit]:
    """Re-file hits the log-specific allowlist excuses, counting them like the trace scanner."""
    kept: list[Hit] = []
    for hit in findings.hits:
        if any(excuse.excuses(hit) for excuse in LOG_ALLOWLIST):
            findings.allowlisted += 1
        else:
            kept.append(hit)
    return kept


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--minutes", type=int, default=60, help="lookback window (default 60)")
    ap.add_argument("--start", help="ISO8601 window start, overrides --minutes")
    ap.add_argument("--end", help="ISO8601 window end, defaults to now")
    ap.add_argument("--slice-minutes", type=int, default=10)
    ap.add_argument("--profile", default="jeongsik-staging-admin")
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()

    end = datetime.fromisoformat(args.end.replace("Z", "+00:00")) if args.end else datetime.now(UTC)
    start = (
        datetime.fromisoformat(args.start.replace("Z", "+00:00"))
        if args.start
        else end - timedelta(minutes=args.minutes)
    )

    patterns = _fixture_patterns() + SHAPE_PATTERNS
    ok, silent = positive_control(patterns)
    print(f"positive control: {len(patterns) - len(silent)}/{len(patterns)} patterns fired")
    if not ok:
        print(f"INVALID - these patterns cannot fire, so a clean result proves nothing: {silent}")
        return 2

    findings, slices, missing = scan(start, end, args.slice_minutes, args.profile, args.region)
    hits = _apply_log_allowlist(findings)

    print(
        f"scanned: {findings.scanned_segments} log events, {findings.scanned_strings} strings "
        f"over {start.isoformat()} .. {end.isoformat()} "
        f"({len(slices)} slices across {len(LOG_GROUPS) - len(missing)} log groups)"
    )
    if missing:
        # Same rule as an unreadable slice: a configured store that was not scanned at all must
        # not come out CLEAN. A log group does not vanish when its retention expires - it stays
        # and goes empty - so an absent one means the infrastructure changed and LOG_GROUPS is
        # stale, which is a decision for a human, not something to note and move past.
        print(
            f"FAIL - configured log group(s) do not exist, so a store criterion 9 covers went "
            f"unscanned: {missing}. Update LOG_GROUPS deliberately if this is intended."
        )
        return 3
    if findings.allowlisted:
        print(f"allowlisted: {findings.allowlisted} matches (see LOG_ALLOWLIST - infra, not data)")

    unqueryable = [s for s in slices if s.unqueryable]
    if unqueryable:
        print(
            f"FAIL - {len(unqueryable)} slice(s) could not be read at all, so this window is "
            "partially or wholly unscanned. 'I could not look' must not report as CLEAN."
        )
        for s in unqueryable[:5]:
            print(f"      {s.group}  {s.start.isoformat()} .. {s.end.isoformat()}: {s.unqueryable}")
        return 3

    truncated = [s for s in slices if s.truncated]
    if truncated:
        print(
            f"FAIL - {len(truncated)} slice(s) returned the {INSIGHTS_RECORD_LIMIT}-record cap, so "
            "events were dropped and a clean result would be S38's false negative again. "
            "Re-run with a smaller --slice-minutes."
        )
        for s in truncated[:5]:
            print(f"      {s.start.isoformat()} .. {s.end.isoformat()}: {s.events} events")
        return 3

    if findings.scanned_segments == 0:
        print(
            "FAIL - zero log events in the window. 'No PII found' over an empty corpus is not "
            "evidence."
        )
        return 3

    if not hits:
        print("CLEAN - no PII pattern matched any log event.")
        return 0

    by_pattern: dict[str, list[Hit]] = {}
    for hit in hits:
        by_pattern.setdefault(hit.pattern, []).append(hit)
    print(f"FOUND {len(hits)} hits across {len(by_pattern)} patterns:")
    for name, group in sorted(by_pattern.items(), key=lambda kv: -len(kv[1])):
        print(f"  {name}: {len(group)}")
        for hit in group[:3]:
            print(f"      {hit.path}  {hit.excerpt}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
