"""SPEC §5.32.3 JSON access log - also resolves the standing D-032 caveat (the SSE
`?token=` bearer value ending up in access logs, since the browser's `EventSource`
can't set an `Authorization` header). This middleware logs the route *template* plus
method/status/duration only - it never touches `request.url` or the raw query string, so
a token can't leak through it by construction, not by a best-effort redaction regex.
`configure_logging` (`logging_config.py`) disables uvicorn's own plain-text access
logger, which does log the full raw path+query, so there is no other line from any
logger that could still leak one.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("intellichoice.access")


def install_request_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path
        logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
