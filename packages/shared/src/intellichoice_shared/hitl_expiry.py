"""How long a pending human-approval pause stays answerable (HB-CHAT-F1, D-459).

**The rule.** A pause that gates an *external action* - an email, a calendar event, the use
of a location - is treated as **declined** once it is older than `PENDING_APPROVAL_TTL`. The
user's decision (2026-09-27): a yes given a day later is not the yes the preview asked for.
The draft was composed for the question as it stood then, and SPEC §5.1.4's approval is
consent to *that* action, not an open cheque. Before this rule, `/respond` checked that the
session existed, that the caller owned it and that the discriminator matched - never how old
the pause was - so a stale approval stayed resumable indefinitely.

**Selection pauses never expire.** `child_selection` and `intervention_choice` choose what
the session *is* (whose session, which kind of help); neither sends anything anywhere, and
declining one on the student's behalf would be a decision with no safe default.

**Where the rule is applied is the routes' business, not this module's.** Both apps apply it
only on a mutation path, under the turn claim (D-346 / D-376), by resuming the pause with that
type's decline value - never by a fresh invoke, which would silently discard it (D-021 #2).
Nothing sweeps: an expired pause is cleared by the next turn that meets it.

**Fails open for the pause.** A missing or unparseable timestamp means "not expired": the
pause stays answerable exactly as it was before this rule existed, and the request carries
on. Crashing a request, or declining a consent, on a malformed timestamp would turn a
bookkeeping anomaly into a user-visible failure. It is logged at WARNING so the anomaly is
seen rather than silently tolerated.

The age is read off the paused checkpoint (`StateSnapshot.created_at`, which LangGraph writes
as an ISO-8601 UTC timestamp), so the rule needs no column and no migration.
"""

import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

PENDING_APPROVAL_TTL = timedelta(hours=24)

#: The `interrupt()` types that gate an external action. Chat raises all three; learning
#: raises `email_approval` only.
EXPIRING_INTERRUPT_TYPES = frozenset({"email_approval", "calendar_action", "location_consent"})


def pause_age(created_at: str | None, *, now: datetime) -> timedelta | None:
    """`now - created_at`, or None (logged at WARNING) when `created_at` is missing or is
    not an ISO-8601 timestamp. A timestamp with no offset is read as UTC, which is what the
    checkpointer writes.
    """
    if now.tzinfo is None:
        # A caller bug, not request data: an aware/naive subtraction would raise anyway,
        # and an explicit message beats a TypeError from inside the arithmetic.
        raise ValueError("now must be timezone-aware")
    if created_at is None:
        logger.warning("hitl_pause_timestamp_invalid", extra={"reason": "missing"})
        return None
    try:
        started = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        # The value itself is not logged: it is not expected to carry anything sensitive,
        # but a log line needs only the fact, and "no free text" is the easier rule to keep.
        logger.warning("hitl_pause_timestamp_invalid", extra={"reason": "unparseable"})
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return now - started


def pause_expired(created_at: str | None, *, now: datetime, interrupt_type: str) -> bool:
    """Whether a pause of `interrupt_type` that began at `created_at` is past its TTL.

    Strictly *older than* the TTL: a pause exactly 24 h old is still answerable. Always
    False for a type outside `EXPIRING_INTERRUPT_TYPES`, and False for a missing or
    unparseable timestamp (see the module docstring for why that fails open).
    """
    if interrupt_type not in EXPIRING_INTERRUPT_TYPES:
        return False
    age = pause_age(created_at, now=now)
    return age is not None and age > PENDING_APPROVAL_TTL
