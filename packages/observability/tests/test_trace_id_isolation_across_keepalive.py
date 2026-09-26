"""D-464: two requests on one keep-alive connection must not share a trace.

**What was measured.** E6.2 found 0.14% of staging requests (19/13,550 learning, 1/424 chat)
sharing an OTel `trace_id` with a *different* request in the same task - sub-second apart,
often the next route the same k6 VU called on the same keep-alive connection - so X-Ray nests
one request's whole span tree inside another's (a real trace has `POST /dev/token` inside
`POST .../answers`). D-464 recorded the mechanism as a hypothesis. This module turns it into a
reproduction and pins the fix.

**The mechanism.** `contextvars` are copied into an asyncio task from whoever calls
`create_task`. uvicorn starts a pipelined request's ASGI task from `on_response_complete()`,
which runs inside the *previous* request's final `send()` - i.e. inside request A's task, with
A's OTel server span still current (the middleware detaches it only after that `send`
returns). Request B's task therefore starts with A's span in its context, and OTel's
`_start_internal_or_server_span` sees a current span and makes B an `INTERNAL` **child of A**
instead of a new `SERVER` root: same `trace_id`, silently. The paused-then-resumed-read path
that k6 actually hit (`transport.resume_reading()` re-registers the socket reader with a copy
of A's context) is the same defect by a probabilistic route; uvicorn labels both CPython
#140947 and ships `reset_contextvars` / `--reset-contextvars` (off by default) as the opt-in
workaround, which starts every ASGI task in a fresh `contextvars.Context()`.

**Why pipelining.** It is the deterministic path: two complete requests written to one raw
socket before any response is read always put B in uvicorn's pipeline queue, so there is no
timing to race. `httptools` is used because it is what the containers run (uvicorn's `auto`
picks it when installed); the flag is the only thing that differs between the two variants.

**The `False` variant is kept deliberately.** It passes on the unfixed configuration and
asserts the *leak*, so the mechanism stays legible and the test notices if a uvicorn or OTel
upgrade changes the behaviour underneath the flag (at which point the flag and this module
should both be revisited).

The instrumentation is `FastAPIInstrumentor.instrument_app` on this module's own app object,
with an explicit `tracer_provider` - no global provider is installed or left behind.
"""

import contextlib
import socket
import threading
import time
from collections.abc import Iterator

import uvicorn
from fastapi import FastAPI, Request
from intellichoice_observability.tracing import build_tracer_provider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanContext, SpanKind

_FIRST = "POST /first"
_SECOND = "GET /second"


def _instrumented_app() -> tuple[FastAPI, InMemorySpanExporter]:
    """A fresh app per variant, instrumented before its first ASGI call (the ordering contract
    `test_instrumentation_ordering.py` pins)."""
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="test-service", span_exporter=exporter)
    app = FastAPI()
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    @app.post("/first")
    async def first(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"received": len(body)}

    @app.get("/second")
    async def second() -> dict[str, bool]:
        return {"ok": True}

    return app, exporter


@contextlib.contextmanager
def _running_server(app: FastAPI, *, reset_contextvars: bool) -> Iterator[int]:
    """The app under a real `uvicorn` on an OS-picked port; yields the port.

    Same shape as `test_stream_personalized_hint_over_http._running_server`, with the one
    setting under test threaded through.
    """
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        log_level="warning",
        reset_contextvars=reset_contextvars,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="keepalive-trace-server", daemon=True)
    thread.start()

    deadline = time.monotonic() + 60.0
    while not server.started:
        if not thread.is_alive():
            raise AssertionError("the test server thread died during startup")
        if time.monotonic() > deadline:
            raise AssertionError("the test server did not start within 60s")
        time.sleep(0.02)

    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield port
    finally:
        server.should_exit = True
        thread.join(timeout=15.0)
        if thread.is_alive():
            server.force_exit = True
            thread.join(timeout=15.0)
        assert not thread.is_alive(), "the test server did not shut down"


def _read_responses(sock: socket.socket, count: int) -> list[bytes]:
    """Read `count` complete HTTP/1.1 responses, framed by `Content-Length` (every response
    here is a small JSON body, so no chunked encoding to handle)."""
    buffer = b""
    responses: list[bytes] = []
    while len(responses) < count:
        head_end = buffer.find(b"\r\n\r\n")
        if head_end != -1:
            head = buffer[:head_end].decode("latin-1")
            length = next(
                int(line.split(":", 1)[1])
                for line in head.split("\r\n")
                if line.lower().startswith("content-length:")
            )
            total = head_end + 4 + length
            if len(buffer) >= total:
                responses.append(buffer[:total])
                buffer = buffer[total:]
                continue
        chunk = sock.recv(65536)
        if not chunk:
            raise AssertionError(f"connection closed after {len(responses)} of {count} responses")
        buffer += chunk
    return responses


def _pipeline_two_requests(port: int) -> list[bytes]:
    """Both requests written on **one** connection before reading anything: the second is
    queued in uvicorn's pipeline and started from inside the first request's final `send`."""
    body = b'{"answer": 42}'
    first = (
        b"POST /first HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"\r\n" + body
    )
    second = b"GET /second HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
    with socket.create_connection(("127.0.0.1", port), timeout=10.0) as sock:
        sock.sendall(first + second)
        return _read_responses(sock, 2)


def _span(spans: tuple[ReadableSpan, ...], name: str) -> ReadableSpan:
    matching = [span for span in spans if span.name == name]
    assert len(matching) == 1, f"expected one {name!r} span, got {[s.name for s in spans]}"
    return matching[0]


def _context(span: ReadableSpan) -> SpanContext:
    assert span.context is not None, f"{span.name!r} has no span context"
    return span.context


def _request_spans(*, reset_contextvars: bool) -> tuple[ReadableSpan, ReadableSpan]:
    app, exporter = _instrumented_app()
    try:
        with _running_server(app, reset_contextvars=reset_contextvars) as port:
            responses = _pipeline_two_requests(port)
    finally:
        FastAPIInstrumentor.uninstrument_app(app)
    assert all(response.startswith(b"HTTP/1.1 200") for response in responses), responses

    # Selected by route name, not by `SpanKind.SERVER`: in the leaking variant the second
    # request's span is `INTERNAL`, which is itself part of what is being asserted.
    spans = exporter.get_finished_spans()
    return _span(spans, _FIRST), _span(spans, _SECOND)


def test_without_reset_contextvars_a_pipelined_request_joins_the_previous_trace() -> None:
    """The reproduction, pinned: uvicorn's default leaks request A's context into request B.

    This passes on the *unfixed* configuration on purpose - it documents the defect E6.2
    measured, not a behaviour anyone wants.
    """
    first, second = _request_spans(reset_contextvars=False)

    assert first.kind == SpanKind.SERVER
    assert first.parent is None
    assert _context(second).trace_id == _context(first).trace_id
    assert second.parent is not None
    assert second.parent.span_id == _context(first).span_id
    # OTel only creates a SERVER span when no span is current; a leaked parent demotes the
    # second request to an INTERNAL child - which is why X-Ray nests it inside the first.
    assert second.kind == SpanKind.INTERNAL


def _assert_each_request_is_its_own_trace(first: ReadableSpan, second: ReadableSpan) -> None:
    """The fixed-variant contract, separate from the test so it can be pointed at the
    `reset_contextvars=False` spans to watch it fail - which is how it was shown to have
    teeth rather than merely to be green."""
    assert first.kind == SpanKind.SERVER
    assert first.parent is None
    assert _context(second).trace_id != _context(first).trace_id, (
        "two pipelined requests on one keep-alive connection share a trace_id - the ASGI task "
        "of the second inherited the first's OTel context (D-464)"
    )
    assert second.parent is None
    assert second.kind == SpanKind.SERVER


def test_with_reset_contextvars_each_pipelined_request_gets_its_own_trace() -> None:
    """The fix the Dockerfiles ship (`--reset-contextvars`): B's ASGI task starts in a fresh
    context, so it is a SERVER root in a trace of its own."""
    first, second = _request_spans(reset_contextvars=True)
    _assert_each_request_is_its_own_trace(first, second)
