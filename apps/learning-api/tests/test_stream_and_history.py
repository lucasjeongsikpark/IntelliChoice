"""S11: the SSE progress stream (SPEC §5.14.1), the dev-only token endpoint, and the
parent-dashboard history endpoint (SPEC §5.14.3).
"""

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer, JwtTokenVerifier
from intellichoice_adapters.mysql_profile_adapter import MySQLProfileAdapter
from intellichoice_adapters.seed.mysql_fixtures import (
    STUDENT_FIRST_CHILD,
    STUDENT_UNLINKED,
    seed,
)
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.auth import Audience, Role
from learning_api import main as main_module
from learning_api.config import Settings
from learning_api.main import app
from learning_api.routers.stream import _initial_snapshot
from learning_api.services.session_events import SessionEventBus
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

issuer = FakeTokenIssuer()


def _mysql_available() -> bool:
    async def check() -> bool:
        engine = create_async_engine(MYSQL_URL, connect_args={"connect_timeout": 1})
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


def _postgres_available() -> bool:
    async def check() -> bool:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1 FROM topics LIMIT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    not (_mysql_available() and _postgres_available()),
    reason="MySQL/PostgreSQL not reachable or not migrated (run `make up && make db-upgrade`)",
)


@pytest.fixture(scope="module", autouse=True)
def seeded_fixtures() -> None:
    asyncio.run(seed(MYSQL_URL))

    async def load() -> None:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _student_token(student_id: str) -> str:
    return issuer.issue(sub=student_id, role=Role.STUDENT, audience=Audience.LEARNING)


def _correct_options(variant_ids: list[str]) -> dict[str, str]:
    async def fetch() -> dict[str, str]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                repo = QuestionRepository(session)
                result = {}
                for variant_id in variant_ids:
                    variant = await repo.get_variant(variant_id)
                    assert variant is not None
                    result[variant_id] = variant.correct_option
                return result
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _other_option(correct: str) -> str:
    for option in ("a", "b", "c", "d"):
        if option != correct:
            return option
    raise AssertionError("no alternate option available")


def test_dev_token_issues_a_verifiable_token() -> None:
    client = TestClient(app)
    resp = client.post("/dev/token", json={"role": "student", "sub": STUDENT_UNLINKED})
    assert resp.status_code == 200

    claims = JwtTokenVerifier().verify(resp.json()["token"], Audience.LEARNING)
    assert claims.sub == STUDENT_UNLINKED
    assert claims.role == Role.STUDENT


def test_dev_token_404s_outside_dev_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "get_settings", lambda: Settings(environment="production"))
    client = TestClient(app)
    resp = client.post("/dev/token", json={"role": "student", "sub": STUDENT_UNLINKED})
    assert resp.status_code == 404


def test_session_event_bus_publishes_only_to_subscribers_of_that_session() -> None:
    bus = SessionEventBus()
    queue_a = bus.subscribe("session-a")
    queue_b = bus.subscribe("session-b")

    bus.publish("session-a", {"phase": "pre_exam"})

    assert queue_a.get_nowait() == {"phase": "pre_exam"}
    assert queue_b.empty()

    bus.unsubscribe("session-a", queue_a)
    bus.publish("session-a", {"phase": "study"})
    assert queue_a.empty()


def test_stream_connect_returns_current_snapshot_for_refresh_restore() -> None:
    """SPEC Phase 11 (§6.12) "Done when": a (re)connect must see exactly where the
    session currently is, proving the same property `/resume` proves for plain REST.

    Exercises `_initial_snapshot` directly rather than the live HTTP `/stream` response:
    that response intentionally never closes on its own (it idles on a 15s keepalive
    between pushes), and `TestClient.stream()`'s synchronous portal doesn't reliably
    unwind against an endpoint that never ends - confirmed hanging in practice. The real
    end-to-end behavior (connect, initial snapshot, live push after an action, clean
    close) was verified manually against a running `uvicorn` server via `curl`; this
    covers the same authorization + snapshot-shaping logic deterministically.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items = topics_resp.json()["items"]

        async def _fetch_snapshot():
            # A fresh `MySQLProfileAdapter`, not `app.state.profile_adapter` - that one's
            # SQLAlchemy engine/pooled connections are bound to `TestClient`'s own portal
            # loop, and `_maybe_fire_pre_intro` (S26) is the first thing on this connect
            # path to actually await a MySQL call, which fails cross-loop under this
            # test's own `asyncio.run`. Disposed explicitly below - unlike the old Motor
            # client, an undisposed `aiomysql` connection's `__del__` raises `RuntimeError:
            # Event loop is closed` once this function's own loop tears down.
            profile_adapter = MySQLProfileAdapter(MYSQL_URL)
            engine = create_engine()
            try:
                session_factory = create_session_factory(engine)
                async with session_scope(session_factory) as session:
                    return await _initial_snapshot(
                        session_id,
                        app.state.learning_graph,
                        profile_adapter,
                        session,
                        app.state.bedrock_gateway,
                        token,
                    )
            finally:
                await profile_adapter.close()
                await engine.dispose()

        snapshot = asyncio.run(_fetch_snapshot())

    assert snapshot.learning_session_id == session_id
    assert snapshot.phase == "pre_exam"
    assert snapshot.items is not None
    assert [item.model_dump() for item in snapshot.items] == pre_items


def test_stream_rejects_a_token_for_a_different_student() -> None:
    token = _student_token(STUDENT_UNLINKED)
    other_token = _student_token(STUDENT_FIRST_CHILD)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )

        async def _fetch_snapshot():
            profile_adapter = MySQLProfileAdapter(MYSQL_URL)
            engine = create_engine()
            try:
                session_factory = create_session_factory(engine)
                async with session_scope(session_factory) as session:
                    return await _initial_snapshot(
                        session_id,
                        app.state.learning_graph,
                        profile_adapter,
                        session,
                        app.state.bedrock_gateway,
                        other_token,
                    )
            finally:
                await profile_adapter.close()
                await engine.dispose()

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_fetch_snapshot())

    assert exc_info.value.status_code == 403


def test_student_history_reflects_a_completed_session() -> None:
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        pre_items = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        ).json()["items"]
        pre_correct = _correct_options([i["question_variant_id"] for i in pre_items])

        body: dict = {}
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            body = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"hist-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            ).json()

        # S22/D-064: pre/post exams no longer auto-advance once the last item is
        # answered - explicit finalize is now required to transition.
        body = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        ).json()

        step = 0
        while body["phase"] == "study":
            variant_id = body["items"][0]["question_variant_id"]
            correct = _correct_options([variant_id])[variant_id]
            body = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"hist-study-{step}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": correct,
                    "response_time_ms": 2000,
                },
            ).json()
            step += 1

        for index, item in enumerate(body["items"]):
            variant_id = item["question_variant_id"]
            correct = _correct_options([variant_id])[variant_id]
            body = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"hist-post-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": correct,
                    "response_time_ms": 2000,
                },
            ).json()

        body = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        ).json()
        assert body["phase"] == "completed"

        history_resp = client.get(
            f"/learning/students/{STUDENT_UNLINKED}/sessions", headers=headers
        )
        assert history_resp.status_code == 200
        history = history_resp.json()

        matching = [
            s
            for s in history["completed_sessions"]
            if s["post_raw_score"] == body["learning_gain"]["post_raw_score"]
            and s["topic_id"] == "linear_equations"
        ]
        assert matching, history["completed_sessions"]
        summary = matching[0]
        assert summary["pre_raw_score"] == body["learning_gain"]["pre_raw_score"]
        assert summary["raw_gain"] == body["learning_gain"]["raw_gain"]

        cross_resp = client.get(
            f"/learning/students/{STUDENT_UNLINKED}/sessions",
            headers=_auth_header(_student_token(STUDENT_FIRST_CHILD)),
        )
        assert cross_resp.status_code == 403
