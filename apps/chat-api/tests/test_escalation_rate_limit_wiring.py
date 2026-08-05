"""AUD-C-27: the app must wire the *shared* escalation limiter, not the per-process one.

Why this file exists, and why the assertions are on the wiring and the HTTP path rather
than on the node: `test_admin_escalation.test_rate_limit_blocks_repeated_anonymous_
escalation` already pins what the node does when a limiter says no, and it passed
throughout the period when the deployed cap of 5 was really 8 - because it injects its own
limiter and so never touches what `lifespan` builds. D-159's corollary, applied: test the
path that actually runs.

Every request here goes through `TestClient`, so the caller key is `testclient` for all of
them and the autouse `reset_escalation_rate_limit` fixture owns the cleanup.
"""

import asyncio
from datetime import timedelta

import pytest
from chat_api.config import get_settings
from chat_api.main import app
from chat_api.services.escalation_rate_limit import PostgresRateLimiter
from fastapi.testclient import TestClient
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.models.rate_limit import SCOPE_ADMIN_ESCALATION
from intellichoice_db.repositories.rate_limit import RateLimitRepository
from intellichoice_shared.rate_limit import hash_caller_key

from .conftest import TEST_CLIENT_CALLER_KEY, postgres_skip_reason

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

ESCALATION_QUERY = "Please pass this to an administrator: who approves a branch transfer?"


def _escalate_once(client: TestClient) -> dict:
    """One escalation on a *fresh* session, which is the shape the live probe used: the
    cap is keyed on the caller, so a new session must not buy a new quota.
    """
    session_id = client.post("/chat/sessions").json()["chat_session_id"]
    return client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"query": ESCALATION_QUERY, "escalate": True},
    ).json()


def _attempts_recorded() -> int:
    """What a *second* ECS task would see: an independently built repository over the same
    database. Before AUD-C-27 this read zero no matter how many attempts had been made.
    """
    key_hash = hash_caller_key(
        TEST_CLIENT_CALLER_KEY, secret=get_settings().jwt_signing_secret
    )

    async def run() -> int:
        engine = create_engine()
        try:
            repo = RateLimitRepository(create_session_factory(engine))
            return await repo.attempts_since(
                scope=SCOPE_ADMIN_ESCALATION,
                caller_key_hash=key_hash,
                window=timedelta(hours=1),
            )
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_the_app_wires_the_shared_escalation_limiter() -> None:
    """A `PostgresRateLimiter` is not merely *a* `RateLimiter` here - it is the only
    implementation whose count survives the process, which is what the cap's number
    depends on.
    """
    with TestClient(app):
        limiter = app.state.email_rate_limiter

    assert isinstance(limiter, PostgresRateLimiter)


def test_an_escalation_over_http_is_counted_where_another_task_can_see_it() -> None:
    """The end-to-end version of the fix, and the local equivalent of the live probe that
    measured 8-against-5 before it.
    """
    assert _attempts_recorded() == 0

    with TestClient(app) as client:
        body = _escalate_once(client)

    assert body["intent"] == "admin_contact", body
    assert body["pending_interrupt"] is not None, body
    assert _attempts_recorded() == 1


def test_the_cap_is_enforced_across_fresh_sessions_and_survives_a_restart() -> None:
    """Two properties in one test because they are the same property viewed twice:
    a new chat session does not reset the cap (it is keyed on the caller), and neither
    does a new app process - the second `TestClient` context is a fresh lifespan, i.e. a
    replacement task, and it must inherit the count rather than start over.
    """
    cap = get_settings().email_rate_limit_max_per_window

    with TestClient(app) as client:
        outcomes = [_escalate_once(client) for _ in range(cap)]

    assert all(o["pending_interrupt"] is not None for o in outcomes), outcomes
    assert _attempts_recorded() == cap

    # A new process. The old limiter object, and its dict, are gone.
    with TestClient(app) as client:
        blocked = _escalate_once(client)

    assert blocked["pending_interrupt"] is None, blocked
    assert blocked["answer"].startswith("Too many escalation requests"), blocked
    # The refusal must not consume an attempt of its own, or a blocked caller's window
    # would keep sliding forward and never reopen.
    assert _attempts_recorded() == cap
