"""SPEC §5.32.2 OpenTelemetry: one `trace_id` spans FastAPI -> LangGraph -> Bedrock
gateway -> MySQL/Postgres -> MCP tools -> external APIs. `FastAPIInstrumentor`/
`SQLAlchemyInstrumentor` cover the FastAPI and MySQL/Postgres hops automatically, no
caller-side changes needed in `packages/adapters` - see `configure_tracing_provider`'s
docstring for exactly *when* it must run relative to app construction, and
`instrument_sqlalchemy_engines`'s docstring for why every traced engine must go through
one combined call rather than one call each.
LangGraph node execution, the Bedrock gateway, and MCP tool calls have no off-the-shelf
OTel instrumentation, so `traced_span()`/`traced_node()` are small manual wrappers used
at those call sites instead.

Exporting is OTLP/HTTP to an otel-collector (`docker-compose.yml`'s `otel-collector`
service, forwarding to Jaeger) - this mirrors the rest of the project's env-selected
real-vs-fake posture (D-002): `otel_enabled=False` (e.g. in tests, where no collector is
running) makes every span a no-op via OTel's own `NoOpTracerProvider`, so instrumented
code never has to branch on whether tracing is on.
"""

import functools
import re
from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import TypeVar

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Tracer
from sqlalchemy.ext.asyncio import AsyncEngine

_StateT = TypeVar("_StateT")

_tracer: Tracer = trace.get_tracer("intellichoice")


# Credential shapes that must never leave the process inside a span (SPEC §5.30).
#
# Found live, not predicted (S39 continuation, AUD-F-13): `FastAPIInstrumentor` sets
# `http.url` to the *full* request URL, query string included, and the learning app's SSE
# stream authenticates as `GET /learning/sessions/{id}/stream?token=<JWT>` - so the first
# hour of real tracing on staging put a 455-character bearer token into X-Ray. The app's
# own access logger was unaffected: it records a templated `path` and drops the query
# string, which is why S38's log scan was clean and is exactly why this needed a second,
# independent scan of a second store.
_REDACTIONS = (
    # `?token=` / `&token=` in a URL - the SSE case above.
    (re.compile(r"([?&](?:token|access_token|api_key)=)[^&\s]+", re.IGNORECASE), r"\1REDACTED"),
    # A bare JWT anywhere (header value, message, manually-set attribute).
    (re.compile(r"eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.?[A-Za-z0-9_-]*"), "REDACTED-JWT"),
    (re.compile(r"([Bb]earer\s+)\S+"), r"\1REDACTED"),
)


def _redact_text(value: str) -> str:
    for pattern, replacement in _REDACTIONS:
        value = pattern.sub(replacement, value)
    return value


def _redact(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _redact_text(value)


def _redacted_event(event: Event) -> Event:
    """A copy of `event` with credentials stripped from its **name and attribute values**, or
    `event` itself when nothing matched - so the caller can tell "no event changed" by
    identity and leave the span alone (DRIFT-82).

    Events carry credentials at least as readily as attributes do: `Span.record_exception`
    writes an upstream failure's message and formatted stacktrace into one, and a 401 tends to
    quote the token it rejected. An `Event`'s attributes are immutable, so a redacted event has
    to be a new object with name, timestamp and every clean attribute carried across by hand.

    Rebuilt as a plain `Event` even where the original was some other `EventBase` subclass:
    name/timestamp/attributes is the whole recorded shape, and losing an unknown subclass's
    extras is the right side of the trade against exporting a credential.
    """
    name = _redact_text(event.name)
    attributes = dict(event.attributes or {})
    cleaned = {key: _redact(value) for key, value in attributes.items()}
    if name == event.name and cleaned == attributes:
        return event
    return Event(name=name, attributes=cleaned, timestamp=event.timestamp)  # type: ignore[arg-type]


class RedactingSpanExporter(SpanExporter):
    """Strips credentials from span attributes **and events** at the **export boundary**.

    Deliberately here rather than in a `server_request_hook`. A hook does work today -
    the instrumentation sets `http.url` before calling it, so an override wins - but that
    is an ordering guarantee no library promises, and this file already documents two
    upstream ordering footguns that silently dropped spans (`build_middleware_stack`
    caching, and `SQLAlchemyInstrumentor`'s process-wide singleton). A leak that returns
    silently on a dependency bump is worse than one that never existed, and export is the
    one point every span from every instrumentation must pass through - including
    SQLAlchemy's, the manual `traced_span()` wrappers, and anything added later.
    """

    def __init__(self, inner: SpanExporter) -> None:
        self._inner = inner

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._inner.export([self._redacted(span) for span in spans])

    @staticmethod
    def _redacted(span: ReadableSpan) -> ReadableSpan:
        attributes = dict(span.attributes or {})
        cleaned = {key: _redact(value) for key, value in attributes.items()}
        events = tuple(span.events or ())
        # Tuple equality falls through to identity per element, and `_redacted_event` returns
        # its argument unchanged when nothing matched - so this is the same "rebuild nothing
        # unless something actually leaked" fast path the attributes have, widened to cover
        # both surfaces. Checking attributes alone is what let DRIFT-82 survive: a span with
        # clean attributes and a credential-bearing event returned here, unredacted.
        redacted_events = tuple(_redacted_event(event) for event in events)
        if cleaned == attributes and redacted_events == events:
            return span
        return ReadableSpan(
            name=span.name,
            context=span.get_span_context(),
            parent=span.parent,
            resource=span.resource,
            attributes=cleaned,  # type: ignore[arg-type]
            events=redacted_events,
            links=span.links,
            kind=span.kind,
            status=span.status,
            start_time=span.start_time,
            end_time=span.end_time,
            instrumentation_scope=span.instrumentation_scope,
        )

    def shutdown(self) -> None:
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._inner.force_flush(timeout_millis)


def build_tracer_provider(
    *, service_name: str, span_exporter: SpanExporter | None = None, otlp_endpoint: str = ""
) -> TracerProvider:
    """`span_exporter` is an explicit override for tests (an `InMemorySpanExporter`,
    exported synchronously via `SimpleSpanProcessor` so a test can assert on it
    immediately without a manual flush) - production callers pass `otlp_endpoint`
    instead and get a real `OTLPSpanExporter` batched via `BatchSpanProcessor`.

    Both branches are wrapped in `RedactingSpanExporter`, so a test asserting on the
    in-memory exporter is asserting on the same redaction production gets. Wrapping only
    the production branch would make the test path structurally unable to catch a
    regression in the thing it exists to check.
    """
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    if span_exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(RedactingSpanExporter(span_exporter)))
    else:
        exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(RedactingSpanExporter(exporter)))
    return provider


def configure_tracing_provider(
    *, service_name: str, otlp_endpoint: str, enabled: bool
) -> TracerProvider | None:
    """Builds the provider and instruments FastAPI - must run at **module level**,
    before `app = FastAPI(...)` (i.e. before `lifespan` ever runs). Confirmed live
    against Jaeger in S31: Starlette's `Starlette.__call__` builds and caches `self.
    middleware_stack` on the very *first* ASGI call it receives - and that first call
    is the `"lifespan"` scope's own startup message, which is what invokes our
    `lifespan` async generator in the first place. `FastAPIInstrumentor.
    instrument_app` works by monkey-patching `app.build_middleware_stack`; patching it
    from inside `lifespan` patches the method *after* Starlette already called and
    cached the unpatched one, so the OTel middleware silently never wraps any real
    request (DB/LangGraph spans appeared, but no parent FastAPI span).

    `SQLAlchemyInstrumentor` doesn't share this problem - it instruments specific
    `Engine` instances handed to it directly, so it stays lifespan-scoped (`instrument_
    sqlalchemy_engines`) since only there do those per-lifespan engines exist. See that
    function's docstring for a *different* footgun it has instead.
    """
    if not enabled:
        return None
    provider = build_tracer_provider(service_name=service_name, otlp_endpoint=otlp_endpoint)
    trace.set_tracer_provider(provider)
    global _tracer
    _tracer = trace.get_tracer("intellichoice")
    return provider


# The health endpoints, excluded from tracing (AUD-F-30). `excluded_urls` is matched by
# OTel as a comma-separated list of regexes against the request path, so these are
# substrings and not anchored patterns.
#
# Measured, not assumed: **2,394 traces in an idle hour and every one of them was
# `GET /readyz`** - two ALB checks every 15s per task, times however many tasks. That put
# recorded traces at ~1.7M/month against X-Ray's 100k free tier (~17x, ~$8/month), and the
# comment in variables.tf claiming the free tier covered it was written when it did.
#
# The cost is the smaller half. The corpus is criterion 9's evidence base, and a scan
# reporting "2,747 traces CLEAN" reads as breadth when ~97% of it is the same three-span
# health check repeated. Excluding these makes the denominator mean what a reader assumes.
#
# `/metrics` is deliberately NOT excluded: it is not routed at the edge and is not polled
# on a timer, so it contributes no volume, and if something ever does scrape it that is
# worth seeing in a trace.
HEALTH_ENDPOINT_URLS = "healthz,readyz"


def instrument_fastapi_app(app: FastAPI, provider: TracerProvider) -> None:
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls=HEALTH_ENDPOINT_URLS
    )


def instrument_sqlalchemy_engines(*engines: AsyncEngine, provider: TracerProvider) -> None:
    """Instruments every given engine in **one** call. `SQLAlchemyInstrumentor` is a
    process-wide singleton (`BaseInstrumentor.instrument()` guards its real
    `_instrument()` behind an `_is_instrumented_by_opentelemetry` flag) - calling
    `.instrument(engine=...)` a second time for a second engine is a silent no-op,
    dropping that engine's spans entirely
    (open-telemetry/opentelemetry-python-contrib#1103). Both apps' `lifespan` now
    construct two engines (the app's own Postgres engine, and `MySQLProfileAdapter.
    engine`) - pass both here together via the library's own `engines=[...]` kwarg,
    never via two separate calls.
    """
    if not engines or SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry:
        return
    SQLAlchemyInstrumentor().instrument(
        engines=[engine.sync_engine for engine in engines], tracer_provider=provider
    )


@contextmanager
def traced_span(name: str, **attributes: str | int | float | bool) -> Iterator[None]:
    """Manual span for a hop OTel has no auto-instrumentation for (LangGraph node
    execution, the Bedrock gateway, MCP tool calls). A no-op
    (`NoOpTracerProvider`) when tracing was never configured (e.g. under `pytest` without
    `configure_tracing_provider` having run) - safe to sprinkle at any call site
    unconditionally.
    """
    with _tracer.start_as_current_span(name, attributes=attributes):
        yield


def traced_node(
    span_name: str,
) -> Callable[[Callable[..., Awaitable[_StateT]]], Callable[..., Awaitable[_StateT]]]:
    """Wraps a LangGraph node function with a span named after the node - applied at
    `graph.add_node(name, traced_node(f"langgraph.{name}")(fn))` registration time
    (`graph/build.py`), never by editing the node function bodies themselves. Node
    bodies are exactly the code D-021 documents two real interrupt/resume replay bugs
    in; a decorator that only wraps the call, changing nothing about arguments, control
    flow, or return value, carries none of that risk, unlike hand-editing each body.
    """

    def decorator(
        fn: Callable[..., Awaitable[_StateT]],
    ) -> Callable[..., Awaitable[_StateT]]:
        @functools.wraps(fn)
        async def wrapper(*args: object, **kwargs: object) -> _StateT:
            with traced_span(span_name):
                return await fn(*args, **kwargs)

        return wrapper

    return decorator


def current_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")
