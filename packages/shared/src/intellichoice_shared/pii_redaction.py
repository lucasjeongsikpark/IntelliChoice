"""Deterministic PII redaction (SPEC §5.30.1 extension, D-072) - applied to a student's
free-text chat message before it crosses the Bedrock wire *and* before it is persisted to
`tutor_chat_messages`, never after. Regex-based email/phone/URL stripping only; name
detection is unreliable and deliberately not attempted (documented residual risk, plan
§15) - this is a floor, not a guarantee that all PII is caught.

The phone pattern intentionally requires a 3-3-4 (or similar punctuated) grouping rather
than matching any long run of digits: this is a math-tutoring chat, where a bare
digit-heavy run is often the student's own work ("2024 - 1998 = 26"), not a phone number.
A looser digit-run pattern would redact legitimate math content.
"""

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# `re.IGNORECASE` is load-bearing, not tidiness: schemes and host labels are
# case-insensitive by RFC 3986, and a phone keyboard autocapitalises the first word of a
# message - which is where a student pastes a link. Without the flag `HTTP://`, `Https://`
# and `WWW.` matched nothing at all (E6.1 F-1, D-458: 6/6 of the labeled corpus's
# `url_uppercase_scheme` cases). The email and phone patterns need no such flag - `\w` and
# `\d` are already case-blind - so their semantics are deliberately left alone.
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")


def redact_free_text(text: str) -> str:
    redacted = _EMAIL_RE.sub("[redacted-email]", text)
    redacted = _URL_RE.sub("[redacted-url]", redacted)
    redacted = _PHONE_RE.sub("[redacted-phone]", redacted)
    return redacted


def contains_pii_pattern(text: str) -> bool:
    """S25 memory consolidation's denylist screen (plan §9: "text mentioning names/
    emails (regex screen) -> dropped"): reuses this module's own email/URL/phone
    patterns rather than duplicating them - a model-generated fact whose text still
    matches one of these is dropped, never stored. Same "floor, not a guarantee"
    caveat as `redact_free_text` - no name detection.
    """
    return bool(_EMAIL_RE.search(text) or _URL_RE.search(text) or _PHONE_RE.search(text))
