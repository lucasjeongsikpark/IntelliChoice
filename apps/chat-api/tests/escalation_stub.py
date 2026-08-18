"""A `TurnContext.escalation_sends` for turns that never escalate (D-421)."""

from intellichoice_db.repositories.chat_escalation_send import (
    ChatEscalationSendRepository,
)


class UnusedEscalationSends(ChatEscalationSendRepository):
    """A `TurnContext.escalation_sends` for turns that never escalate (D-421).

    Two things this is better than a real repository. It **creates no engine**, so building a
    context in a loop does not leak a connection pool per call - `rollback_session` above disposes
    the one it opens, and a helper that quietly opened undisposed ones alongside it is how a suite
    starts failing on connection exhaustion far from the change that caused it.

    And it **fails loudly if it is ever reached**. A context wired with this one is asserting that
    its turn does not escalate; if that stops being true, a test should say so rather than silently
    claim rows against the developer's database - where they would then persist past the
    surrounding `rollback_session`, because the real repository commits independently by design.
    """

    def __init__(self) -> None:  # deliberately does not call super().__init__
        pass

    async def claim(self, *, chat_session_id: str, question: str) -> bool:
        raise AssertionError(
            "this TurnContext was built for a turn that does not escalate, and it escalated"
        )

    async def release(self, *, chat_session_id: str, question: str) -> None:
        raise AssertionError(
            "this TurnContext was built for a turn that does not escalate, and it escalated"
        )
