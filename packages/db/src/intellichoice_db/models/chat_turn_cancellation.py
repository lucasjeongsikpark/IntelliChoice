"""Turn-scoped cancellation requests for in-flight chat turns (D-402).

**Why a table and not a signal.** Pressing Stop in chat-web aborted the client's fetch and
nothing else: uvicorn does not cancel a request handler when the client disconnects (measured
directly - a handler with a hung-up client reports `ran-to-completion`), so the graph kept
running under its 50s deadline holding the per-session advisory lock, and the visitor's *next*
question was refused with "This conversation is already working on a question."

The cancel arrives as a **separate HTTP request**, and chat-api runs up to three ECS tasks
behind an ALB, so the signal has to be visible to a different process than the one that
receives it. That rules out an in-process flag. It also argues against reusing
`ChatSessionEventRelay`'s `LISTEN`/`NOTIFY`, which is deliberately fire-and-forget (see its own
docstring): a dropped notification there costs one live update, and a dropped *cancellation*
costs the thing the feature exists to deliver - the lock stays held and the visitor still waits.
A committed row is visible to every replica by construction.

**Keyed by `(chat_session_id, client_turn_id)`, not by session.** Cancelling "whatever is
running on this session" is ambiguous the moment a retry is in flight: the visitor's Stop is
about the turn they were watching, and a session-scoped flag would also kill the turn they
started next. `client_turn_id` already exists on the wire (D-348) and is already echoed on every
snapshot, so the identifier the client would use is the one it already has.

**No PII.** Both columns are opaque ids the client mints; neither is parsed or interpreted here.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base


class ChatTurnCancellation(Base):
    __tablename__ = "chat_turn_cancellations"

    # The LangGraph thread id. Composite primary key with the turn id: one row per turn, and
    # a repeated Stop on the same turn is an idempotent no-op rather than a second row.
    chat_session_id: Mapped[str] = mapped_column(String, primary_key=True)
    # Bounded at 64 to match `AskMessageRequest.client_turn_id`'s own limit - the server never
    # mints one, so anything longer could only come from a caller ignoring that contract.
    client_turn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Used only for pruning. A cancellation for a turn that was never running - a Stop that
    # raced the turn's own completion - has nobody to observe and delete it, so
    # `request_cancellation` sweeps this session's stale rows as it writes.
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
