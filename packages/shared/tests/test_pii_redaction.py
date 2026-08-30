from intellichoice_shared.pii_redaction import contains_pii_pattern, redact_free_text


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


def test_redacts_urls_whose_scheme_or_host_label_is_capitalised() -> None:
    """E6.1 F-1 (D-458): `_URL_RE` was compiled without `re.IGNORECASE`, so `HTTP://`,
    `Https://` and `WWW.` matched nothing at all - 6/6 of the corpus's
    `url_uppercase_scheme` cases exported verbatim. Scheme and host labels are
    case-insensitive by RFC 3986, and a phone keyboard autocapitalises the first word of a
    message, which is exactly where a student pastes a link.
    """
    for text in (
        "HTTP://EXAMPLE.ORG/help",
        "HTTPS://EXAMPLE.ORG",
        "Https://example.org/help",
        "Http://school.example",
        "WWW.EXAMPLE.ORG",
        "Www.example.org/help",
    ):
        assert redact_free_text(text) == "[redacted-url]", text


def test_uppercase_urls_are_screened_by_the_consolidation_denylist_too() -> None:
    """`contains_pii_pattern` shares the same compiled patterns, so the flag has to move
    both call sites at once - a model-generated fact holding `Www.example.org` must be
    dropped, not stored.
    """
    assert contains_pii_pattern("see Https://example.org/help")
    assert contains_pii_pattern("WWW.EXAMPLE.ORG")


def test_the_url_near_misses_stay_untouched_after_the_case_widening() -> None:
    """The false-positive arm of F-1: widening a pattern is only safe if the shapes that
    were deliberately *not* URLs still are not. These are the corpus's
    `neg_near_miss_url` negatives, uppercased where case is the only thing that changed.
    """
    for text in (
        "HTTP:/broken",
        "HTP://example.org",
        "WWWX.example.org",
        "the WWW prefix is optional",
        "HTTPS//example.org",
        "SCHEME://",
    ):
        assert redact_free_text(text) == text, text
