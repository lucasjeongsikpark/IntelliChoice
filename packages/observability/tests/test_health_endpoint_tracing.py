"""AUD-F-30: the health endpoints must not be traced, and a real route must still be.

Both halves matter. An exclusion list that silently swallowed everything would pass a
test that only asserts `/readyz` produced no span, and "no traces at all" is the failure
mode that made AUD-F-12 possible - an empty trace store certifying an hour of traffic as
PII-clean. So the negative and the positive assertions live in the same test.

Why this is worth a test rather than a comment: ~97% of every trace this project has
scanned was `GET /readyz` (2,394 in an idle hour), which put recorded traces ~17x over
X-Ray's free tier and diluted criterion 9's denominator. If a future refactor drops the
`excluded_urls` argument, nothing else in the suite notices - the app keeps working and
the bill and the corpus quietly go back to being 97% health checks.
"""

import intellichoice_observability.tracing as tracing_module
from fastapi import FastAPI
from fastapi.testclient import TestClient
from intellichoice_observability.tracing import (
    build_tracer_provider,
    instrument_fastapi_app,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _install_test_provider() -> tuple[InMemorySpanExporter, TracerProvider]:
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)
    tracing_module._tracer = provider.get_tracer("intellichoice")
    return exporter, provider


def test_health_endpoints_are_not_traced_but_real_routes_are() -> None:
    exporter, provider = _install_test_provider()

    app = FastAPI()
    # Via the project's own helper, not FastAPIInstrumentor directly - the exclusion is
    # part of how this project instruments an app, so the test has to exercise that seam
    # or it proves only that OTel's own feature works.
    instrument_fastapi_app(app, provider)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict:
        return {"status": "ready"}

    @app.get("/learning/sessions")
    async def real_route() -> dict:
        return {"ok": True}

    try:
        with TestClient(app) as client:
            assert client.get("/healthz").status_code == 200
            assert client.get("/readyz").status_code == 200
            assert client.get("/learning/sessions").status_code == 200

        names = {span.name for span in exporter.get_finished_spans()}
        assert "GET /healthz" not in names
        assert "GET /readyz" not in names
        # The positive half: instrumentation is still on and still wrapping real traffic.
        assert "GET /learning/sessions" in names
    finally:
        FastAPIInstrumentor.uninstrument_app(app)


def test_the_exclusion_list_names_both_health_endpoints() -> None:
    """A cheap guard on the constant itself.

    The regexes are matched against the request path as substrings, so this asserts the
    two endpoint names are present rather than pattern-matching anything - if someone
    trims the list to just `readyz`, the ALB's own check is still excluded but
    `/healthz` (which AUD-F-16 put the build identity on) silently returns to the corpus.
    """
    assert "healthz" in tracing_module.HEALTH_ENDPOINT_URLS
    assert "readyz" in tracing_module.HEALTH_ENDPOINT_URLS
    # /metrics is deliberately still traced - see the constant's comment.
    assert "metrics" not in tracing_module.HEALTH_ENDPOINT_URLS
