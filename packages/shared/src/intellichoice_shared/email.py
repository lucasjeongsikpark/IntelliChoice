from typing import Protocol

from pydantic import BaseModel, field_validator


class EmailMessage(BaseModel):
    recipient: str
    subject: str
    body: str

    @field_validator("recipient", "subject")
    @classmethod
    def _no_header_injection(cls, value: str) -> str:
        """SPEC §5.24.2 header-injection defense - reject `\\r`/`\\n` in whatever
        becomes an SMTP header field, so a crafted recipient/subject can never smuggle
        an extra `Bcc:`/`To:` line into a real send. `body` is deliberately not
        validated here - it's not a header and legitimately contains newlines.
        """
        if "\r" in value or "\n" in value:
            raise ValueError("must not contain CR/LF (header injection)")
        return value


class EmailTransport(Protocol):
    """Gmail MCP stand-in (SPEC §5.24), called only through the MCP tool registry
    (`intellichoice_shared.mcp`, S14) as the `gmail.send_email` tool - `send` itself
    stays a plain interface so a dev fake can stand in for it (D-002's pattern).
    """

    async def send(self, message: EmailMessage) -> None: ...
