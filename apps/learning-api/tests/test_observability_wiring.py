"""D-242: the OTel trace_id reaches the RunnableConfig LangSmith reads."""

from typing import Any, cast

from learning_api.routers.sessions import _graph_config


def test_the_graph_config_carries_the_trace_id_so_langsmith_can_be_joined() -> None:
    """D-242: the correlation is only real if it reaches the `RunnableConfig` the graph is
    actually invoked with - the helper existing proves nothing on its own.

    Both apps assemble this config for every `graph.ainvoke`, and LangSmith's tracer reads
    `metadata` off it, so this is the single seam where a run gains the id that X-Ray and
    every CloudWatch log line already carry.
    """
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer(__name__)

    without_span = cast(dict[str, Any], _graph_config("session-1"))
    assert without_span["configurable"]["thread_id"] == "session-1"
    assert "metadata" not in without_span, "no active span must add no dead field"

    with tracer.start_as_current_span("a-request"):
        with_span = cast(dict[str, Any], _graph_config("session-1"))
    assert with_span["configurable"]["thread_id"] == "session-1"
    assert len(with_span["metadata"]["otel_trace_id"]) == 32
