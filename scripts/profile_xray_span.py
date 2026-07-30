#!/usr/bin/env python
"""Profile one named X-Ray span's SQL cost (§2.6 criterion 7, AUD-F-31's before/after).

Why this is a script and not an ad-hoc CLI pipeline: D-129 §5 profiled
`langgraph.select_topic` by hand and its first answer was **102 statements and 131% of
wall time in SQL** - a profile claiming more SQL time than the request took is reporting
on itself. X-Ray records each SQLAlchemy statement **twice**: once as a child subsegment
of the span that issued it, and again as a standalone top-level segment in the same
trace. A before/after that has to survive a code review needs the correction to live
somewhere reviewable, and to be identical on both sides of the comparison.

**How the double-count is handled here.** Not by deduping on `(start_time, query)`, which
is what the hand-rolled version eventually did, but structurally: a statement counts only
if it is a *descendant of the target span*. The standalone copies are top-level segments
with no such ancestor, so they are excluded by construction rather than by matching a
timestamp. The `(start_time, sanitized_query)` dedup is still computed over the whole
trace and reported beside it, so the two methods can be seen to agree - if they diverge,
the assumption that the standalone copies really are duplicates has stopped holding, and
that is worth seeing rather than averaging away.

Three structural guards, in the spirit of scan_xray_pii.py's positive control:

1. **SQL time may not exceed the span it sits inside.** This is the exact check that would
   have caught the 131%. Any span that violates it is reported and the run exits INVALID.
2. **Zero matching spans is a FAIL, not a clean "0 statements".** An empty corpus
   certifying an improvement is the false negative this whole file exists to prevent.
3. **Coverage is printed, never assumed** - how many summaries the window held, how many
   traces were fetched, how many contained the span. `~97%` of staging's traces are
   `/readyz` (AUD-F-30), so an unfiltered denominator flatters a scan that never looked at
   the interesting request.
4. **A degenerate span is a failure, not a result.** `langgraph.select_student` is a real,
   findable span that reports **0 ms and zero SQL** in every trace - the graph node does no
   database work. Profiling it prints a tidy table of zeros, and "0 statements" is exactly
   what a *successful* batching fix also looks like. Since this script exists to certify a
   statement count going down, a span that is 0 ms at the median must not be reportable as
   an improvement: it exits DEGENERATE instead. D-131 §4's lesson, one layer up - a positive
   control proves the detector fires, not that it measured the quantity in its own name.

Usage:
    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)"
    uv run python scripts/profile_xray_span.py --start 2026-07-30T23:38:00Z \\
        --end 2026-07-30T23:42:00Z --span langgraph.select_topic --url-contains topics
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3


@dataclass
class SpanProfile:
    """One occurrence of the target span in one trace."""

    trace_id: str
    duration_ms: float
    statements: list[tuple[str, float]] = field(default_factory=list)

    @property
    def sql_ms(self) -> float:
        return sum(ms for _, ms in self.statements)

    @property
    def sql_share(self) -> float:
        return self.sql_ms / self.duration_ms if self.duration_ms else 0.0


@dataclass
class Coverage:
    """What was looked at. Printed with every result - see guard 3."""

    summaries: int = 0
    fetched: int = 0
    traces_with_span: int = 0
    sql_nodes_seen: int = 0
    sql_nodes_in_span: int = 0
    dedup_statements: int = 0


def _walk(node: dict[str, Any], depth: int = 0) -> Iterator[tuple[dict[str, Any], int]]:
    """Yield every segment/subsegment in a document tree, with its depth."""
    yield node, depth
    for sub in node.get("subsegments") or []:
        yield from _walk(sub, depth + 1)


def _duration_ms(node: dict[str, Any]) -> float:
    start, end = node.get("start_time"), node.get("end_time")
    if start is None or end is None:
        return 0.0
    return (end - start) * 1000.0


def _statement(node: dict[str, Any]) -> str | None:
    """The SQL text, or None if this node is not a SQL node.

    Connection-level nodes carry a `sql` block with no `sanitized_query` (a connect or a
    rollback). They are real round-trips, so they are counted - under a stable label
    rather than dropped, because dropping them is how a statement count quietly shrinks.
    """
    sql = node.get("sql")
    if not isinstance(sql, dict):
        return None
    return str(sql.get("sanitized_query") or "<connection-level>")


def profile(
    span_name: str,
    start: datetime,
    end: datetime,
    url_contains: str | None,
    region: str,
    profile_name: str,
) -> tuple[list[SpanProfile], Coverage, list[str]]:
    # Same credential note as scan_xray_pii.py: boto3 cannot read the CLI's `aws login`
    # cache without botocore[crt], so the caller exports credentials first.
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        session = boto3.Session(region_name=region)
    else:
        session = boto3.Session(profile_name=profile_name, region_name=region)
    xray = session.client("xray")

    cov = Coverage()
    trace_ids: list[str] = []
    for page in xray.get_paginator("get_trace_summaries").paginate(StartTime=start, EndTime=end):
        for summary in page.get("TraceSummaries", []):
            cov.summaries += 1
            url = (summary.get("Http") or {}).get("HttpURL") or ""
            if url_contains and url_contains not in url:
                continue
            trace_ids.append(summary["Id"])

    profiles: list[SpanProfile] = []
    violations: list[str] = []

    for i in range(0, len(trace_ids), 5):
        batch = trace_ids[i : i + 5]
        pages = xray.get_paginator("batch_get_traces").paginate(TraceIds=batch)
        for page in pages:
            for trace in page.get("Traces", []):
                cov.fetched += 1
                trace_id = trace.get("Id", "?")
                # (start_time, statement) over the *whole* trace - the alternative method,
                # reported alongside the structural count so the two can be compared.
                dedup: set[tuple[Any, str]] = set()
                found_span = False

                for segment in trace.get("Segments", []):
                    try:
                        document = json.loads(segment.get("Document", "{}"))
                    except json.JSONDecodeError:
                        continue

                    for node, _ in _walk(document):
                        statement = _statement(node)
                        if statement is not None:
                            cov.sql_nodes_seen += 1
                            dedup.add((node.get("start_time"), statement))
                        if node.get("name") != span_name:
                            continue
                        # This node IS the target span: everything below it is its own SQL.
                        found_span = True
                        span = SpanProfile(trace_id=trace_id, duration_ms=_duration_ms(node))
                        for child, depth in _walk(node):
                            if depth == 0:
                                continue
                            child_statement = _statement(child)
                            if child_statement is None:
                                continue
                            cov.sql_nodes_in_span += 1
                            span.statements.append((child_statement, _duration_ms(child)))
                        # Guard 1: a span cannot contain more SQL time than its own duration.
                        if span.sql_ms > span.duration_ms * 1.02:
                            violations.append(
                                f"{trace_id}: {span.sql_ms:.0f} ms SQL inside a "
                                f"{span.duration_ms:.0f} ms span "
                                f"({span.sql_share:.0%}) - the double-count is back"
                            )
                        profiles.append(span)

                cov.dedup_statements += len(dedup)
                if found_span:
                    cov.traces_with_span += 1

    return profiles, cov, violations


def _quantiles(values: list[float]) -> tuple[float, float, float]:
    """min / median / p95 - p95 by nearest-rank, honest about small n."""
    ordered = sorted(values)
    if not ordered:
        return (0.0, 0.0, 0.0)
    index = max(0, min(len(ordered) - 1, round(0.95 * len(ordered)) - 1))
    return ordered[0], statistics.median(ordered), ordered[index]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--span", default="langgraph.select_topic", help="exact span name")
    ap.add_argument("--start", help="ISO8601 UTC, e.g. 2026-07-30T23:38:00Z")
    ap.add_argument("--end", help="ISO8601 UTC")
    ap.add_argument("--minutes", type=int, default=15, help="lookback if --start is absent")
    ap.add_argument(
        "--url-contains",
        default=None,
        help="only fetch traces whose HTTP URL contains this - ~97%% of staging traces "
        "are /readyz (AUD-F-30), so an unfiltered run is mostly health checks",
    )
    ap.add_argument("--profile", default="jeongsik-staging-admin")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--label", default="", help="free-text tag for the printed header")
    args = ap.parse_args()

    if args.start:
        start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
        end = (
            datetime.fromisoformat(args.end.replace("Z", "+00:00"))
            if args.end
            else datetime.now(UTC)
        )
    else:
        end = datetime.now(UTC)
        start = end - timedelta(minutes=args.minutes)

    print(f"profiling span '{args.span}' {start:%Y-%m-%dT%H:%M:%SZ} .. {end:%Y-%m-%dT%H:%M:%SZ}")
    if args.label:
        print(f"label: {args.label}")

    profiles, cov, violations = profile(
        args.span, start, end, args.url_contains, args.region, args.profile
    )

    print(
        f"coverage: {cov.summaries} summaries in window, {cov.fetched} traces fetched"
        f"{f' (URL contains {args.url_contains!r})' if args.url_contains else ''}, "
        f"{cov.traces_with_span} contained the span"
    )

    # Guard 2: an empty corpus must not certify an improvement.
    if not profiles:
        print(
            f"FAIL - the span '{args.span}' appears in zero fetched traces. "
            "A statement count of 0 over an empty corpus is not evidence."
        )
        return 3

    # Guard 1's verdict.
    if violations:
        print(f"INVALID - {len(violations)} span(s) report more SQL time than wall time:")
        for line in violations[:5]:
            print(f"    {line}")
        return 2

    counts = [float(len(p.statements)) for p in profiles]
    durations = [p.duration_ms for p in profiles]
    sql_times = [p.sql_ms for p in profiles]
    shares = [p.sql_share for p in profiles]

    # Guard 4: see the module docstring. A span that is ~0 ms at the median is not being
    # measured, and its "0 statements" is indistinguishable from a batching win.
    #
    # The threshold is 1 ms, not equality with zero, and that distinction is the bug this
    # comment exists to prevent recurring: `langgraph.select_student` reports a *fraction*
    # of a millisecond, not a clean 0.0, so an `== 0.0` test passed it straight through
    # while the table beside it printed "med 0" under a `:.0f` format. The guard read as
    # firing and was not. Durations below print at one decimal for the same reason.
    median_duration = statistics.median(durations)
    if median_duration < 1.0:
        print(
            f"DEGENERATE - '{args.span}' was found in {len(profiles)} traces but reports "
            f"{median_duration:.3f} ms at the median, so it does no measurable work and its "
            "statement count cannot evidence anything. Profile the span that owns the queries."
        )
        return 4

    c_min, c_med, c_p95 = _quantiles(counts)
    d_min, d_med, d_p95 = _quantiles(durations)
    s_min, s_med, s_p95 = _quantiles(sql_times)

    print(f"span occurrences: {len(profiles)}")
    print(f"  SQL statements per span : min {c_min:.0f}  med {c_med:.0f}  p95 {c_p95:.0f}")
    print(f"  span duration (ms)      : min {d_min:.1f}  med {d_med:.1f}  p95 {d_p95:.1f}")
    print(f"  SQL time in span (ms)   : min {s_min:.1f}  med {s_med:.1f}  p95 {s_p95:.1f}")
    print(f"  SQL share of span       : med {statistics.median(shares):.0%}")

    # The two methods, side by side - see the module docstring on why both are printed.
    print(
        f"  double-count check      : {cov.sql_nodes_seen} SQL nodes seen across "
        f"{cov.fetched} traces, {cov.sql_nodes_in_span} inside the span, "
        f"{cov.dedup_statements} after (start_time, query) dedup over whole traces"
    )

    # The statement mix, which is what tells you whether a batch landed.
    mix: dict[str, int] = {}
    for span in profiles:
        for statement, _ in span.statements:
            key = " ".join(statement.split()[:6])
            mix[key] = mix.get(key, 0) + 1
    print(f"  distinct statement forms: {len(mix)}")
    for key, count in sorted(mix.items(), key=lambda kv: -kv[1])[:12]:
        print(f"      {count:5d}  {key[:96]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
