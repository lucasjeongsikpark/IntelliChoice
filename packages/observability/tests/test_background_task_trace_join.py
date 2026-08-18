"""D-400: can a detached background task's log line be joined to the request that spawned it?

**Why this is a test and not a throwaway probe.** The 08-16 audit's *"Bedrock spend is attributable
per day and per app but never per student or per session"* turned out to be partly already solved -
`cost_reservations` gives queryable per-student-per-day spend for `student_report` and `tutor_chat`,
and a per-session running total enforces a ceiling. What is genuinely unattributed is the
highest-volume path: `hint_generation`, `solution_generation`, `hint_personalization` and
`stage_narrative` each emit a `bedrock_call` line carrying `task`, `model_id`, tokens and
`cost_cents` and **no subject of any kind**.

The cheap fix for that is not a new field. `JsonLogFormatter` already stamps `trace_id` on every
line from the active span, and `request_logging` already puts `learning_session_id` on the access
line - so *"which session ran up this spend?"* is a join on `trace_id`, with nothing to build. That
holds only if the trace id survives into the **detached** tasks, which is where those calls actually
run (D-217's deferred narratives, D-329's hint personalization). `asyncio.create_task` copies the
current `contextvars.Context`, so it should - but "should" has lost to a measurement four times in
two days in this project, so it is asserted here instead of assumed.

The property is asserted twice, and the second assertion is the one with teeth: **a task spawned
outside any span must not inherit a stale trace id.** A fabricated join is worse than no join,
because it silently attributes one student's spend to another student's request.
"""

import asyncio
import io
import json
import logging

from intellichoice_observability.logging_config import JsonLogFormatter
from intellichoice_observability.tracing import build_tracer_provider, current_trace_id, traced_span
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _capturing_logger(stream: io.StringIO) -> logging.Logger:
    """The shipped formatter, so the assertion is about the line that would really be written."""
    logger = logging.getLogger(f"test.background.{id(stream)}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger.handlers = [handler]
    return logger


def _install_provider() -> InMemorySpanExporter:
    import intellichoice_observability.tracing as tracing_module

    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)
    tracing_module._tracer = provider.get_tracer("intellichoice")
    return exporter


def test_a_detached_task_logs_the_trace_id_of_the_request_that_spawned_it() -> None:
    """The join the spend fix depends on: a `bedrock_call` line emitted from a background task
    carries the same `trace_id` as the access line of the request that scheduled it.

    Shaped like the real thing rather than a bare `create_task`: the span is opened and **closed**
    before the task runs, because that is what happens in production - the response is sent, the
    server span ends, and the deferred narrative generates afterwards. A trace id read from an
    ended span is still that request's id, which is the part worth pinning.
    """
    _install_provider()
    stream = io.StringIO()
    logger = _capturing_logger(stream)

    async def run() -> str | None:
        request_trace_id: str | None = None
        task: asyncio.Task[None] | None = None

        async def deferred_work() -> None:
            # Stands in for `ResilientBedrockGateway.generate_structured`'s own log line.
            logger.info("bedrock_call", extra={"task": "stage_narrative", "cost_cents": 0.19})

        with traced_span("POST /learning/sessions/{id}/answer"):
            request_trace_id = current_trace_id()
            # Scheduled inside the request, exactly as the deferred narrative and hint
            # personalization schedulers do.
            task = asyncio.create_task(deferred_work())

        # The span is now closed - the response has gone out. The task runs after it.
        await task
        return request_trace_id

    request_trace_id = asyncio.run(run())
    assert request_trace_id is not None, "no span was active, so this test measured nothing"

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "bedrock_call"
    assert payload.get("trace_id") == request_trace_id, (
        "a background Bedrock call cannot be joined back to the request that caused it, so "
        "per-session spend attribution needs a subject field rather than a trace-id join"
    )


def test_a_task_spawned_outside_a_span_carries_no_trace_id() -> None:
    """The control, and the assertion that makes the one above worth trusting.

    A stale or fabricated trace id is worse than a missing one here: joining on it would attribute
    one session's spend to a different request. Scheduled work with no request behind it - a cron
    job, a startup task - must produce a line with **no** `trace_id` key at all, which is the same
    "absent, never null" convention `request_logging` follows for session ids.
    """
    _install_provider()
    stream = io.StringIO()
    logger = _capturing_logger(stream)

    async def run() -> None:
        async def scheduled_job() -> None:
            logger.info("bedrock_call", extra={"task": "memory_consolidation", "cost_cents": 0.42})

        await asyncio.create_task(scheduled_job())

    asyncio.run(run())

    payload = json.loads(stream.getvalue())
    assert "trace_id" not in payload, (
        "a task with no request behind it reported a trace id, so a spend join would silently "
        "attribute it to an unrelated request"
    )
