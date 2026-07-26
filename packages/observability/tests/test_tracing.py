import intellichoice_observability.tracing as tracing_module
from intellichoice_observability.tracing import build_tracer_provider, traced_span
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


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
