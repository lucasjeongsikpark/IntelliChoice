"""Regression tests for two independent real bugs found via this session's own live
verification against Jaeger (see D-081 / `tracing.configure_tracing_provider`'s and
`tracing.instrument_sqlalchemy_engines`'s docstrings):

1. `FastAPIInstrumentor` only takes effect for app instances constructed *after* it
   runs - `learning_api.main`/`chat_api.main` originally called it from inside
   `lifespan`, which is too late (the "lifespan" ASGI scope is itself the first call
   that caches Starlette's middleware stack). The first two tests below encode this
   ordering contract directly so a future change that moves instrumentation back into
   `lifespan` fails loudly instead of silently dropping spans.
2. `SQLAlchemyInstrumentor` is a process-wide singleton - calling `.instrument(engine=
   ...)` once per engine (instead of once with `engines=[...]`) silently drops every
   engine after the first. The last two tests below encode that contract, mirroring the
   same "document the footgun, not just the fix" structure as the FastAPI pair.
"""

import intellichoice_observability.tracing as tracing_module
from fastapi import FastAPI
from fastapi.testclient import TestClient
from intellichoice_observability.tracing import build_tracer_provider, traced_span
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import create_engine, text


def _install_test_provider() -> tuple[InMemorySpanExporter, TracerProvider]:
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)
    tracing_module._tracer = provider.get_tracer("intellichoice")
    return exporter, provider


def test_instrumenting_before_app_construction_wraps_every_real_request() -> None:
    """The correct pattern (`main.py`'s current shape): instrument, *then* build the
    `FastAPI()` instance and let it serve its first ASGI call (lifespan startup,
    triggered here by `with TestClient(app)`)."""
    exporter, provider = _install_test_provider()

    app = FastAPI()
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    @app.get("/hello")
    async def hello() -> dict:
        with traced_span("manual.child"):
            pass
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/hello")
    assert response.status_code == 200

    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}
    assert "manual.child" in names
    assert "GET /hello" in names

    fastapi_root = next(s for s in spans if s.name == "GET /hello")
    manual_child = next(s for s in spans if s.name == "manual.child")
    assert fastapi_root.context is not None
    assert manual_child.context is not None
    assert fastapi_root.context.trace_id == manual_child.context.trace_id
    FastAPIInstrumentor.uninstrument_app(app)


def test_instrumenting_after_the_first_asgi_call_silently_drops_fastapi_spans() -> None:
    """The bug this session found and fixed: instrumenting from inside `lifespan` (i.e.
    after the app has already handled the `"lifespan"` startup scope, which is itself
    the first ASGI call and is what caches Starlette's middleware stack) never wraps any
    subsequent real request. This test exists to document the footgun, not to endorse
    the pattern - `main.py` must never instrument inside `lifespan`.
    """
    exporter, provider = _install_test_provider()

    app = FastAPI()

    @app.get("/hello")
    async def hello() -> dict:
        return {"ok": True}

    with TestClient(app) as client:
        # The app has now handled its first ASGI call (lifespan startup) - Starlette's
        # `middleware_stack` is already built and cached, unpatched.
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        response = client.get("/hello")
    assert response.status_code == 200

    spans = exporter.get_finished_spans()
    assert "GET /hello" not in {s.name for s in spans}
    FastAPIInstrumentor.uninstrument_app(app)


def test_instrumenting_multiple_engines_in_one_call_traces_all_of_them() -> None:
    """The correct pattern (`tracing.instrument_sqlalchemy_engines`'s shape): pass every
    engine that needs tracing to a single `.instrument(engines=[...])` call."""
    exporter, provider = _install_test_provider()
    engine_a = create_engine("sqlite:///:memory:")
    engine_b = create_engine("sqlite:///:memory:")
    try:
        SQLAlchemyInstrumentor().instrument(engines=[engine_a, engine_b], tracer_provider=provider)
        with engine_a.connect() as conn:
            conn.execute(text("SELECT 1"))
        with engine_b.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Each instrumented engine produces a generic "connect" span plus a query span
        # named after the operation (`db.statement` holds the actual SQL) - only the
        # query spans distinguish a *traced* engine from an untraced one, so that's what
        # this test (and its footgun-documenting sibling below) counts.
        query_spans = [s for s in exporter.get_finished_spans() if s.name == "SELECT :memory:"]
        assert len(query_spans) == 2
    finally:
        SQLAlchemyInstrumentor().uninstrument()


def test_instrumenting_a_second_engine_via_a_separate_call_silently_drops_its_spans() -> None:
    """The bug this session found and fixed: `SQLAlchemyInstrumentor` is a process-wide
    singleton (`BaseInstrumentor.instrument()` guards `_instrument()` behind an
    `_is_instrumented_by_opentelemetry` flag), so a *second*, separate `.instrument(
    engine=...)` call for a second engine never runs `_instrument()` again - that
    engine's spans are silently dropped. This test exists to document the footgun, not
    to endorse the pattern - callers must always use `instrument_sqlalchemy_engines`'s
    single combined `engines=[...]` call instead.
    """
    exporter, provider = _install_test_provider()
    engine_a = create_engine("sqlite:///:memory:")
    engine_b = create_engine("sqlite:///:memory:")
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine_a, tracer_provider=provider)
        SQLAlchemyInstrumentor().instrument(engine=engine_b, tracer_provider=provider)
        with engine_a.connect() as conn:
            conn.execute(text("SELECT 1"))
        with engine_b.connect() as conn:
            conn.execute(text("SELECT 1"))

        # engine_b's `.connect()` still gets a generic "connect" span (that wrap is a
        # global monkeypatch applied on the *first* `_instrument()` call), but its query
        # never does - the second `.instrument()` call was a no-op, so no `EngineTracer`
        # was ever attached to engine_b to emit one. Only engine_a's query is traced.
        query_spans = [s for s in exporter.get_finished_spans() if s.name == "SELECT :memory:"]
        assert len(query_spans) == 1
    finally:
        SQLAlchemyInstrumentor().uninstrument()
