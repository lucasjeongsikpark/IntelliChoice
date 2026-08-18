"""The browser-crash sink for the anonymous-first app (`POST /chat/client-errors`).

learning-api's equivalent is authenticated and keyed per token. This one cannot be: chat's
primary caller is anonymous (SPEC §5.19.1), so a token gate would drop the majority of the
crashes the endpoint exists to see — the reason `chat-web`'s `ErrorBoundary` stayed console-only
until now, recorded in its own docstring rather than shrugged at.

These tests pin the gate that replaces the token, and in particular the property that makes it a
gate at all: **an anonymous caller cannot buy a fresh allowance by inventing a session id.**
"""

import logging

import pytest
from chat_api.main import app
from chat_api.routers.client_errors import (
    _ANONYMOUS_REPORTS_PER_MINUTE,
    _REPORTS_PER_MINUTE_PER_TOKEN,
    MAX_MESSAGE_CHARS,
    MAX_STACK_CHARS,
    _anonymous_limiter,
    _scrub,
    _token_limiter,
)
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_shared.auth import Audience, Role

issuer = FakeTokenIssuer()

ENDPOINT = "/chat/client-errors"


def _auth(sub: str = "client-error-parent") -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {issuer.issue(sub=sub, role=Role.PARENT, audience=Audience.CHAT)}"
        )
    }


@pytest.fixture(autouse=True)
def _reset_limiters():
    """Both limiters are module-level, so without this each test inherits its predecessors'
    counts and the rate-limit tests pass or fail depending on execution order."""
    _token_limiter._calls_by_key.clear()
    _anonymous_limiter._calls_by_key.clear()
    yield


# --- the anonymous path, which is the whole reason this differs from learning's ------------


def test_an_anonymous_crash_is_accepted() -> None:
    """The property the token-gated design could not have. chat-web's visitor has no account,
    and their blank screen is exactly the failure a maintainer never hears about otherwise."""
    with TestClient(app) as client:
        resp = client.post(ENDPOINT, json={"message": "Cannot read properties of undefined"})
    assert resp.status_code == 202, "accepted, not created - nothing is persisted"
    assert resp.json() == {"recorded": True}


def test_a_forged_session_id_does_not_buy_a_fresh_allowance() -> None:
    """**The test this endpoint exists to pass.**

    The tempting design keys the anonymous bucket on `chat_session_id`. That field is
    unverified free text — verifying it would mean a checkpoint read on an error path — so a
    per-id bucket hands an attacker a brand-new allowance for every id they invent, which is
    not a rate limit. One shared bucket cannot be walked around that way.

    Falsified by switching the limiter key to `payload.chat_session_id`: every request below
    then returns 202 and this goes red.
    """
    with TestClient(app) as client:
        for i in range(_ANONYMOUS_REPORTS_PER_MINUTE):
            accepted = client.post(ENDPOINT, json={"message": "boom", "chat_session_id": f"s-{i}"})
            assert accepted.status_code == 202
        refused = client.post(
            ENDPOINT, json={"message": "boom", "chat_session_id": "a-brand-new-id"}
        )
    assert refused.status_code == 429, (
        "a new session id bought another allowance, so an anonymous caller can write to the "
        "log without bound by rotating one unverified field"
    )
    assert refused.headers["Retry-After"] == "60"


def test_an_anonymous_flood_does_not_consume_a_signed_in_caller_s_allowance() -> None:
    """The two buckets are separate, so a visitor's crash loop cannot silence a signed-in
    parent — the same isolation learning gets from keying on `sub`, at the one boundary this
    design can still draw."""
    with TestClient(app) as client:
        for _ in range(_ANONYMOUS_REPORTS_PER_MINUTE):
            client.post(ENDPOINT, json={"message": "flood"})
        assert client.post(ENDPOINT, json={"message": "flood"}).status_code == 429
        assert client.post(ENDPOINT, headers=_auth(), json={"message": "mine"}).status_code == 202


def test_a_signed_in_crash_loop_is_limited_per_token() -> None:
    def report(client: TestClient, sub: str) -> int:
        return client.post(ENDPOINT, headers=_auth(sub), json={"message": "x"}).status_code

    with TestClient(app) as client:
        for _ in range(_REPORTS_PER_MINUTE_PER_TOKEN):
            assert report(client, "loop") == 202
        assert report(client, "loop") == 429
        assert report(client, "someone-else") == 202


def test_a_present_but_invalid_token_is_refused_rather_than_downgraded() -> None:
    """`get_optional_claims`'s existing contract, and it matters more here than elsewhere: if a
    bad token silently became "anonymous", an expired session would look like a working one and
    the caller would never learn their token had lapsed."""
    with TestClient(app) as client:
        resp = client.post(
            ENDPOINT, headers={"Authorization": "Bearer not-a-real-token"}, json={"message": "x"}
        )
    assert resp.status_code == 401


# --- the parts copied from learning, pinned again because they are the PII surface ---------


def test_an_unknown_field_is_refused_rather_than_ignored() -> None:
    """Pydantic's default would drop it silently. A future client that starts sending
    `visitor_name` must get a 422, not quiet acceptance."""
    with TestClient(app) as client:
        resp = client.post(ENDPOINT, json={"message": "x", "visitor_name": "Ada"})
    assert resp.status_code == 422


def test_a_stack_containing_a_question_stem_is_truncated() -> None:
    """Truncation is what bounds what redaction cannot catch. A question stem is not PII-shaped
    and sails through a regex screen; length is the only property that separates a useful stack
    frame from one that has swallowed content."""
    stem = "What is 3/4 of 128? " * 300
    scrubbed = _scrub(stem, MAX_STACK_CHARS)
    assert len(scrubbed) <= MAX_STACK_CHARS
    assert scrubbed.endswith("…[truncated]")


def test_an_email_inside_a_stack_is_redacted_before_truncation() -> None:
    """Order matters: truncating first could cut an address in half and leave a fragment the
    pattern no longer matches."""
    scrubbed = _scrub("at send (mail.ts) for parent@example.test", MAX_MESSAGE_CHARS)
    assert "parent@example.test" not in scrubbed


def test_a_short_message_is_left_exactly_as_it_is() -> None:
    """The control. A scrubber that mangles ordinary input makes every log line untrustworthy."""
    assert _scrub("Cannot read properties of undefined", MAX_MESSAGE_CHARS) == (
        "Cannot read properties of undefined"
    )


def test_the_logged_record_marks_an_anonymous_caller_without_inventing_an_id(caplog) -> None:
    """SPEC §5.30: logs carry external ids or nothing. "Anonymous" must read as absent rather
    than as some substitute identifier minted to fill the column."""
    with caplog.at_level(logging.ERROR), TestClient(app) as client:
        client.post(ENDPOINT, json={"message": "boom", "chat_session_id": "sess-1"})
    record = next(r for r in caplog.records if r.message == "client_error")
    assert record.caller_external_id is None
    assert record.is_anonymous is True
    assert record.chat_session_id == "sess-1"


def test_the_logged_record_carries_the_external_id_when_there_is_one(caplog) -> None:
    with caplog.at_level(logging.ERROR), TestClient(app) as client:
        client.post(ENDPOINT, headers=_auth("parent-ext-1"), json={"message": "boom"})
    record = next(r for r in caplog.records if r.message == "client_error")
    assert record.caller_external_id == "parent-ext-1"
    assert record.is_anonymous is False
