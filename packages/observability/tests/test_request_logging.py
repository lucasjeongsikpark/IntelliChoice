import io
import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
from intellichoice_observability.logging_config import JsonLogFormatter, PiiDenylistFilter
from intellichoice_observability.request_logging import install_request_logging_middleware


def test_access_log_never_includes_the_query_string() -> None:
    """Regression gate for D-032: an SSE `?token=...` bearer value must never appear in
    an access log line, since the browser's `EventSource` client puts it there instead
    of an `Authorization` header."""
    stream = io.StringIO()
    logger = logging.getLogger("intellichoice.access")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(PiiDenylistFilter())
    logger.handlers = [handler]

    app = FastAPI()
    install_request_logging_middleware(app)

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
