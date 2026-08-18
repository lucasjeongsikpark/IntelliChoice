"""The sink for browser-side crashes in the **anonymous-first** app (D-322 §2, option A).

learning-api has had one since D-328. chat-web's `ErrorBoundary` has been console-only, and its
docstring said exactly why rather than shrugging: *"chat's primary caller is anonymous (SPEC
§5.19.1), so the majority of chat crashes would have no token to attribute and would be dropped
by the same rule. A sink worth building for this app needs a different authentication answer,
which is a decision this component must not make on its own."*

This is that answer. Everything about redaction, truncation and the accepted field set is copied
deliberately from `learning_api.routers.client_errors` — read that module for why each of those
is the way it is. **Only the gate differs**, and that is what this docstring is about.

**The gate: optional token, two buckets, and one of them is shared.**

A bearer token is *optional* here because requiring it would drop most of the crashes this
endpoint exists to see. A present-but-invalid token still 401s, which is `get_optional_claims`'s
existing contract everywhere else in this app — a client with an expired token gets a clear
signal instead of silently downgrading to anonymous.

That leaves the question a token was answering: what stops this being an open log-injection
endpoint? The rate limit, and it has to be built so that it cannot be walked around:

- **Authenticated reports are keyed on `sub`**, 20/minute — the same key and figure as learning,
  for the same reason (a classroom behind one school NAT shares an IP, so a per-IP key would let
  one student's crash loop throttle their classmates).
- **Anonymous reports share a single app-wide bucket**, 60/minute.

**Why shared rather than per `chat_session_id`, which is the tempting design.** An anonymous
caller can put any string in that field — it is not verified here and could not be cheaply, since
session state lives in the LangGraph checkpoint and this is an error path that must not add a
database read. A per-id bucket would therefore hand an attacker a fresh 20/minute allowance for
every id they invent, which is not a rate limit at all. One shared bucket cannot be evaded by
forging ids.

**What that costs, stated rather than buried:** two unrelated visitors crashing in the same
minute compete for the same allowance, so a real report can be dropped because of someone else's
loop. That is the safe direction — the failure mode is a missing log line, never an amplified
one — and 60/minute is far above the rate at which real, distinct visitors crash on a service
this size. It is a weaker gate than learning's and is not claimed to be equivalent.

`chat_session_id` is still accepted, and only as a **correlation** field: logged so a crash can be
joined to a conversation, never trusted, and never used as a limit key.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from intellichoice_shared.auth import TokenClaims
from intellichoice_shared.pii_redaction import redact_free_text
from intellichoice_shared.rate_limit import InMemoryRateLimiter
from pydantic import BaseModel, Field

from chat_api.dependencies import get_optional_claims

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/client-errors", tags=["chat-client-errors"])

# Same figures as learning's, for the same measured reason: `ErrorBoundary`'s captured stacks run
# ~400-900 characters, so this holds a real component trace and refuses a question stem, a
# serialized payload or a pasted transcript.
MAX_MESSAGE_CHARS = 500
MAX_STACK_CHARS = 2_000

_TRUNCATION_MARKER = "…[truncated]"

_REPORTS_PER_MINUTE_PER_TOKEN = 20
_ANONYMOUS_REPORTS_PER_MINUTE = 60

# The single key every anonymous report shares. A constant, which is the whole point - see this
# module's docstring for why a per-`chat_session_id` bucket would be forgeable and therefore not
# a limit.
_ANONYMOUS_BUCKET = "anonymous"

_token_limiter = InMemoryRateLimiter(max_per_window=_REPORTS_PER_MINUTE_PER_TOKEN, window_s=60.0)
_anonymous_limiter = InMemoryRateLimiter(
    max_per_window=_ANONYMOUS_REPORTS_PER_MINUTE, window_s=60.0
)


class ClientErrorRequest(BaseModel):
    # `forbid` rather than the default: an unknown field is a client sending something this
    # endpoint never agreed to receive, and silence is how that becomes a PII path later.
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1)
    stack: str | None = None
    # Optional because a crash before the first request has no trace to join to.
    trace_id: str | None = Field(default=None, max_length=64)
    # Correlation only. Bounded because it is unverified free text from an anonymous caller.
    chat_session_id: str | None = Field(default=None, max_length=64)


class ClientErrorResponse(BaseModel):
    recorded: bool


def _scrub(text: str, limit: int) -> str:
    """Redact what the patterns catch, then bound what they cannot.

    Order matters: truncating first could cut an email in half and leave a fragment the regex no
    longer matches, so redaction runs on the whole string and truncation second.
    """
    redacted = redact_free_text(text)
    if len(redacted) <= limit:
        return redacted
    return redacted[: limit - len(_TRUNCATION_MARKER)] + _TRUNCATION_MARKER


@router.post("", response_model=ClientErrorResponse, status_code=status.HTTP_202_ACCEPTED)
async def record_client_error(
    payload: ClientErrorRequest,
    request: Request,
    claims: Annotated[TokenClaims | None, Depends(get_optional_claims)],
) -> ClientErrorResponse:
    """**202, not 201.** Nothing is created and the client must not wait on or retry this: a
    crash reporter that retries turns one broken render into a burst.
    """
    if claims is not None:
        allowed = await _token_limiter.allow(claims.sub)
    else:
        allowed = await _anonymous_limiter.allow(_ANONYMOUS_BUCKET)
    if not allowed:
        # Dropped rather than queued: a crash loop's tenth identical stack says nothing the
        # first one did not. `Retry-After` so a client that does retry backs off correctly.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many client error reports; the first reports already described this",
            headers={"Retry-After": "60"},
        )
    logger.error(
        "client_error",
        extra={
            # `sub` when there is one and `None` when there is not - never a name, and never a
            # substitute identifier invented for anonymous callers. SPEC §5.30's
            # external-id-only rule applies to logs, and "anonymous" is a truthful value here.
            "caller_external_id": claims.sub if claims is not None else None,
            "is_anonymous": claims is None,
            "client_message": _scrub(payload.message, MAX_MESSAGE_CHARS),
            "client_stack": _scrub(payload.stack, MAX_STACK_CHARS) if payload.stack else None,
            "client_trace_id": payload.trace_id,
            # Correlation only; unverified by construction (see the module docstring).
            "chat_session_id": payload.chat_session_id,
            "user_agent": request.headers.get("user-agent", "")[:200],
        },
    )
    return ClientErrorResponse(recorded=True)
