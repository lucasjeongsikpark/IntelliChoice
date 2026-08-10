"""SPEC §5.32.1 LangSmith wiring. `langgraph`/`langchain-core`'s own tracer picks up
`LANGSMITH_TRACING`/`LANGSMITH_API_KEY`/`LANGSMITH_PROJECT` from the process environment
automatically (no code-level client to construct or pass through `ainvoke`) - this module
only decides *whether* to turn that on and, if so, forces the masking SPEC §5.32.1
requires for the Cloud option ("complete PII masking").

**No real LangSmith account exists for this project** (D-002's posture, same as every
other external dependency) - `LANGSMITH_API_KEY` is unset in dev/tests, so
`configure_langsmith()` is a no-op and this path is wired but unexercised, same footing as
D-025 (`AnthropicBedrockProvider`)/D-035 (`TitanEmbeddingProvider`). SPEC §5.32.1's
self-hosted-vs-cloud choice itself needs contractual review before real minor data ever
reaches either option - not decided here, and not something a code change can decide.
"""

import os

from intellichoice_observability.tracing import current_trace_id


def configure_langsmith() -> bool:
    """Returns whether LangSmith tracing was actually enabled (for a startup log line).
    Forces `LANGSMITH_HIDE_INPUTS`/`LANGSMITH_HIDE_OUTPUTS=true` whenever an API key is
    present - full masking, not a selective redaction callable, since env-var-driven
    tracing (the only way `langgraph`'s default tracer picks up a client) only supports
    the boolean form (see `langsmith.utils.get_env_var`), and this project has no
    contractually-reviewed basis yet for judging any subset of a prompt/trace "safe" to
    send unmasked to LangSmith Cloud.
    """
    if not os.environ.get("LANGSMITH_API_KEY"):
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", "intellichoice")
    os.environ["LANGSMITH_HIDE_INPUTS"] = "true"
    os.environ["LANGSMITH_HIDE_OUTPUTS"] = "true"
    return True


def langsmith_correlation_metadata() -> dict[str, str]:
    """The active OTel `trace_id`, shaped for a LangSmith run's `metadata` (D-242).

    **Why the two legs needed joining.** System telemetry (X-Ray spans, CloudWatch log
    lines) and AI telemetry (LangGraph node trees) are the same request seen two ways, and
    until this they shared no identifier. `logging_config` stamps `trace_id` on every log
    line and X-Ray keys on the same value, so those two join; a LangSmith run carried
    nothing, so getting from a slow span to *that request's* node tree meant matching on
    timestamp - which stops working the moment two students are active at once, and is
    worst exactly when you need it most.

    Returned as metadata rather than a tag because LangSmith tags are a flat searchable set
    and a 32-hex id in that set is noise; metadata is the keyed field, and
    `metadata.otel_trace_id` is directly filterable in the LangSmith UI.

    **Empty dict, never `{"otel_trace_id": None}`.** Tracing is env-selected (D-002), so no
    active span is the normal case in dev and in every test. A null-valued key would put a
    dead field on every run and make "correlation missing" indistinguishable from
    "correlation is null", which is the distinction this exists to provide.

    Note this carries no PII and cannot: a `trace_id` is 16 random bytes. The masking
    `configure_langsmith` forces (`LANGSMITH_HIDE_INPUTS`/`_OUTPUTS`) is untouched by it -
    the join is on an id, not on payloads.
    """
    trace_id = current_trace_id()
    return {"otel_trace_id": trace_id} if trace_id is not None else {}
