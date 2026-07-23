from fastapi import FastAPI
from fastapi.testclient import TestClient
from intellichoice_observability import metrics


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
