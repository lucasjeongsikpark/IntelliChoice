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


def test_a_traceback_is_redacted_before_it_reaches_the_payload() -> None:
    """D-394. `PiiDenylistFilter` matches *keys*, and a traceback is free text under a key it
    deliberately skips - `exc_info` is in `_STANDARD_LOG_RECORD_ATTRS`, so the filter passes over
    it and the formatter then re-added the whole formatted traceback verbatim.

    The realistic carrier is a Pydantic `ValidationError`, which embeds the offending input in
    its own message; on a structured-output repair failure (SPEC §5.25.3) that input is model
    output derived from a student's question. The 08-16 audit filed this as a hazard rather than
    a confirmed leak - the criterion-9 scan found 3,269 events clean - and a hazard in the one
    field no key-based rule can inspect is worth closing on its own.
    """
    stream = io.StringIO()
    logger = _make_logger(stream)

    try:
        raise ValueError("could not parse 'contact me at student@example.com or 555-123-4567'")
    except ValueError:
        logger.warning("structured_output_repair_failed", exc_info=True)

    log_output = stream.getvalue()
    assert "student@example.com" not in log_output
    assert "555-123-4567" not in log_output
    payload = json.loads(log_output)
    # Redacted, not dropped: the traceback is how an operator finds the failing frame, and the
    # marker says which kind of value was removed.
    assert "[redacted-email]" in payload["exc_info"]
    assert "[redacted-phone]" in payload["exc_info"]
    assert "ValueError" in payload["exc_info"]


def test_an_interpolated_log_message_keeps_a_stable_event_and_redacts_the_values() -> None:
    """D-394's other half. `record.getMessage()` applies `%`-interpolation, so the 13 call sites
    that spell `logger.warning("... : %s", exc)` put the exception's text into `event` itself -
    the one field an operator groups and filters by.

    Two costs, and both are fixed here rather than at those 13 sites, because a fix at the
    formatter also covers the fourteenth site someone writes next month. `event` becomes the
    static template, so `$.event` filters group correctly instead of splitting into one bucket
    per distinct value; the interpolated text moves to `message` and goes through
    `redact_free_text`, so a `str(exc)` carrying an email can no longer travel as part of the
    field name. A floor, not a guarantee - the redactor knows contact details, not arbitrary
    prose, which is the same caveat its own module states.
    """
    stream = io.StringIO()
    logger = _make_logger(stream)

    logger.warning(
        "hint_generation_fell_back: %s",
        "upstream rejected reply-to student@example.com",
    )

    log_output = stream.getvalue()
    assert "student@example.com" not in log_output
    payload = json.loads(log_output)
    assert payload["event"] == "hint_generation_fell_back: %s"
    assert payload["message"] == (
        "hint_generation_fell_back: upstream rejected reply-to [redacted-email]"
    )


def test_a_log_call_without_arguments_is_shaped_exactly_as_before() -> None:
    """The control for the test above, and the reason it is safe to change the formatter rather
    than the call sites: the overwhelming majority of this codebase's log calls pass a bare event
    name and everything else through `extra=`. Those must gain no `message` key and must keep
    the identical `event`, or every existing query changes meaning at once.
    """
    stream = io.StringIO()
    logger = _make_logger(stream)

    logger.info("bedrock_call", extra={"model_id": "haiku", "cost_cents": 0.4})

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "bedrock_call"
    assert "message" not in payload
    assert payload["model_id"] == "haiku"


def test_logging_an_exception_object_as_the_message_is_redacted_too() -> None:
    """The branch found while writing the two tests above, and closed rather than noted.

    `event` is the static template only when `record.msg` is a `str` literal from a call site.
    `logger.error(exc)` makes it an object, `getMessage()` stringifies it, and `record.args` is
    empty - so neither of the other two defences applies and arbitrary text lands in the grouping
    field. No call site does this today, which is exactly the argument for closing it now: the
    reason `exc_info` needed fixing is that a field nobody was watching went unexamined for months.
    """
    stream = io.StringIO()
    logger = _make_logger(stream)

    logger.error(ValueError("write to student@example.com"))

    assert "student@example.com" not in stream.getvalue()
    assert json.loads(stream.getvalue())["event"] == "write to [redacted-email]"


def test_configure_logging_disables_uvicorns_raw_access_logger() -> None:
    """D-032: uvicorn's own access logger logs the full raw request line, query string
    included - exactly what would leak an SSE `?token=` bearer value."""
    configure_logging.cache_clear()
    configure_logging()
    assert logging.getLogger("uvicorn.access").disabled is True
