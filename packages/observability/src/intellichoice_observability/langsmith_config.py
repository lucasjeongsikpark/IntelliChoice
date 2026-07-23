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
