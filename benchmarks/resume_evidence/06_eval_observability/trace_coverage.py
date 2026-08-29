#!/usr/bin/env python
"""E6.2 - per-hop trace coverage over a pinned staging window (API -> LangGraph ->
SQLAlchemy -> Bedrock -> MCP).

The repository's only existing coverage number is D-400's trace-to-spend join: 99.9%
(2,209/2,212 and 297/299), which answers one question about two Bedrock call types. It
says nothing about whether a request's *chain* is complete - whether the FastAPI span,
the SQLAlchemy statements, the LangGraph node and the model call all landed in the same
trace. That is what this measures.

**The denominator is the whole problem, and it has two traps in it.**

1. *The health-check trap* (AUD-F-30). ~97% of staging's traces were once `GET /readyz`;
   `tracing.py`'s `HEALTH_ENDPOINT_URLS` now excludes `healthz`/`readyz` at the
   instrumentation layer, so they never reach X-Ray at all. That fix is verified here
   rather than assumed (`health_endpoint_traces` in the output must be 0), and the
   remaining non-request traffic - the collector's own `GET /metrics` scrape on
   `localhost` - is classified `internal` and excluded from the authenticated denominator
   instead of being quietly counted as coverage.

2. *The short-circuit trap*, found by this run and the reason the expected-hop map is
   conditioned on the response status. In the pinned chat window, 90 of 210
   `POST /chat/sessions/{id}/messages` traces contain no LangGraph and no Bedrock span.
   Read naively that is 57.1% coverage and an alarming instrumentation gap. Every one of
   those 90 is an HTTP **429**: `install_global_rate_limit_middleware`
   (`packages/shared/src/intellichoice_shared/rate_limit.py:114`) and
   `_reject_if_over_caller_limit` (`apps/chat-api/src/chat_api/routers/sessions.py:673`)
   refuse the request *before* `_run_turn` is ever reached, so there is no node to
   instrument and no model call to make. The spans are not missing; the work never
   happened. Conditioned on a 2xx the same corpus is 120/120. Both numbers are reported.

**The expected-hop map is derived from the route handlers, not from what the traces
happen to contain** - deriving it from the traces would make any missing span invisible by
construction. Each entry cites the code it comes from; see `EXPECTED_HOPS`.

**SQLAlchemy double-count.** X-Ray records each SQLAlchemy statement twice: once as a
child subsegment of the span that issued it, and again as a standalone top-level segment
with `origin == "Database::SQL"` (`scripts/profile_xray_span.py`'s docstring records the
131%-of-wall-time reading that came from missing this). Hop presence here is decided
*structurally*, from descendants of the entry segment only; the standalone copies are
counted separately as `orphan_sql_segments` so the two views can be compared rather than
averaged.

**Sampling posture.** Read from configuration, not assumed: neither app sets a sampler
(`build_tracer_provider` in `packages/observability/src/intellichoice_observability/
tracing.py` constructs `TracerProvider(resource=...)` with no `sampler=`, so the SDK
default `ParentBased(ALWAYS_ON)` applies), no `OTEL_TRACES_SAMPLER` env var is set in
`terraform/environments/staging/main.tf`, and the collector's traces pipeline is
`otlp -> batch -> awsxray` with no sampling processor
(`terraform/modules/ecs-service/main.tf`). So one request should equal one trace, which
is what makes the k6 reconciliation below meaningful.

Read-only: `xray:GetTraceSummaries`, `xray:BatchGetTraces`, `logs:FilterLogEvents`. No
writes, no model spend.

Usage:
    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)"
    uv run python benchmarks/resume_evidence/06_eval_observability/trace_coverage.py \\
      --window e1_sustained_25vu_10m=2026-08-29T19:46:49Z..2026-08-29T19:56:56Z \\
      --k6-summary docs/resume_evidence/01_platform/raw/sustained_25vu_10m.json \\
      --correlation-log-group /ecs/intellichoice-staging-learning-api \\
      --correlation-stream-prefix learning-api \\
      --collector-log-group /ecs/intellichoice-staging-learning-api \\
      --out-json docs/resume_evidence/06_eval_observability/trace_coverage_results.json \\
      --out-csv  docs/resume_evidence/06_eval_observability/trace_coverage_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import boto3

# ---------------------------------------------------------------------------
# Hops
# ---------------------------------------------------------------------------

FASTAPI = "fastapi"
SQLALCHEMY = "sqlalchemy"
LANGGRAPH = "langgraph"
BEDROCK = "bedrock"
MCP = "mcp"

HOPS: tuple[str, ...] = (FASTAPI, SQLALCHEMY, LANGGRAPH, BEDROCK, MCP)

# The two manual Bedrock spans, from
# `packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:309,522`.
BEDROCK_SPANS = frozenset({"bedrock.generate_structured", "bedrock.create_embedding"})

# The five MCP span names, from their `traced_span()` call sites:
#   apps/learning-api/src/learning_api/services/video_catalog.py:108
#   apps/learning-api/src/learning_api/services/attendance.py:179
#   apps/chat-api/src/chat_api/services/branch_locator.py:64,90
#   apps/chat-api/src/chat_api/graph/nodes.py:991,1198
MCP_SPANS = frozenset(
    {
        "mcp.youtube_catalog.search",
        "mcp.gmail.send_email",
        "mcp.maps.geocode",
        "mcp.maps.compute_routes",
        "mcp.calendar.create_event",
    }
)

# The 25 named LangGraph node spans (8 learning + 17 chat), registered at
# `graph.add_node(...)` time in each app's `graph/build.py`. Listed so that an
# unrecognised `langgraph.*` name is reported rather than silently counted - a node
# renamed without updating this list is a real drift signal.
LEARNING_NODE_SPANS = frozenset(
    {
        "langgraph.select_student",
        "langgraph.await_child_selection",
        "langgraph.select_topic",
        "langgraph.resolve_attendance",
        "langgraph.submit_answer",
        "langgraph.intervention_choice",
        "langgraph.finalize_exam",
        "langgraph.resume",
    }
)
CHAT_NODE_SPANS = frozenset(
    {
        "langgraph.resolve_role",
        "langgraph.scope_guard",
        "langgraph.refuse",
        "langgraph.service_unavailable",
        "langgraph.unavailable_intent",
        "langgraph.retrieve_context",
        "langgraph.join_scope_and_retrieval",
        "langgraph.synthesize_answer",
        "langgraph.explain_access",
        "langgraph.prepare_admin_escalation",
        "langgraph.admin_escalation_blocked",
        "langgraph.admin_escalation",
        "langgraph.calendar_extract",
        "langgraph.calendar_no_event",
        "langgraph.calendar_event_listing",
        "langgraph.calendar_action",
        "langgraph.branch_locator_consent",
    }
)
NODE_SPANS = LEARNING_NODE_SPANS | CHAT_NODE_SPANS

# ---------------------------------------------------------------------------
# The expected-hop map - derived from the route handlers (see module docstring)
# ---------------------------------------------------------------------------

# Every entry is what a **2xx** on that route must produce. `expected_hops()` narrows this
# for non-2xx outcomes, because a request refused by middleware or by a pre-flight guard
# never reaches the deeper hops.
EXPECTED_HOPS: dict[str, frozenset[str]] = {
    # learning-api
    # `main.py`'s dev-token route mints a JWT in-process: no DB session, no graph.
    "POST /dev/token": frozenset({FASTAPI}),
    # routers/sessions.py:912 `create_session` - `del claims`, one `uuid4()`, one counter
    # increment. It touches nothing else, so a SQLAlchemy span here would be the surprise.
    "POST /learning/sessions": frozenset({FASTAPI}),
    # routers/sessions.py:922 `select_student` - resolves the student through the
    # `ProfileAdapter` (an instrumented engine) and invokes the graph
    # (`langgraph.select_student`). No model call on this route.
    "POST /learning/sessions/{id}/student": frozenset({FASTAPI, SQLALCHEMY, LANGGRAPH}),
    # routers/sessions.py:1016 `select_topic` - reads checkpoint state, `CurriculumRepository`
    # lookup, then the graph (`langgraph.select_topic`, `langgraph.resolve_attendance`).
    "POST /learning/sessions/{id}/topics": frozenset({FASTAPI, SQLALCHEMY, LANGGRAPH}),
    # routers/sessions.py:1208 `submit_answer` - `AssessmentRepository`/`StudyRepository`
    # pre-flights, then the graph (`langgraph.submit_answer`). Grading is deterministic
    # (rule 2), so a pre-exam answer makes no model call; D-217 defers the study-transition
    # narrative to a background task under the real Bedrock provider, off this trace's
    # critical path. Hence no BEDROCK here.
    "POST /learning/sessions/{id}/answers": frozenset({FASTAPI, SQLALCHEMY, LANGGRAPH}),
    # chat-api
    # routers/sessions.py `create_session` - mirrors the learning app: identifier only.
    "POST /chat/sessions": frozenset({FASTAPI}),
    # apps/chat-api/src/chat_api/routers/sessions.py:650 `post_message` - rate-limit read,
    # `_claim_turn`, then `_run_turn` over the chat graph, which retrieves (embedding) and
    # synthesizes (structured generation). Both Bedrock span names appear.
    "POST /chat/sessions/{id}/messages": frozenset({FASTAPI, SQLALCHEMY, LANGGRAPH, BEDROCK}),
}

# Routes that exist to be polled by infrastructure rather than by a user. Counted, then
# excluded from the authenticated denominator - the AUD-F-30 correction, applied to what
# is left after `HEALTH_ENDPOINT_URLS` already removed `/healthz` and `/readyz`.
INTERNAL_ROUTES = frozenset({"GET /metrics", "POST /metrics"})

# Routes reachable without a bearer token. `/dev/token` authenticates with a shared secret
# *header* and is the thing that mints the bearer, so it is traffic but not authenticated
# traffic; counting it as such would inflate the denominator with the cheapest request in
# the corpus.
UNAUTHENTICATED_ROUTES = frozenset({"POST /dev/token"})

# `tracing.py:HEALTH_ENDPOINT_URLS`. Any trace matching these is a regression in the
# exclusion, not a coverage datum - reported separately and loudly.
HEALTH_ROUTE_MARKERS = ("healthz", "readyz")

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_LONG_HEX = re.compile(r"^[0-9a-fA-F]{16,}$")
_DIGITS = re.compile(r"^\d+$")


def route_template(method: str | None, url: str | None) -> str:
    """`POST http://host/learning/sessions/<uuid>/answers?x=1` ->
    `POST /learning/sessions/{id}/answers`.

    Derived from the URL rather than from FastAPI's own templated span name on purpose: the
    templated name lives on the ASGI child spans, and a trace that lost those is exactly the
    kind of gap this instrument exists to count. `facts_from_documents` records the
    framework's template alongside, so the two can be compared.
    """
    if not url:
        return f"{(method or '?').upper()} <no-url>"
    path = url.split("://", 1)[-1]
    path = path[path.find("/") :] if "/" in path else "/"
    path = path.split("?", 1)[0].split("#", 1)[0]
    parts = []
    for part in path.split("/"):
        if _UUID.fullmatch(part) or _LONG_HEX.match(part) or _DIGITS.fullmatch(part):
            parts.append("{id}")
        else:
            parts.append(part)
    normalized = "/".join(parts) or "/"
    if len(normalized) > 1 and normalized.endswith("/"):
        normalized = normalized[:-1]
    return f"{(method or '?').upper()} {normalized}"


def expected_hops(route: str, status: int | None) -> frozenset[str]:
    """What a complete chain looks like for this route *at this outcome*.

    A non-2xx is not evidence of a missing span. The 429s in the chat corpus are refused by
    middleware before any node runs (`rate_limit.py:114`), and a 4xx from a pre-flight guard
    (`sessions.py`'s 409s) returns before `_invoke_with_deadline`. For those, only the
    entry span is expected; they are bucketed as `short_circuit` and kept out of the primary
    coverage denominator rather than scored against a chain that was never supposed to run.
    """
    base = EXPECTED_HOPS.get(route)
    if base is None:
        return frozenset()
    if status is not None and not (200 <= status < 300):
        return frozenset({FASTAPI})
    return base


# ---------------------------------------------------------------------------
# Trace decomposition (pure - fixtures in the tests are literal segment documents)
# ---------------------------------------------------------------------------


@dataclass
class TraceFacts:
    """One trace, decomposed. Everything the classification needs, and nothing from AWS."""

    trace_id: str
    route: str = "? <no-url>"
    method: str | None = None
    status: int | None = None
    service: str | None = None
    fastapi_route_template: str | None = None
    hops_present: frozenset[str] = frozenset()
    span_names: tuple[str, ...] = ()
    node_spans: tuple[str, ...] = ()
    unknown_node_spans: tuple[str, ...] = ()
    descendant_sql: int = 0
    orphan_sql_segments: int = 0
    entry_segments: int = 0
    nested_request_spans: tuple[str, ...] = ()
    total_segments: int = 0

    @property
    def is_merged_request_trace(self) -> bool:
        """More than one HTTP request inside one trace - see `nested_request_spans`."""
        return bool(self.nested_request_spans) or self.entry_segments > 1


@dataclass
class Verdict:
    """The classification of one trace against the expected-hop map."""

    facts: TraceFacts
    bucket: str  # authenticated | unauthenticated | internal | health | unmapped
    outcome: str  # success | short_circuit
    expected: frozenset[str]
    missing: frozenset[str]
    unexpected: frozenset[str]

    @property
    def complete(self) -> bool:
        return not self.missing


def _walk(node: dict[str, Any], depth: int = 0) -> Iterator[tuple[dict[str, Any], int]]:
    yield node, depth
    for sub in node.get("subsegments") or []:
        yield from _walk(sub, depth + 1)


_ASGI_SPAN = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) (\S+) http (send|receive)$")


def facts_from_documents(trace_id: str, documents: Sequence[dict[str, Any]]) -> TraceFacts:
    """Decompose one trace's already-parsed segment documents.

    `documents` is the list of `json.loads(segment["Document"])` for every segment in the
    X-Ray trace. Split into:

    * **entry segments** - the ones carrying an `http.request.url`. In this deployment the
      FastAPI server span is translated by the `awsxray` exporter into the root segment,
      named after the OTel service resource (`learning-api` / `chat-api`), with the HTTP
      block attached. Its presence *is* the FastAPI hop.
    * **orphan SQL segments** - standalone top-level segments with `origin ==
      "Database::SQL"`, the duplicate copy of each SQLAlchemy statement. Counted, never
      used to satisfy a hop.
    """
    hops: set[str] = set()
    names: list[str] = []
    nodes: list[str] = []
    unknown_nodes: list[str] = []
    descendant_sql = 0
    orphan_sql = 0
    entry_segments = 0
    nested_requests: list[str] = []
    method: str | None = None
    url: str | None = None
    status: int | None = None
    service: str | None = None
    fastapi_template: str | None = None

    for document in documents:
        http = document.get("http") or {}
        request = http.get("request") or {}
        is_entry = bool(request.get("url"))
        if document.get("origin") == "Database::SQL" and not is_entry:
            orphan_sql += 1
            continue
        # A segment with neither an HTTP block nor the `Database::SQL` origin is still
        # walked below - nothing is dropped - but it cannot supply the FastAPI hop.
        if is_entry:
            entry_segments += 1
            hops.add(FASTAPI)
            method = method or request.get("method")
            url = url or request.get("url")
            response_status = (http.get("response") or {}).get("status")
            if status is None and response_status is not None:
                status = int(response_status)
            service = service or document.get("name")

        for node, depth in _walk(document):
            name = node.get("name")
            if not isinstance(name, str):
                continue
            names.append(name)
            if depth > 0:
                nested_url = ((node.get("http") or {}).get("request") or {}).get("url")
                if nested_url:
                    # A *second* HTTP request's server span, sitting inside another
                    # request's trace. Measured live: 19 of 13,550 requests in the E1.1
                    # window (0.14%) share a trace id with a different request in the same
                    # task, and X-Ray nests the loser under the winner - one trace in the
                    # corpus has a whole `POST /dev/token` hanging off a
                    # `POST .../answers`. Recorded rather than silently absorbed: those
                    # spans would otherwise be credited to the host route's chain and make
                    # coverage look better than it is.
                    nested_requests.append(
                        route_template(
                            ((node.get("http") or {}).get("request") or {}).get("method"),
                            nested_url,
                        )
                    )
            if node.get("sql") is not None and depth > 0:
                descendant_sql += 1
                hops.add(SQLALCHEMY)
            if name.startswith("langgraph."):
                hops.add(LANGGRAPH)
                nodes.append(name)
                if name not in NODE_SPANS:
                    unknown_nodes.append(name)
            elif name in BEDROCK_SPANS or name.startswith("bedrock."):
                hops.add(BEDROCK)
            elif name in MCP_SPANS or name.startswith("mcp."):
                hops.add(MCP)
            elif fastapi_template is None:
                match = _ASGI_SPAN.match(name)
                if match:
                    fastapi_template = f"{match.group(1)} {match.group(2)}"

    return TraceFacts(
        trace_id=trace_id,
        route=route_template(method, url),
        method=method,
        status=status,
        service=service,
        fastapi_route_template=fastapi_template,
        hops_present=frozenset(hops),
        span_names=tuple(names),
        node_spans=tuple(sorted(set(nodes))),
        unknown_node_spans=tuple(sorted(set(unknown_nodes))),
        descendant_sql=descendant_sql,
        orphan_sql_segments=orphan_sql,
        entry_segments=entry_segments,
        nested_request_spans=tuple(sorted(set(nested_requests))),
        total_segments=len(documents),
    )


def classify(facts: TraceFacts) -> Verdict:
    """Bucket the trace and score it against `expected_hops(route, status)`."""
    route = facts.route
    if any(marker in route for marker in HEALTH_ROUTE_MARKERS):
        bucket = "health"
    elif route in INTERNAL_ROUTES:
        bucket = "internal"
    elif route in UNAUTHENTICATED_ROUTES:
        bucket = "unauthenticated"
    elif route in EXPECTED_HOPS:
        bucket = "authenticated"
    else:
        bucket = "unmapped"

    outcome = (
        "success" if facts.status is not None and 200 <= facts.status < 300 else "short_circuit"
    )
    expected = expected_hops(route, facts.status)
    missing = expected - facts.hops_present
    # Only hops that the map *knows about* count as unexpected - a trace on an unmapped
    # route has no expectation to exceed.
    unexpected = (facts.hops_present - expected) if route in EXPECTED_HOPS else frozenset()
    return Verdict(
        facts=facts,
        bucket=bucket,
        outcome=outcome,
        expected=expected,
        missing=missing,
        unexpected=unexpected,
    )


# ---------------------------------------------------------------------------
# Correlation IDs
# ---------------------------------------------------------------------------


def otel_trace_id_to_xray(trace_id: str) -> str | None:
    """`logging_config.py` stamps the OTel `trace_id` as 32 lowercase hex on every JSON log
    line. X-Ray's own id for the same trace is `1-<first 8 hex>-<remaining 24 hex>` - the
    first 8 are the epoch seconds the trace started. Converting rather than string-matching
    makes the log/trace correlation an actual **join** instead of a field-presence check:
    "the field is set" and "the field points at a trace that exists" are different claims,
    and only the second one is worth anything during an incident.
    """
    cleaned = (trace_id or "").strip().lower()
    if len(cleaned) != 32 or any(c not in "0123456789abcdef" for c in cleaned):
        return None
    return f"1-{cleaned[:8]}-{cleaned[8:]}"


# ---------------------------------------------------------------------------
# Aggregation (pure)
# ---------------------------------------------------------------------------


@dataclass
class RouteCoverage:
    route: str
    bucket: str
    total: int = 0
    success: int = 0
    short_circuit: int = 0
    complete_success: int = 0
    missing_by_hop: Counter[str] = field(default_factory=Counter)
    expected_hops: tuple[str, ...] = ()
    statuses: Counter[int] = field(default_factory=Counter)

    def as_row(self) -> dict[str, Any]:
        denom = self.success
        return {
            "route": self.route,
            "bucket": self.bucket,
            "expected_hops_on_2xx": "|".join(self.expected_hops),
            "traces_total": self.total,
            "traces_2xx": self.success,
            "traces_non_2xx_short_circuit": self.short_circuit,
            "complete_chain_2xx": self.complete_success,
            "coverage_2xx": (self.complete_success / denom) if denom else None,
            "coverage_naive_all_statuses": (
                (self.complete_success / self.total) if self.total else None
            ),
            "missing_hops": "|".join(
                f"{hop}:{count}" for hop, count in sorted(self.missing_by_hop.items())
            ),
            "status_counts": "|".join(
                f"{status}:{count}" for status, count in sorted(self.statuses.items())
            ),
        }


def aggregate(verdicts: Sequence[Verdict]) -> dict[str, RouteCoverage]:
    """Per-route-class coverage. `coverage_2xx` is the headline; the naive all-statuses
    number is carried beside it so the report can show the gap the 429s open."""
    by_route: dict[str, RouteCoverage] = {}
    for verdict in verdicts:
        route = verdict.facts.route
        entry = by_route.get(route)
        if entry is None:
            entry = RouteCoverage(
                route=route,
                bucket=verdict.bucket,
                expected_hops=tuple(sorted(EXPECTED_HOPS.get(route, frozenset()))),
            )
            by_route[route] = entry
        entry.total += 1
        if verdict.facts.status is not None:
            entry.statuses[verdict.facts.status] += 1
        if verdict.outcome == "success":
            entry.success += 1
            if verdict.complete:
                entry.complete_success += 1
            for hop in verdict.missing:
                entry.missing_by_hop[hop] += 1
        else:
            entry.short_circuit += 1
            for hop in verdict.missing:
                entry.missing_by_hop[hop] += 1
    return by_route


def per_hop_rates(verdicts: Sequence[Verdict]) -> dict[str, dict[str, Any]]:
    """Missing-span rate per hop, over the traces that *expect* that hop on a 2xx.

    The denominator is per hop and never the whole corpus: `POST /learning/sessions`
    expects no SQLAlchemy span, so counting it in the SQLAlchemy denominator would report a
    route that is behaving correctly as a coverage failure.
    """
    out: dict[str, dict[str, Any]] = {}
    for hop in HOPS:
        expecting = [v for v in verdicts if hop in v.expected and v.outcome == "success"]
        present = sum(1 for v in expecting if hop in v.facts.hops_present)
        out[hop] = {
            "traces_expecting_hop": len(expecting),
            "traces_with_hop": present,
            "traces_missing_hop": len(expecting) - present,
            "missing_rate": ((len(expecting) - present) / len(expecting)) if expecting else None,
            "routes_expecting": sorted({v.facts.route for v in expecting}),
        }
    return out


# ---------------------------------------------------------------------------
# AWS I/O
# ---------------------------------------------------------------------------


def _parse_window(spec: str) -> tuple[str, datetime, datetime]:
    """`label=2026-08-29T19:46:49Z..2026-08-29T19:56:56Z` -> (label, start, end), both UTC.

    Explicit UTC at the boundary, deliberately: the CLI prints `get-metric-statistics`
    datapoints in the caller's local zone (`-05:00` here) and D-135 §3 records one wrong
    reading that came from exactly that offset. A naive datetime is refused rather than
    localized.
    """
    label, _, window = spec.partition("=")
    start_raw, _, end_raw = window.partition("..")
    if not (label and start_raw and end_raw):
        raise ValueError(f"--window must be LABEL=START..END, got {spec!r}")
    start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("window bounds must carry an explicit timezone (use ...Z)")
    return label, start.astimezone(UTC), end.astimezone(UTC)


def _client(service: str, region: str, profile: str | None) -> Any:
    # Same credential note as `scripts/scan_xray_pii.py`: boto3 cannot read the CLI's
    # `aws login` cache without botocore[crt], so the caller exports credentials first.
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        session = boto3.Session(region_name=region)
    else:
        session = boto3.Session(profile_name=profile, region_name=region)
    return session.client(service)


def fetch_verdicts(
    xray: Any,
    start: datetime,
    end: datetime,
    *,
    filter_expression: str | None,
    progress: bool = True,
) -> tuple[list[Verdict], int]:
    """Enumerate every trace summary in the window, then fetch and decompose every trace.

    Full enumeration, not a sample: the window is bounded and the corpus is the point. The
    summary count is returned separately so the report can state fetched-vs-summarized -
    a trace that a summary announced and `BatchGetTraces` did not return is itself a
    finding, not a rounding error.
    """
    trace_ids: list[str] = []
    kwargs: dict[str, Any] = {"StartTime": start, "EndTime": end}
    if filter_expression:
        kwargs["FilterExpression"] = filter_expression
    for page in xray.get_paginator("get_trace_summaries").paginate(**kwargs):
        for summary in page.get("TraceSummaries", []):
            trace_ids.append(summary["Id"])

    verdicts: list[Verdict] = []
    for index in range(0, len(trace_ids), 5):
        batch = trace_ids[index : index + 5]
        for page in xray.get_paginator("batch_get_traces").paginate(TraceIds=batch):
            for trace in page.get("Traces", []):
                documents = []
                for segment in trace.get("Segments", []):
                    try:
                        documents.append(json.loads(segment.get("Document", "{}")))
                    except json.JSONDecodeError:
                        continue
                verdicts.append(classify(facts_from_documents(trace.get("Id", "?"), documents)))
        if progress and index and index % 500 == 0:
            print(f"  ... {index}/{len(trace_ids)} traces fetched", file=sys.stderr, flush=True)
    return verdicts, len(trace_ids)


def correlation_spot_check(
    logs: Any,
    log_group: str,
    start: datetime,
    end: datetime,
    xray_trace_ids: set[str],
    *,
    stream_prefix: str,
    max_events: int = 40_000,
) -> dict[str, Any]:
    """Join the JSON access log to X-Ray, in both directions.

    Forward: what share of `http_request` access lines carry a `trace_id` at all
    (`logging_config.py` stamps it only when a span context is active - a line emitted
    outside a traced request has none, which is a real gap and not an error).
    Reverse: what share of those `trace_id`s, converted to X-Ray form, name a trace that
    the window's own fetch actually returned. That direction is the one that matters:
    an id that points nowhere is worse than an absent one, because it looks like evidence.
    """
    total = 0
    access_lines = 0
    with_trace_id = 0
    joinable = 0
    joined = 0
    unmatched_sample: list[str] = []
    events_without_trace: Counter[str] = Counter()
    log_trace_ids: set[str] = set()
    paths_without_trace_id: Counter[str] = Counter()
    trace_id_line_counts: Counter[str] = Counter()
    lines_by_trace_id: dict[str, list[str]] = {}

    paginator = logs.get_paginator("filter_log_events")
    for page in paginator.paginate(
        logGroupName=log_group,
        logStreamNamePrefix=stream_prefix,
        startTime=int(start.timestamp() * 1000),
        endTime=int(end.timestamp() * 1000),
    ):
        for event in page.get("events", []):
            total += 1
            if total > max_events:
                break
            try:
                payload = json.loads(event["message"])
            except (json.JSONDecodeError, KeyError):
                continue
            if payload.get("event") != "http_request":
                if not payload.get("trace_id"):
                    events_without_trace[str(payload.get("event"))[:60]] += 1
                continue
            access_lines += 1
            raw = payload.get("trace_id")
            path = f"{payload.get('method')} {payload.get('path')}"
            if not raw:
                # Not an error by itself: `tracing.py` excludes `/healthz` and `/readyz`
                # from instrumentation, so their access lines have no span context to
                # stamp. Broken out by path so that benign absence and a real gap are
                # distinguishable in the artifact rather than in a reader's head.
                paths_without_trace_id[path] += 1
                continue
            with_trace_id += 1
            converted = otel_trace_id_to_xray(str(raw))
            if converted is None:
                continue
            joinable += 1
            log_trace_ids.add(converted)
            trace_id_line_counts[converted] += 1
            lines_by_trace_id.setdefault(converted, []).append(path)
            if converted in xray_trace_ids:
                joined += 1
            elif len(unmatched_sample) < 5:
                unmatched_sample.append(converted)
        if total > max_events:
            break

    # Two requests that logged the same `trace_id` are two requests that cannot be told
    # apart in the trace store. This is the *only* place the collision is visible: X-Ray
    # merges them into one trace, so counting traces alone reports it as a shortfall and
    # invites the wrong conclusion ("spans were dropped").
    shared = {tid: n for tid, n in trace_id_line_counts.items() if n > 1}
    shared_sample = [
        {"xray_trace_id": tid, "routes": sorted(set(lines_by_trace_id[tid]))}
        for tid in list(shared)[:10]
    ]
    return {
        "log_group": log_group,
        "log_stream_prefix": stream_prefix,
        "log_events_read": total,
        "trace_ids_shared_by_more_than_one_request": len(shared),
        "access_lines_sharing_a_trace_id": sum(shared.values()),
        "extra_requests_with_no_trace_of_their_own": sum(n - 1 for n in shared.values()),
        "shared_trace_id_sample": shared_sample,
        "access_lines_without_trace_id_by_route": dict(paths_without_trace_id.most_common(10)),
        "truncated_at_max_events": total > max_events,
        "access_log_lines": access_lines,
        "access_lines_with_trace_id": with_trace_id,
        "trace_id_presence_rate": (with_trace_id / access_lines) if access_lines else None,
        "access_lines_with_wellformed_trace_id": joinable,
        "access_lines_joined_to_a_fetched_trace": joined,
        "log_to_trace_join_rate": (joined / joinable) if joinable else None,
        "distinct_log_trace_ids": len(log_trace_ids),
        "xray_traces_named_by_a_log_line": len(log_trace_ids & xray_trace_ids),
        "xray_traces_fetched": len(xray_trace_ids),
        "trace_to_log_join_rate": (
            len(log_trace_ids & xray_trace_ids) / len(xray_trace_ids) if xray_trace_ids else None
        ),
        "unmatched_trace_id_sample": unmatched_sample,
        "non_access_events_without_trace_id": dict(events_without_trace.most_common(10)),
    }


def collector_export_posture(
    logs: Any,
    log_group: str,
    start: datetime,
    end: datetime,
    *,
    stream_prefix: str = "otel-collector",
    max_control_pages: int = 20,
) -> dict[str, Any]:
    """What the collector said about its own exporting during the window.

    AUD-F-12 is the reason this is here: the collector once discarded **100%** of spans
    silently, and nothing alarmed. The honest answer this returns is usually "no error
    lines", which is weaker than it sounds - the ADOT collector serves its own
    `otelcol_exporter_sent_spans` / `otelcol_exporter_send_failed_spans` counters on
    `localhost:8888` (`"metrics level": "Normal"` in its startup line), and the Prometheus
    receiver in `terraform/modules/ecs-service/main.tf` scrapes `localhost:<app port>`
    only. So the success/failure *counts* exist inside the task and are exported nowhere;
    the log is the only external surface, and it carries errors, not rates.
    """

    def read(window_start: datetime, window_end: datetime) -> tuple[int, Counter[str], list[str]]:
        seen = 0
        found_levels: Counter[str] = Counter()
        found_errors: list[str] = []
        for page in logs.get_paginator("filter_log_events").paginate(
            logGroupName=log_group,
            logStreamNamePrefix=stream_prefix,
            startTime=int(window_start.timestamp() * 1000),
            endTime=int(window_end.timestamp() * 1000),
        ):
            for event in page.get("events", []):
                seen += 1
                message = event.get("message", "")
                parts = message.split("\t")
                level = parts[1].strip() if len(parts) > 1 else "unstructured"
                found_levels[level] += 1
                if level in {"error", "warn"} and len(found_errors) < 10:
                    found_errors.append(message[:300])
        return seen, found_levels, found_errors

    total, levels, errors = read(start, end)

    # **Positive control.** "Zero collector log events, therefore no export failures" is
    # precisely the AUD-F-12 false negative - a silent reader certifying a silent
    # collector. So when the window is empty, the reader has to prove itself on data it
    # *can* see before the empty result means anything.
    #
    # Done by reading the newest collector stream directly rather than by widening the
    # `filter_log_events` window: that call fans out over every stream in the group, and
    # even a 7-day sweep of this group takes longer than the entire 13,571-trace fetch.
    # `describe_log_streams` + `get_log_events` is a bounded number of calls and answers
    # the same question - can this code read this container's log at all.
    control: dict[str, Any] = {"needed": total == 0}
    if total == 0:
        newest_name: str | None = None
        newest_ts = -1
        pages = 0
        for page in logs.get_paginator("describe_log_streams").paginate(
            logGroupName=log_group, logStreamNamePrefix=stream_prefix
        ):
            pages += 1
            for stream in page.get("logStreams", []):
                last = stream.get("lastEventTimestamp") or 0
                if last > newest_ts:
                    newest_ts, newest_name = last, stream.get("logStreamName")
            if pages >= max_control_pages:
                break
        sample: list[str] = []
        if newest_name:
            events = logs.get_log_events(
                logGroupName=log_group,
                logStreamName=newest_name,
                startFromHead=True,
                limit=5,
            ).get("events", [])
            sample = [event.get("message", "")[:200] for event in events]
        control["method"] = "newest collector stream, read directly"
        control["newest_stream_last_event_utc"] = (
            datetime.fromtimestamp(newest_ts / 1000, UTC).isoformat().replace("+00:00", "Z")
            if newest_ts > 0
            else None
        )
        control["events_read_from_newest_stream"] = len(sample)
        control["sample"] = sample
        control["reader_proven"] = bool(sample)
    return {
        "log_group": log_group,
        "log_stream_prefix": stream_prefix,
        "collector_log_events_in_window": total,
        "levels": dict(levels),
        "error_or_warn_sample": errors,
        "positive_control": control,
        "export_success_count_available": False,
        "export_failure_count_available": False,
        "why": (
            "ADOT serves otelcol_exporter_sent_spans/send_failed_spans on localhost:8888; "
            "the collector's own prometheus receiver scrapes localhost:<app-port> only, so "
            "those counters leave the task nowhere. Only error log lines are externally "
            "visible."
        ),
    }


# ---------------------------------------------------------------------------
# k6 reconciliation
# ---------------------------------------------------------------------------

# k6 check name -> route template. The k6 script issues exactly one request per check
# (`load-tests/k6/learning_sessions_staging_sustained.js`), so a check's passes+fails is
# that route's request count - the ground-truth denominator X-Ray has to be reconciled
# against.
K6_CHECK_TO_ROUTE = {
    "dev-token 200": "POST /dev/token",
    "create session 200": "POST /learning/sessions",
    "select student 200": "POST /learning/sessions/{id}/student",
    "select topic 200": "POST /learning/sessions/{id}/topics",
    "answer 200": "POST /learning/sessions/{id}/answers",
}


def k6_route_counts(summary: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Per-route request counts from a k6 legacy summary export."""
    counts: dict[str, dict[str, int]] = {}

    def visit(group: dict[str, Any]) -> None:
        checks = group.get("checks")
        if isinstance(checks, dict):
            for check in checks.values():
                route = K6_CHECK_TO_ROUTE.get(str(check.get("name")))
                if route is None:
                    continue
                passes = int(check.get("passes", 0))
                fails = int(check.get("fails", 0))
                counts[route] = {
                    "k6_requests": passes + fails,
                    "k6_passes": passes,
                    "k6_fails": fails,
                }
        for child in (group.get("groups") or {}).values():
            visit(child)

    visit(summary.get("root_group") or {})
    return counts


def reconcile_with_k6(
    summary: dict[str, Any], coverage: dict[str, RouteCoverage]
) -> dict[str, Any]:
    """k6's request count vs X-Ray's trace count, per route and in total.

    With no sampler anywhere in the pipeline this should be 1:1. A shortfall is either an
    export drop or a request the app never saw (refused at CloudFront/ALB); the direction
    of the difference is reported so the two are not conflated.
    """
    per_route = k6_route_counts(summary)
    rows = []
    k6_total = 0
    trace_total = 0
    for route, k6 in sorted(per_route.items()):
        traces = coverage[route].total if route in coverage else 0
        k6_total += k6["k6_requests"]
        trace_total += traces
        rows.append(
            {
                "route": route,
                **k6,
                "xray_traces": traces,
                "delta_traces_minus_requests": traces - k6["k6_requests"],
                "trace_per_request": (traces / k6["k6_requests"]) if k6["k6_requests"] else None,
            }
        )
    metrics = summary.get("metrics") or {}
    # k6 has moved this key between summary versions: `metrics.http_reqs.count` in the
    # legacy export this repository's runs produce, `metrics.http_reqs.values.count` in
    # newer ones. Reading only one shape returns `null` and silently drops the
    # cross-check against the per-check totals.
    http_reqs_metric = metrics.get("http_reqs") or {}
    http_reqs = http_reqs_metric.get("count")
    if http_reqs is None:
        http_reqs = (http_reqs_metric.get("values") or {}).get("count")
    return {
        "per_route": rows,
        "k6_requests_total_from_checks": k6_total,
        "k6_http_reqs_metric": http_reqs,
        "xray_traces_on_k6_routes": trace_total,
        "delta_traces_minus_requests": trace_total - k6_total,
        "trace_per_request": (trace_total / k6_total) if k6_total else None,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def summarize_window(
    label: str, start: datetime, end: datetime, verdicts: Sequence[Verdict], summaries_seen: int
) -> dict[str, Any]:
    coverage = aggregate(verdicts)
    authenticated = [v for v in verdicts if v.bucket == "authenticated"]
    auth_success = [v for v in authenticated if v.outcome == "success"]
    complete = [v for v in auth_success if v.complete]
    health = [v for v in verdicts if v.bucket == "health"]
    unmapped = sorted({v.facts.route for v in verdicts if v.bucket == "unmapped"})
    unknown_nodes = sorted({name for v in verdicts for name in v.facts.unknown_node_spans})
    return {
        "window_label": label,
        "window_start_utc": start.isoformat().replace("+00:00", "Z"),
        "window_end_utc": end.isoformat().replace("+00:00", "Z"),
        "window_seconds": (end - start).total_seconds(),
        "trace_summaries_seen": summaries_seen,
        "traces_fetched": len(verdicts),
        "traces_announced_but_not_returned": summaries_seen - len(verdicts),
        "health_endpoint_traces": len(health),
        "buckets": dict(Counter(v.bucket for v in verdicts)),
        "authenticated_traces": len(authenticated),
        "authenticated_2xx_traces": len(auth_success),
        "authenticated_short_circuit_traces": len(authenticated) - len(auth_success),
        "authenticated_2xx_complete_chains": len(complete),
        "coverage_authenticated_2xx": (len(complete) / len(auth_success) if auth_success else None),
        "coverage_authenticated_naive_all_statuses": (
            len(complete) / len(authenticated) if authenticated else None
        ),
        "per_route": [c.as_row() for c in sorted(coverage.values(), key=lambda c: c.route)],
        "per_hop": per_hop_rates(verdicts),
        "merged_request_traces": sum(1 for v in verdicts if v.facts.is_merged_request_trace),
        "nested_request_span_routes": dict(
            Counter(route for v in verdicts for route in v.facts.nested_request_spans).most_common()
        ),
        "orphan_sql_segments_total": sum(v.facts.orphan_sql_segments for v in verdicts),
        "descendant_sql_spans_total": sum(v.facts.descendant_sql for v in verdicts),
        "unmapped_routes": unmapped,
        "unknown_langgraph_span_names": unknown_nodes,
        "node_span_frequency": dict(
            Counter(name for v in verdicts for name in v.facts.node_spans).most_common()
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window",
        action="append",
        required=True,
        metavar="LABEL=START..END",
        help="pinned UTC window, e.g. e1=2026-08-29T19:46:49Z..2026-08-29T19:56:56Z",
    )
    parser.add_argument(
        "--filter",
        action="append",
        default=None,
        help="X-Ray FilterExpression, one per --window in the same order (or omit for all)",
    )
    parser.add_argument("--k6-summary", default=None, help="k6 legacy summary JSON to reconcile")
    parser.add_argument(
        "--k6-window",
        default=None,
        help="which --window label the k6 summary belongs to (default: the first)",
    )
    # These three are positional against `--window`, the same convention `--filter` uses:
    # entry *i* applies to window *i*, and an omitted entry skips that sub-measurement.
    # A window's correlation check has to read the log group of the service that served it,
    # so one global value cannot cover a learning window and a chat window in one run.
    parser.add_argument("--correlation-log-group", action="append", default=None)
    parser.add_argument("--correlation-stream-prefix", action="append", default=None)
    parser.add_argument("--collector-log-group", action="append", default=None)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--profile", default="jeongsik-staging-admin")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()

    windows = [_parse_window(spec) for spec in args.window]
    filters = args.filter or []
    xray = _client("xray", args.region, args.profile)
    logs = _client("logs", args.region, args.profile)

    results: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    exit_code = 0

    for index, (label, start, end) in enumerate(windows):
        expression = filters[index] if index < len(filters) else None
        print(
            f"[{label}] {start.isoformat()} -> {end.isoformat()} filter={expression or '(none)'}",
            file=sys.stderr,
            flush=True,
        )
        verdicts, summaries_seen = fetch_verdicts(xray, start, end, filter_expression=expression)
        # Positive control, in the spirit of `scripts/scan_xray_pii.py`: an empty corpus
        # certifying full coverage is the AUD-F-12 false negative, so zero traces is a
        # failure of the instrument and not a clean result.
        if not verdicts:
            print(
                f"[{label}] FAIL: zero traces in the window - refusing to report coverage",
                file=sys.stderr,
            )
            exit_code = 2
            continue
        summary = summarize_window(label, start, end, verdicts, summaries_seen)

        if args.k6_summary and label == (args.k6_window or windows[0][0]):
            with open(args.k6_summary, encoding="utf-8") as handle:
                summary["k6_reconciliation"] = reconcile_with_k6(
                    json.load(handle), aggregate(verdicts)
                )
        correlation_groups = args.correlation_log_group or []
        correlation_prefixes = args.correlation_stream_prefix or []
        if index < len(correlation_groups) and correlation_groups[index]:
            summary["correlation_spot_check"] = correlation_spot_check(
                logs,
                correlation_groups[index],
                start,
                end,
                {v.facts.trace_id for v in verdicts},
                stream_prefix=(
                    correlation_prefixes[index] if index < len(correlation_prefixes) else "api"
                ),
            )
        collector_groups = args.collector_log_group or []
        if index < len(collector_groups) and collector_groups[index]:
            summary["export_posture"] = collector_export_posture(
                logs, collector_groups[index], start, end
            )
        results.append(summary)
        for row in summary["per_route"]:
            all_rows.append({"window_label": label, **row})

    payload = {
        "experiment": "E6.2 per-hop trace coverage",
        "generated_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "environment": "deployed staging, read-only trace analysis",
        "sampling_posture": {
            "app_sdk_sampler": "SDK default ParentBased(ALWAYS_ON) - no sampler= argument in "
            "packages/observability/src/intellichoice_observability/tracing.py",
            "otel_traces_sampler_env": "unset in terraform/environments/staging/main.tf",
            "collector_traces_pipeline": "otlp -> batch -> awsxray (no sampling processor, "
            "terraform/modules/ecs-service/main.tf)",
            "conclusion": "no sampling; one request should equal one trace",
        },
        "expected_hop_map": {route: sorted(hops) for route, hops in sorted(EXPECTED_HOPS.items())},
        "windows": results,
    }
    with open(args.out_json, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")

    if all_rows:
        with open(args.out_csv, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    for window in results:
        print(
            f"[{window['window_label']}] fetched={window['traces_fetched']} "
            f"auth2xx={window['authenticated_2xx_traces']} "
            f"complete={window['authenticated_2xx_complete_chains']} "
            f"coverage={window['coverage_authenticated_2xx']}"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
