"""SPEC §5.32.3 structured JSON logging. Every `logging.info("event_name", extra={...})`
call already used across this codebase (e.g. `ResilientBedrockGateway`'s `bedrock_call`)
maps directly onto this format - the message becomes the `"event"` field (the *template*
since D-394, not the interpolated result), and
whatever was passed via `extra=` becomes the rest of the payload, with `trace_id`/
`span_id` auto-injected from the active OpenTelemetry span so a log line and a trace span
for the same request can be correlated without every call site doing it by hand.

`PiiDenylistFilter` is the actual regression gate for SPEC §5.32.3's "do not log" list
(student name, email, precise location, images, entire prompts, entire chat transcripts,
OAuth tokens) - it redacts rather than raising, since a logging call must never crash the
request it's describing. It checks only top-level `extra` keys (D-011's exact-match, not
substring, precedent) - a call site that nests PII inside a dict value under an innocuous
key is not caught; call sites must keep `extra=` flat.
"""

import json
import logging
from datetime import UTC, datetime
from functools import lru_cache

from intellichoice_shared.pii_redaction import redact_free_text
from opentelemetry import trace

# Attributes `logging.LogRecord` always carries - excluded from the JSON payload so only
# fields a caller actually passed via `extra=` show up in it.
_STANDARD_LOG_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
    }
)

# SPEC §5.32.3's "do not log" list, translated into the snake_case field names a caller
# would plausibly pass via `extra=`. Exact-match denylist (D-011's precedent) so unrelated
# fields like `question_id`/`session_id`/`skill_name`... wait, `skill_name` deliberately
# isn't listed here since curriculum content names (topics/skills) aren't people's names,
# same distinction D-011 draws for `Topic.name`/`Skill.name`.
_DENYLISTED_LOG_KEYS = frozenset(
    {
        "name",
        "student_name",
        "parent_name",
        "guardian_name",
        "display_name",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "phone_number",
        "location",
        "precise_location",
        "latitude",
        "longitude",
        "coordinates",
        "image",
        "image_bytes",
        "image_data",
        "image_url",
        "photo",
        "prompt",
        "system_prompt",
        "full_prompt",
        "user_message",
        "transcript",
        "chat_transcript",
        "messages",
        "conversation",
        "chat_history",
        "token",
        "access_token",
        "refresh_token",
        "oauth_token",
        "id_token",
        "bearer_token",
        "authorization",
    }
)

REDACTED_MARKER = "[REDACTED:pii-denylist]"


class JsonLogFormatter(logging.Formatter):
    """**Two of these fields are free text, and `PiiDenylistFilter` cannot see either (D-394).**

    That filter matches top-level `extra` *keys*, which is the right shape for structured fields
    and no defence at all for text. Both gaps are closed here, in the one place every line in
    both apps passes through, rather than at the call sites - a call-site rule is vigilance, and
    the next call site is written by someone who has not read this docstring.

    - `exc_info` is skipped by the filter (it is a standard record attribute) and was then
      re-added verbatim. A Pydantic `ValidationError` embeds the offending input, which on a
      structured-output repair failure is model output derived from a student's question.
    - `event` used to be `record.getMessage()`, i.e. `%`-interpolated. **22 call sites** (counted
      with an AST sweep, after a regex said 13 and the live logs showed one it had missed) spell
      `logger.warning("...: %s", exc)`, so an exception's text landed in the field an operator
      groups by - unbounded cardinality *and* free text in one move.

    `redact_free_text` is a floor, not a guarantee: it knows emails, URLs and phone numbers, not
    arbitrary prose. That is this project's stated position on the redactor (SPEC §5.30.1) and
    the reason this is defence in depth behind "do not put text in logs", not a licence to.
    """

    def format(self, record: logging.LogRecord) -> str:
        # The static template, not the interpolated result. Call sites with no `%` args - the
        # overwhelming majority - are unchanged, because `record.msg` *is* the event name there.
        #
        # A non-`str` `msg` (`logger.error(exc)`) is dynamic by definition, so it is redacted
        # rather than trusted. The same AST sweep found no call site doing it - two pass a
        # variable holding a `%s` literal and one an f-string, all still `str` - so this branch
        # is defence in depth. Leaving the one place where `event` can hold arbitrary text
        # unredacted is how this field got here in the first place.
        event = record.msg if isinstance(record.msg, str) else redact_free_text(record.getMessage())
        payload: dict[str, object] = {
            "event": event,
            "level": record.levelname,
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "logger": record.name,
        }
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format(span_context.trace_id, "032x")
            payload["span_id"] = format(span_context.span_id, "016x")
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        # Only when there was something to interpolate, so no existing line gains a key.
        if record.args:
            payload["message"] = redact_free_text(record.getMessage())
        if record.exc_info:
            payload["exc_info"] = redact_free_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


class PiiDenylistFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__.keys()):
            if key in _STANDARD_LOG_RECORD_ATTRS or key.startswith("_"):
                continue
            if key in _DENYLISTED_LOG_KEYS:
                record.__dict__[key] = REDACTED_MARKER
        return True


@lru_cache
def configure_logging(*, level: str = "INFO") -> None:
    """Idempotent (`lru_cache`) so every app/worker can call this once at startup
    without worrying about double-attaching handlers on reload.

    Disables uvicorn's own plain-text access logger - it logs the full raw request
    line, query string included, which is exactly what leaks the SSE `?token=` bearer
    value (D-032). `request_logging.install_request_logging_middleware` is this
    project's replacement: a structured JSON line built from the route *template* only,
    never the raw URL.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(PiiDenylistFilter())
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").disabled = True
