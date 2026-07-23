import io
import json
import logging

from intellichoice_observability.logging_config import (
    REDACTED_MARKER,
    JsonLogFormatter,
    PiiDenylistFilter,
    configure_logging,
)


def _make_logger(stream: io.StringIO) -> logging.Logger:
    logger = logging.getLogger(f"test.{id(stream)}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(PiiDenylistFilter())
    logger.addHandler(handler)
    return logger


def test_json_formatter_emits_the_spec_shape() -> None:
    stream = io.StringIO()
    logger = _make_logger(stream)

    logger.info(
        "learning_answer_submitted",
        extra={
            "student_id_hash": "hashed-id",
            "session_id": "session-id",
            "question_id": "question-id",
            "is_correct": False,
            "latency_ms": 251,
        },
    )

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "learning_answer_submitted"
    assert payload["level"] == "INFO"
    assert payload["student_id_hash"] == "hashed-id"
    assert payload["is_correct"] is False
    assert payload["latency_ms"] == 251
    assert "timestamp" in payload


def test_denylisted_field_is_redacted_not_dropped() -> None:
    stream = io.StringIO()
    logger = _make_logger(stream)

    logger.info(
        "chat_turn",
        extra={"session_id": "session-id", "email": "student@example.com"},
    )

    payload = json.loads(stream.getvalue())
    assert payload["email"] == REDACTED_MARKER
    assert "student@example.com" not in stream.getvalue()
    assert payload["session_id"] == "session-id"


def test_every_spec_5_32_3_denylisted_field_is_caught() -> None:
    """Regression gate for SPEC §5.32.3's literal "do not log" list."""
    stream = io.StringIO()
    logger = _make_logger(stream)

    denylisted_examples = {
        "student_name": "Jane Doe",
        "email": "jane@example.com",
        "precise_location": "40.7128,-74.0060",
        "image_bytes": b"...".hex(),
        "full_prompt": "You are a tutor...",
        "chat_transcript": "student: hi\ntutor: hello",
        "oauth_token": "ya29.abc123",
    }
    logger.info("audit_event", extra=denylisted_examples)

    payload = json.loads(stream.getvalue())
    for key, original_value in denylisted_examples.items():
        assert payload[key] == REDACTED_MARKER, key
        assert str(original_value) not in stream.getvalue()


def test_safe_curriculum_content_fields_are_not_denylisted() -> None:
    """D-011's precedent: `name`-shaped keys that hold lesson content, not people's
    names, must not be swept up by the same denylist."""
    stream = io.StringIO()
    logger = _make_logger(stream)

    logger.info(
        "question_generated",
        extra={"topic_id": "linear_equations", "skill_name": "linear_one_step"},
    )

    payload = json.loads(stream.getvalue())
    assert payload["topic_id"] == "linear_equations"
    assert payload["skill_name"] == "linear_one_step"


def test_configure_logging_disables_uvicorns_raw_access_logger() -> None:
    """D-032: uvicorn's own access logger logs the full raw request line, query string
    included - exactly what would leak an SSE `?token=` bearer value."""
    configure_logging.cache_clear()
    configure_logging()
    assert logging.getLogger("uvicorn.access").disabled is True
