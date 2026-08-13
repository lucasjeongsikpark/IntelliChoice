import io
import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from intellichoice_observability.logging_config import JsonLogFormatter, PiiDenylistFilter
from intellichoice_observability.request_logging import (
    UNMATCHED_PATH,
    install_request_logging_middleware,
)


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
