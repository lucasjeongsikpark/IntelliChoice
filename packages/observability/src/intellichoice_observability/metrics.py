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
from itertools import product

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from intellichoice_observability.request_logging import UNMATCHED_PATH

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
LEARNING_GAIN = Histogram("learning_gain_score", "Post - pre accuracy gain per completed session")
SUPPORT_USAGE = Counter(
    "learning_support_usage_total",
    "Hint/solution/video assistance used during study",
    labelnames=("support_type",),  # "hint" | "solution" | "video"
)
RETRIES = Counter("learning_retry_total", "Study-ladder retry attempts")

# D-329's other half, and the half the incident was actually about. 117 swallowed
# personalization failures in 48 hours were invisible because *nothing said anything* - and only
# the raising half of that is watched now (the scheduler's `logger.exception` feeds a metric
# filter and the `BackgroundTaskFailures` alarm). Its silent terminal outcomes were not: a
# fallback to the canonical rung, a stale drop, a missing precondition and an empty checkpoint
# each returned normally and counted nothing, so a config regression that made *every* call fall
# back raised nothing and read on every dashboard exactly like a week when nobody clicked
# "Get a hint".
#
# **The shape this exists to make visible: `learning_support_usage_total{support_type="hint"}`
# moving while `learning_hint_personalization_outcomes_total{outcome="published"}` stays flat at
# zero is personalization running dead.** Whether that should raise an alarm is UD-5's held user
# question - this is the number the question is about, not an answer to it.
#
# One dimension, because the EMF export is capped at one (see `graph/nodes.py`'s
# `video_unavailable` comment); the six outcome values below are the whole vocabulary, and
# `BackgroundHintPersonalizationScheduler._run` increments exactly one of them per task run.
# Like every other metric here it reaches CloudWatch only once the collector's `filter/kpis`
# allowlist names it (`terraform/modules/ecs-service/main.tf`), which is deliberately a separate
# edit - and is not part of this change.
HINT_PERSONALIZATION_OUTCOMES = Counter(
    "learning_hint_personalization_outcomes_total",
    "Terminal outcomes of the background hint-personalization task (D-272/D-329)",
    labelnames=("outcome",),
)

# AUD-X-07: a session whose checkpoint referenced a domain row that did not exist, rolled
# back so the student can continue. Should be flat at zero; any movement means requests are
# dying between the checkpoint commit and the domain commit, which a deploy's task drain
# can cause on its own - so this is the signal that the underlying ordering, still
# unfixed, is actually being hit rather than merely reachable.
CHECKPOINT_REPAIRS = Counter(
    "learning_checkpoint_repairs_total",
    "Checkpoints rolled back to match the database (AUD-X-07)",
)
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
QA_MAPS_CALLS = Counter("qa_maps_calls_total", "Branch-locator maps calls", labelnames=("result",))
QA_CALENDAR_CALLS = Counter(
    "qa_calendar_calls_total", "Calendar intent lookups", labelnames=("result",)
)
QA_OUT_OF_SCOPE = Counter("qa_out_of_scope_total", "Queries refused as out of scope")
# AUD-C-08: the operator-visible half. A degraded turn used to be indistinguishable from
# a genuine out-of-scope refusal - same message, same counter - so a Bedrock outage read
# on a dashboard as a sudden surge of off-topic questions. `stage` says which call failed.
QA_SERVICE_DEGRADED = Counter(
    "qa_service_degraded_total",
    "Turns answered with the temporarily-unavailable message after a provider failure",
    labelnames=("stage",),  # "scope_guard" | "document_qa_retrieval" | "calendar_retrieval"
)
QA_CONVERSATION_COST_CENTS = Histogram(
    "qa_conversation_cost_cents", "Bedrock spend per Q&A conversation, in cents"
)

# --- SSE (D-396) -----------------------------------------------------------------------
#
# **The 08-16 audit's wording was "SSE has no telemetry at all", and D-395 is what that costs.**
# The cross-replica fan-out lost four events out of five in a five-event burst, and nothing
# counted it - the failure was logged into a `warning` nobody queries and the mechanism looked
# healthy from every dashboard. These three exist so the *next* one is a line on a graph.
#
# No `app` label, following this module's existing convention: learning-api and chat-api are
# separate processes with separate registries, so the metric name is already unambiguous per
# scrape target and a label would only invite double counting.
SSE_CONNECTIONS = Gauge("sse_connections", "SSE subscriptions this process is currently holding")
SSE_EVENTS_DELIVERED = Counter(
    "sse_events_delivered_total", "SSE events handed to a local subscriber's queue"
)
SSE_RELAY_FAILURES = Counter(
    "sse_relay_failures_total",
    "Cross-replica fan-out attempts that did not send, by why",
    # "notify_failed" - the NOTIFY itself raised (D-395's shared-connection collision, a closed
    # connection, a Postgres restart). "payload_too_large" - over the 7000-byte ceiling, dropped
    # deliberately rather than truncated. "publish_failed" - the relay callable raised before the
    # notify was even scheduled.
    labelnames=("reason",),
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

# --- Label pre-initialisation (COST-22) -------------------------------------------------
#
# **A labelled counter has no series until its first event, which is the moment an alarm on it
# would have been useful.** `prometheus_client` creates a child on the first `.labels(...)` call
# and the EMF exporter writes what it is given, so before this block `qa_service_degraded_total`
# - built specifically so a Bedrock outage stops reading on a dashboard as a surge of off-topic
# questions - was absent from the deployed namespace entirely. Nothing could alarm on it until
# an outage created it, and "the metric does not exist" and "the metric is at zero" are the two
# states a monitor most needs to tell apart.
#
# Touching every documented combination at import makes a first occurrence a **delta on an
# existing series** rather than the birth of one, which is what a floor, a rate or an anomaly
# detector needs. The label values are the enumerated call-site vocabulary, not a guess; a value
# a call site can produce but this table omits is still lazily created, so this list is only as
# good as its agreement with the call sites - which is what
# `test_metrics_label_preinitialisation.py` holds in place.
PREINITIALISED_LABEL_VALUES: tuple[tuple[Counter, dict[str, tuple[str, ...]]], ...] = (
    (ATTENDANCE_CHECKS, {"result": ("present", "blocked", "unknown")}),
    (EXAM_COMPLETIONS, {"phase": ("pre", "post")}),
    (SUPPORT_USAGE, {"support_type": ("hint", "solution", "video")}),
    # The detection shape above only works if `published` is a series before the first publish:
    # "flat at zero" and "absent" have to be distinguishable, and this metric's whole purpose is
    # to be read while it is zero.
    (
        HINT_PERSONALIZATION_OUTCOMES,
        {
            "outcome": (
                "published",
                "fallback_canonical",
                "dropped_stale",
                "dropped_late",
                "precondition_missing",
                "failed",
            )
        },
    ),
    (QA_ANSWERS, {"result": ("grounded", "no_answer")}),
    # `qa_maps_calls_total` and `qa_calendar_calls_total` carry no documented vocabulary; these
    # are every value their call sites can emit (`branch_locator.py:72/77`,
    # `chat_api/graph/nodes.py:1042/1047`).
    (QA_MAPS_CALLS, {"result": ("success", "failure")}),
    (QA_CALENDAR_CALLS, {"result": ("success", "failure")}),
    (
        QA_SERVICE_DEGRADED,
        {"stage": ("scope_guard", "document_qa_retrieval", "calendar_retrieval")},
    ),
    (SSE_RELAY_FAILURES, {"reason": ("notify_failed", "payload_too_large", "publish_failed")}),
)

# **Deliberately not pre-initialised, and this is the list a reviewer should argue with.** Both
# carry label values that are only bounded by the route table and the HTTP status space, and
# `path` is already the D-393/D-316 cardinality hazard: pre-initialising it would mean choosing a
# cross product of every route, method and status per process, permanently, to make a series that
# the first real request creates anyway. These two are also the only metrics here that no
# low-traffic alarm depends on - the ALB reports request and error rate independently.
UNBOUNDED_LABEL_EXEMPT: tuple[Counter | Histogram, ...] = (HTTP_REQUESTS, HTTP_REQUEST_DURATION)


def _preinitialise_label_sets() -> None:
    """Create every combination in `PREINITIALISED_LABEL_VALUES` at value 0.

    A function rather than a module-scope loop so the loop variables do not leak into the
    module namespace, which the completeness test walks looking for declared metrics.
    """
    for metric, label_values in PREINITIALISED_LABEL_VALUES:
        for combination in product(*label_values.values()):
            metric.labels(**dict(zip(label_values, combination, strict=True)))


_preinitialise_label_sets()


def install_http_metrics_middleware(app: FastAPI, *, service_name: str) -> None:
    def _record(request: Request, *, status: str, start: float) -> None:
        duration_s = time.monotonic() - start
        route = request.scope.get("route")
        # **`UNMATCHED_PATH`, not `request.url.path` (D-393).** `request_logging` stopped using
        # the raw path in D-316 and this module kept it, which is the D-347 "fixed in one
        # direction" shape again. A raw path is worse here than in a log line: Prometheus keeps
        # one time series per distinct label set for the process's life, so an unbounded `path`
        # label grows the scrape target's memory permanently rather than adding noise to a
        # query - and the branch is taken by **every CORS preflight**, since `CORSMiddleware`
        # answers `OPTIONS` before routing sets `scope["route"]`. The same token as the log
        # line's, imported rather than re-spelled, so one word finds both stores.
        path = route.path if route is not None else UNMATCHED_PATH
        HTTP_REQUESTS.labels(
            app=service_name, method=request.method, path=path, status=status
        ).inc()
        HTTP_REQUEST_DURATION.labels(app=service_name, method=request.method, path=path).observe(
            duration_s
        )

    @app.middleware("http")
    async def _record_http_metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.monotonic()
        # D-393, and see `request_logging._log_request` for why this is `except Exception`
        # rather than `finally`. Without it `http_requests_total{status="500"}` could never be
        # incremented by an actual unhandled exception - `ServerErrorMiddleware` converts it to
        # a 500 response above this middleware - so the counter an operator would alarm on was
        # blind to exactly the failures worth alarming on.
        try:
            response = await call_next(request)
        except Exception:
            _record(request, status="500", start=start)
            raise
        _record(request, status=str(response.status_code), start=start)
        return response


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
