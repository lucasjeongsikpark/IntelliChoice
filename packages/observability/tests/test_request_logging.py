import asyncio
import io
import json
import logging
from collections.abc import Awaitable, Callable
from typing import cast

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from intellichoice_observability.logging_config import JsonLogFormatter, PiiDenylistFilter
from intellichoice_observability.request_logging import (
    UNMATCHED_PATH,
    install_request_logging_middleware,
)
from intellichoice_observability.tracing import build_tracer_provider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _capturing_app(*, with_cors: bool = False) -> tuple[FastAPI, io.StringIO]:
    """A real app with the shipped middleware, logging through the shipped formatter and PII
    filter into a buffer - so every assertion below is about the line that would actually be
    written, not about a rehearsal of it.

    **`with_cors` installs `CORSMiddleware` before the logging middleware, which is the order
    both real apps use and is load-bearing here.** Starlette's stack is LIFO by registration,
    so whatever is installed last is outermost: with CORS added *after*, it answers the
    preflight and the logging middleware never runs, and a test asserting on the log line then
    fails against an empty buffer for a reason that has nothing to do with the subject. That is
    how the first version of the preflight test below failed - not a wrong expectation, a wrong
    app. `learning_api.main` installs CORS at module line ~272 and request logging at ~327, and
    S34's comment there records the same ordering rule after a real 429-invisibility incident.
    """
    stream = io.StringIO()
    logger = logging.getLogger("intellichoice.access")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(PiiDenylistFilter())
    logger.handlers = [handler]

    app = FastAPI()
    if with_cors:
        app.add_middleware(
            CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
        )
    install_request_logging_middleware(app)
    return app, stream


def test_access_log_never_includes_the_query_string() -> None:
    """Regression gate for D-032: an SSE `?token=...` bearer value must never appear in
    an access log line, since the browser's `EventSource` client puts it there instead
    of an `Authorization` header."""
    app, stream = _capturing_app()

    @app.get("/learning/sessions/{session_id}/stream")
    async def stream_endpoint(session_id: str) -> dict[str, str]:
        return {"session_id": session_id}

    client = TestClient(app)
    response = client.get("/learning/sessions/abc-123/stream?token=super-secret-bearer-value")
    assert response.status_code == 200

    log_output = stream.getvalue()
    assert "super-secret-bearer-value" not in log_output
    payload = json.loads(log_output)
    # Route template, not the raw path with its interpolated session id or query string.
    assert payload["path"] == "/learning/sessions/{session_id}/stream"
    assert payload["status_code"] == 200


def test_the_session_id_is_logged_so_two_lines_can_be_tied_to_one_sitting() -> None:
    """The D-288 unblock: `trace_id` joins the spans of one *request*, and there was nothing
    that joined the requests of one student's sitting - which is why that defect's recorded
    next step ("server-side logs for that session") was impossible rather than merely undone.
    """
    app, stream = _capturing_app()

    @app.get("/learning/sessions/{learning_session_id}/exam/overview")
    async def overview(learning_session_id: str) -> dict[str, str]:
        return {"id": learning_session_id}

    assert (
        TestClient(app)
        .get("/learning/sessions/7511e038-fd2a-4612-8bb1-4b9c3e1a61bb/exam/overview")
        .status_code
        == 200
    )
    payload = json.loads(stream.getvalue())
    assert payload["learning_session_id"] == "7511e038-fd2a-4612-8bb1-4b9c3e1a61bb"
    # Still the template, so this addition did not quietly reintroduce the raw path.
    assert payload["path"] == "/learning/sessions/{learning_session_id}/exam/overview"


def test_a_path_param_outside_the_allowlist_is_never_logged() -> None:
    """`student_id` is a stable reference to a real minor, and `/students/{student_id}` routes
    already exist. The middleware reads an allowlist rather than `path_params` wholesale
    precisely so the next route someone adds cannot start logging a person by accident - a
    guarantee by construction, which is the same standard the query-string test above holds
    this module to.

    Both directions in one test on purpose: that the allowed id is present is what makes the
    absence of the other one meaningful rather than vacuous.
    """
    app, stream = _capturing_app()

    @app.get("/learning/students/{student_id}/sessions/{learning_session_id}")
    async def both(student_id: str, learning_session_id: str) -> dict[str, str]:
        return {"student_id": student_id, "learning_session_id": learning_session_id}

    response = TestClient(app).get("/learning/students/student-ext-7/sessions/sess-abc")
    assert response.status_code == 200

    log_output = stream.getvalue()
    assert "student-ext-7" not in log_output
    payload = json.loads(log_output)
    assert "student_id" not in payload
    assert payload["learning_session_id"] == "sess-abc"


def test_a_cors_preflight_does_not_log_the_raw_path() -> None:
    """D-316. `CORSMiddleware` answers `OPTIONS` before routing, so `scope["route"]` is unset
    and the old fallback logged `request.url.path` verbatim - measured as 23 lines in one local
    session, every one an `OPTIONS` carrying a raw `/learning/students/student-ext-N/...`.

    Asserted through a real `CORSMiddleware`, not by faking an unrouted scope, because the
    whole point is that the *ordinary* preflight takes this branch. The route below exists and
    would match a `GET`; it is the preflight that never reaches it.
    """
    app, stream = _capturing_app(with_cors=True)

    @app.get("/learning/students/{student_id}/dashboard")
    async def dashboard(student_id: str) -> dict[str, str]:
        return {"student_id": student_id}

    response = TestClient(app).options(
        "/learning/students/student-ext-7/dashboard",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200

    log_output = stream.getvalue()
    assert "student-ext-7" not in log_output
    payload = json.loads(log_output)
    assert payload["path"] == UNMATCHED_PATH
    assert payload["method"] == "OPTIONS"


def test_an_unhandled_exception_still_produces_an_access_line() -> None:
    """D-393. The middleware did `response = await call_next(request)` with no `try`, and
    Starlette's `ServerErrorMiddleware` sits *above* every `@app.middleware("http")` and turns
    the exception into a 500 before this one can see it. So the single worst class of failure -
    an unhandled server exception - produced **no access line at all**: no method, no path, no
    status, and therefore no `trace_id`, because the formatter injects that per line and there
    was no line. Only the ALB knew a 500 had happened.

    `raise_server_exceptions=False` is what makes this a test of the deployed path rather than
    of the test client: with the default the exception is re-raised into the test and no 500
    response is ever produced, which is the opposite of what production does.

    The session id is asserted alongside, because a 500 is exactly the line someone needs to tie
    to one student's sitting (D-288), and `scope["route"]` is populated by the router *before*
    the endpoint runs - so the template and params survive the exception rather than falling
    back to `UNMATCHED_PATH`.
    """
    app, stream = _capturing_app()

    @app.get("/learning/sessions/{learning_session_id}/boom")
    async def boom(learning_session_id: str) -> dict[str, str]:
        raise RuntimeError("the handler failed")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/learning/sessions/sess-abc/boom"
    )
    assert response.status_code == 500

    log_output = stream.getvalue()
    assert log_output, "an unhandled exception produced no access line at all"
    payload = json.loads(log_output)
    assert payload["status_code"] == 500
    assert payload["method"] == "GET"
    assert payload["path"] == "/learning/sessions/{learning_session_id}/boom"
    assert payload["learning_session_id"] == "sess-abc"


def test_the_500_access_line_carries_a_trace_id() -> None:
    """The other half of D-393's finding, asserted rather than inferred.

    The audit's wording was "no JSON access line, no `trace_id`, and no
    `http_requests_total{status="500"}`" - and the `trace_id` clause is only true *because* the
    line was missing, since `JsonLogFormatter` injects it from whatever span is active. That
    made it worth checking rather than assuming: it holds only if the server span is still
    active when this middleware logs, which depends on `FastAPIInstrumentor` wrapping the whole
    middleware stack (it patches `build_middleware_stack`) and on OTel ending the span *after*
    the exception has passed back through user middleware. Both are true, and this pins them -
    a trace id on the 500 line is what turns "something failed" into "this request failed".
    """
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)

    app, stream = _capturing_app()
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    try:

        @app.get("/learning/sessions/{learning_session_id}/boom")
        async def boom(learning_session_id: str) -> dict[str, str]:
            raise RuntimeError("the handler failed")

        response = TestClient(app, raise_server_exceptions=False).get(
            "/learning/sessions/sess-abc/boom"
        )
        assert response.status_code == 500
    finally:
        FastAPIInstrumentor.uninstrument_app(app)

    payload = json.loads(stream.getvalue())
    assert payload["status_code"] == 500
    # The span the exception belongs to, not merely "some hex string".
    span = next(s for s in exporter.get_finished_spans() if s.name.endswith("/boom"))
    assert span.context is not None
    assert payload["trace_id"] == format(span.context.trace_id, "032x")


def test_a_cancelled_request_is_not_logged_as_a_server_error() -> None:
    """The other direction of D-393: the fix is `except Exception`, not a `finally` that records
    unconditionally, because a cancellation is not a server error.

    A cancellation reaching this frame means the request was abandoned before a response began -
    the client went away before headers, or the server is shutting down. Recording those as 500s
    would invent failures on `/stream`, the endpoint students hold open the longest, and the
    invented 500s would be indistinguishable from the real ones this session is making visible.

    **This is a direct call to the dispatch function, and the reason is a measurement.** The
    obvious version of this test - an endpoint that raises `asyncio.CancelledError`, driven
    through `TestClient` - proves nothing: `BaseHTTPMiddleware` converts it into a `RuntimeError`
    before this middleware sees it, so it arrives as an ordinary `Exception` and both
    implementations behave identically. Measured, after that version failed with `DID NOT RAISE`.
    A true `CancelledError` in this frame comes from the task *around* the middleware being
    cancelled, which no `TestClient` request reproduces - so the branch is exercised where it
    lives, white-box on purpose rather than through a route that cannot reach it.

    Driven by `asyncio.run` rather than declared `async def`: nothing else in this repo's 1694
    tests is an async test, so no asyncio plugin is configured, and an undriven coroutine test
    would be collected and *pass* without running a line of it.
    """
    app, stream = _capturing_app()
    # Starlette types `Middleware.kwargs` values as `object`, so the callable needs naming for
    # pyright. Spelled out rather than cast to `Any` - the signature is the contract this test
    # depends on, and writing it down means a Starlette change that alters it fails here.
    dispatch = cast(
        Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]],
        app.user_middleware[0].kwargs["dispatch"],
    )

    async def call_next(_request: Request) -> Response:
        raise asyncio.CancelledError

    async def drive() -> None:
        request = Request({"type": "http", "method": "GET", "path": "/x", "headers": []})
        await dispatch(request, call_next)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(drive())

    assert stream.getvalue() == "", "a cancelled request was recorded as a server error"


def test_a_request_with_no_session_in_its_path_logs_no_session_key() -> None:
    """Absent, not null. A `learning_session_id: null` on every `/healthz` line would be noise
    in the store that a Logs Insights filter then has to exclude - and `configure_logging`
    already omits rather than nulls its trace fields when nothing is tracing, so this follows
    the convention that module set.
    """
    app, stream = _capturing_app()

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    assert TestClient(app).get("/healthz").status_code == 200
    payload = json.loads(stream.getvalue())
    assert "learning_session_id" not in payload
    assert "chat_session_id" not in payload
