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

Each line also carries the session id from its path, when it has one - `LOGGABLE_PATH_PARAMS`,
an allowlist. Without it two lines could not be recognised as belonging to one student's
sitting, which is the specific reason D-288's "next step is server-side logs for that session"
could not be taken.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("intellichoice.access")

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


def install_request_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
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
        # Read after `call_next`, which is the only point at which routing has happened and
        # `path_params` is populated. Flat keys, because `PiiDenylistFilter` only inspects
        # top-level `extra` keys (its own documented limit) - a nested dict would travel
        # unexamined.
        params = request.scope.get("path_params") or {}
        session_ids = {
            name: params[name] for name in LOGGABLE_PATH_PARAMS if params.get(name) is not None
        }
        logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                **session_ids,
            },
        )
        return response
