"""S11: the SSE progress stream (SPEC §5.14.1), the dev-only token endpoint, and the
parent-dashboard history endpoint (SPEC §5.14.3).
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import cast

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import (
    DEV_JWT_SECRET,
    FakeTokenIssuer,
    JwtTokenVerifier,
    TokenError,
)
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
from learning_api.routers.sessions import SessionSnapshotEvent
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


def test_dev_token_404s_when_endpoint_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-085: environment=="dev" alone must not be enough - this is the second,
    independent gate that stops a repeat of the S32 staging misconfiguration.
    """
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(environment="dev", dev_token_endpoint_enabled=False),
    )
    client = TestClient(app)
    resp = client.post("/dev/token", json={"role": "student", "sub": STUDENT_UNLINKED})
    assert resp.status_code == 404


STAGING_SECRET = "s" * 64


def _staging_settings() -> Settings:
    """Exactly staging's real posture (S36/D-097): not a dev environment, the D-085 flag
    off, and only the shared secret configured - so these tests prove the secret alone is
    what opens the endpoint, not some residual dev setting.
    """
    return Settings(
        environment="staging",
        dev_token_endpoint_enabled=False,
        staging_token_shared_secret=STAGING_SECRET,
    )


def test_dev_token_issues_a_token_on_staging_with_the_shared_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S36/D-097: the audit sessions' authenticated path against live staging. The point
    of the test is the *combination* - a non-dev environment with the D-085 flag off still
    mints a token, but only for a caller holding the Secrets-Manager secret.
    """
    monkeypatch.setattr(main_module, "get_settings", _staging_settings)
    client = TestClient(app)

    resp = client.post(
        "/dev/token",
        json={"role": "student", "sub": STUDENT_UNLINKED},
        headers={"X-Staging-Token-Secret": STAGING_SECRET},
    )

    assert resp.status_code == 200
    claims = JwtTokenVerifier().verify(resp.json()["token"], Audience.LEARNING)
    assert claims.sub == STUDENT_UNLINKED
    assert claims.role == Role.STUDENT


def test_dev_token_signs_with_the_configured_secret_not_the_dev_constant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S36 regression, found live and not by any unit test. Every other test here leaves
    `jwt_signing_secret` at its default, which *is* `DEV_JWT_SECRET` - so a bare
    `FakeTokenIssuer()` (signing with that constant) and the settings-driven verifier
    agreed by coincidence. On real staging, where D-085 injects a random per-app secret
    from Secrets Manager, they did not: `/dev/token` returned 200 with a token every
    authenticated route then rejected with 401. The endpoint was live, green, and useless.

    Pinning it with a deliberately non-default secret is what makes the two sides' agreement
    a tested property rather than a shared default.
    """
    real_secret = "not-the-public-dev-constant-" + "x" * 32
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(
            environment="staging",
            dev_token_endpoint_enabled=False,
            staging_token_shared_secret=STAGING_SECRET,
            jwt_signing_secret=real_secret,
        ),
    )
    client = TestClient(app)

    resp = client.post(
        "/dev/token",
        json={"role": "student", "sub": STUDENT_UNLINKED},
        headers={"X-Staging-Token-Secret": STAGING_SECRET},
    )
    assert resp.status_code == 200
    token = resp.json()["token"]

    # Verifies under the configured secret...
    claims = JwtTokenVerifier(secret=real_secret).verify(token, Audience.LEARNING)
    assert claims.sub == STUDENT_UNLINKED
    # ...and must NOT verify under the public dev constant, or the real secret is decorative.
    with pytest.raises(TokenError):
        JwtTokenVerifier(secret=DEV_JWT_SECRET).verify(token, Audience.LEARNING)


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no_header"),
        pytest.param({"X-Staging-Token-Secret": "wrong-secret"}, id="wrong_secret"),
        pytest.param({"X-Staging-Token-Secret": ""}, id="empty_secret"),
    ],
)
def test_dev_token_404s_on_staging_without_the_shared_secret(
    monkeypatch: pytest.MonkeyPatch, headers: dict[str, str]
) -> None:
    """The gate's real job. `empty_secret` is the fail-closed case that matters most: a
    caller presenting "" must never match, including in the (future production) case where
    the secret itself is unset - see `staging_secret_matches`.
    """
    monkeypatch.setattr(main_module, "get_settings", _staging_settings)
    client = TestClient(app)

    resp = client.post(
        "/dev/token", json={"role": "student", "sub": STUDENT_UNLINKED}, headers=headers
    )

    assert resp.status_code == 404


def test_dev_token_404s_on_staging_when_no_secret_is_configured_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The absence of a configured credential must not be satisfiable by presenting the
    absence of one - the fail-open shape this project has produced three times (D-096).
    """
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(environment="staging", dev_token_endpoint_enabled=False),
    )
    client = TestClient(app)

    for headers in ({}, {"X-Staging-Token-Secret": ""}):
        resp = client.post(
            "/dev/token", json={"role": "student", "sub": STUDENT_UNLINKED}, headers=headers
        )
        assert resp.status_code == 404


# AUD-L-01 (D-175). Mirrors chat-api's `test_auth.py` block - see that file for the full
# reasoning. Both apps are asserted because the finding was measured on both public edges
# (D-171) and because the fix lives in shared code that either app could stop calling.
_DISCLOSING_REQUEST_SHAPES = [
    pytest.param("POST", {"role": "not-a-role"}, id="invalid_role_body"),
    pytest.param("POST", {}, id="empty_body"),
    pytest.param("POST", None, id="no_body"),
    pytest.param("GET", None, id="wrong_method"),
    pytest.param("PUT", None, id="unregistered_method"),
]


@pytest.mark.parametrize(("method", "body"), _DISCLOSING_REQUEST_SHAPES)
def test_closed_dev_token_is_indistinguishable_from_an_absent_path(
    monkeypatch: pytest.MonkeyPatch, method: str, body: dict | None
) -> None:
    monkeypatch.setattr(main_module, "get_settings", _staging_settings)
    client = TestClient(app)

    resp = client.request(method, "/dev/token", json=body)
    control = client.request(method, "/dev/nonexistent", json=body)

    assert (resp.status_code, resp.json()) == (control.status_code, control.json())
    assert resp.status_code == 404


def test_the_absent_path_control_is_not_vacuous() -> None:
    client = TestClient(app)
    assert client.post("/dev/nonexistent", json={}).status_code == 404


def test_an_open_dev_token_still_validates_its_body_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller holding the secret must still get FastAPI's ordinary 422 - only the closed
    case has to be silent, and a gate that swallowed validation for everyone would be a
    different defect.
    """
    monkeypatch.setattr(main_module, "get_settings", _staging_settings)
    client = TestClient(app)

    resp = client.post(
        "/dev/token",
        json={"role": "not-a-role"},
        headers={"X-Staging-Token-Secret": STAGING_SECRET},
    )

    assert resp.status_code == 422


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


def test_stream_connect_rereads_state_after_the_narrative_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUD-F-26: the initial snapshot must describe the session as it is when the snapshot
    is *sent*, not as it was before a seconds-long Bedrock call.

    `_maybe_fire_pre_intro` is a real model call on staging (~2.3s measured). The browser
    opens `EventSource` as soon as it has a session id, so it routinely starts a topic - and
    the pre-exam - while this connect is still inside that call. Serving the pre-call state
    then pushes the client *backwards*: measured on staging, a student at `pre_exam` by
    994ms received a `student_selected` snapshot at 2736ms, landed back on the topic-select
    screen, and the exam screen's view-time cleanup flushed a truncated 1653ms into
    `time_spent_minutes` on its way out.

    Faked at the seam rather than by racing a real Bedrock call, because the defect is an
    *ordering* one and a test for it should be deterministic: `aget_state` returns
    `student_selected` first and `pre_exam` afterwards, which is exactly what the real
    checkpoint does when the client advances mid-call. Against the pre-fix code this
    returns `student_selected`.

    The mock provider is why this never showed locally - it returns in ~26ms and leaves no
    window to lose - so this is the AUD-C-02/AUD-F-19/AUD-F-21 lesson paid for a fourth
    time, and the reason the fake is the right tool here.
    """
    token = _student_token(STUDENT_UNLINKED)

    class _FakeSnapshot:
        def __init__(self, values: dict) -> None:
            self.values = values
            self.tasks = ()

    before = {
        "phase": "student_selected",
        "student_external_id": STUDENT_UNLINKED,
        "user_external_id": STUDENT_UNLINKED,
    }
    after = {
        "phase": "pre_exam",
        "student_external_id": STUDENT_UNLINKED,
        "user_external_id": STUDENT_UNLINKED,
        "last_items": [],
    }
    reads: list[str] = []

    class _FakeGraph:
        async def aget_state(self, _config: dict) -> _FakeSnapshot:
            # First read is the pre-call state; every later read sees the advanced session.
            values = before if not reads else after
            reads.append(values["phase"])
            return _FakeSnapshot(values)

    async def _fake_pre_intro(**_kwargs: object) -> tuple[str, list[str]]:
        return "Welcome to math practice!", []

    monkeypatch.setattr(
        "learning_api.routers.stream._maybe_fire_pre_intro", _fake_pre_intro
    )

    async def _fetch() -> SessionSnapshotEvent:
        profile_adapter = MySQLProfileAdapter(MYSQL_URL)
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                return await _initial_snapshot(
                    "sess-aud-f-26",
                    _FakeGraph(),  # type: ignore[arg-type]
                    profile_adapter,
                    session,
                    app.state.bedrock_gateway,
                    token,
                )
        finally:
            await profile_adapter.close()
            await engine.dispose()

    with TestClient(app):
        snapshot = asyncio.run(_fetch())

    assert reads == ["student_selected", "pre_exam"], (
        "the connect path read the checkpoint only once, so the snapshot it sends was "
        "captured before the narrative call rather than after it"
    )
    assert snapshot.phase == "pre_exam", (
        "the initial snapshot served a phase the session had already left - a client that "
        "started an exam during the narrative call is pushed back to topic selection "
        "(AUD-F-26)"
    )
    # The fallback narrative still rides along; re-reading must not discard it.
    assert snapshot.stage_narrative == "Welcome to math practice!"


class _StaleSnapshotFake:
    """`aget_state` result whose values already carry a narrative, so `_initial_snapshot`
    takes its single-read path - these two tests are about what happens *around* the read,
    not AUD-F-26's re-read inside it.
    """

    def __init__(self, values: dict) -> None:
        self.values = values
        self.tasks = ()


def test_stream_delivers_an_event_published_during_the_initial_read() -> None:
    """AUD-F-36: an action that completes while `/stream` is still reading its initial
    snapshot must still reach that stream.

    The failing staging record: a parent's child-selection `/respond` and the SSE connect
    stamped at the same millisecond; `/respond`'s publish found no subscriber (the old code
    subscribed only *after* the read), the initial frame was built from the pre-resume
    checkpoint, and the stream then had nothing left to say - the client sat on "who's
    learning today" through 123 polls of a 60s timeout with every request returning 200.
    ~1 in 3 whole-suite e2e runs, 0 of 3 in isolation, which is why the deterministic fake
    publishes at the exact seam instead of racing real requests.

    Against the pre-fix code this times out waiting for the second frame: the published
    event was lost, and the next thing the stream would say is a keep-alive at 15s.
    """
    from learning_api.routers import stream as stream_module

    token = _student_token(STUDENT_UNLINKED)
    session_id = "sess-aud-f-36"
    bus = SessionEventBus()

    values = {
        "phase": "student_selected",
        "user_external_id": STUDENT_UNLINKED,
        "stage_narrative": "already have one",
        "stage_narrative_evidence": [],
    }

    class _PublishingGraph:
        async def aget_state(self, _config: dict) -> _StaleSnapshotFake:
            # The seam: a `/respond` resume completes and publishes while this connect
            # is mid-read - before the old code's subscribe ever ran.
            bus.publish(session_id, {"phase": "pre_exam", "pending_interrupt": None})
            return _StaleSnapshotFake(values)

    async def _run() -> list[str]:
        response = await stream_module.stream_session(
            session_id,
            token,
            profile_adapter=None,  # type: ignore[arg-type] - unreachable: no student resolved
            events=bus,
            graph=_PublishingGraph(),  # type: ignore[arg-type]
            db=None,  # type: ignore[arg-type] - unreachable on this path
            bedrock_gateway=None,  # type: ignore[arg-type] - narrative already present
        )
        frames = []
        # `body_iterator` is typed as the broad `AsyncContentStream`; this endpoint's is
        # always the async generator `event_stream()`.
        iterator = cast(AsyncGenerator[str, None], response.body_iterator)
        try:
            frames.append(await asyncio.wait_for(anext(iterator), timeout=2.0))
            frames.append(await asyncio.wait_for(anext(iterator), timeout=2.0))
        finally:
            await iterator.aclose()
        return [str(frame) for frame in frames]

    frames = asyncio.run(_run())
    assert '"phase":"student_selected"' in frames[0].replace(" ", ""), (
        "first frame should be the initial snapshot"
    )
    assert '"phase":"pre_exam"' in frames[1].replace(" ", ""), (
        "the event published during the initial read never reached the stream - the "
        "subscription must be registered before the read, or a client whose action "
        "completes in that window waits forever on a state change that already "
        "happened (AUD-F-36)"
    )
    assert not bus._subscribers, "closing the stream must unsubscribe its queue"


def test_stream_unsubscribes_when_the_initial_read_fails() -> None:
    """The hazard the AUD-F-36 ordering introduces: subscribing first means the auth/404
    failures inside `_initial_snapshot` now happen with a live subscription, which must
    not leak.
    """
    from learning_api.routers import stream as stream_module

    bus = SessionEventBus()

    class _NeverReached:
        async def aget_state(self, _config: dict) -> _StaleSnapshotFake:
            raise AssertionError("token verification fails before any read")

    async def _run() -> None:
        await stream_module.stream_session(
            "sess-aud-f-36-leak",
            "not-a-valid-token",
            profile_adapter=None,  # type: ignore[arg-type]
            events=bus,
            graph=_NeverReached(),  # type: ignore[arg-type]
            db=None,  # type: ignore[arg-type]
            bedrock_gateway=None,  # type: ignore[arg-type]
        )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 401
    assert not bus._subscribers, (
        "a rejected connect left its queue subscribed - every failed auth attempt "
        "would accumulate an unbounded queue the bus keeps publishing into"
    )
