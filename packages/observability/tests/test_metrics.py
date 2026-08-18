from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from intellichoice_observability import metrics
from intellichoice_observability.request_logging import UNMATCHED_PATH


def _counter_value(counter, **labels) -> float:
    child = counter.labels(**labels) if labels else counter
    return child._value.get()  # prometheus_client's own test-friendly accessor


def test_learning_kpi_counters_increment() -> None:
    before = _counter_value(metrics.SESSION_STARTS)
    metrics.SESSION_STARTS.inc()
    assert _counter_value(metrics.SESSION_STARTS) == before + 1

    before_blocked = _counter_value(metrics.ATTENDANCE_CHECKS, result="blocked")
    metrics.ATTENDANCE_CHECKS.labels(result="blocked").inc()
    assert _counter_value(metrics.ATTENDANCE_CHECKS, result="blocked") == before_blocked + 1

    metrics.SUPPORT_USAGE.labels(support_type="hint").inc()
    metrics.TUTOR_REVIEW_FLAGGED.inc()
    metrics.QUARANTINE_COUNT.inc()
    metrics.SESSION_COST_CENTS.observe(4.2)


def test_qa_kpi_counters_increment() -> None:
    before = _counter_value(metrics.QA_ANSWERS, result="no_answer")
    metrics.QA_ANSWERS.labels(result="no_answer").inc()
    assert _counter_value(metrics.QA_ANSWERS, result="no_answer") == before + 1

    metrics.QA_CITATIONS_PER_ANSWER.observe(2)
    metrics.QA_EMAIL_ESCALATIONS.inc()
    metrics.QA_MAPS_CALLS.labels(result="success").inc()
    metrics.QA_OUT_OF_SCOPE.inc()


def test_http_middleware_records_requests_and_metrics_endpoint_exposes_them() -> None:
    app = FastAPI()
    metrics.install_http_metrics_middleware(app, service_name="test-app")

    @app.get("/widgets/{widget_id}")
    async def get_widget(widget_id: str) -> dict[str, str]:
        return {"id": widget_id}

    client = TestClient(app)
    response = client.get("/widgets/abc123")
    assert response.status_code == 200

    body, content_type = metrics.render_metrics()
    text = body.decode()
    assert "text/plain" in content_type
    # Route template, not the raw path - avoids per-widget-id cardinality explosion.
    assert 'path="/widgets/{widget_id}"' in text
    assert 'app="test-app"' in text
    assert "http_request_duration_seconds" in text


def test_an_unhandled_exception_is_counted_as_a_500() -> None:
    """D-393. `http_requests_total{status="500"}` could never be incremented by an actual
    unhandled exception: the middleware recorded only after `call_next` returned, and
    `ServerErrorMiddleware` converts the exception into a 500 response above it, so the counter
    the operator would alarm on was blind to precisely the failures worth alarming on.

    Both directions in one test, because the first assertion alone would pass on a middleware
    that counted *every* request as a 500.
    """
    app = FastAPI()
    metrics.install_http_metrics_middleware(app, service_name="boom-app")

    @app.get("/widgets/{widget_id}")
    async def get_widget(widget_id: str) -> dict[str, str]:
        if widget_id == "explode":
            raise RuntimeError("the handler failed")
        return {"id": widget_id}

    labels = {"app": "boom-app", "method": "GET", "path": "/widgets/{widget_id}"}
    before_500 = _counter_value(metrics.HTTP_REQUESTS, status="500", **labels)
    before_200 = _counter_value(metrics.HTTP_REQUESTS, status="200", **labels)

    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/widgets/explode").status_code == 500
    assert client.get("/widgets/fine").status_code == 200

    assert _counter_value(metrics.HTTP_REQUESTS, status="500", **labels) == before_500 + 1
    assert _counter_value(metrics.HTTP_REQUESTS, status="200", **labels) == before_200 + 1


def test_an_unmatched_route_does_not_become_a_metric_label() -> None:
    """The sibling of D-316, found while fixing D-393 and in the same three lines.

    `request_logging` stopped falling back to `request.url.path` in D-316, after 23 raw
    `/learning/students/student-ext-N/...` paths were measured in one local session - every one
    a CORS preflight, since `CORSMiddleware` answers `OPTIONS` before routing sets
    `scope["route"]`. **This module kept the fallback**, and a raw path is worse as a metric
    label than as a log line: Prometheus holds one time series per distinct label set forever,
    so an unbounded `path` label is a memory leak in the scrape target rather than noise in a
    query. Both real apps register CORS before this middleware, so the preflight reaches it.

    The same token as the log line's, imported rather than re-spelled, so an operator moving
    between the two stores searches for one word.
    """
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])
    metrics.install_http_metrics_middleware(app, service_name="preflight-app")

    @app.get("/learning/students/{student_id}/dashboard")
    async def dashboard(student_id: str) -> dict[str, str]:
        return {"student_id": student_id}

    response = TestClient(app).options(
        "/learning/students/student-ext-7/dashboard",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200

    text = metrics.render_metrics()[0].decode()
    assert "student-ext-7" not in text
    assert f'path="{UNMATCHED_PATH}"' in text
