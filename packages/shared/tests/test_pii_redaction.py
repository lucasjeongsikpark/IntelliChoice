from intellichoice_shared.pii_redaction import redact_free_text


def test_redacts_email() -> None:
    assert redact_free_text("email me at kid@example.com please") == (
        "email me at [redacted-email] please"
    )


def test_redacts_url() -> None:
    assert redact_free_text("check https://example.com/page for help") == (
        "check [redacted-url] for help"
    )


def test_redacts_phone_number() -> None:
    assert redact_free_text("call me at 555-123-4567 tonight") == (
        "call me at [redacted-phone] tonight"
    )
    assert redact_free_text("call (555) 123-4567") == "call [redacted-phone]"


def test_does_not_redact_math_expressions() -> None:
    """The whole point of this app: a bare digit run is almost always the student's own
    work, not a phone number - a looser digit-run pattern would corrupt math content.
    """
    assert redact_free_text("Solve for x: 3x + 18 = 27") == "Solve for x: 3x + 18 = 27"
    assert redact_free_text("2024 - 1998 = 26") == "2024 - 1998 = 26"
    assert redact_free_text("I got x = 3") == "I got x = 3"


def test_leaves_ordinary_text_untouched() -> None:
    text = "I don't understand why my answer is wrong, can you help?"
    assert redact_free_text(text) == text
