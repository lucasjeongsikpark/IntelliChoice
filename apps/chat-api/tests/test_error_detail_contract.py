"""The contract between what this API says in `detail` and what chat-web matches on.

**This file exists because of D-378, which is the only defect in this project that shipped, was
tested, was reviewed, and was still unmatchable by construction.** The fix added a rule to
`apps/chat-web/src/api/errors.ts` keyed on the field name `query`:

    { status: 422, detail: ["query"], message: "That question is too long…" }

and Pydantic puts the field name **only** in `loc`, never in `msg`. `detailText` joined the
`msg`s, so the haystack the rule searched could not contain the needle. It took a live browser
audit a day later to notice, and the visitor saw the generic line the whole time.

The rule now matches against `loc` too (`matchText`), which makes it depend on a wire shape no
test asserts. That is what this file pins: the 422 body for an over-long query really does carry
`query` in `loc`, so the rule really can fire.

See `apps/learning-api/tests/test_error_detail_contract.py` for the sibling file and the rule this
one's existence turned up there.
"""

import pytest
from chat_api.main import app
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_db.engine import create_engine
from intellichoice_shared.auth import Audience, Role
from sqlalchemy import text

issuer = FakeTokenIssuer()

# `MessageRequest.query` is `Field(min_length=1, max_length=2000)`, and chat-web's
# `MAX_QUERY_CHARS` is the same 2000. One character past it is the smallest input that produces
# the failure the rule is written for.
TOO_LONG = "a" * 2001


def _postgres_available() -> bool:
    import asyncio

    async def check() -> bool:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL not reachable (run `make up && make db-upgrade`)",
)


def _headers() -> dict[str, str]:
    token = issuer.issue(sub="student-ext-1", role=Role.STUDENT, audience=Audience.CHAT)
    return {"Authorization": f"Bearer {token}"}


def test_an_overlong_query_puts_the_field_name_in_loc_not_in_msg() -> None:
    """D-378's rule, pinned to the wire shape it depends on.

    Both halves are asserted, and the second is the one that matters: the field name is in `loc`
    and **is not** in `msg`. A future Pydantic or FastAPI version that moved it into `msg` would
    make `matchText`'s `loc` handling unnecessary; one that renamed `loc` would make the rule
    unmatchable again, silently, exactly as before.
    """
    headers = _headers()
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions", headers=headers).json()["chat_session_id"]
        resp = client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"query": TOO_LONG},
        )

    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert isinstance(detail, list), detail
    locs = [entry.get("loc") for entry in detail]
    assert any("query" in (loc or []) for loc in locs), locs

    # The half that made the shipped rule a no-op: nothing in `msg` names the field, so a client
    # matching only on `msg` cannot distinguish "too long" from any other validation failure.
    messages = " ".join(str(entry.get("msg", "")) for entry in detail).lower()
    assert "query" not in messages, (
        "the field name is now in `msg` as well as `loc`, which is not what chat-web's 422 rule "
        f"was written against - re-read `matchText` before relying on it: {messages!r}"
    )


def test_the_two_conflict_fragments_are_in_the_messages_the_routes_raise() -> None:
    """chat-web's other two substring rules, pinned at their source rather than driven - and the
    difference is worth stating instead of hiding.

    - 409 `["already working on a question"]` -> "Still working on your last question…"
    - 409 `["pending interrupt"]` -> "Answer the prompt above first, then you can carry on."

    Reaching either from a test means either racing two turns (the D-374 lock) or standing up a
    paused graph, both of which existing tests already do for their own purposes
    (`test_admin_escalation.py`, `test_chat_endpoints.py`). Re-creating that setup to re-check a
    substring would be a worse test than this one: what actually breaks these rules is somebody
    rewording the message, and that is exactly what this catches. Both texts are now module
    constants so there is something to reference - the second one was inline until today.
    """
    from chat_api.routers.sessions import PENDING_INTERRUPT_MESSAGE, TURN_ALREADY_RUNNING_MESSAGE

    assert "already working on a question" in TURN_ALREADY_RUNNING_MESSAGE.lower(), (
        TURN_ALREADY_RUNNING_MESSAGE
    )
    assert "pending interrupt" in PENDING_INTERRUPT_MESSAGE.lower(), PENDING_INTERRUPT_MESSAGE
