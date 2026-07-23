"""Deterministic Gmail admin-escalation draft (SPEC §5.24.1) - a fixed template, not an
LLM call, mirroring `learning_api.services.attendance.build_attendance_email_draft`'s
shape (no new `BedrockTask` needed just to fill in a template).
"""

from pydantic import BaseModel

# Defensive cap on the constructed body - independent of `AskMessageRequest.query`'s own
# 2000-char bound, since the draft also appends `missing_information` and a template
# wrapper (SPEC §5.24.2 "maximum body length").
_MAX_BODY_LENGTH = 4000


class EmailDraftState(BaseModel):
    """What actually gets checkpointed in `QAState.email_draft` - subject/body only,
    deliberately never a recipient. `QAState`'s own docstring states "no names or email
    addresses are stored here" (SPEC §5.30); the real `EmailMessage` (with
    `recipient=settings.admin_escalation_email`) is constructed at send time from
    config, never from anything checkpointed.
    """

    subject: str
    body: str


def build_escalation_draft(
    *, query: str, missing_information: str | None, user_role: str, chat_session_id: str
) -> EmailDraftState:
    subject = f"IntelliChoice Q&A escalation - session {chat_session_id}"
    lines = [
        f"A user (role: {user_role}) asked a question the assistant could not answer:",
        "",
        f"Question: {query}",
    ]
    if missing_information:
        lines.append(f"Missing information: {missing_information}")
    lines.append("")
    lines.append(f"Chat session: {chat_session_id}")
    body = "\n".join(lines)[:_MAX_BODY_LENGTH]
    return EmailDraftState(subject=subject, body=body)
