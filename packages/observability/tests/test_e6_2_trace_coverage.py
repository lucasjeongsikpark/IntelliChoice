"""E6.2's trace-coverage classifier, tested on literal X-Ray span trees.

This is an *instrument*, not shipped code, and it is the kind of instrument that fails
quietly: a classifier that mis-scores one route produces a coverage report that is
internally consistent, precise-looking and wrong. Four things here are worth more than
the rest, and each pins a mistake that has already been made once somewhere in this
repository's measurement history:

- **An orphan SQL segment must not satisfy the SQLAlchemy hop.** X-Ray writes every
  SQLAlchemy statement twice - as a child of the span that issued it, and again as a
  standalone top-level segment. `scripts/profile_xray_span.py` exists because a hand-rolled
  profile that missed this reported 131% of wall time in SQL. Here the same double-count
  would let a route with *no* instrumented database access appear fully covered.
- **A non-2xx is not a missing span.** 90 of the 210 chat-message traces in the measured
  corpus are HTTP 429s refused by middleware before any node runs. Scoring them against the
  full chain reports 57.1% coverage for a system that is behaving exactly as designed.
- **The classifier must still fire.** The complement of the above: a genuine 200 that lost
  its LangGraph span has to come back missing. A test suite that only proves the instrument
  stays quiet proves nothing about a detector.
- **Per-hop denominators are per hop.** `POST /learning/sessions` expects no SQLAlchemy
  span, so counting it in the SQLAlchemy denominator would score a correct route as a gap -
  the AUD-F-30 denominator error, one layer down.

Pure: literals in, dataclasses out. No AWS, no network, no filesystem.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "resume_evidence" / "06_eval_observability"


def _load(name: str) -> Any:
    """`benchmarks/` is outside the uv workspace on purpose (measurement code, not shipped
    code), so there is no package to import - the same by-path load the other benchmark
    tests use."""
    spec = importlib.util.spec_from_file_location(name, BENCH / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tc = _load("trace_coverage")


# --------------------------------------------------------------------------- fixtures


def sql_child(query: str = "SELECT 1") -> dict[str, Any]:
    """A SQLAlchemy statement as X-Ray records it *inside* the span that issued it."""
    return {"name": "intellichoice", "namespace": "remote", "sql": {"sanitized_query": query}}


def orphan_sql_segment(query: str = "SELECT 1") -> dict[str, Any]:
    """The duplicate copy of the same statement: a standalone top-level segment."""
    return {"name": "intellichoice", "origin": "Database::SQL", "sql": {"sanitized_query": query}}


def entry_segment(
    *,
    method: str = "POST",
    url: str,
    status: int = 200,
    service: str = "learning-api",
    subsegments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The FastAPI server span as the `awsxray` exporter writes it: the root segment, named
    after the OTel service resource, carrying the HTTP block."""
    return {
        "name": service,
        "http": {"request": {"method": method, "url": url}, "response": {"status": status}},
        "subsegments": subsegments or [],
    }


ANSWERS_URL = "http://d35dfnjzmgrm01.cloudfront.net/learning/sessions/6f652965-814a-4a1a-ac32-ffe27147594e/answers"
MESSAGES_URL = (
    "http://d2ex.cloudfront.net/chat/sessions/592e8acf-37fe-481a-9415-298062af61df/messages"
)


def learning_answers_trace(
    *, with_langgraph: bool = True, orphans: int = 3
) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = [
        sql_child("SELECT assessment_items"),
        {"name": "POST /learning/sessions/learning_session_id/answers http receive"},
    ]
    if with_langgraph:
        children.append(
            {
                "name": "langgraph.submit_answer",
                "subsegments": [sql_child("UPDATE mastery"), sql_child("INSERT answer")],
            }
        )
    children.append({"name": "POST /learning/sessions/learning_session_id/answers http send"})
    return [
        entry_segment(url=ANSWERS_URL, subsegments=children),
        *[orphan_sql_segment() for _ in range(orphans)],
    ]


# --------------------------------------------------------------------------- route_template


@pytest.mark.parametrize(
    ("method", "url", "expected"),
    [
        ("POST", ANSWERS_URL, "POST /learning/sessions/{id}/answers"),
        ("POST", "http://h/learning/sessions", "POST /learning/sessions"),
        ("POST", "http://h/dev/token", "POST /dev/token"),
        ("GET", "http://localhost:8001/metrics", "GET /metrics"),
        # The SSE URL carries a query string the exporter already redacted; the template
        # must drop it either way - a token in a route key would be a PII/credential leak
        # in the artifact itself.
        (
            "GET",
            "http://h/chat/sessions/592e8acf-37fe-481a-9415-298062af61df/stream?token=REDACTED",
            "GET /chat/sessions/{id}/stream",
        ),
        ("GET", "http://h/students/12345/dashboard", "GET /students/{id}/dashboard"),
        ("GET", None, "GET <no-url>"),
    ],
)
def test_route_template_normalizes_identifiers(method: str, url: str | None, expected: str) -> None:
    assert tc.route_template(method, url) == expected


# --------------------------------------------------------------------------- decomposition


def test_descendant_sql_supplies_the_hop_and_orphans_are_only_counted() -> None:
    facts = tc.facts_from_documents("t-1", learning_answers_trace())
    assert facts.route == "POST /learning/sessions/{id}/answers"
    assert facts.status == 200
    assert facts.hops_present == frozenset({tc.FASTAPI, tc.SQLALCHEMY, tc.LANGGRAPH})
    assert facts.descendant_sql == 3
    assert facts.orphan_sql_segments == 3
    assert facts.node_spans == ("langgraph.submit_answer",)


def test_an_orphan_sql_segment_cannot_satisfy_the_sqlalchemy_hop() -> None:
    """The double-count guard. `POST /learning/sessions` does no database work; if the
    standalone `Database::SQL` copies of some *other* request's statements could satisfy
    the hop, every route in the corpus would look instrumented."""
    documents = [
        entry_segment(url="http://h/learning/sessions", subsegments=[]),
        orphan_sql_segment(),
        orphan_sql_segment(),
    ]
    facts = tc.facts_from_documents("t-2", documents)
    assert facts.hops_present == frozenset({tc.FASTAPI})
    assert facts.descendant_sql == 0
    assert facts.orphan_sql_segments == 2
    assert tc.classify(facts).complete is True


def test_fastapi_route_template_is_recorded_from_the_asgi_span_but_not_relied_on() -> None:
    """The framework's own templated name is captured for comparison. It is deliberately not
    the source of `route`: a trace that lost its ASGI child spans is exactly the gap this
    instrument counts, and it must still be classifiable."""
    facts = tc.facts_from_documents("t-3", learning_answers_trace())
    assert facts.fastapi_route_template == "POST /learning/sessions/learning_session_id/answers"

    stripped = [entry_segment(url=ANSWERS_URL, subsegments=[sql_child()])]
    bare = tc.facts_from_documents("t-4", stripped)
    assert bare.fastapi_route_template is None
    assert bare.route == "POST /learning/sessions/{id}/answers"


def test_unknown_langgraph_span_names_are_surfaced() -> None:
    """A node renamed in `graph/build.py` without updating `NODE_SPANS` is drift, not a
    silent pass."""
    documents = [
        entry_segment(
            url=ANSWERS_URL,
            subsegments=[sql_child(), {"name": "langgraph.brand_new_node"}],
        )
    ]
    facts = tc.facts_from_documents("t-5", documents)
    assert tc.LANGGRAPH in facts.hops_present
    assert facts.unknown_node_spans == ("langgraph.brand_new_node",)


# --------------------------------------------------------------------------- classification


def test_a_429_is_a_short_circuit_not_a_missing_span() -> None:
    """The measured case: `install_global_rate_limit_middleware` and
    `_reject_if_over_caller_limit` refuse the request before `_run_turn`, so the LangGraph
    and Bedrock spans were never supposed to exist."""
    documents = [
        entry_segment(
            method="POST",
            url=MESSAGES_URL,
            status=429,
            service="chat-api",
            subsegments=[
                sql_child("SELECT rate_limit_events"),
                {"name": "POST /chat/sessions/chat_session_id/messages http send"},
            ],
        )
    ]
    verdict = tc.classify(tc.facts_from_documents("t-6", documents))
    assert verdict.bucket == "authenticated"
    assert verdict.outcome == "short_circuit"
    assert verdict.expected == frozenset({tc.FASTAPI})
    assert verdict.missing == frozenset()
    assert verdict.complete is True


def test_a_200_missing_its_langgraph_span_is_reported_missing() -> None:
    """The detector's positive control: quiet on the 429 above, loud here."""
    verdict = tc.classify(
        tc.facts_from_documents("t-7", learning_answers_trace(with_langgraph=False))
    )
    assert verdict.outcome == "success"
    assert verdict.missing == frozenset({tc.LANGGRAPH})
    assert verdict.complete is False


def test_a_complete_chat_message_trace_requires_the_bedrock_hop() -> None:
    documents = [
        entry_segment(
            url=MESSAGES_URL,
            status=200,
            service="chat-api",
            subsegments=[
                sql_child(),
                {
                    "name": "langgraph.retrieve_context",
                    "subsegments": [{"name": "bedrock.create_embedding"}],
                },
                {
                    "name": "langgraph.synthesize_answer",
                    "subsegments": [{"name": "bedrock.generate_structured"}],
                },
            ],
        )
    ]
    verdict = tc.classify(tc.facts_from_documents("t-8", documents))
    assert verdict.expected == frozenset({tc.FASTAPI, tc.SQLALCHEMY, tc.LANGGRAPH, tc.BEDROCK})
    assert verdict.complete is True

    without_model = [
        entry_segment(
            url=MESSAGES_URL,
            status=200,
            service="chat-api",
            subsegments=[sql_child(), {"name": "langgraph.synthesize_answer"}],
        )
    ]
    assert tc.classify(tc.facts_from_documents("t-9", without_model)).missing == frozenset(
        {tc.BEDROCK}
    )


def test_health_and_internal_routes_leave_the_authenticated_denominator() -> None:
    """AUD-F-30, verified rather than assumed. `/readyz` should never reach X-Ray at all
    (`tracing.py`'s `HEALTH_ENDPOINT_URLS`); if one does it is bucketed `health` and
    counted separately, never folded into coverage."""
    readyz = tc.classify(
        tc.facts_from_documents("t-10", [entry_segment(method="GET", url="http://h/readyz")])
    )
    metrics = tc.classify(
        tc.facts_from_documents(
            "t-11", [entry_segment(method="GET", url="http://localhost:8001/metrics")]
        )
    )
    token = tc.classify(tc.facts_from_documents("t-12", [entry_segment(url="http://h/dev/token")]))
    assert readyz.bucket == "health"
    assert metrics.bucket == "internal"
    assert token.bucket == "unauthenticated"


def test_an_unmapped_route_has_no_expectation_to_fail() -> None:
    """A route the map does not know about is reported as unmapped, never scored - inventing
    an expectation would manufacture a coverage gap out of ignorance."""
    verdict = tc.classify(
        tc.facts_from_documents("t-13", [entry_segment(method="GET", url="http://h/chat/meta")])
    )
    assert verdict.bucket == "unmapped"
    assert verdict.expected == frozenset()
    assert verdict.missing == frozenset()
    assert verdict.unexpected == frozenset()


# --------------------------------------------------------------------------- aggregation


def test_aggregate_separates_the_naive_and_conditioned_coverage() -> None:
    """The number the report has to show both ways: 1 complete 200 beside 3 refused 429s is
    100% coverage conditioned on a 2xx and 25% read naively."""
    complete = tc.classify(
        tc.facts_from_documents(
            "ok",
            [
                entry_segment(
                    url=MESSAGES_URL,
                    status=200,
                    service="chat-api",
                    subsegments=[
                        sql_child(),
                        {"name": "langgraph.synthesize_answer"},
                        {"name": "bedrock.generate_structured"},
                    ],
                )
            ],
        )
    )
    refused = [
        tc.classify(
            tc.facts_from_documents(
                f"429-{i}",
                [
                    entry_segment(
                        url=MESSAGES_URL,
                        status=429,
                        service="chat-api",
                        subsegments=[sql_child()],
                    )
                ],
            )
        )
        for i in range(3)
    ]
    rows = tc.aggregate([complete, *refused])
    row = rows["POST /chat/sessions/{id}/messages"].as_row()
    assert row["traces_total"] == 4
    assert row["traces_2xx"] == 1
    assert row["traces_non_2xx_short_circuit"] == 3
    assert row["coverage_2xx"] == 1.0
    assert row["coverage_naive_all_statuses"] == 0.25
    assert row["status_counts"] == "200:1|429:3"


def test_per_hop_denominators_only_count_routes_that_expect_the_hop() -> None:
    create = tc.classify(
        tc.facts_from_documents("c", [entry_segment(url="http://h/learning/sessions")])
    )
    answers = tc.classify(tc.facts_from_documents("a", learning_answers_trace()))
    rates = tc.per_hop_rates([create, answers])
    # Both traces expect FastAPI; only the answers trace expects SQLAlchemy/LangGraph.
    assert rates[tc.FASTAPI]["traces_expecting_hop"] == 2
    assert rates[tc.SQLALCHEMY]["traces_expecting_hop"] == 1
    assert rates[tc.SQLALCHEMY]["missing_rate"] == 0.0
    # Nothing in this corpus calls a model or an MCP tool: 0/0, reported as None rather than
    # as a 0% or 100% that would read as a measurement.
    assert rates[tc.BEDROCK]["traces_expecting_hop"] == 0
    assert rates[tc.BEDROCK]["missing_rate"] is None
    assert rates[tc.MCP]["missing_rate"] is None


# --------------------------------------------------------------------------- correlation


@pytest.mark.parametrize(
    ("otel", "expected"),
    [
        (
            "68b1f2c9a1b2c3d4e5f60718293a4b5c",
            "1-68b1f2c9-a1b2c3d4e5f60718293a4b5c",
        ),
        ("68B1F2C9A1B2C3D4E5F60718293A4B5C", "1-68b1f2c9-a1b2c3d4e5f60718293a4b5c"),
        ("", None),
        ("not-hex-at-all-not-hex-at-all-xx", None),
        ("68b1f2c9a1b2c3d4e5f60718293a4b", None),
    ],
)
def test_otel_trace_id_to_xray(otel: str, expected: str | None) -> None:
    assert tc.otel_trace_id_to_xray(otel) == expected


# --------------------------------------------------------------------------- k6 + windows


def test_k6_route_counts_sum_passes_and_fails() -> None:
    """A failed check is still a request that should have produced a trace - counting only
    passes would shrink the ground-truth denominator toward whatever X-Ray happened to
    return."""
    summary = {
        "root_group": {
            "checks": {
                "0": {"name": "answer 200", "passes": 9668, "fails": 2},
                "1": {"name": "select topic 200", "passes": 967, "fails": 3},
                "2": {"name": "unrelated check", "passes": 5, "fails": 0},
            },
            "groups": {},
        },
        "metrics": {"http_reqs": {"values": {"count": 13550}}},
    }
    counts = tc.k6_route_counts(summary)
    assert counts["POST /learning/sessions/{id}/answers"]["k6_requests"] == 9670
    assert counts["POST /learning/sessions/{id}/topics"]["k6_requests"] == 970
    assert "unrelated check" not in counts

    coverage = tc.aggregate(
        [
            tc.classify(tc.facts_from_documents(f"a{i}", learning_answers_trace()))
            for i in range(9670)
        ]
    )
    recon = tc.reconcile_with_k6(summary, coverage)
    answers = next(r for r in recon["per_route"] if r["route"].endswith("/answers"))
    assert answers["xray_traces"] == 9670
    assert answers["delta_traces_minus_requests"] == 0
    assert answers["trace_per_request"] == 1.0
    assert recon["k6_http_reqs_metric"] == 13550


def test_parse_window_refuses_a_naive_timestamp() -> None:
    """The `-05:00` snare, made structural: a window without an explicit zone is refused
    rather than silently localized (D-135 §3 recorded one wrong reading from exactly that)."""
    label, start, end = tc._parse_window("w=2026-08-29T19:46:49Z..2026-08-29T19:56:56Z")
    assert label == "w"
    assert start.isoformat() == "2026-08-29T19:46:49+00:00"
    assert (end - start).total_seconds() == 607

    with pytest.raises(ValueError):
        tc._parse_window("w=2026-08-29T19:46:49..2026-08-29T19:56:56")
    with pytest.raises(ValueError):
        tc._parse_window("no-window-here")


# --------------------------------------------------------------------------- merged traces


def test_a_second_request_nested_inside_a_trace_is_detected_not_absorbed() -> None:
    """The measured collision: 19 of 13,550 requests in the E1.1 window shared a trace id
    with a different request in the same task, and X-Ray nested the loser under the winner -
    one real trace has a whole `POST /dev/token` hanging off a `POST .../answers`.

    Absorbing it silently is the dangerous outcome: the nested request drags its own
    FastAPI/SQL spans in with it, so the host route's chain looks complete on evidence that
    belongs to a different request."""
    nested = {
        "name": "10.0.10.199:8001",
        "http": {
            "request": {"method": "POST", "url": "http://h/dev/token"},
            "response": {"status": 200},
        },
        "subsegments": [{"name": "POST /dev/token http send"}],
    }
    documents = [
        entry_segment(
            url=ANSWERS_URL,
            subsegments=[sql_child(), {"name": "langgraph.submit_answer"}, nested],
        )
    ]
    facts = tc.facts_from_documents("merged", documents)
    assert facts.entry_segments == 1
    assert facts.nested_request_spans == ("POST /dev/token",)
    assert facts.is_merged_request_trace is True
    # The host route still classifies normally - the nesting is reported beside the
    # verdict, not used to invalidate it.
    assert facts.route == "POST /learning/sessions/{id}/answers"
    assert tc.classify(facts).complete is True


def test_a_clean_trace_is_not_flagged_as_merged() -> None:
    facts = tc.facts_from_documents("clean", learning_answers_trace())
    assert facts.nested_request_spans == ()
    assert facts.is_merged_request_trace is False


def test_k6_http_reqs_is_read_from_either_summary_shape() -> None:
    """k6 has moved this key between summary versions; reading only one shape returns null
    and silently drops the cross-check against the per-check totals."""
    legacy = {"root_group": {}, "metrics": {"http_reqs": {"count": 13550}}}
    modern = {"root_group": {}, "metrics": {"http_reqs": {"values": {"count": 13550}}}}
    assert tc.reconcile_with_k6(legacy, {})["k6_http_reqs_metric"] == 13550
    assert tc.reconcile_with_k6(modern, {})["k6_http_reqs_metric"] == 13550
