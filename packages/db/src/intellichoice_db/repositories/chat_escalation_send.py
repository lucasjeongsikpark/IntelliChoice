"""Claim-or-refuse for escalation emails (D-421). See the model for what a duplicate is here."""

import hashlib
import re
from datetime import timedelta

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from intellichoice_db.models.chat_escalation_send import ChatEscalationSend

#: How long the same question stays "already sent" for this session.
#:
#: One hour is chosen against two failure modes rather than picked. Too short and the case this
#: exists for slips through - a visitor who sees no reply and presses the button again a few minutes
#: later. Too long and a legitimate follow-up is silently swallowed: "I asked yesterday and nobody
#: replied" is a *different* request to a human, and suppressing it would make this table worse than
#: the duplicate it prevents.
DEDUPE_WINDOW = timedelta(hours=1)

_WHITESPACE = re.compile(r"\s+")


def fingerprint(question: str) -> str:
    """A stable digest of the question, insensitive to whitespace and case.

    Normalised because the two sends this catches are the *same* question retyped or re-submitted,
    and "Who do I ask about billing?" differing from "who do i ask about billing?" would defeat the
    check for no reason. Deliberately nothing cleverer than that: stemming or embedding similarity
    would make "is this a duplicate" a judgement, and a judgement that suppresses a message to a
    human is the wrong place for one.
    """
    normalised = _WHITESPACE.sub(" ", question).strip().casefold()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


class ChatEscalationSendRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def claim(self, *, chat_session_id: str, question: str) -> bool:
        """Reserve this question for sending. `True` means send it; `False` means it already went.

        A claim rather than a check-then-write, because two replicas can be resuming approvals at
        the same moment: `ON CONFLICT DO NOTHING` with `RETURNING` makes the database the arbiter,
        so exactly one caller is told to send. A separate SELECT would let both read "absent" and
        both send, which is the defect this table exists to prevent, reintroduced by the shape of
        its own check.

        **The sweep is global from the start** (D-416's lesson, applied rather than repeated): a
        per-session sweep only ever reaps sessions that come back, so rows for sessions that never
        return would accumulate with nothing able to reach them. Any claim reaps every expired row,
        which also means an expired row for *this* session is gone before the insert - so the window
        is enforced by deletion rather than by a timestamp comparison the insert would have to make.
        """
        digest = fingerprint(question)
        async with self._session_factory() as session:
            await session.execute(
                delete(ChatEscalationSend).where(
                    ChatEscalationSend.sent_at < func.now() - DEDUPE_WINDOW
                )
            )
            claimed = await session.scalar(
                pg_insert(ChatEscalationSend)
                .values(chat_session_id=chat_session_id, question_fingerprint=digest)
                .on_conflict_do_nothing(index_elements=["chat_session_id", "question_fingerprint"])
                .returning(ChatEscalationSend.question_fingerprint)
            )
            await session.commit()
            return claimed is not None

    async def release(self, *, chat_session_id: str, question: str) -> None:
        """Give the claim back when the send did not happen.

        Called when Gmail fails. Without this, a transient MCP failure would leave the question
        marked as sent for an hour, so the visitor's retry - which SPEC §5.29's "preserve draft"
        exists to make possible, and which `EMAIL_FAILED_MESSAGE` explicitly invites - would be
        refused as a duplicate of an email nobody received. A claim reserves the *send*, so it has
        to be surrendered when the send does not occur.
        """
        async with self._session_factory() as session:
            await session.execute(
                delete(ChatEscalationSend).where(
                    ChatEscalationSend.chat_session_id == chat_session_id,
                    ChatEscalationSend.question_fingerprint == fingerprint(question),
                )
            )
            await session.commit()
