"""D-349: a chat SSE event published on one replica reaches a subscriber on another.

The chat twin of `apps/learning-api/tests/test_session_event_relay.py`, and the same
argument for its existence: two `ChatSessionEventBus` instances with two relays are two
replicas as far as this mechanism is concerned - separate objects, separate origins,
separate Postgres connections. Publishing on one and asserting the *other* one's subscriber
receives it is the property that was silently false on learning-api in production, where it
showed up as 2-of-4 delivery (D-334).

The old bus could not fail this test, because there was nothing to fail: with one in-process
dict, "another replica" was not expressible. That is why the defect survives review - not a
missing assertion, but a missing seam.
"""

import asyncio
import json

import pytest
from chat_api.services.session_event_relay import (
    CHANNEL,
    MAX_PAYLOAD_BYTES,
    ChatSessionEventRelay,
    connect_kwargs,
)
from chat_api.services.session_events import ChatSessionEventBus
from intellichoice_db.engine import create_engine
from sqlalchemy import text


def _postgres_available() -> bool:
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
    not _postgres_available(), reason="PostgreSQL is not reachable (run `make up`)"
)


async def _two_replicas() -> tuple[
    ChatSessionEventBus, ChatSessionEventRelay, ChatSessionEventBus, ChatSessionEventRelay
]:
    engine = create_engine()
    url = engine.url.render_as_string(hide_password=False)
    await engine.dispose()
    bus_a, bus_b = ChatSessionEventBus(), ChatSessionEventBus()
    relay_a = ChatSessionEventRelay(bus_a, url)
    relay_b = ChatSessionEventRelay(bus_b, url)
    await relay_a.start()
    await relay_b.start()
    return bus_a, relay_a, bus_b, relay_b


def test_an_event_published_on_one_replica_reaches_a_subscriber_on_another() -> None:
    """**The regression test for the whole phase.** Replica A publishes; B's subscriber
    must receive it. Before this, a `/stream` connection pinned to the other task from the
    POST simply never heard anything."""

    async def run() -> dict:
        bus_a, relay_a, bus_b, relay_b = await _two_replicas()
        try:
            queue_b = bus_b.subscribe("chat-session-x")
            bus_a.publish("chat-session-x", {"answer": "hello", "marker": "from-a"})
            # NOTIFY is scheduled, not awaited, and the round trip is a real one.
            return await asyncio.wait_for(queue_b.get(), timeout=5)
        finally:
            await relay_a.stop()
            await relay_b.stop()

    event = asyncio.run(run())
    assert event["marker"] == "from-a"


def test_the_publishing_replica_still_delivers_locally_exactly_once() -> None:
    """Local delivery must not regress, and must not double.

    `publish` serves local subscribers directly *and* sends a NOTIFY this process's own
    listener also receives. Without the origin check that echo would be delivered a second
    time - the client would apply the same snapshot twice.
    """

    async def run() -> int:
        bus_a, relay_a, _bus_b, relay_b = await _two_replicas()
        try:
            queue_a = bus_a.subscribe("chat-session-y")
            bus_a.publish("chat-session-y", {"answer": "hello"})
            await asyncio.sleep(1.5)
            return queue_a.qsize()
        finally:
            await relay_a.stop()
            await relay_b.stop()

    assert asyncio.run(run()) == 1


def test_a_replica_with_no_subscriber_for_that_session_ignores_the_event() -> None:
    """Fan-out is broadcast, so every replica receives every notification. A replica not
    holding a connection for that session must drop it rather than buffer traffic for
    sessions it knows nothing about."""

    async def run() -> int:
        bus_a, relay_a, bus_b, relay_b = await _two_replicas()
        try:
            other = bus_b.subscribe("some-other-session")
            bus_a.publish("chat-session-z", {"answer": "hello"})
            await asyncio.sleep(1.5)
            return other.qsize()
        finally:
            await relay_a.stop()
            await relay_b.stop()

    assert asyncio.run(run()) == 0


def test_the_channel_is_namespaced_to_this_app() -> None:
    """**Chat-specific, and the reason the channel name differs from learning-api's.**

    Both apps share one Postgres and `NOTIFY` is broadcast to every listener on a channel,
    so a shared name would deliver every learning snapshot into chat's bus and back. Those
    events would then be discarded because the session ids do not match - but only by luck:
    chat thread ids and learning thread ids are both bare uuid4 strings living in the *same*
    `checkpoints` table, so "they cannot collide" is a claim about uuid4, not about design.

    Pinned as a literal rather than compared against `learning_api.services.
    session_event_relay.CHANNEL`, which is what this test did first: chat-api does not
    declare learning-api as a dependency (see its `pyproject.toml`), and that import only
    resolved because the whole workspace shares one venv. A test that reaches across the
    seam the apps are built to keep is a worse defect than the one it guards.
    """
    assert CHANNEL == "chat_session_events"


def test_an_oversized_event_is_dropped_from_the_fanout_but_still_delivered_locally() -> None:
    """Postgres rejects a NOTIFY payload at 8000 bytes, and a truncated snapshot is worse
    than a missing one - the client would render half an event as though it were whole. The
    local subscriber is still served, so an oversized event degrades to the pre-D-349
    behaviour rather than corrupting anything."""

    async def run() -> tuple[int, int]:
        bus_a, relay_a, bus_b, relay_b = await _two_replicas()
        try:
            queue_a = bus_a.subscribe("chat-session-big")
            queue_b = bus_b.subscribe("chat-session-big")
            bus_a.publish("chat-session-big", {"filler": "x" * (MAX_PAYLOAD_BYTES + 1000)})
            await asyncio.sleep(1.5)
            return queue_a.qsize(), queue_b.qsize()
        finally:
            await relay_a.stop()
            await relay_b.stop()

    local, remote = asyncio.run(run())
    assert local == 1, "the local subscriber must still be served"
    assert remote == 0, "an oversized payload must not be sent, and must not be truncated"


def test_the_payload_ceiling_stays_under_the_postgres_limit() -> None:
    assert MAX_PAYLOAD_BYTES < 8000


def test_connection_arguments_survive_a_password_with_url_characters() -> None:
    """**The assertion that would have caught D-335, written here before shipping rather
    than after.**

    learning-api's first version of this relay string-replaced the DSN scheme and handed the
    result to `asyncpg.connect`. RDS's generated password contains URL-significant
    characters, so asyncpg parsed part of it as a query string and raised
    `ValueError: bad query field: '48>k['`. Relay startup is non-fatal, so the API booted
    green and the fan-out silently did not exist - on **both** replicas. Its test passed,
    because it asserted the transformation the code performed rather than the property that
    mattered.

    Asserting on parsed *components* cannot be satisfied by a broken transformation. The
    password is synthetic and deliberately hostile: `?`, `&`, `=`, `>`, `[`, `#`, `/` are
    all URL-significant.
    """
    hostile = "p%3Fa%26b%3Dc%3Ed%5Be%23f%2Fg"  # what SQLAlchemy holds, percent-encoded
    kwargs = connect_kwargs(f"postgresql+asyncpg://user:{hostile}@db.example:5432/mydb")

    assert kwargs["user"] == "user"
    assert kwargs["host"] == "db.example"
    assert kwargs["port"] == 5432
    assert kwargs["database"] == "mydb"
    # Decoded exactly once, by the same parser the engine uses - never re-quoted into a URL.
    assert kwargs["password"] == "p?a&b=c>d[e#f/g"


def test_a_local_connection_asks_for_no_ssl_and_a_remote_one_does() -> None:
    """S34: RDS ships `rds.force_ssl=1`, and local docker-compose Postgres neither needs nor
    supports SSL. Detected by host, the same way `create_engine` and `alembic/env.py` do it,
    so the relay cannot end up with a different posture from the rest of the app."""
    assert "ssl" not in connect_kwargs("postgresql+asyncpg://u:p@localhost:5432/d")
    assert "ssl" in connect_kwargs("postgresql+asyncpg://u:p@db.rds.amazonaws.com:5432/d")


def test_a_bus_with_no_relay_still_delivers_locally() -> None:
    """Dev, tests, and the degraded path where `relay.start()` failed: the bus must behave
    exactly as it did before D-349 rather than dropping events because fan-out is absent."""
    bus = ChatSessionEventBus()
    queue = bus.subscribe("chat-solo")
    bus.publish("chat-solo", {"answer": "hello"})
    assert queue.get_nowait() == {"answer": "hello"}


def test_a_failing_relay_does_not_break_local_delivery() -> None:
    """A fan-out problem must never surface in a request. The local subscriber has already
    been served by the time the relay is called, and the checkpoint backs any reconnect."""

    def _explode(session_id: str, event: dict) -> None:
        raise RuntimeError("relay is down")

    bus = ChatSessionEventBus()
    bus.attach_relay(_explode)
    queue = bus.subscribe("chat-fail")
    bus.publish("chat-fail", {"answer": "hello"})
    assert queue.get_nowait() == {"answer": "hello"}


def test_two_buses_have_different_origins() -> None:
    """The origin is what lets a listener drop the echo of its own publish. Two buses sharing
    one would each ignore the other's events - the fan-out would be wired and silent."""
    assert ChatSessionEventBus().origin != ChatSessionEventBus().origin


def test_the_relay_message_shape_is_what_the_listener_expects() -> None:
    """Publisher and listener are the same class, so nothing else would catch a rename of a
    key on one side only - the fan-out would go quiet with no error anywhere."""
    bus = ChatSessionEventBus()
    payload = json.dumps({"origin": bus.origin, "session_id": "s", "event": {"answer": "a"}})
    message = json.loads(payload)
    assert set(message) == {"origin", "session_id", "event"}
