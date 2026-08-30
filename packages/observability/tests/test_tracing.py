from collections.abc import Callable

import intellichoice_observability.tracing as tracing_module
from intellichoice_observability.tracing import (
    RedactingSpanExporter,
    build_tracer_provider,
    traced_span,
)
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Tracer


def _install_test_provider() -> InMemorySpanExporter:
    """OTel only allows the *global* TracerProvider to be set once per process, so this
    swaps `tracing_module._tracer` directly (what `traced_span` actually reads) rather
    than calling `trace.set_tracer_provider` again on every test.
    """
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)
    tracing_module._tracer = provider.get_tracer("intellichoice")
    return exporter


def test_nested_spans_share_one_trace_id() -> None:
    """Proxy for the SPEC §5.32.2/ROADMAP S31 "one request, one trace_id across every
    hop" requirement - here across two manually-instrumented hops standing in for
    (e.g.) the Bedrock gateway and a DB call."""
    exporter = _install_test_provider()

    with traced_span("fastapi.request", route="/learning/sessions"):
        with traced_span("bedrock.generate_structured", task="TUTOR"):
            pass
        with traced_span("db.query", table="mastery"):
            pass

    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}
    assert names == {"fastapi.request", "bedrock.generate_structured", "db.query"}
    trace_ids = set()
    for s in spans:
        assert s.context is not None
        trace_ids.add(s.context.trace_id)
    assert len(trace_ids) == 1


def test_span_attributes_are_recorded() -> None:
    exporter = _install_test_provider()

    with traced_span("mcp.tool_call", tool_name="gmail.send_email"):
        pass

    (span,) = exporter.get_finished_spans()
    assert span.attributes is not None
    assert span.attributes["tool_name"] == "gmail.send_email"


def test_current_trace_id_matches_the_active_span() -> None:
    exporter = _install_test_provider()

    observed_trace_id = None
    with traced_span("outer"):
        observed_trace_id = tracing_module.current_trace_id()

    (span,) = exporter.get_finished_spans()
    assert span.context is not None
    assert observed_trace_id == format(span.context.trace_id, "032x")


def test_sse_token_query_string_is_redacted_before_export() -> None:
    """AUD-F-13 regression, driven through the real instrumentation.

    Asserted at the level the defect actually occurred: `FastAPIInstrumentor` populating
    `http.url` with the full request URL, on the SSE route whose only auth channel *is*
    `?token=<JWT>` (EventSource cannot set an Authorization header). A unit test of the
    redaction regex alone would have passed while the leak continued, because the leak was
    about which attribute the instrumentation sets, not about the pattern.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from intellichoice_observability.tracing import instrument_fastapi_app

    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdHVkZW50LWV4dC0xIn0.sig-value"
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)

    app = FastAPI()

    @app.get("/learning/sessions/{learning_session_id}/stream")
    def stream(learning_session_id: str) -> dict[str, str]:
        return {"session": learning_session_id}

    instrument_fastapi_app(app, provider)
    response = TestClient(app).get(f"/learning/sessions/abc-123/stream?token={jwt}")
    assert response.status_code == 200

    exported = [dict(s.attributes or {}) for s in exporter.get_finished_spans()]
    urls = [str(a["http.url"]) for a in exported if "http.url" in a]
    assert urls, "no span carried http.url - the assertion would be vacuous"
    for url in urls:
        assert jwt not in url
        assert "eyJ" not in url
        assert "token=REDACTED" in url
        # The rest of the URL must survive, or the span stops being useful.
        assert "/learning/sessions/abc-123/stream" in url


def test_redaction_leaves_ordinary_attributes_untouched() -> None:
    """The negative arm: a redactor that rewrites everything would also pass the test
    above, and would quietly destroy the trace store's value."""
    exporter = _install_test_provider()

    with traced_span("db.query", table="mastery", statement="SELECT id FROM users"):
        pass

    (span,) = exporter.get_finished_spans()
    assert span.attributes is not None
    assert span.attributes["table"] == "mastery"
    assert span.attributes["statement"] == "SELECT id FROM users"


def _raw_span(record: Callable[[Tracer], None]) -> ReadableSpan:
    """A finished span that has **not** been through `RedactingSpanExporter`, for the two
    tests below that assert on the rebuild itself rather than on what a collector receives.
    `build_tracer_provider` wraps both of its branches on purpose, so the redacted output is
    all it can hand back - and "was this span rebuilt at all?" is not a question the redacted
    output can answer.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    record(provider.get_tracer("intellichoice"))
    (span,) = exporter.get_finished_spans()
    return span


def test_credentials_inside_span_events_are_redacted_before_export() -> None:
    """DRIFT-82. `_redacted` rebuilt the span's *attributes* and passed `events=span.events`
    through untouched, so a credential recorded as an event left the process.

    **The span's own attributes are deliberately clean**, which is the half of the defect that
    a naive fix misses: the `cleaned == attributes` fast path returned the original span
    *before* any events could be rebuilt, so the leak survived exactly on the spans that had
    nothing else wrong with them.

    All three `_REDACTIONS` patterns appear, because events are reached by a different code
    path than attributes and "the regexes work" was never the open question.
    """
    exporter = _install_test_provider()
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzdHVkZW50LWV4dC0xIn0.sig-value"

    with traced_span("bedrock.generate_structured"):
        span = trace.get_current_span()
        span.add_event("http.retry", {"http.url": f"https://x.test/stream?token={jwt}"})
        span.add_event("auth.rejected", {"http.request.header.authorization": f"Bearer {jwt}"})
        span.add_event(f"upstream refused Bearer {jwt}", {"attempt": 2})

    (exported,) = exporter.get_finished_spans()
    assert dict(exported.attributes or {}) == {}, (
        "the span must carry no dirty attributes, or the early-return case is not covered"
    )
    events = list(exported.events)
    assert len(events) == 3, "the events must survive the rebuild, not just be scrubbed away"
    rendered = repr([(event.name, dict(event.attributes or {})) for event in events])
    assert jwt not in rendered
    assert "eyJ" not in rendered
    assert "token=REDACTED" in rendered
    assert "Bearer REDACTED" in rendered
    # The event's own name is user-controlled text too, and it is exported.
    assert events[2].name == "upstream refused Bearer REDACTED"
    # The rest of each event must survive, or the trace stops being useful.
    assert [event.name for event in events[:2]] == ["http.retry", "auth.rejected"]
    assert events[2].attributes is not None
    assert events[2].attributes["attempt"] == 2


def test_a_recorded_exception_message_is_redacted() -> None:
    """The shape the register nominates as the likely one: `Span.record_exception` writes the
    message *and* the formatted stacktrace into an event, and an upstream 401 tends to quote
    the credential it rejected. Driven through `record_exception` rather than `add_event`
    because that is the API that puts an arbitrary upstream string into a span.
    """
    exporter = _install_test_provider()
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJwYXJlbnQtZXh0LTIifQ.other-sig"

    with traced_span("gateway.invoke"):
        trace.get_current_span().record_exception(RuntimeError(f"401 from Bearer {jwt}"))

    (exported,) = exporter.get_finished_spans()
    (event,) = list(exported.events)
    assert event.name == "exception"
    assert event.attributes is not None
    rendered = repr(dict(event.attributes))
    assert jwt not in rendered
    assert "eyJ" not in rendered
    assert "Bearer REDACTED" in rendered
    # `exception.type` is not a credential and must still identify the failure.
    assert event.attributes["exception.type"] == "RuntimeError"


def test_event_redaction_preserves_name_timestamp_and_ordinary_attributes() -> None:
    """The negative arm for events, and the one that keeps the rebuild honest: an `Event` is
    immutable, so a redacted event is a *new* object, and everything about it other than the
    credential has to be carried across by hand.
    """

    def record(tracer: Tracer) -> None:
        with tracer.start_as_current_span("db.query") as span:
            span.add_event("statement", {"table": "mastery", "sql": "SELECT id FROM users"})
            span.add_event("leaked", {"url": "https://x.test/s?token=abc123"})

    raw = _raw_span(record)
    redacted = RedactingSpanExporter._redacted(raw)

    assert [event.name for event in redacted.events] == ["statement", "leaked"]
    assert [event.timestamp for event in redacted.events] == [e.timestamp for e in raw.events]
    clean, dirty = list(redacted.events)
    assert clean.attributes is not None and dirty.attributes is not None
    assert dict(clean.attributes) == {"table": "mastery", "sql": "SELECT id FROM users"}
    assert dirty.attributes["url"] == "https://x.test/s?token=REDACTED"
    # Everything the span carries besides events is unchanged by an events-only rebuild.
    assert redacted.name == raw.name
    assert redacted.start_time == raw.start_time
    assert redacted.end_time == raw.end_time
    assert redacted.get_span_context() == raw.get_span_context()


def test_a_span_with_nothing_to_redact_is_not_rebuilt() -> None:
    """The cost guard. `_redacted` short-circuits when nothing matched so the exporter does
    not rebuild every span it sees; widening it to events must widen that fast path too,
    rather than making every clean span pay for a copy.
    """

    def record(tracer: Tracer) -> None:
        with tracer.start_as_current_span("db.query", attributes={"table": "mastery"}) as span:
            span.add_event("statement", {"sql": "SELECT id FROM users"})

    raw = _raw_span(record)
    assert RedactingSpanExporter._redacted(raw) is raw


def test_both_exporter_branches_are_wrapped_in_the_redactor() -> None:
    """The events fix lives in `RedactingSpanExporter`, so it reaches production only for as
    long as the *production* branch still goes through it. Every other redaction test here
    drives the `span_exporter` branch, which is precisely the branch that cannot notice the
    day the OTLP one stops being wrapped - the failure `build_tracer_provider`'s docstring
    already names, asserted rather than only described.
    """
    for provider in (
        build_tracer_provider(service_name="test-service", span_exporter=InMemorySpanExporter()),
        build_tracer_provider(service_name="test-service", otlp_endpoint="http://localhost:4318"),
    ):
        (processor,) = provider._active_span_processor._span_processors
        assert isinstance(getattr(processor, "span_exporter", None), RedactingSpanExporter)
        provider.shutdown()


def test_uppercase_bearer_credentials_are_redacted_before_export() -> None:
    """E6.1 F-2 (D-458): the pattern named `[Bb]earer` only, so `BEARER abc123XYZ` - an
    opaque token, so the JWT pattern cannot catch it either - was exported verbatim. HTTP
    auth schemes are case-insensitive by RFC 7235, so the uppercased form is the same
    credential, not a different one.
    """
    exporter = _install_test_provider()

    with traced_span("http.client", authorization="BEARER abc123XYZ"):
        pass

    (span,) = exporter.get_finished_spans()
    assert span.attributes is not None
    assert span.attributes["authorization"] == "BEARER REDACTED"


def test_refresh_and_id_token_query_parameters_are_redacted_before_export() -> None:
    """E6.1 F-2's other half: the span redactor's query-parameter alternation named
    `token|access_token|api_key` while the *log* denylist
    (`_DENYLISTED_LOG_KEYS`) already listed `refresh_token` and `id_token` as keys. Two
    credential vocabularies drifting apart is the finding; a JWT-valued parameter was still
    caught by the JWT pattern, an opaque-valued one was not.
    """
    exporter = _install_test_provider()

    with traced_span(
        "auth.exchange",
        refresh="https://idp.example/t?refresh_token=abc123XYZ",
        identity="https://idp.example/t?id_token=abc123XYZ",
        oauth="https://idp.example/t?oauth_token=abc123XYZ",
    ):
        pass

    (span,) = exporter.get_finished_spans()
    assert span.attributes is not None
    assert span.attributes["refresh"] == "https://idp.example/t?refresh_token=REDACTED"
    assert span.attributes["identity"] == "https://idp.example/t?id_token=REDACTED"
    assert span.attributes["oauth"] == "https://idp.example/t?oauth_token=REDACTED"


def test_the_span_credential_vocabulary_covers_the_log_denylist_credential_keys() -> None:
    """The reconciliation itself, asserted rather than left to the comment: every
    credential-shaped key the log denylist filters is also a parameter name the span
    redactor strips. This is the test that fails the next time one list grows and the
    other does not - which is exactly how F-2 happened.
    """
    from intellichoice_observability.logging_config import _DENYLISTED_LOG_KEYS
    from intellichoice_observability.tracing import _CREDENTIAL_QUERY_PARAMS

    credential_keys = {key for key in _DENYLISTED_LOG_KEYS if key.endswith(("token", "api_key"))}
    assert credential_keys, "vacuous: the log denylist named no credential key"
    missing = sorted(credential_keys - set(_CREDENTIAL_QUERY_PARAMS))
    assert not missing, f"span redactor does not name these log-denylisted credentials: {missing}"


def test_clean_operational_attributes_survive_the_widened_credential_patterns() -> None:
    """The false-positive arm of F-2. Widening an alternation is only safe if the span
    content the store exists for still arrives intact.
    """
    exporter = _install_test_provider()

    with traced_span(
        "db.query",
        statement="SELECT id FROM mastery WHERE student_external_id = :sid",
        route="/learning/sessions/{session_id}/answer",
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        token_count="1287",
        prose="refresh_token and id_token are rotated nightly",
    ):
        pass

    (span,) = exporter.get_finished_spans()
    assert span.attributes is not None
    assert span.attributes["statement"] == "SELECT id FROM mastery WHERE student_external_id = :sid"
    assert span.attributes["route"] == "/learning/sessions/{session_id}/answer"
    assert span.attributes["model_id"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert span.attributes["token_count"] == "1287"
    # No `?`/`&` context, so these are parameter *names* in prose, not a credential.
    assert span.attributes["prose"] == "refresh_token and id_token are rotated nightly"
