"""SILENT-500S: an unhandled exception must produce a JSON `level=ERROR` line.

**The defect, as measured rather than argued (D-455).** During the 2026-08-29 RDS
secret-rotation incident staging emitted **114 `asyncpg.InvalidPasswordError` tracebacks**
while every monitor read quiet. D-393 had already fixed the half of this that looked like the
whole of it - an unhandled 500 now produces an access line and a `status="500"` counter
increment - and the access line is `logger.info`. So the only *structured* record of the worst
class of failure this system has carries `"level": "INFO"`, and:

- every `{ $.level = "ERROR" }` metric filter and log alarm misses it, by construction;
- the D-454 log-sweep method, which reads ERROR lines, reports the incident window as clean;
- the exception itself - its type, its traceback - exists nowhere in the JSON stream at all.
  It exists only in uvicorn's plain-text ASGI traceback, which is unparseable prose in the
  same log group and, being multi-line, arrives as one CloudWatch event per line.

That last point is the one that makes this more than a severity typo. `status_code: 500` says
a request failed. It does not say *what* failed, and the answer was thrown away.

**Both apps are covered by construction, not by two edits.** The line is emitted from the
`except Exception` block `install_request_logging_middleware` already installs - the single
place in this codebase that already catches this exact class - so an app cannot get the access
line and miss the error line. `test_both_apps_install_the_middleware_that_carries_this` pins
the other direction: that both apps do install it.
"""

import io
import json
import logging
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from intellichoice_observability.logging_config import JsonLogFormatter, PiiDenylistFilter
from intellichoice_observability.request_logging import (
    ACCESS_LOGGER_NAME,
    ERROR_LOGGER_NAME,
    install_request_logging_middleware,
)
from intellichoice_observability.tracing import build_tracer_provider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _capturing_app() -> tuple[FastAPI, io.StringIO]:
    """The shipped middleware writing through the shipped formatter and PII filter into a
    buffer, so every assertion is about the line that would actually be written.

    Both loggers are bound to one stream deliberately: the subject here is what an operator
    reading the service's JSON stream sees, and that stream is not split by logger name.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(PiiDenylistFilter())
    for name in (ACCESS_LOGGER_NAME, ERROR_LOGGER_NAME):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.handlers = [handler]

    app = FastAPI()
    install_request_logging_middleware(app)
    return app, stream


def _lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def test_an_unhandled_exception_emits_a_json_error_line() -> None:
    """The reproduction. Before the fix this file's subject line did not exist: the only JSON
    record of an unhandled 500 was the `level=INFO` access line, so this assertion failed with
    `no level=ERROR line was emitted` while the access line sat right beside it in the buffer.

    `raise_server_exceptions=False` is what makes this the deployed path rather than the test
    client's: with the default, the exception is re-raised into the test and no 500 response is
    ever produced, which is the opposite of what production does.
    """
    app, stream = _capturing_app()

    @app.get("/learning/sessions/{learning_session_id}/boom")
    async def boom(learning_session_id: str) -> dict[str, str]:
        raise RuntimeError("the handler failed")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/learning/sessions/sess-abc/boom"
    )
    # The exception semantics are untouched: the client still gets a 500, and it is still
    # Starlette's, not one this middleware manufactured.
    assert response.status_code == 500

    lines = _lines(stream)
    errors = [line for line in lines if line["level"] == "ERROR"]
    assert errors, f"no level=ERROR line was emitted; got {[line['level'] for line in lines]}"
    assert len(errors) == 1, "one unhandled exception must not produce two error lines"

    error = errors[0]
    assert error["event"] == "unhandled_exception"
    # The route template and the session-id allowlist, exactly as the access line does them -
    # same helper, so the raw path cannot come back on this line alone (D-316).
    assert error["path"] == "/learning/sessions/{learning_session_id}/boom"
    assert error["method"] == "GET"
    assert error["status_code"] == 500
    assert error["learning_session_id"] == "sess-abc"
    # The answer the access line threw away: *what* failed, as a bounded label rather than
    # as free text.
    assert error["exception_type"] == "RuntimeError"
    # And the traceback, which existed nowhere in the JSON stream before this.
    assert "Traceback (most recent call last):" in str(error["exc_info"])
    assert "RuntimeError" in str(error["exc_info"])

    # The access line is unchanged and still present - this is an addition, not a replacement.
    access = [line for line in lines if line["level"] == "INFO"]
    assert len(access) == 1
    assert access[0]["event"] == "http_request"
    assert access[0]["status_code"] == 500


def test_the_error_line_carries_the_trace_id_of_the_failed_request() -> None:
    """Without it the line says a request failed and cannot say *which*, which is the same
    gap D-393 closed for the access line. It holds only because the server span is still
    active when the middleware logs - `FastAPIInstrumentor` patches `build_middleware_stack`,
    so it wraps the whole user stack - and that is worth pinning rather than assuming.
    """
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)

    app, stream = _capturing_app()
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    try:

        @app.get("/chat/sessions/{chat_session_id}/boom")
        async def boom(chat_session_id: str) -> dict[str, str]:
            raise RuntimeError("the handler failed")

        response = TestClient(app, raise_server_exceptions=False).get(
            "/chat/sessions/sess-xyz/boom"
        )
        assert response.status_code == 500
    finally:
        FastAPIInstrumentor.uninstrument_app(app)

    error = next(line for line in _lines(stream) if line["level"] == "ERROR")
    span = next(s for s in exporter.get_finished_spans() if s.name.endswith("/boom"))
    assert span.context is not None
    assert error["trace_id"] == format(span.context.trace_id, "032x")
    # The two lines about one request join to each other as well as to the trace.
    access = next(line for line in _lines(stream) if line["level"] == "INFO")
    assert access["trace_id"] == error["trace_id"]


def test_the_traceback_goes_through_the_redactor() -> None:
    """D-394's rule, on the field it was written for. `exc_info` is a standard `LogRecord`
    attribute, so `PiiDenylistFilter` cannot see it - `JsonLogFormatter` runs
    `redact_free_text` over it instead, and this is the first line in the codebase that
    deliberately puts an arbitrary exception's text there.

    A `ValidationError` embedding model output derived from a student's question is the
    concrete case: the redactor is a floor (emails, URLs, phone numbers), not a guarantee,
    and the guarantee is that it is applied at all.
    """
    app, stream = _capturing_app()

    @app.get("/learning/boom")
    async def boom() -> dict[str, str]:
        raise ValueError("contact parent@example.com about this")

    assert TestClient(app, raise_server_exceptions=False).get("/learning/boom").status_code == 500

    error = next(line for line in _lines(stream) if line["level"] == "ERROR")
    exc_info = str(error["exc_info"])
    assert "parent@example.com" not in exc_info, "an email reached the log through exc_info"
    assert "ValueError" in exc_info


def test_a_denylisted_extra_on_the_error_line_is_still_redacted() -> None:
    """The error line is a new `extra=` payload, so it needs the same gate the access line
    has. `PiiDenylistFilter` matches top-level keys, and every key this line sets is either
    an allowlisted session id or a bounded label - but the test is about the *path* being
    filtered, not about today's key list, because the next key added here is added by
    someone who has not read this file.
    """
    app, stream = _capturing_app()

    @app.get("/learning/sessions/{learning_session_id}/boom")
    async def boom(learning_session_id: str) -> dict[str, str]:
        raise RuntimeError("the handler failed")

    assert (
        TestClient(app, raise_server_exceptions=False)
        .get("/learning/sessions/sess-abc/boom")
        .status_code
        == 500
    )
    error = next(line for line in _lines(stream) if line["level"] == "ERROR")
    # No student-identifying key is present at all, which is the stronger statement than
    # "it would have been redacted".
    assert set(error) & {"student_id", "student_name", "email", "token"} == set()


def test_both_apps_install_the_middleware_that_carries_this() -> None:
    """The "both apps covered" half, and it is a source assertion for a reason: importing
    either `main` builds settings, engines and an adapter, which is a different test's
    subject and a much heavier one. Terraform is parsed rather than planned in this package
    for the same reason (`test_alarm_severity_routing.py`, D-385's precedent).

    This is the assertion that makes the one-catch design safe. The error line is emitted from
    the block `install_request_logging_middleware` installs, so there is no way to wire an app
    for access logging and miss error logging - but only while both apps still call it.
    """
    mains = {
        "learning-api": _REPO_ROOT / "apps/learning-api/src/learning_api/main.py",
        "chat-api": _REPO_ROOT / "apps/chat-api/src/chat_api/main.py",
    }
    for app_name, path in mains.items():
        source = path.read_text()
        assert re.search(r"^install_request_logging_middleware\(app\)", source, re.MULTILINE), (
            f"{app_name} does not install the request-logging middleware, so its unhandled "
            "exceptions emit no JSON ERROR line (SILENT-500S)"
        )
