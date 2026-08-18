"""D-402: Stop actually stops the server, and does it turn by turn.

**The defect.** Pressing Stop aborted the client's fetch and nothing else. uvicorn does not
cancel a request handler when the client disconnects - measured against real uvicorn rather than
reasoned about, and a handler whose client hung up reports `ran-to-completion` - so the graph ran
on under its 50s deadline holding the per-session advisory lock, and the visitor's *next*
question came back 409 `TURN_ALREADY_RUNNING_MESSAGE`. p50 for a healthy grounded turn is ~10s
and p95 ~16s, so a visitor who stopped and immediately re-asked was routinely refused.

Four properties, one per requirement, and each is asserted separately because they fail
independently:

1. **Turn-scoped.** Cancelling turn A must not stop turn B - "Ask again" reuses a turn id and a
   session-scoped flag would kill the retry.
2. **Cooperative.** The running turn observes the request at a checkpoint boundary rather than
   being killed mid-node.
3. **A cancelled terminal state**, as a `TurnReason` code the client can branch on.
4. **The lock released immediately**, which is what the visitor actually feels.

**How the mid-turn observation is driven deterministically.** The check runs after each
`astream` super-step, so a cancellation recorded *before* the POST is observed at the first
boundary. That is a real observation by the real code path - not a mock - and it does not depend
on winning a race against a graph that finishes in milliseconds under the fakes.
"""

import asyncio
import uuid
from datetime import timedelta

from chat_api.main import app
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.models.chat_turn_cancellation import ChatTurnCancellation
from intellichoice_db.repositories.chat_turn_cancellation import (
    STALE_AFTER,
    ChatTurnCancellationRepository,
)
from intellichoice_shared.auth import Audience, Role
from sqlalchemy import func, insert

issuer = FakeTokenIssuer()

QUESTION = "What are the volunteering options at the downtown branch?"


def _request_cancellation(session_id: str, turn_id: str) -> None:
    """Write the row directly, the same way the endpoint would.

    Its own engine rather than `app.state.db_session_factory`, which is bound to
    `TestClient`'s internal event loop and cannot be driven from a separate `asyncio.run`
    (the same reason `test_chat_endpoints._snapshot` builds its own).
    """

    async def run() -> None:
        engine = create_engine()
        try:
            repo = ChatTurnCancellationRepository(create_session_factory(engine))
            await repo.request(chat_session_id=session_id, client_turn_id=turn_id)
        finally:
            await engine.dispose()

    asyncio.run(run())


def _is_requested(session_id: str, turn_id: str) -> bool:
    async def run() -> bool:
        engine = create_engine()
        try:
            repo = ChatTurnCancellationRepository(create_session_factory(engine))
            return await repo.is_requested(chat_session_id=session_id, client_turn_id=turn_id)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_a_cancelled_turn_stops_and_says_it_was_cancelled() -> None:
    """Requirements 2 and 3 together: the running turn observes the request at its first
    checkpoint boundary and returns the cancelled terminal state.

    `reason` rather than a new boolean, because that is already the closed code a client
    branches on and is already carried by all three response models - a field added to
    `MessageResponse` alone would be *nulled* on every broadcast (AUD-C-14/D-058) instead of
    failing loudly.

    `answer` is asserted absent as well, because "stopped" and "answered anyway" are the two
    outcomes this whole feature exists to keep apart.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        _request_cancellation(session_id, "turn-a")
        response = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": QUESTION, "client_turn_id": "turn-a"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reason"] == "cancelled", body
    assert body["client_turn_id"] == "turn-a"
    assert body["answer"] is None, "a withdrawn turn still produced an answer"
    assert body["citations"] == []


def test_cancelling_one_turn_does_not_stop_another() -> None:
    """Requirement 1, and the reason the endpoint is keyed by turn rather than by session.

    "Ask again" reuses the turn id, and a visitor who stops one question and asks a different
    one must get an answer to the second. A session-scoped flag would have refused it - and
    would have looked like Stop having jammed the conversation.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        _request_cancellation(session_id, "turn-stopped")
        response = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": QUESTION, "client_turn_id": "turn-other"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reason"] != "cancelled", (
        "a cancellation for a different turn id stopped this one, so Stop is session-scoped "
        "and the retry path is broken"
    )
    assert body["client_turn_id"] == "turn-other"


def test_the_next_question_is_not_refused_after_a_cancellation() -> None:
    """Requirement 4, stated as what the visitor feels.

    The advisory lock is transaction-scoped (`pg_try_advisory_xact_lock`) and this request's
    session commits at dependency teardown, so returning early *is* the release - that the lock
    is exclusive and per-thread is already pinned by
    `test_turn_containment.test_a_second_turn_on_the_same_thread_is_refused_while_one_is_running`.
    What this adds is the half that was missing: the handler now returns at a checkpoint boundary
    instead of running the full turn first, so a follow-up question lands outside the window
    rather than inside it.

    Sequential rather than concurrent on purpose. Two real overlapping requests would make this
    a race, and the existing lock test already drives contention at the lock itself for exactly
    that reason. What is asserted here is that the cancelled turn does not poison the session:
    the next question is served normally, with no 409 and no leftover cancelled state.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        _request_cancellation(session_id, "turn-1")
        first = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": QUESTION, "client_turn_id": "turn-1"},
        )
        second = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": QUESTION, "client_turn_id": "turn-2"},
        )

    assert first.json()["reason"] == "cancelled"
    assert second.status_code == 200, second.text
    assert second.json()["reason"] != "cancelled"


def test_the_row_is_consumed_so_a_retry_of_the_same_turn_id_runs() -> None:
    """The subtle one, and the reason `consume` exists.

    chat-web's "Ask again" reuses the turn id. If the cancellation row survived the turn that
    acted on it, the retry would be cancelled the instant it started - Stop would appear to have
    permanently broken that turn, and the visitor's only escape would be a new session.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        _request_cancellation(session_id, "turn-retried")
        assert _is_requested(session_id, "turn-retried") is True

        cancelled = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": QUESTION, "client_turn_id": "turn-retried"},
        )
        assert cancelled.json()["reason"] == "cancelled"
        assert _is_requested(session_id, "turn-retried") is False, "the row outlived the turn"

        retry = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": QUESTION, "client_turn_id": "turn-retried"},
        )

    assert retry.status_code == 200
    assert retry.json()["reason"] != "cancelled", "the retry of a stopped turn was stopped too"


def test_the_endpoint_records_a_cancellation_and_is_idempotent() -> None:
    """The endpoint itself: 202, and a double-tap on Stop is one row rather than two.

    202 rather than 200 because a cancellation is a request, not an outcome - the turn observes
    it at its next boundary, and this handler cannot honestly report that it stopped.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        first = client.post(f"/chat/sessions/{session_id}/turns/turn-x/cancel")
        second = client.post(f"/chat/sessions/{session_id}/turns/turn-x/cancel")

    assert first.status_code == 202
    assert second.status_code == 202, "a second Stop on the same turn was rejected"
    assert _is_requested(session_id, "turn-x") is True


def test_a_stranger_cannot_cancel_an_owned_sessions_turn() -> None:
    """The gate `/messages` has, applied here too.

    `_reject_if_paused` bundles the ownership check with the paused-turn 409 deliberately - its
    docstring says so - and this endpoint cannot reuse it, because a paused turn is a legitimate
    thing to cancel. So the access half is called directly, and this is the test that says the
    other half was left behind on purpose rather than by accident. Without it, anyone holding a
    session id could stop a stranger's question.
    """
    owner = issuer.issue(sub="student-ext-1", role=Role.STUDENT, audience=Audience.CHAT)
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        # One real turn, because ownership is written to the checkpoint by the first turn -
        # a session with no turns yet is legitimately unowned and cancellable by anyone.
        client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": QUESTION, "client_turn_id": "turn-owned"},
            headers={"Authorization": f"Bearer {owner}"},
        )
        anonymous = client.post(f"/chat/sessions/{session_id}/turns/turn-owned/cancel")
        as_owner = client.post(
            f"/chat/sessions/{session_id}/turns/turn-owned/cancel",
            headers={"Authorization": f"Bearer {owner}"},
        )

    assert anonymous.status_code == 403, "an anonymous caller cancelled an owned session's turn"
    # The positive control: the same call from the owner is what makes the 403 meaningful
    # rather than the endpoint being broken for everyone.
    assert as_owner.status_code == 202


def test_an_over_long_turn_id_is_refused_rather_than_stored() -> None:
    """The column is `String(64)` because `AskMessageRequest.client_turn_id` is bounded at 64.
    Without the matching bound on the path parameter, an over-long id would reach Postgres and
    come back as a 500 - a validation failure wearing an outage's clothes.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        response = client.post(f"/chat/sessions/{session_id}/turns/{'x' * 65}/cancel")

    assert response.status_code == 422


def _request_cancellation_aged(session_id: str, turn_id: str, older_than: timedelta) -> None:
    """Insert a row that is already `older_than` old, on the **database's** clock.

    The age is expressed as SQL arithmetic (`now() - interval`) rather than a Python
    `datetime`, because the sweep compares against `func.now()`: computing the timestamp here
    would put the test on one clock and the code under test on another, and a container whose
    clock drifts by a second would decide the outcome.
    """

    async def run() -> None:
        engine = create_engine()
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                await session.execute(
                    insert(ChatTurnCancellation).values(
                        chat_session_id=session_id,
                        client_turn_id=turn_id,
                        requested_at=func.now() - older_than,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_a_stale_row_for_any_session_is_swept_by_the_next_cancellation() -> None:
    """D-416: the sweep is global, and this is the property that makes the table self-limiting.

    **Found on the deployed edge, not by reading.** `POST /chat/sessions/{invented}/turns/x/cancel`
    answers **202** to an anonymous caller, because `POST /chat/sessions` persists nothing (D-345 -
    a session id is a bare uuid4 until a message spends against it) and so the endpoint cannot tell
    a real session from a fabricated one. It must not try, either: a visitor pressing Stop on their
    *first* turn has no checkpoint yet, so refusing to write without one would silently restore the
    defect D-402 exists to fix.

    While the sweep was scoped to `chat_session_id`, every fabricated id left a row that nothing
    could ever reach - not the observing turn (that session has none) and not the sweep (that id
    never returns). Unscoped, any Stop press reaps all expired rows, so the table is bounded by 15
    minutes of insert traffic rather than by callers being well behaved.
    """
    stale_session = "sess-stale-" + uuid.uuid4().hex
    live_session = "sess-live-" + uuid.uuid4().hex
    _request_cancellation_aged(stale_session, "turn-abandoned", STALE_AFTER + timedelta(minutes=1))
    assert _is_requested(stale_session, "turn-abandoned") is True, "the fixture did not insert"

    # A cancellation for an entirely unrelated session.
    _request_cancellation(live_session, "turn-live")

    assert _is_requested(stale_session, "turn-abandoned") is False, (
        "a stale row for another session survived, so nothing reaps a fabricated session id"
    )
    assert _is_requested(live_session, "turn-live") is True, "the sweep took the new row with it"


def test_a_fresh_row_for_another_session_is_left_alone() -> None:
    """The negative control, and it is what stops the fix above from being 'delete everything'.

    Two visitors can have live cancellations at the same time - one on each of two replicas, which
    is the case D-395's fan-out exists for. A sweep that ignored `requested_at` would cancel one
    visitor's Stop because another visitor pressed theirs.
    """
    other_session = "sess-fresh-" + uuid.uuid4().hex
    mine = "sess-mine-" + uuid.uuid4().hex
    _request_cancellation(other_session, "turn-theirs")

    _request_cancellation(mine, "turn-mine")

    assert _is_requested(other_session, "turn-theirs") is True, (
        "a live cancellation belonging to another session was swept"
    )
    assert _is_requested(mine, "turn-mine") is True
