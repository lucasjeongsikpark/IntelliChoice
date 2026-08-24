"""D-272/D-329: does the personalized hint reach a connected client over the real HTTP SSE route?

**What was already proven, and what was not.** `test_hint_personalization_scheduler.py` follows a
personalized hint up to an in-process `SessionEventBus` queue - the scheduler publishes, a
subscriber receives, the text differs from the canonical rung. Everything after that was
inference: that `GET /learning/sessions/{id}/stream` would serialize that event, that the frame
would survive `SessionSnapshotEvent` round-tripping, and that a client holding the connection
open would actually be handed it. Those hops have never been exercised together, and
`test_stream_and_history.py` says why - `TestClient.stream()` hangs against an endpoint that
never closes (D-033/D-404, one attempt hung for seven minutes), so every stream test in this
repository asserts against `_initial_snapshot` or the handler's `body_iterator` instead.

**So this one runs a real `uvicorn` server on an ephemeral port and reads real bytes off a real
socket.** It is the only test here that does; the cost is a server thread, and what it buys is
that nothing between the scheduler's `publish` and the wire is assumed. The whole student journey
runs over HTTP too - session, topic, pre-exam, finalize, a wrong answer, "Get a hint" - so the
marker the scheduler consumes is the one the graph really produced.

**Determinism.** Nothing here races: the client holds the stream open and answers nothing while
the rewrite is in flight, so the staleness guard cannot fire (that guard has its own tests, and
on staging it is the *usual* outcome because the e2e walk answers faster than Bedrock returns).
The frame either arrives within the read timeout or the test fails; there is no sleep-and-hope.

**Why the scheduler is installed by hand.** `main.py` builds it only under
`bedrock_provider == "bedrock"`; under the mock provider the rewrite stays inline in the graph
node, so there would be no background task and no publish to wait for (D-272). Injecting the real
scheduler class - with the mock gateway, the app's own bus, graph, factory and builder - is what
puts the deployed two-stage shape under test without a paid call.
"""

import asyncio
import contextlib
import json
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_observability.metrics import HINT_PERSONALIZATION_OUTCOMES
from intellichoice_shared.auth import Audience, Role
from intellichoice_shared.bedrock import BedrockTask
from learning_api.main import app
from learning_api.routers.sessions import build_personalized_hint_snapshot
from learning_api.services.hint_personalization_scheduler import (
    BackgroundHintPersonalizationScheduler,
)
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
            async with session_scope(create_session_factory(engine)) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


@contextlib.contextmanager
def _running_server() -> Iterator[str]:
    """The app under a real `uvicorn`, on a port the OS picks. Yields its base URL.

    Port 0 rather than a fixed one: the dev server (8001) and a prior run's socket in
    TIME_WAIT are both real ways a hard-coded port turns a green suite red.
    """
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="sse-test-server", daemon=True)
    thread.start()

    deadline = time.monotonic() + 60.0
    while not server.started:
        if not thread.is_alive():
            raise AssertionError("the test server thread died during startup")
        if time.monotonic() > deadline:
            raise AssertionError("the test server did not start within 60s")
        time.sleep(0.02)

    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        # `force_exit` as well as `should_exit`: a graceful shutdown waits for open
        # connections, and an SSE handler that is parked on its 15s keepalive is exactly
        # such a connection. The stream below is closed before this runs, so this is a
        # backstop rather than the normal path.
        server.should_exit = True
        thread.join(timeout=15.0)
        if thread.is_alive():
            server.force_exit = True
            thread.join(timeout=15.0)
        assert not thread.is_alive(), "the test server did not shut down"


@contextlib.contextmanager
def _deferred_hint_personalization() -> Iterator[None]:
    """Install the real background scheduler over the app the lifespan just built.

    Restored afterwards, since `app` is a module-level object every other test in this
    directory drives too.
    """
    previous = app.state.hint_personalization_scheduler
    mock = MockBedrockProvider()
    app.state.hint_personalization_scheduler = BackgroundHintPersonalizationScheduler(
        session_factory=app.state.db_session_factory,
        gateway_factory=lambda: ResilientBedrockGateway(
            provider=mock,
            embedding_provider=mock,
            # The registry entry D-329 was missing. Without it the task raises, the
            # scheduler swallows it, and this test would time out on a frame that was
            # never published.
            model_registry={BedrockTask.HINT_PERSONALIZATION: "us.anthropic.claude-haiku-4-5"},
        ),
        graph_getter=lambda: app.state.learning_graph,
        events=app.state.session_events,
        profile_adapter=app.state.profile_adapter,
        snapshot_builder=build_personalized_hint_snapshot,
    )
    try:
        yield
    finally:
        app.state.hint_personalization_scheduler = previous


def _next_data_frame(lines: Iterator[str], *, budget: int = 3) -> dict:
    """The next unnamed `data:` frame, skipping keepalives.

    Named frames are skipped rather than failed on: `KEEPALIVE_FRAME` is `event: keepalive`
    precisely so `EventSource.onmessage` ignores it, and a client reading this stream has to
    do the same. `budget` bounds the walk so a stream that only ever keepalives fails here
    rather than sitting on the read timeout: three keepalives is 45s, and every frame this
    test waits for is published within milliseconds of the request that causes it. Verified by
    removing the scheduler installed below - the run then fails here instead of passing.
    """
    for _ in range(budget):
        fields: list[tuple[str, str]] = []
        for line in lines:
            if line == "":
                break
            name, _, value = line.partition(":")
            fields.append((name, value.lstrip()))
        if not fields:
            continue
        if any(name == "event" for name, _ in fields):
            continue
        data = "".join(value for name, value in fields if name == "data")
        return json.loads(data)
    raise AssertionError("no data frame arrived before the frame budget was exhausted")


def _correct_option(variant_id: str) -> str:
    async def fetch() -> str:
        engine = create_engine()
        try:
            async with session_scope(create_session_factory(engine)) as session:
                variant = await QuestionRepository(session).get_variant(variant_id)
                assert variant is not None
                return variant.correct_option
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _authored_first_rung(variant_id: str) -> str:
    """The hint the bank holds for this variant, straight from the template.

    Read independently so "the click served the authored rung" is checked against the source
    of that text rather than against the response that is supposed to carry it.
    """

    async def fetch() -> str:
        engine = create_engine()
        try:
            async with session_scope(create_session_factory(engine)) as session:
                repo = QuestionRepository(session)
                variant = await repo.get_variant(variant_id)
                assert variant is not None
                template = await repo.get_template(variant.question_template_id)
                assert template is not None and template.hint_ladder
                return str(template.hint_ladder[0])
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _other_option(correct: str) -> str:
    for option in ("a", "b", "c", "d"):
        if option != correct:
            return option
    raise AssertionError("no alternate option available")


def test_a_personalized_hint_arrives_on_the_http_stream_a_student_is_holding_open() -> None:
    """The last hop, end to end: canonical rung on the click, personalized rewrite on the wire.

    Asserted on the *text differing* rather than on a frame arriving, for the same reason the
    bus-level test is: republishing the canonical rung would repaint the panel with what the
    student already had, and would be indistinguishable from success in every log and counter.
    """
    token = issuer.issue(sub=STUDENT_UNLINKED, role=Role.STUDENT, audience=Audience.LEARNING)
    headers = {"Authorization": f"Bearer {token}"}
    published_before = HINT_PERSONALIZATION_OUTCOMES.labels(outcome="published")._value.get()

    with _running_server() as base_url, _deferred_hint_personalization():
        with httpx.Client(base_url=base_url, timeout=httpx.Timeout(30.0)) as client:
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
            for index, item in enumerate(pre_items):
                variant_id = item["question_variant_id"]
                client.post(
                    f"/learning/sessions/{session_id}/answers",
                    headers={**headers, "Idempotency-Key": f"sse-pre-{index}-{session_id}"},
                    json={
                        "question_variant_id": variant_id,
                        "selected_option": _correct_option(variant_id),
                        "response_time_ms": 2000,
                    },
                )
            finalize = client.post(
                f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
            ).json()
            assert finalize["phase"] == "study"

            study_variant_id = finalize["items"][0]["question_variant_id"]
            wrong = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"sse-wrong-{session_id}"},
                json={
                    "question_variant_id": study_variant_id,
                    "selected_option": _other_option(_correct_option(study_variant_id)),
                    "response_time_ms": 2000,
                },
            ).json()
            assert wrong["pending_interrupt"]["interrupt_type"] == "intervention_choice"

            # Connected *before* the hint is asked for, which is what a browser does - the
            # tab has held `EventSource` open since the session started.
            stream_url = f"/learning/sessions/{session_id}/stream?token={token}"
            with client.stream("GET", stream_url) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                lines = response.iter_lines()

                initial = _next_data_frame(lines)
                assert initial["learning_session_id"] == session_id

                served = client.post(
                    f"/learning/sessions/{session_id}/respond",
                    headers=headers,
                    json={"interrupt_type": "intervention_choice", "choice": "hint"},
                ).json()["intervention"]
                assert served["type"] == "hint"
                canonical_text = served["hint_text"]
                # The two-stage shape D-272 exists for: the click returns the *authored* rung,
                # not a spinner and not a rewrite the student waited ~2.3s for.
                assert canonical_text == _authored_first_rung(study_variant_id)

                # Frame 1: the route's own publish of the canonical rung it just served.
                # Frame 2: the background rewrite. Reading both rather than skipping to the
                # last one keeps the ordering itself asserted.
                canonical_frame = _next_data_frame(lines)
                assert canonical_frame["intervention"]["hint_text"] == canonical_text

                personalized_frame = _next_data_frame(lines)

    # The delivery and the instrumentation, pinned to each other: this is the one run where
    # `published` is known to be the truth, so it is the run that proves the label means what
    # the dashboard will read it as (D-329).
    assert (
        HINT_PERSONALIZATION_OUTCOMES.labels(outcome="published")._value.get()
        == published_before + 1
    )

    intervention = personalized_frame["intervention"]
    assert intervention["type"] == "hint"
    assert intervention["hint_level"] == 1
    assert intervention["hint_text"] != canonical_text, (
        "the frame that reached the client over HTTP still carried the canonical rung - the "
        "student waited for a repaint of the text they already had"
    )
    assert intervention["hint_text"] == _stored_hint_text(session_id), (
        "the text on the wire is not the text in `hint_events` - the student is reading "
        "something no audit row records"
    )
    # The pause has to survive the frame, or the client replaces its snapshot with one that
    # says the ladder closed and the panel the hint lands in collapses (D-272).
    assert personalized_frame["pending_interrupt"] is not None
    assert personalized_frame["assistance_question"]["question_variant_id"] is not None


def _stored_hint_text(learning_session_id: str) -> str:
    """The personalized text the background task committed, read on its own connection."""

    async def fetch() -> str:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            "SELECT personalized_hint_text, was_personalized FROM hint_events "
                            "WHERE student_external_id = :s ORDER BY created_at DESC LIMIT 1"
                        ),
                        {"s": STUDENT_UNLINKED},
                    )
                ).one()
            assert bool(row[1]) is True, "the row still says the rewrite never happened"
            return str(row[0])
        finally:
            await engine.dispose()

    return asyncio.run(fetch())
