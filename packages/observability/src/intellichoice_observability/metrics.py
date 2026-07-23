"""SPEC §5.32.4 Prometheus KPIs. One counter/histogram per named KPI, recorded from the
existing service call sites that already know the outcome (no new business logic - this
module is instrumentation only). Uses the default global `prometheus_client` registry,
which assumes one process per app - the same single-Uvicorn-worker posture D-032 already
established for the SSE event bus, not a new assumption.

Infra KPIs (request rate, error rate, P50/P95/P99 latency) come from
`install_http_metrics_middleware`, not a manual call site, since every request already
passes through it. CPU/memory/pod count are container-runtime metrics (cAdvisor/
node-exporter in a real deployment) - out of scope for an application-level `/metrics`
endpoint and not built here; there is no deployed container runtime yet to scrape them
from (S32's decision, D-004).
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# --- Learning KPIs (SPEC §5.32.4) ---------------------------------------------------

SESSION_STARTS = Counter("learning_session_starts_total", "Learning sessions started")
ATTENDANCE_CHECKS = Counter(
    "learning_attendance_checks_total",
    "Attendance gate outcomes",
    labelnames=("result",),  # "present" | "blocked" | "unknown"
)
EXAM_COMPLETIONS = Counter(
    "learning_exam_completions_total",
    "Pre/post exam completions",
    labelnames=("phase",),  # "pre" | "post"
)
SESSIONS_COMPLETED = Counter(
    "learning_sessions_completed_total", "Full pre->study->post sessions completed"
)
LEARNING_GAIN = Histogram(
    "learning_gain_score", "Post - pre accuracy gain per completed session"
)
SUPPORT_USAGE = Counter(
    "learning_support_usage_total",
    "Hint/solution/video assistance used during study",
    labelnames=("support_type",),  # "hint" | "solution" | "video"
)
RETRIES = Counter("learning_retry_total", "Study-ladder retry attempts")
TUTOR_REVIEW_FLAGGED = Counter(
    "learning_tutor_review_flagged_total", "Skills that exhausted the retry ladder unresolved"
)
PROBLEM_REPORTS = Counter("learning_problem_reports_total", "Question templates reported")
QUARANTINE_COUNT = Counter(
    "learning_quarantine_total", "Question templates auto-quarantined from reports"
)
SESSION_COST_CENTS = Histogram(
    "learning_session_cost_cents", "Bedrock spend per learning session, in cents"
)

# --- Q&A KPIs (SPEC §5.32.4) ---------------------------------------------------------

QA_ANSWERS = Counter(
    "qa_answers_total",
    "document_qa intent outcomes",
    labelnames=("result",),  # "grounded" | "no_answer"
)
QA_CITATIONS_PER_ANSWER = Histogram(
    "qa_citations_per_answer", "Verified citations returned per grounded answer"
)
QA_EMAIL_ESCALATIONS = Counter("qa_email_escalations_total", "Admin-escalation emails sent")
QA_MAPS_CALLS = Counter(
    "qa_maps_calls_total", "Branch-locator maps calls", labelnames=("result",)
)
QA_CALENDAR_CALLS = Counter(
    "qa_calendar_calls_total", "Calendar intent lookups", labelnames=("result",)
)
QA_OUT_OF_SCOPE = Counter("qa_out_of_scope_total", "Queries refused as out of scope")
QA_CONVERSATION_COST_CENTS = Histogram(
    "qa_conversation_cost_cents", "Bedrock spend per Q&A conversation, in cents"
)

# --- Infra (via middleware) -----------------------------------------------------------

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests",
    labelnames=("app", "method", "path", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    labelnames=("app", "method", "path"),
)


def install_http_metrics_middleware(app: FastAPI, *, service_name: str) -> None:
    @app.middleware("http")
    async def _record_http_metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_s = time.monotonic() - start
        route = request.scope.get("route")
        path = route.path if route is not None else request.url.path
        HTTP_REQUESTS.labels(
            app=service_name, method=request.method, path=path, status=str(response.status_code)
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            app=service_name, method=request.method, path=path
        ).observe(duration_s)
        return response


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
