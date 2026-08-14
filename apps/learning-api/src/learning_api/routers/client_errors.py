"""The sink for browser-side crashes (U5, SPEC §5.32's client half).

**D-315 built both ends of this telemetry and deliberately left the middle.** `ErrorBoundary`
catches a render crash and `main.tsx` listens for uncaught errors and unhandled rejections - and
every one of them is written to a `console.error` in a browser nobody is watching. A student's
blank screen currently reaches no one, which is the one failure mode a parent notices and the
server cannot see.

**Why an endpoint here rather than Sentry** (D-322 §2): the alternative was a third-party
processor of minors' data, and this project's whole posture is that it does not add one for
convenience. What arrives here is bounded to three fields and passes the same redaction every
other log line does.

**What a crash report may contain, and what happens to it:**

- `message` and `stack` are free text from the browser, so they are **redacted and then
  truncated**, in that order. `redact_free_text` catches emails, URLs and phone numbers.
  Truncation is what bounds everything it cannot catch - most importantly a **question stem**,
  which is not PII-shaped and would sail through a regex screen. A stack frame naming a
  component is useful; a stack that has swallowed a whole question is a content leak, and length
  is the only property that reliably separates the two.
- `trace_id` is 16 random bytes and carries nothing. It is the point of the endpoint: it joins
  the crash to the server-side request that produced the page, which is the one thing a console
  log could never do.
- Nothing else is accepted. Pydantic's default `extra="ignore"` would silently drop unknown
  fields; `extra="forbid"` refuses them instead, so a future client that starts sending
  `student_name` gets a 422 rather than quiet acceptance.

The write goes through the app's configured logger, so `PiiDenylistFilter` screens the structured
keys as it does everywhere else. That filter is **key-based**, which is exactly why the two free
text fields need their own treatment above - it would pass a stack containing an email through
untouched, because the key is `stack` and not `email`.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from intellichoice_shared.auth import TokenClaims
from intellichoice_shared.pii_redaction import redact_free_text
from intellichoice_shared.rate_limit import InMemoryRateLimiter
from pydantic import BaseModel, Field

from learning_api.dependencies import get_current_claims

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning/client-errors", tags=["learning-client-errors"])

# Long enough for a real stack (a React component trace runs a few hundred characters), short
# enough that a question stem, a serialized payload, or a pasted transcript cannot ride along.
# Measured against the app's own boundary: `ErrorBoundary`'s captured stacks are ~400-900 chars.
MAX_MESSAGE_CHARS = 500
MAX_STACK_CHARS = 2_000

_TRUNCATION_MARKER = "…[truncated]"

# **Per token, and deliberately not the app's global middleware.** That middleware is keyed by
# `request.client.host` and capped at 6000/60s - a figure chosen as roughly 3x a legitimate burst
# across *all* traffic. Neither property fits a crash reporter: a render loop can emit thousands
# of reports and stay far under 6000, and a whole classroom behind one school NAT shares a single
# IP key, so one student's crash loop would throttle their classmates. Keying on `sub` makes the
# limit mean "this student's browser", which is the thing that can actually run away.
#
# 20/minute is generous for a human-triggered crash and hostile to a loop: `ErrorBoundary` fires
# once per failed render, so a student hitting this ceiling is already in a broken state that the
# first few reports have described. Dropping the rest costs nothing and bounds the log volume.
_REPORTS_PER_MINUTE = 20
_reporter_limiter = InMemoryRateLimiter(max_per_window=_REPORTS_PER_MINUTE, window_s=60.0)


class ClientErrorRequest(BaseModel):
    # `forbid` rather than the default: an unknown field is a client sending something this
    # endpoint never agreed to receive, and silence is how that becomes a PII path later.
    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1)
    stack: str | None = None
    # Optional because a crash before the first request has no trace to join to.
    trace_id: str | None = Field(default=None, max_length=64)


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
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
) -> ClientErrorResponse:
    """Authenticated so this cannot be an open log-injection endpoint, and rate-limited **per
    token** - see `_REPORTS_PER_MINUTE` for why the app's global per-IP middleware does not
    cover this case.

    **202, not 201.** Nothing is created and the client must not wait on or retry this: a crash
    reporter that retries turns one broken render into a burst.
    """
    if not await _reporter_limiter.allow(claims.sub):
        # 429 with the window, so a client that does retry backs off by the right amount. The
        # report is dropped rather than queued: a crash loop's tenth identical stack says nothing
        # the first one did not.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many client error reports; the first reports already described this",
            headers={"Retry-After": "60"},
        )
    logger.error(
        "client_error",
        extra={
            # `sub` rather than any name: SPEC §5.30's external-id-only rule applies to logs as
            # much as to Postgres, and it is what makes a crash attributable without being
            # identifying.
            "student_external_id": claims.sub,
            "client_message": _scrub(payload.message, MAX_MESSAGE_CHARS),
            "client_stack": _scrub(payload.stack, MAX_STACK_CHARS) if payload.stack else None,
            # The client's own trace id when it has one; the server's for this request otherwise,
            # so a report is never orphaned.
            "client_trace_id": payload.trace_id,
            "user_agent": request.headers.get("user-agent", "")[:200],
        },
    )
    return ClientErrorResponse(recorded=True)
