"""Deterministic Gmail admin-escalation draft (SPEC §5.24.1) - a fixed template, not an
LLM call, mirroring `learning_api.services.attendance.build_attendance_email_draft`'s
shape (no new `BedrockTask` needed just to fill in a template).
"""

from typing import Literal

from pydantic import BaseModel

# Defensive cap on the constructed body - independent of `AskMessageRequest.query`'s own
# 2000-char bound, since the draft also appends `missing_information` and a template
# wrapper (SPEC §5.24.2 "maximum body length").
_MAX_BODY_LENGTH = 4000

# D-221: which of the two paths into `prepare_admin_escalation` built this draft. The
# distinction is not "what did the user want" - it is *what does this system actually
# know*, which is a narrower thing and the only honest basis for a sentence an
# administrator will act on.
#
#   user_escalated   - `QAState.escalate` came in on the request. A real, recorded user
#                      action (chat-web's "Contact an administrator" button on a no-source
#                      refusal), so the assistant-could-not-answer reason is a fact.
#   assistant_routed - the scope guard classified the turn `admin_contact`. That is a
#                      *model* decision, and it is measurably not always the user's: live
#                      on 2026-08-08, "My kid got marked absent by mistake - how do I fix
#                      that?" routed here and the draft told the administrator the user had
#                      "asked to be put in touch with an administrator", which they had not.
EscalationOrigin = Literal["user_escalated", "assistant_routed"]


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
    *,
    query: str,
    missing_information: str | None,
    user_role: str,
    chat_session_id: str,
    origin: EscalationOrigin,
) -> EmailDraftState:
    """`origin` distinguishes the two ways this draft gets built (D-219, corrected by D-221).

    The body used to open with "asked a question the assistant could not answer" for *every*
    escalation - including the `admin_contact` path, where the user simply asked to be put in
    touch and the assistant answered them correctly. Walked on staging 2026-08-08: "Please
    send a message to an administrator asking about volunteer training dates" produced a draft
    telling the administrator the assistant had failed. The administrator reads this line to
    decide how to reply, so a wrong reason is worse than a vague one.

    D-221 is the same lesson applied to D-219's own fix, which turned out to be inert. Its
    discriminator (`state.intent == "admin_contact"`) is set on *both* paths - `resolve_role`
    writes that intent for an escalate request too (D-164) - so the branch below that names
    the failure was unreachable through the graph, and every escalation email claimed the
    user had asked to be put in touch. See `prepare_admin_escalation` for the wiring and
    `test_the_node_picks_the_origin_from_the_request_not_from_the_intent` for the proof.

    The wording changed as well as the wiring, because "asked to be put in touch with an
    administrator" is not something this system knows on the routed path - it is what a
    classifier inferred, and the sweep that measured the scope guard caught it inferring
    wrong. The opening now reports the *system's* action, which is true whether or not the
    classification was right. `user_escalated` keeps naming the failure: there the reason is
    recorded rather than inferred, and it is the one signal telling an administrator the
    corpus has a gap.

    `origin` is deliberately required and deliberately not a bool: a new call site has to
    say which path it is on, and neither value is the "default" that a forgotten argument
    would quietly assert.
    """
    subject = f"IntelliChoice Q&A escalation - session {chat_session_id}"
    opening = (
        f"A user (role: {user_role}) asked a question the assistant could not answer:"
        if origin == "user_escalated"
        else (
            f"A user (role: {user_role}) asked the assistant this, and the assistant "
            f"routed it to an administrator:"
        )
    )
    lines = [
        opening,
        "",
        f"Question: {query}",
    ]
    if missing_information:
        lines.append(f"Missing information: {missing_information}")
    lines.append("")
    lines.append(f"Chat session: {chat_session_id}")
    body = "\n".join(lines)[:_MAX_BODY_LENGTH]
    return EmailDraftState(subject=subject, body=body)
