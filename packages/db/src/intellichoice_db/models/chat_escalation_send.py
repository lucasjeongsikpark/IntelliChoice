"""One row per escalation actually emailed to staff, so the same one is not emailed twice (D-421).

**What a duplicate is here.** The visitor presses "Ask an administrator", approves the draft, and
the email goes. Then nothing visibly happens — no reply arrives in the chat, because a human replies
by email hours later — so they press it again. Staff receive the same question twice, from a channel
that exists precisely because they are the fallback. The rate limiter bounds *volume* and cannot see
that two sends are the same send; that is this table's whole job.

**A fingerprint, never the question.** The column stores a SHA-256 of the normalised question rather
than the text, because equality is the only thing this table needs to decide and storing the text
would put visitor free text into a new table for no gain (SPEC §5.30). The question is already
redacted by the time anything here sees it, so this is depth rather than the only control.

**Keyed on the question, not on the question *and* the note.** A second note on the same
question is suppressed, and that is the deliberate side of the trade: keying on the note too
would let any caller defeat the check by adding a space, which is the failure mode worth
preventing. The visitor is told the question has already gone rather than being silently
ignored — see `EMAIL_ALREADY_SENT_MESSAGE`.

**Scoped per session.** Two different visitors asking the same thing are two requests a human should
see, not a duplicate.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base


class ChatEscalationSend(Base):
    __tablename__ = "chat_escalation_sends"

    chat_session_id: Mapped[str] = mapped_column(String, primary_key=True)
    #: SHA-256 hex of the normalised question. 64 chars, fixed by the digest rather than by a
    #: guess about how long a question is.
    question_fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
