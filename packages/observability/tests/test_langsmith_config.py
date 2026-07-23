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
