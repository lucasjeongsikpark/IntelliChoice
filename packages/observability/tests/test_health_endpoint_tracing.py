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

**The `excluded_urls` half was shipped alone first and made the problem worse**, which is
why `test_readyz_emits_no_spans_at_all` below asserts on the *total span count* rather
than on the absence of a server span. Measured on staging: trace volume went **up 3.4x**
(320 -> 1,095 per idle 10 minutes). Dropping a server span does not drop its children, it
**orphans** them - each `SELECT 1` from the two health pings became its own root segment,
so one trace became two, and the new ones carried no HTTP URL to attribute them by. The
original version of this file asserted only `"GET /readyz" not in names` and passed
cleanly against exactly that regression. **An assertion that names the mechanism you fixed
cannot see a mechanism you did not think of; count the output instead.**
"""

import asyncio

import intellichoice_observability.tracing as tracing_module
from fastapi import FastAPI
from fastapi.testclient import TestClient
from intellichoice_observability.tracing import (
    build_tracer_provider,
    instrument_fastapi_app,
)
from intellichoice_shared.db_ready import ping_engine
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.utils import suppress_instrumentation
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine


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


def test_readyz_emits_no_spans_at_all_including_its_database_pings() -> None:
    """The regression the first version of this file could not see.

    `/readyz` pings two engines. With only `excluded_urls`, the server span disappears and
    the two `SELECT 1` spans become *root* segments - more traces than before, none of
    them attributable to a route. So this counts every span the exporter received during
    the health check and requires it to be zero, then proves the same instrumented engine
    does emit spans for a real route, so "zero" cannot be an inert exporter.
    """
    exporter, provider = _install_test_provider()

    engine = create_engine("sqlite:///:memory:")
    app = FastAPI()
    instrument_fastapi_app(app, provider)

    @app.get("/readyz")
    async def readyz() -> dict:
        # The real handler's shape: a DB round-trip inside the health endpoint. Uses the
        # sync engine because `ping_engine` takes an AsyncEngine and the suppression
        # being tested is `ping_engine`'s, exercised directly below.
        with suppress_instrumentation():
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/learning/sessions")
    async def real_route() -> dict:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}

    try:
        SQLAlchemyInstrumentor().instrument(engines=[engine], tracer_provider=provider)

        with TestClient(app) as client:
            assert client.get("/readyz").status_code == 200

        # The whole assertion: nothing at all, not merely "no server span".
        assert exporter.get_finished_spans() == ()

        with TestClient(app) as client:
            assert client.get("/learning/sessions").status_code == 200

        # The positive arm: the same engine and the same provider do produce spans, so the
        # zero above measured suppression and not a dead exporter.
        after = exporter.get_finished_spans()
        assert any(s.name == "GET /learning/sessions" for s in after)
        assert any("SELECT" in s.name for s in after)
    finally:
        SQLAlchemyInstrumentor().uninstrument()
        FastAPIInstrumentor.uninstrument_app(app)


def test_ping_engine_itself_emits_no_spans() -> None:
    """`ping_engine` is the shared helper both apps' `/readyz` calls, so the suppression
    belongs to it rather than to each handler. Asserted against a real instrumented async
    engine, because the suppression has to take effect in the task that actually runs the
    query - `ping_engine` wraps its query in `asyncio.wait_for`, and a suppression attached
    to the calling context instead of the executing one would pass a mock and fail live.

    Driven by `asyncio.run` from a sync test because this repo has no async tests and no
    `pytest-asyncio`; adding a plugin to assert one thing is a worse trade than one
    `asyncio.run`.
    """
    exporter, provider = _install_test_provider()

    async def scenario() -> tuple[bool, int, int]:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            SQLAlchemyInstrumentor().instrument(
                engines=[engine.sync_engine], tracer_provider=provider
            )
            ok = await ping_engine(engine)
            during_health_check = len(exporter.get_finished_spans())

            # Positive arm: the same engine, same provider, not suppressed - so a zero
            # above measured suppression rather than an inert exporter or a dead engine.
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            after_real_query = len(exporter.get_finished_spans())
            return ok, during_health_check, after_real_query
        finally:
            SQLAlchemyInstrumentor().uninstrument()
            await engine.dispose()

    ok, during_health_check, after_real_query = asyncio.run(scenario())
    assert ok is True
    assert during_health_check == 0
    assert after_real_query > 0


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
