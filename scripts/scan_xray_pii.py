#!/usr/bin/env python
"""Scan live X-Ray trace segments for PII (SPEC §5.30, §2.6 gate criterion 9).

Why this is a script and not an ad-hoc CLI pipeline (S38/D-102's lesson): the first
version of S38's *log* scan reported zero hits for strings that were demonstrably
present, because `filter-log-events --max-items` paginates and only the first page was
read. A scan that cannot fail is worthless, so this one carries two structural guards:

1. **A positive control runs every time, before the real scan is trusted.** A synthetic
   segment document containing every needle is walked by the *same* matcher. If any
   pattern fails to fire on it, the run aborts as INVALID rather than reporting clean.
2. **Coverage is reported, not assumed.** The trace/segment counts are printed with the
   findings, and zero traces scanned is an explicit FAIL - "no hits" over an empty
   corpus is the exact false negative this guard exists to prevent.

Segments are parsed as JSON and walked as objects (keys *and* values), not regexed as
flat text: D-101 §5 records a `CAST(blob AS text) LIKE` check certifying a database full
of coordinates as clean because it could not parse its own target.

Usage:
    uv run python scripts/scan_xray_pii.py [--hours 6] [--profile jeongsik-staging-admin]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3

# Needles are sourced from the fixture seed module rather than written down here, so this
# script never becomes a place PII is committed and cannot drift from the fixtures.
sys.path.insert(0, "packages/adapters/src")
from intellichoice_adapters.seed import mysql_fixtures as fx  # noqa: E402


@dataclass(frozen=True)
class Pattern:
    """One thing that must not appear in a trace, and how to recognise it."""

    name: str
    kind: str  # "exact" (case-insensitive substring) or "regex"
    needle: str
    # What the positive control feeds the matcher to prove this pattern can fire.
    control: str


def _fixture_patterns() -> list[Pattern]:
    """Exact values from the seeded fixtures: names, emails, addresses, coordinates."""
    out: list[Pattern] = []
    for user in fx._USERS:
        name = user["display_name"]
        out.append(Pattern(f"fixture-name:{name}", "exact", name, f"student is {name}"))
    for branch in fx._BRANCHES:
        email = branch["manager_email"]
        address = branch["address"]
        out.append(Pattern(f"manager-email:{email}", "exact", email, f"contact {email}"))
        out.append(Pattern(f"branch-address:{address}", "exact", address, f"at {address}"))
        for axis in ("latitude", "longitude"):
            value = str(branch[axis])
            # Boundary-aware, not a substring: "39.85" as a substring matches the epoch
            # `start_time` on *every* X-Ray segment (1785093039.8546414), which is how the
            # first run of this scan reported 17 hits that were all timestamps. Same
            # mistake AUD-X-06 records in a test assertion one session earlier. Trailing
            # digits are still allowed so a more precise leak (39.850012) is caught.
            out.append(
                Pattern(
                    f"branch-{axis}:{value}",
                    "regex",
                    rf"(?<![\d.]){re.escape(value)}\d*(?![\d.])",
                    f"{axis}={value}",
                )
            )
    return out


# Shape patterns catch PII this project has not seeded but could still leak - a real
# caller's coordinates (AUD-C-03), a token in a URL (SSE `?token=`), an echoed answer.
SHAPE_PATTERNS = [
    Pattern(
        "shape:email",
        "regex",
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "someone@example.org",
    ),
    Pattern(
        "shape:jwt",
        "regex",
        r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.sig",
    ),
    Pattern("shape:bearer", "regex", r"[Bb]earer\s+[A-Za-z0-9._-]{8,}", "Bearer abcdefgh12345678"),
    Pattern("shape:token-query", "regex", r"[?&]token=[^&\s\"]+", "/stream?token=abc123"),
    Pattern(
        "shape:pii-field-name",
        "regex",
        r"\b(display_name|full_name|first_name|last_name|email|phone|address|latitude|longitude|lat|lng|coords?)\b",
        "display_name",
    ),
    # A bare decimal pair in the continental-US range - a real caller's location.
    Pattern(
        "shape:coordinate-pair",
        "regex",
        r"-?\b(2[5-9]|[3-4][0-9])\.\d{3,}\b.{0,40}-?\b(6[5-9]|[7-9][0-9]|1[0-2][0-9])\.\d{3,}\b",
        "39.78170, -89.65010",
    ),
]


@dataclass
class Hit:
    pattern: str
    path: str
    excerpt: str


@dataclass
class Findings:
    scanned_traces: int = 0
    scanned_segments: int = 0
    scanned_strings: int = 0
    allowlisted: int = 0
    hits: list[Hit] = field(default_factory=list)


def _walk(node: Any, path: str = "$") -> Iterator[tuple[str, str]]:
    """Yield every (path, string) in a parsed document - keys as well as values.

    X-Ray segments nest annotations, metadata and subsegments arbitrarily deep, and a
    leaked field *name* is itself evidence (`display_name` present at all means a name
    was attached), so keys are walked too.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{path}.{key}", str(key)
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk(value, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node
        # Segments carry JSON-in-string (metadata blobs, captured payloads). Parse it so
        # a nested document is walked as a document rather than matched as flat text.
        stripped = node.strip()
        if stripped[:1] in ("{", "[") and len(stripped) > 1:
            try:
                yield from _walk(json.loads(stripped), f"{path}<json>")
            except (json.JSONDecodeError, ValueError):
                pass
    elif node is not None:
        yield path, str(node)


# One narrow, deliberately visible exception. The SQL instrumentation records
# `sql.sanitized_query` - the statement with its parameters stripped - so a query over the
# branches table legitimately contains the column names `manager_email, address, latitude,
# longitude`. Those are schema, not data, and the stripping is exactly the behavior we
# want. Only the field-*name* pattern is excused, and only at this key: a coordinate or
# address *value* appearing in a sanitized query would still be reported, because it would
# mean parameters were not stripped. Counted and printed rather than silently dropped, so
# the exception cannot quietly grow to cover a real leak.
ALLOWLIST = [("shape:pii-field-name", re.compile(r"\.sql\.sanitized_query$"))]


def _allowlisted(pattern_name: str, path: str) -> bool:
    return any(name == pattern_name and rx.search(path) for name, rx in ALLOWLIST)


def _match(patterns: list[Pattern], document: Any, findings: Findings) -> None:
    compiled = [
        (p, re.compile(p.needle, re.IGNORECASE) if p.kind == "regex" else None) for p in patterns
    ]
    for path, text in _walk(document):
        findings.scanned_strings += 1
        for pattern, rx in compiled:
            at: int | None = None
            if rx is not None:
                m = rx.search(text)
                at = m.start() if m else None
            elif pattern.needle.lower() in text.lower():
                at = text.lower().index(pattern.needle.lower())
            if at is None:
                continue
            if _allowlisted(pattern.name, path):
                findings.allowlisted += 1
                continue
            findings.hits.append(Hit(pattern.name, path, _excerpt(text, at)))


def _excerpt(text: str, at: int) -> str:
    start, end = max(0, at - 30), min(len(text), at + 70)
    body = text[start:end].replace("\n", " ")
    return ("..." if start else "") + body + ("..." if end < len(text) else "")


def positive_control(patterns: list[Pattern]) -> tuple[bool, list[str]]:
    """Prove every pattern can fire, on a document shaped like a real segment."""
    control_segment = {
        "name": "control-service",
        "id": "1234567890abcdef",
        "annotations": {f"control_{i}": p.control for i, p in enumerate(patterns)},
        "metadata": {"nested": json.dumps({"payload": [p.control for p in patterns]})},
        "subsegments": [{"name": "control-sub", "http": {"request": {"url": "/x"}}}],
    }
    findings = Findings()
    _match(patterns, control_segment, findings)
    fired = {h.pattern for h in findings.hits}
    silent = [p.name for p in patterns if p.name not in fired]
    return not silent, silent


def scan(hours: int, profile: str, region: str) -> Findings:
    # Prefer credentials already in the environment. The CLI's `aws login` token cache
    # needs `botocore[crt]` to be readable by boto3, which this project does not install -
    # the same limitation that makes Terraform need
    # `eval "$(aws configure export-credentials --profile ... --format env)"`.
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        session = boto3.Session(region_name=region)
    else:
        session = boto3.Session(profile_name=profile, region_name=region)
    xray = session.client("xray")
    end = datetime.now(UTC)
    start = end - timedelta(hours=hours)

    trace_ids: list[str] = []
    paginator = xray.get_paginator("get_trace_summaries")
    for page in paginator.paginate(StartTime=start, EndTime=end):
        trace_ids.extend(s["Id"] for s in page.get("TraceSummaries", []))

    findings = Findings(scanned_traces=len(trace_ids))
    patterns = _fixture_patterns() + SHAPE_PATTERNS

    # batch-get-traces takes at most 5 ids per call.
    for i in range(0, len(trace_ids), 5):
        batch = trace_ids[i : i + 5]
        pages = xray.get_paginator("batch_get_traces").paginate(TraceIds=batch)
        for page in pages:
            for trace in page.get("Traces", []):
                for segment in trace.get("Segments", []):
                    findings.scanned_segments += 1
                    raw = segment.get("Document", "{}")
                    try:
                        document = json.loads(raw)
                    except json.JSONDecodeError:
                        document = raw
                    _match(patterns, document, findings)
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hours", type=int, default=6, help="lookback window (default 6)")
    ap.add_argument("--profile", default="jeongsik-staging-admin")
    ap.add_argument("--region", default="us-east-1")
    args = ap.parse_args()

    patterns = _fixture_patterns() + SHAPE_PATTERNS
    ok, silent = positive_control(patterns)
    print(f"positive control: {len(patterns) - len(silent)}/{len(patterns)} patterns fired")
    if not ok:
        print(f"INVALID - these patterns cannot fire, so a clean result proves nothing: {silent}")
        return 2

    findings = scan(args.hours, args.profile, args.region)
    print(
        f"scanned: {findings.scanned_traces} traces, {findings.scanned_segments} segments, "
        f"{findings.scanned_strings} strings over the last {args.hours}h"
    )
    if findings.allowlisted:
        print(f"allowlisted: {findings.allowlisted} matches (see ALLOWLIST - schema, not data)")
    if findings.scanned_traces == 0:
        print(
            "FAIL - zero traces in the window. 'No PII found' over an empty corpus is not evidence."
        )
        return 3

    if not findings.hits:
        print("CLEAN - no PII pattern matched any segment.")
        return 0

    by_pattern: dict[str, list[Hit]] = {}
    for hit in findings.hits:
        by_pattern.setdefault(hit.pattern, []).append(hit)
    print(f"FOUND {len(findings.hits)} hits across {len(by_pattern)} patterns:")
    for name, hits in sorted(by_pattern.items(), key=lambda kv: -len(kv[1])):
        print(f"  {name}: {len(hits)}")
        for hit in hits[:3]:
            print(f"      {hit.path}  {hit.excerpt}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
