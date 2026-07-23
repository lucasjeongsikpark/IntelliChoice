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

import pytest
from chat_api.main import app
from chat_api.routers.stream import _initial_snapshot
from fastapi import HTTPException
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer, JwtTokenVerifier
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.models.chat import ChatSuggestion
from intellichoice_db.repositories.chat import ChatSuggestionRepository
from intellichoice_shared.auth import Audience, Role
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
