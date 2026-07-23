from intellichoice_shared.email import EmailMessage


class FakeEmailTransport:
    """Dev/test `EmailTransport` (SPEC §5.24) - appends to an in-memory list instead of
    calling Gmail. Not persisted anywhere; a real client is selected by env config once
    S14 builds the full MCP gateway (mirrors D-002).
    """

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
