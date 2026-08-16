"""HTTP-level tests for the S13 `POST /chat/sessions` + `POST .../messages` +
`GET .../stream` endpoints (SPEC §5.28.2 subset). Runs against the real `TestClient(app)`
lifespan (live dev Postgres for LangGraph checkpoints only - no RAG content is seeded
through these tests, so nothing but a handful of small checkpoint rows under a fresh
random session id is ever written, the same footprint `apps/learning-api`'s own dev-
token/session-creation HTTP tests already have).

`/stream` itself is exercised via `_initial_snapshot` directly rather than a live SSE
response, same reasoning as `apps/learning-api/tests/test_stream_and_history.py`
(D-033): the endpoint intentionally never closes on its own, and `TestClient.stream()`
hangs against it.
"""

import asyncio
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import cast

import pytest
from chat_api.main import app
from chat_api.routers.sessions import SessionSnapshotEvent
from chat_api.routers.stream import _initial_snapshot
from fastapi import HTTPException
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer, JwtTokenVerifier
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.models.chat import ChatSuggestion
from intellichoice_db.repositories.chat import ChatSuggestionRepository
from intellichoice_shared.auth import Audience, Role
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import text

issuer = FakeTokenIssuer()
verifier = JwtTokenVerifier()


async def _snapshot(session_id: str, token: str | None):
    """`_initial_snapshot` needs a db session (for `suggested_followups`) that a plain
    direct call outside a real request doesn't get for free. Builds its own fresh engine
    rather than reusing `app.state.db_session_factory` - that one is bound to
    `TestClient`'s own internal event loop, which a separate `asyncio.run()` call here
    can't share (a real request never hits this, since FastAPI's dependency injection
    runs the whole request on one loop).
    """
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            return await _initial_snapshot(session_id, app.state.qa_graph, token, session)
    finally:
        await engine.dispose()


def _token(sub: str, role: Role) -> str:
    return issuer.issue(sub=sub, role=role, audience=Audience.CHAT)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_session_allows_anonymous_callers() -> None:
    client = TestClient(app)
    response = client.post("/chat/sessions")
    assert response.status_code == 200
    assert response.json()["chat_session_id"]


def test_post_message_out_of_scope_is_refused_anonymously() -> None:
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        response = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "What's the best recipe for chocolate chip cookies?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "out_of_scope"
    assert body["citations"] == []


def test_post_message_in_scope_with_no_source_offers_escalation() -> None:
    # A generic "tutor procedure" phrase now risks a real match (S17's real org
    # content, including tutor bios, is retrievable today) - "zqxvchunk" can't
    # coincidentally appear in any real or synthetic seeded content (D-018's pattern);
    # "handbook" keeps the mock scope-guard's in_scope+document_qa keyword match (a
    # supported topic keyword absent from the real S17 docs). No filler words
    # (the/what/is/...) - the mock reranker's query-word overlap only excludes words
    # <=2 chars, so common English words would spuriously "match" real prose too.
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        response = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "zqxvchunk handbook"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "in_scope"
    assert body["intent"] == "document_qa"
    assert body["escalation_recommended"] is True
    assert body["citations"] == []
    # D-164/AUD-C-11: the refusal must not ship a citation chip under a sentence saying no
    # source exists. Asserted at the HTTP boundary too, because that is where chat-web
    # reads it.
    assert body["access_hint"] is None


def test_post_message_with_escalate_pauses_for_email_approval() -> None:
    """D-164: the `escalate` flag's pass-through, end to end over HTTP. The button on a
    no-source refusal posts that refusal's own question back with `escalate: true`, and the
    turn must come back paused on the email approval rather than answered.

    `intent` is `admin_contact` and `scope` is null: no classification ran (the escalate
    path skips `scope_guard`), and claiming one would be a statement nothing made.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        question = "Do you offer transport from the middle school to the Dallas branch?"
        response = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": question, "escalate": True},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "admin_contact"
    assert body["scope"] is None
    assert body["pending_interrupt"]["interrupt_type"] == "email_approval"
    # The draft a human is about to approve carries the user's question and no identity.
    assert question in body["pending_interrupt"]["email_body"]
    assert body["pending_interrupt"]["email_subject"].startswith("IntelliChoice Q&A escalation")


def test_post_message_redacts_typed_pii_before_the_graph() -> None:
    """AUD-C-24: the typed question is redacted at the request boundary - the one place
    free text enters this graph - so nothing downstream ever holds the raw text: not the
    escalation draft a human is shown, and not the checkpointed `QAState`. Asserted on
    the escalate path because its email draft is the most human-visible artifact built
    from the query, and on the raw checkpoint writes because that is where AUD-C-03
    taught us redaction claims go to die (decode with LangGraph's own serializer, not
    `CAST(blob AS text)`).
    """
    raw_email = "zqxv.parent@example.com"
    question = f"My mum's email is {raw_email}, when is the next class?"
    serde = JsonPlusSerializer()

    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        response = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": question, "escalate": True},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["pending_interrupt"]["interrupt_type"] == "email_approval"
    assert "[redacted-email]" in body["pending_interrupt"]["email_body"]
    assert raw_email not in body["pending_interrupt"]["email_body"]

    rows = asyncio.run(_checkpoint_writes_for_thread(session_id))
    assert rows, "expected checkpoint writes for the thread - wrong thread id?"
    decoded = " ".join(repr(serde.loads_typed((type_, blob))) for _, type_, blob in rows)
    assert raw_email not in decoded
    assert "[redacted-email]" in decoded


def test_post_message_with_pii_still_classifies_and_answers_normally() -> None:
    """AUD-C-24's other half: redaction must not cost the caller their turn. An
    email-bearing but otherwise in-scope question still classifies and takes the normal
    no-source escalation-offer path (learning-api already proves an answer survives the
    pass; this is the same property at chat-api's boundary).
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        response = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "zqxvchunk handbook contact zqxv.parent@example.com please"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "in_scope"
    assert body["intent"] == "document_qa"
    assert body["escalation_recommended"] is True


def test_post_message_includes_deterministic_followups() -> None:
    """SPEC §18-C3: `suggested_followups` are picked from `chat_suggestions`, never the
    LLM. Seeds one marker row via a committing session - `TestClient`'s own lifespan
    opens a separate connection to the same database, so a committed row is visible to
    it - and cleans it up afterward (same small, bounded HTTP-test footprint this file's
    own docstring already accepts for checkpoint rows).
    """
    marker_id = "zqxvhttp-general"

    async def seed() -> None:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                await ChatSuggestionRepository(session).upsert(
                    ChatSuggestion(
                        id=marker_id,
                        role_audience="public",
                        category="general",
                        prompt_text="Zqxvhttp follow-up prompt",
                        sort_order=0,
                        active=True,
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    async def cleanup() -> None:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                await session.execute(
                    text("DELETE FROM chat_suggestions WHERE id = :id"), {"id": marker_id}
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    try:
        with TestClient(app) as client:
            session_id = client.post("/chat/sessions").json()["chat_session_id"]
            response = client.post(
                f"/chat/sessions/{session_id}/messages",
                json={"query": "zqxvchunk handbook"},
            )
        body = response.json()
        assert "Zqxvhttp follow-up prompt" in body["suggested_followups"]
    finally:
        asyncio.run(cleanup())


def test_stream_initial_snapshot_reflects_the_last_message() -> None:
    token = _token("student-ext-1", Role.STUDENT)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/chat/sessions", headers=headers).json()["chat_session_id"]
        client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"query": "What's the best recipe for chocolate chip cookies?"},
        )

        snapshot = asyncio.run(_snapshot(session_id, token))

    assert snapshot.chat_session_id == session_id
    assert snapshot.scope == "out_of_scope"


def test_stream_rejects_a_token_for_a_different_user() -> None:
    token = _token("student-ext-1", Role.STUDENT)
    other_token = _token("student-ext-2", Role.STUDENT)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/chat/sessions", headers=headers).json()["chat_session_id"]
        client.post(
            f"/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"query": "What's the best recipe for chocolate chip cookies?"},
        )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_snapshot(session_id, other_token))

    assert exc_info.value.status_code == 403


def test_stream_allows_anonymous_access_to_an_anonymous_session() -> None:
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "What's the best recipe for chocolate chip cookies?"},
        )

        snapshot = asyncio.run(_snapshot(session_id, None))

    assert snapshot.chat_session_id == session_id


def test_stream_404s_for_an_unknown_session() -> None:
    with TestClient(app):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_snapshot("does-not-exist", None))

    assert exc_info.value.status_code == 404


def test_stream_delivers_an_event_published_during_the_initial_read() -> None:
    """AUD-F-36 (found on learning-api's identical endpoint, fixed on both): an event
    published while `/stream` is still building its initial snapshot must reach that
    stream. Pre-fix, the subscription was registered only after the read, so such an
    event went to nobody and the connection served a stale initial frame it would never
    correct. The fake publishes at the exact seam - inside `aget_state` - because the
    defect is an ordering one and ~1-in-3 whole-suite reproduction is not a test.
    """
    from chat_api.routers import stream as stream_module
    from chat_api.services.session_events import ChatSessionEventBus

    session_id = "chat-aud-f-36"
    bus = ChatSessionEventBus()

    class _FakeSnapshot:
        # An anonymous session (no `user_external_id`) so `token=None` authorizes, with
        # a real-shaped answered state so `_suggested_followups` has what it reads.
        values = {"scope": "in_scope", "intent": "document_qa", "answer": "old answer"}
        tasks = ()

    class _PublishingGraph:
        async def aget_state(self, _config: dict) -> _FakeSnapshot:
            bus.publish(session_id, {"answer": "new answer", "pending_interrupt": None})
            return _FakeSnapshot()

    async def _run() -> list[str]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            # D-348: the endpoint now opens its own short-lived session from
            # `app.state.db_session_factory` instead of holding a request-scoped one for the
            # life of the stream, so the fake request carries the factory rather than a
            # session. `SimpleNamespace` because only that one attribute is read.
            fake_request = SimpleNamespace(
                app=SimpleNamespace(state=SimpleNamespace(db_session_factory=session_factory))
            )
            response = await stream_module.stream_session(
                session_id,
                fake_request,  # type: ignore[arg-type]
                events=bus,
                graph=_PublishingGraph(),  # type: ignore[arg-type]
                token=None,
            )
            frames = []
            # `body_iterator` is typed as the broad `AsyncContentStream`; this
            # endpoint's is always the async generator `event_stream()`.
            iterator = cast(AsyncGenerator[str, None], response.body_iterator)
            try:
                frames.append(await asyncio.wait_for(anext(iterator), timeout=2.0))
                frames.append(await asyncio.wait_for(anext(iterator), timeout=2.0))
            finally:
                await iterator.aclose()
            return [str(frame) for frame in frames]
        finally:
            await engine.dispose()

    with TestClient(app):
        frames = asyncio.run(_run())
    # Pydantic's model_dump_json is compact (no space after ':'); json.dumps is not.
    assert '"answer":"old answer"' in frames[0]
    assert '"answer": "new answer"' in frames[1], (
        "the event published during the initial read was lost to this stream (AUD-F-36)"
    )
    assert not bus._subscribers, "closing the stream must unsubscribe its queue"


def test_branch_locator_consent_then_zip_round_trip_over_http() -> None:
    """SPEC §5.1.3/§5.22 end-to-end through the real HTTP endpoints (real MySQL-seeded
    branches via `MySQLProfileAdapter`, real `FakeMapsProvider` registered by
    `main.py`'s lifespan) - the Phase 16 "consent tests pass" completion criterion.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        preview = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "What is the nearest branch to me?"},
        ).json()
        assert preview["pending_interrupt"]["interrupt_type"] == "location_consent"
        assert "location will be used only" in preview["pending_interrupt"]["notice"]

        result = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={
                "interrupt_type": "location_consent",
                "approved": True,
                "zip_code": "62704",
            },
        ).json()

    assert "Main Branch" in result["answer"]
    assert "North Branch" in result["answer"]


def test_respond_carries_scope_and_intent_into_its_snapshot() -> None:
    """AUD-C-14. `RespondResponse` omitted `scope`/`intent`, and because `_publish_snapshot`
    re-validates a `SessionSnapshotEvent` from `response.model_dump()`, the omission did not
    raise - it *nulled* both fields for every connected client on every broadcast after a
    `/respond`. Watched failing before the fix, on both assertions.

    Asserted on the same interrupt round trip as the test above, because that is the shortest
    real path that reaches `/respond`: the `/messages` turn classifies, the `/respond` turn
    resumes it, and the resumed turn's state still carries the classification.
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        preview = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "What is the nearest branch to me?"},
        ).json()
        assert preview["pending_interrupt"]["interrupt_type"] == "location_consent"
        # The control: `/messages` already reports these, so a null after `/respond` is the
        # defect and not simply "this journey never classifies anything".
        assert preview["scope"] == "in_scope"
        assert preview["intent"] is not None

        result = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={
                "interrupt_type": "location_consent",
                "approved": True,
                "zip_code": "62704",
            },
        ).json()

    assert result["scope"] == preview["scope"], (
        "the /respond response dropped `scope`, so its SSE snapshot nulls it (AUD-C-14)"
    )
    assert result["intent"] == preview["intent"], (
        "the /respond response dropped `intent`, so its SSE snapshot nulls it (AUD-C-14)"
    )

    # The field being present on the response is only half of it - the snapshot is what
    # connected clients actually receive, and it is built by re-validating the response.
    snapshot = SessionSnapshotEvent.model_validate(result)
    assert snapshot.scope == preview["scope"]
    assert snapshot.intent == preview["intent"]


async def _checkpoint_writes_for_thread(thread_id: str) -> list[tuple[str, str, bytes]]:
    """Raw `(channel, type, blob)` rows LangGraph's `AsyncPostgresSaver` persisted for
    one thread. Fresh engine for the same reason as `_snapshot` (separate event loop).
    """
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT channel, type, blob FROM checkpoint_writes "
                    "WHERE thread_id = :thread_id"
                ),
                {"thread_id": thread_id},
            )
            return [(row.channel, row.type, bytes(row.blob)) for row in result]
    finally:
        await engine.dispose()


def test_resume_coordinates_do_not_outlive_the_locator_turn_in_checkpoint_writes() -> None:
    """AUD-C-03: the caller's precise coordinates arrived in the `/respond` resume
    payload and stayed in `checkpoint_writes` channel `__resume__` forever, against
    `LOCATION_CONSENT_NOTICE`'s verbatim "will not permanently store your precise
    location" (SPEC §5.1.3). After the locator turn completes, no `__resume__` row may
    remain for the thread, and the coordinates must not appear in any surviving write.

    Blobs are decoded with LangGraph's own serializer before matching - the audit's
    first probe used `CAST(blob AS text) LIKE`, and msgpack renders a float as eight
    binary bytes, so that version certified a database full of coordinates as clean.
    """
    distinctive_lat, distinctive_lon = 12.345678, -98.765432
    serde = JsonPlusSerializer()

    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        paused = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "What is the nearest branch to me?"},
        ).json()
        assert paused["pending_interrupt"]["interrupt_type"] == "location_consent"

        result = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={
                "interrupt_type": "location_consent",
                "approved": True,
                "latitude": distinctive_lat,
                "longitude": distinctive_lon,
            },
        ).json()
        # The coordinates really were used - the locator answered with distances.
        assert result["answer"] is not None
        assert "miles away" in result["answer"]

        # The audit measured the coordinates surviving two further turns; the purge
        # must not break the thread for them either.
        for query in ("zqxvchunk handbook", "What is the nearest branch to me?"):
            followup = client.post(
                f"/chat/sessions/{session_id}/messages", json={"query": query}
            )
            assert followup.status_code == 200

    rows = asyncio.run(_checkpoint_writes_for_thread(session_id))
    assert rows, "expected checkpoint writes for the thread - wrong thread id?"

    resume_rows = [row for row in rows if row[0] == "__resume__"]
    # The second locator turn above is still paused on its consent interrupt and was
    # never resumed, so no `__resume__` value exists for it either.
    assert resume_rows == []

    decoded = " ".join(repr(serde.loads_typed((type_, blob))) for _, type_, blob in rows)
    assert str(distinctive_lat) not in decoded
    assert str(distinctive_lon) not in decoded


def test_an_anonymous_caller_cannot_continue_an_owned_thread() -> None:
    """AUD-C-01 (S40, D-107), the first half.

    Verified live on staging before the fix: an unauthenticated caller continued a
    tutor's thread, got the tutor's answer and citation back, and resolved its interrupt
    - all 200. `/messages` was the only one of the three session entry points with no
    ownership check, and it is the one that starts every turn.
    """
    tutor = _token("tutor-ext-1", Role.TUTOR)
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions", headers=_auth_header(tutor)).json()[
            "chat_session_id"
        ]
        owner_turn = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "zqxvchunk handbook"},
            headers=_auth_header(tutor),
        )
        anonymous_turn = client.post(
            f"/chat/sessions/{session_id}/messages", json={"query": "zqxvchunk handbook"}
        )
        other_user_turn = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "zqxvchunk handbook"},
            headers=_auth_header(_token("student-ext-1", Role.STUDENT)),
        )

    assert owner_turn.status_code == 200
    assert anonymous_turn.status_code == 403
    assert other_user_turn.status_code == 403


def test_an_anonymous_turn_cannot_erase_a_thread_owner() -> None:
    """AUD-C-01's second half, which is what made the first half permanent.

    `resolve_role` wrote `user_external_id=None` for an anonymous turn, so a single
    unauthenticated request downgraded an owned session to ownerless - disabling the
    checks `/respond` and `/stream` *do* perform, for good. Asserted through `/stream`'s
    independent check rather than by reading state, so it fails if the owner is lost by
    any route.
    """
    tutor = _token("tutor-ext-1", Role.TUTOR)
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions", headers=_auth_header(tutor)).json()[
            "chat_session_id"
        ]
        client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "zqxvchunk handbook"},
            headers=_auth_header(tutor),
        )
        client.post(f"/chat/sessions/{session_id}/messages", json={"query": "zqxvchunk handbook"})

        # Inside the lifespan: `_snapshot` reads the app's own graph, whose checkpointer
        # connection closes when the client exits.
        #
        # The owner still holds the session...
        asyncio.run(_snapshot(session_id, tutor))
        # ...and an anonymous viewer still cannot read it.
        with pytest.raises(HTTPException) as caught:
            asyncio.run(_snapshot(session_id, None))
        assert caught.value.status_code == 403


def test_a_paused_turn_does_not_return_the_previous_turns_answer() -> None:
    """AUD-C-04 (S40, D-107): a node that pauses on `interrupt()` never returns, so
    nothing reset these fields and `/messages` answered with the *previous* turn's answer,
    citations and access hint. That is the vehicle that turned AUD-C-01 from a missing
    check into an actual disclosure - the anonymous caller was handed the tutor's answer
    because it was still sitting in state.

    The turn has to genuinely pause, which is why this drives the branch locator rather
    than two ordinary turns: an ordinary second turn overwrites every field on its way
    through and the stale-read is invisible (confirmed - a two-ordinary-turn version of
    this test passed with the fix removed).
    """
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        answered = client.post(
            f"/chat/sessions/{session_id}/messages", json={"query": "zqxvchunk handbook"}
        ).json()
        paused = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "What is the nearest branch to me?"},
        ).json()

    # The first turn really did produce a result worth leaking.
    assert answered["scope"] == "in_scope"
    assert answered["escalation_recommended"] is True
    assert answered["answer"] is not None

    # The second really did pause...
    assert paused["pending_interrupt"]["interrupt_type"] == "location_consent"
    # ...and carries none of the first turn's result.
    assert paused["answer"] is None
    assert paused["citations"] == []
    assert paused["escalation_recommended"] is False
    assert paused["access_hint"] is None
    assert paused["ics_content"] is None
