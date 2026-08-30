"""SPEC §5.32.3 JSON access log - also resolves the standing D-032 caveat (the SSE
`?token=` bearer value ending up in access logs, since the browser's `EventSource`
can't set an `Authorization` header). This middleware logs the route *template* plus
method/status/duration only - it never touches `request.url` or the raw query string, so
a token can't leak through it by construction, not by a best-effort redaction regex.
`configure_logging` (`logging_config.py`) disables uvicorn's own plain-text access
logger, which does log the full raw path+query, so there is no other line from any
logger that could still leak one.

The "never touches `request.url`" sentence above is now true of every branch. It was not:
until D-316 an unmatched route fell back to `request.url.path`, which is the path **every
CORS preflight** takes (`CORSMiddleware` answers `OPTIONS` before routing sets
`scope["route"]`). See `UNMATCHED_PATH`.

Since SILENT-500S this module writes a **second** line, and only on the unhandled-exception
path: a `level=ERROR` `unhandled_exception` record carrying the exception type and its redacted
traceback. See `_log_unhandled_exception` for why it lives here rather than in a middleware or
an `Exception` handler of its own.

Each line also carries the session id from its path, when it has one - `LOGGABLE_PATH_PARAMS`,
an allowlist. Without it two lines could not be recognised as belonging to one student's
sitting, which is the specific reason D-288's "next step is server-side logs for that session"
could not be taken.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

ACCESS_LOGGER_NAME = "intellichoice.access"
# **A separate logger, at ERROR, for the one line that is not an access line (SILENT-500S).**
# See `_log_unhandled_exception`.
ERROR_LOGGER_NAME = "intellichoice.errors"

logger = logging.getLogger(ACCESS_LOGGER_NAME)
error_logger = logging.getLogger(ERROR_LOGGER_NAME)

# **An allowlist, never `path_params` wholesale.** A blanket dump would log whatever route
# param someone adds next - `/students/{student_id}` already exists - and this module's
# guarantee is that nothing sensitive can reach a log line *by construction* rather than by
# vigilance. Both names below are ids this system mints for a session, not references to a
# person: `student_id` and `assessment_item_id` are deliberately absent, the first because it
# is a stable reference to a real minor and the second because nothing needs it.
#
# Why this exists at all: until now a log line named the route template and nothing else, so
# **two lines could not be recognised as belonging to the same session.** `trace_id` joins the
# requests of one *request*, not of one student's sitting. That is the specific reason D-288
# (a staging-only mid-exam refresh landing on the wrong question) sat at "the next step is
# server-side logs for that session" - the logs could not isolate one session, so the step was
# impossible rather than merely undone.
LOGGABLE_PATH_PARAMS = ("learning_session_id", "chat_session_id")

# What `path` says when no route matched - a CORS preflight, or a genuine 404. A fixed token so
# the store keeps bounded cardinality and so these lines can be counted rather than only read.
UNMATCHED_PATH = "<unmatched>"


def _route_and_session_ids(request: Request) -> tuple[str, dict[str, str]]:
    """The route template and the allowlisted session ids, for both lines this module writes.

    Shared rather than duplicated because both halves are guarantees - the template instead of
    the raw path, and the allowlist instead of `path_params` wholesale - and a second copy is a
    second place for either to drift. `_log_unhandled_exception` is the second caller.
    """
    # **`UNMATCHED_PATH` rather than `request.url.path`, and that replaced a fallback this
    # module's own docstring said did not exist.** The docstring promised the middleware
    # "never touches `request.url`"; the fallback branch did, on every request that
    # reaches no route - which is not a rare error case but **every CORS preflight**,
    # since `CORSMiddleware` answers `OPTIONS` before routing and `scope["route"]` is
    # therefore never set. Measured in one local session: 23 lines, all `OPTIONS`, each
    # carrying a raw `/learning/students/student-ext-N/...` path.
    #
    # Not a rule-1 violation - an `*_external_id` is the reference Postgres stores by
    # design (SPEC §5.30), not PII - and the token claim did survive, because `.path`
    # drops the query string. But the guarantee was "by construction", and a branch the
    # docstring denies is not a guarantee. Two further costs: the same endpoint logged one
    # way as `GET` and another as `OPTIONS` cannot be grouped by `path`, and the raw form
    # is unbounded cardinality in a store queried by exactly that field.
    #
    # Nothing is lost that the system does not already hold: the ALB and CloudFront access
    # logs record raw paths at the edge, which is where an unmatched-route question belongs
    # anyway.
    route = request.scope.get("route")
    path = route.path if route is not None else UNMATCHED_PATH
    # Read once routing has happened, which is what populates `path_params`. On the 500 path
    # that is still true when the endpoint itself raised; an exception from *below* routing
    # leaves both unset and falls back to `UNMATCHED_PATH`, which is the honest answer rather
    # than a guess. Flat keys, because `PiiDenylistFilter` only inspects top-level `extra` keys
    # (its own documented limit) - a nested dict would travel unexamined.
    params = request.scope.get("path_params") or {}
    session_ids = {
        name: params[name] for name in LOGGABLE_PATH_PARAMS if params.get(name) is not None
    }
    return path, session_ids


def _log(request: Request, *, status_code: int, start: float) -> None:
    """One line, from either the success path or the 500 path.

    Shared rather than duplicated because everything below is a guarantee - the route template
    instead of the raw path, the session-id allowlist - and a second copy is a second place for
    those to drift. A 500 is the line most worth tying to one student's sitting, so it gets the
    same treatment as any other rather than a reduced one.
    """
    duration_ms = (time.monotonic() - start) * 1000
    path, session_ids = _route_and_session_ids(request)
    logger.info(
        "http_request",
        extra={
            "method": request.method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            **session_ids,
        },
    )


def _log_unhandled_exception(request: Request, exc: BaseException) -> None:
    """SILENT-500S: the JSON `level=ERROR` line an unhandled 500 did not have.

    **D-393 fixed the visible half and left this one.** After it, an unhandled exception
    produces an access line, a `trace_id` and a `status="500"` counter increment - and the
    access line is `logger.info`. So the only structured record of the worst class of failure
    this system has carried `"level": "INFO"`: invisible to every `{ $.level = "ERROR" }`
    metric filter and log alarm, and invisible to the D-454 sweep method, which reads ERROR
    lines. Staging emitted **114 `asyncpg.InvalidPasswordError` tracebacks** during the
    2026-08-29 rotation incident (D-455) while every monitor read quiet.

    The exception itself was worse off than its severity. `status_code: 500` says a request
    failed and cannot say *what* failed; the type and the traceback existed only in uvicorn's
    plain-text ASGI traceback - unparseable prose, in the same log group, arriving as one
    CloudWatch event per line because the awslogs driver splits on newlines.

    **Emitted from the `except Exception` block above rather than from a second middleware or
    an `Exception` handler**, for three reasons, in order of weight:

    - *One catch, one wiring point.* Both apps already call
      `install_request_logging_middleware`, so an app cannot be wired for the access line and
      miss the error line. A separate installer is a second call site to forget, and the
      forgetting is silent.
    - *Same route discipline.* `_route_and_session_ids` is shared, so the template-not-raw-path
      guarantee (D-316) and the session-id allowlist hold on this line by construction rather
      than by a second correct copy.
    - *`app.add_exception_handler(Exception, ...)` would change behaviour.* Starlette hands
      that handler to `ServerErrorMiddleware`, which then builds the 500 response *from it* -
      so registering one to get a log line quietly replaces the error response both apps
      currently return. Logging here leaves the response Starlette's own.

    Nothing about the exception's semantics changes: the caller re-raises, so the 500 is still
    produced by `ServerErrorMiddleware` and uvicorn still writes its plain-text traceback. This
    is an addition to the JSON stream, not a replacement for anything.

    **`exc_info=exc`, and the redaction that makes it safe is `JsonLogFormatter`'s.** `exc_info`
    is a standard `LogRecord` attribute, so `PiiDenylistFilter` never inspects it; the formatter
    runs `redact_free_text` over the formatted traceback instead (D-394, written for exactly
    this hazard - a Pydantic `ValidationError` embeds the offending input, which on a
    structured-output repair failure is model output derived from a student's question). That
    redactor is a floor, not a guarantee (SPEC §5.30.1); the guarantee is that it is applied.

    `exception_type` is the class name only. The `str(exc)` is deliberately *not* a field: it is
    unbounded free text in a value an operator groups by, which is the D-394 `event` mistake,
    and it is already inside the redacted `exc_info`.
    """
    path, session_ids = _route_and_session_ids(request)
    error_logger.error(
        "unhandled_exception",
        exc_info=exc,
        extra={
            "method": request.method,
            "path": path,
            "status_code": 500,
            "exception_type": type(exc).__name__,
            **session_ids,
        },
    )


def install_request_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.monotonic()
        # **D-393: `except Exception`, not a bare await and not a `finally`.** Starlette's
        # `ServerErrorMiddleware` is installed above every `@app.middleware("http")` and turns
        # an unhandled exception into a 500 *before* this middleware could see a response - so
        # with a bare `response = await call_next(...)` the worst class of failure produced no
        # access line at all, and therefore no `trace_id` either, since the formatter injects
        # that per line. Only the ALB knew a 500 had happened.
        #
        # `finally` would be the shorter spelling and the wrong one: a `CancelledError` reaching
        # this frame means the request was abandoned before any response began (client gone
        # before headers, or shutdown), and recording those as 500s would invent failures on
        # `/stream` - the endpoint students hold open the longest - indistinguishable from the
        # real ones this exists to surface. `CancelledError` derives from `BaseException`, so
        # `except Exception` lets it past untouched.
        try:
            response = await call_next(request)
        except Exception as exc:
            # Two lines, deliberately, and in this order. The access line is the request's
            # record (method, path, duration, session id) and stays `INFO` so every existing
            # `http_request` query keeps returning the same rows; the error line is the
            # *failure's* record and is the one an ERROR filter can see (SILENT-500S).
            _log(request, status_code=500, start=start)
            _log_unhandled_exception(request, exc)
            raise
        _log(request, status_code=response.status_code, start=start)
        return response
