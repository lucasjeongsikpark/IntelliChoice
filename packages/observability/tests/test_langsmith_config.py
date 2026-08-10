import pytest
from intellichoice_observability.langsmith_config import configure_langsmith

_LANGSMITH_ENV_VARS = (
    "LANGSMITH_API_KEY",
    "LANGSMITH_TRACING",
    "LANGSMITH_PROJECT",
    "LANGSMITH_HIDE_INPUTS",
    "LANGSMITH_HIDE_OUTPUTS",
)


@pytest.fixture(autouse=True)
def _clean_langsmith_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _LANGSMITH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_no_op_without_a_real_api_key() -> None:
    """No real LangSmith account exists for this project (D-002) - the default dev/test
    environment must never silently start tracing."""
    assert configure_langsmith() is False
    import os

    assert "LANGSMITH_TRACING" not in os.environ


def test_enables_tracing_with_forced_masking_when_a_key_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "fake-test-key")

    assert configure_langsmith() is True

    import os

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "intellichoice"
    # SPEC §5.32.1: "LangSmith Cloud with complete PII masking" - not optional.
    assert os.environ["LANGSMITH_HIDE_INPUTS"] == "true"
    assert os.environ["LANGSMITH_HIDE_OUTPUTS"] == "true"


def test_a_langsmith_run_can_be_found_from_an_xray_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-242: the two observability legs must share one id, or neither can reach the other.

    `logging_config` already stamps `trace_id` into every structured log line and
    `tracing.current_trace_id()` already exposes it, so CloudWatch and X-Ray join on it.
    LangSmith did not: `configure_langsmith()` sets env vars and nothing else, so a run
    carried no reference to the request that produced it. When a turn is slow or its answer
    is wrong you could find the X-Ray span and the log lines and then have to match the
    LangGraph node tree **by timestamp**, which stops working the moment two students are
    active at once.

    `langsmith_correlation_metadata()` is what closes that, and it lives here rather than in
    each app because both apps assemble the same `RunnableConfig` (D-223: one rule, one
    implementation).
    """
    from intellichoice_observability.langsmith_config import langsmith_correlation_metadata
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer(__name__)
    with tracer.start_as_current_span("a-request"):
        metadata = langsmith_correlation_metadata()
        expected = format(
            trace.get_current_span().get_span_context().trace_id, "032x"
        )
    assert metadata == {"otel_trace_id": expected}
    assert len(expected) == 32, "X-Ray and the log lines both format it this way"


def test_correlation_metadata_is_empty_when_nothing_is_tracing() -> None:
    """Tracing is env-selected (`otel_enabled=False` in dev and every test), so the common
    case is no active span. That must produce **no** metadata key rather than a null one:
    a `RunnableConfig` carrying `{"otel_trace_id": None}` would put a dead field on every
    LangSmith run in dev and make a real correlation indistinguishable from a missing one.
    """
    from intellichoice_observability.langsmith_config import langsmith_correlation_metadata

    assert langsmith_correlation_metadata() == {}
