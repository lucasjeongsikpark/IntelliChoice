"""SPEC §5.24.2 header-injection defense - `EmailMessage.recipient`/`.subject` reject
CR/LF so a crafted value can never smuggle an extra header line into a real send.
"""

import pytest
from intellichoice_shared.email import EmailMessage
from pydantic import ValidationError


def test_valid_message_round_trips() -> None:
    message = EmailMessage(recipient="a@example.test", subject="Hello", body="Line one\nLine two")
    assert message.recipient == "a@example.test"
    assert "\n" in message.body  # body newlines are legitimate, not header injection


@pytest.mark.parametrize("field", ["recipient", "subject"])
def test_crlf_in_header_field_is_rejected(field: str) -> None:
    kwargs = {"recipient": "a@example.test", "subject": "Hello", "body": "hi"}
    kwargs[field] = "a@example.test\r\nBcc: evil@example.test"
    with pytest.raises(ValidationError):
        EmailMessage(**kwargs)


@pytest.mark.parametrize("field", ["recipient", "subject"])
def test_bare_lf_in_header_field_is_rejected(field: str) -> None:
    kwargs = {"recipient": "a@example.test", "subject": "Hello", "body": "hi"}
    kwargs[field] = "a@example.test\nBcc: evil@example.test"
    with pytest.raises(ValidationError):
        EmailMessage(**kwargs)
