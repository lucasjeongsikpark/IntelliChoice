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

# Empty, and empty as a measured result rather than an oversight. The trace scanner needs one
# exception because SQL instrumentation records column names; this scanner was written expecting
# to need a similar one for `shape:pii-field-name` (uvicorn's bind address, Container Insights'
# network fields), and over 2,774 real log events across all three groups **no pattern fired at
# all** - the access log emits `method`, `path`, `status_code`, `duration_ms` and trace ids, and
# nothing else. So the honest state is "nothing needed excusing", which is a stronger result
# than an excused hit and is left visible here instead of being encoded as a rule.
#
# Anything added must obey the trace scanner's rules: one pattern, one narrow path or shape,
# counted and printed rather than silently dropped. An allowlist that grows to cover a real leak
# is the failure mode this comment exists to slow down.
LOG_ALLOWLIST: list[tuple[str, re.Pattern[str]]] = []


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
        excused = any(name == hit.pattern and rx.search(hit.excerpt) for name, rx in LOG_ALLOWLIST)
        if excused:
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
