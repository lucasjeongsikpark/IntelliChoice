"""CHECKPOINTER-UNINSTRUMENTED (D-464): checkpoint I/O must appear in the trace, and its payload
must not.

`AsyncPostgresSaver` opens its own psycopg connection - a separate driver from the asyncpg
engines `instrument_sqlalchemy_engines` covers - so before `instrument_psycopg` existed **no span
in any trace represented a checkpoint read or write**, on routes whose whole state model is the
checkpoint (E6.2). The first test drives a real saver against the dev Postgres and asserts both
halves together, for the same reason `test_health_endpoint_tracing` does: a checkpoint span that
carried the serialized graph state would be worse than no span at all, and an assertion that only
looks for the payload's absence passes trivially against an exporter that received nothing.

The payload half is a marker string placed in the checkpoint's channel values twice - once as a
primitive (inlined into the checkpoint's JSONB parameter) and once inside a dict (serialized into
a `checkpoint_blobs` parameter) - so both of the saver's write paths are covered. It must reach
the database (read back through the same traced connection) and reach **no** exported span.
"""

import asyncio
import inspect
import types
import uuid
from collections.abc import Callable

import intellichoice_observability.tracing as tracing_module
import psycopg
import pytest
from intellichoice_observability.tracing import (
    build_tracer_provider,
    instrument_psycopg,
    traced_span,
)
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# The docker-compose dev database, in the driverless DSN shape `checkpoint_database_url` uses.
_DEV_CHECKPOINT_DSN = "postgresql://intellichoice:intellichoice@localhost:5432/intellichoice"


def _postgres_skip_reason() -> str | None:
    """`packages/db/tests/conftest.py`'s `postgres_skip_reason()` pattern, probed through psycopg
    (the checkpointer's own driver) rather than the asyncpg engine - and run at collection time,
    before any test here has instrumented psycopg."""

    async def check() -> str | None:
        try:
            conn = await psycopg.AsyncConnection.connect(_DEV_CHECKPOINT_DSN, connect_timeout=3)
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
        return None

    return asyncio.run(check())


_SKIP_REASON = _postgres_skip_reason()


def _span_text(span: ReadableSpan) -> list[str]:
    """Every string a span would export: its name, attribute values and event contents."""
    texts = [span.name]
    texts.extend(str(value) for value in (span.attributes or {}).values())
    for event in span.events or ():
        texts.append(event.name)
        texts.extend(str(value) for value in (event.attributes or {}).values())
    return texts


def _checkpoint_round_trip(
    instrument: Callable[[TracerProvider], None],
) -> tuple[tuple[ReadableSpan, ...], str, object]:
    """One `aput` + `aget_tuple` on a throwaway thread under a `test-parent` span, with psycopg
    instrumented by `instrument` for exactly the duration. Returns the finished spans, the
    payload marker, and the value read back from the checkpoint."""
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)
    previous_tracer = tracing_module._tracer
    tracing_module._tracer = provider.get_tracer("intellichoice")
    marker = f"CHECKPOINT-PAYLOAD-MARKER-{uuid.uuid4().hex}"
    thread_id = f"test-checkpointer-spans-{uuid.uuid4()}"

    async def run() -> object:
        # Opened *after* instrumentation, as `lifespan`'s `from_conn_string` is after main.py's
        # module-level call: the patch is on `AsyncConnection.connect`, so only connections
        # opened afterwards are traced.
        async with AsyncPostgresSaver.from_conn_string(_DEV_CHECKPOINT_DSN) as saver:
            await saver.setup()
            config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            checkpoint = empty_checkpoint()
            checkpoint["channel_values"] = {"answer": marker, "state": {"note": marker}}
            checkpoint["channel_versions"] = {"answer": "1", "state": "1"}
            try:
                with traced_span("test-parent"):
                    saved = await saver.aput(
                        config,  # type: ignore[arg-type]
                        checkpoint,
                        {"source": "input", "step": -1},
                        {"answer": "1", "state": "1"},
                    )
                    loaded = await saver.aget_tuple(saved)
            finally:
                await saver.adelete_thread(thread_id)
            assert loaded is not None
            return loaded.checkpoint["channel_values"].get("answer")

    instrument(provider)
    try:
        read_back = asyncio.run(run())
    finally:
        PsycopgInstrumentor().uninstrument()
        tracing_module._tracer = previous_tracer
    return exporter.get_finished_spans(), marker, read_back


def _leaks(spans: tuple[ReadableSpan, ...], marker: str) -> list[tuple[str, str]]:
    return [(span.name, text) for span in spans for text in _span_text(span) if marker in text]


@pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "")
def test_checkpoint_io_is_a_child_span_and_carries_no_payload() -> None:
    spans, marker, read_back = _checkpoint_round_trip(instrument_psycopg)

    # The payload really crossed the traced connection - so "absent from every span" below is a
    # statement about a value the instrumentation had in hand, not one it never saw.
    assert read_back == marker

    parent = next(span for span in spans if span.name == "test-parent")
    assert parent.context is not None
    checkpoint_children = [
        span
        for span in spans
        if (span.attributes or {}).get("db.system") == "postgresql"
        and span.parent is not None
        and span.parent.span_id == parent.context.span_id
    ]
    assert checkpoint_children, (
        "no db.system=postgresql span under the request span - checkpoint I/O is untraced; "
        f"spans seen: {[(s.name, dict(s.attributes or {})) for s in spans]}"
    )
    # Both directions: `aput`'s writes and `aget_tuple`'s read (span names are the statement's
    # leading keyword, in whatever case the saver's SQL uses).
    assert {"INSERT", "SELECT"} <= {span.name.upper() for span in checkpoint_children}

    assert _leaks(spans, marker) == []


@pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "")
def test_the_payload_check_catches_captured_parameters() -> None:
    """The negative control for the test above: with `capture_parameters=True` the marker does
    reach a span (`db.statement.parameters`), so an empty leak list there is evidence that the
    default kept it out - not a detector that cannot see the payload at all."""

    def instrument_capturing_parameters(provider: TracerProvider) -> None:
        PsycopgInstrumentor().instrument(tracer_provider=provider, capture_parameters=True)

    spans, marker, read_back = _checkpoint_round_trip(instrument_capturing_parameters)

    assert read_back == marker
    assert _leaks(spans, marker) != []


def _connect_wrapper_depth() -> int:
    """How many instrumentation layers sit on `AsyncConnection.connect`: each wrap adds one proxy
    whose `__wrapped__` is the layer beneath it. The bare attribute is the `classmethod` psycopg
    defines - or, once `uninstrument()` has run in this process, the bound method wrapt restores
    in its place. Compared by exact `type()`, because a wrapt proxy forwards `__class__` and so
    passes `isinstance(proxy, classmethod)`."""
    attribute = inspect.getattr_static(psycopg.AsyncConnection, "connect")
    depth = 0
    while type(attribute) not in (classmethod, types.MethodType):
        attribute = attribute.__wrapped__
        depth += 1
    return depth


def test_instrument_psycopg_is_idempotent() -> None:
    """The same process-wide-singleton shape as `instrument_sqlalchemy_engines`: a second call is
    a no-op, so `AsyncConnection.connect` carries exactly one wrapper, and a single
    `uninstrument()` leaves it bare (a doubled wrap would leave one layer behind)."""
    provider = build_tracer_provider(
        service_name="test-service", span_exporter=InMemorySpanExporter()
    )
    assert _connect_wrapper_depth() == 0
    try:
        instrument_psycopg(provider)
        instrument_psycopg(provider)
        assert PsycopgInstrumentor().is_instrumented_by_opentelemetry
        assert _connect_wrapper_depth() == 1
    finally:
        PsycopgInstrumentor().uninstrument()
    assert _connect_wrapper_depth() == 0
    assert not PsycopgInstrumentor().is_instrumented_by_opentelemetry
