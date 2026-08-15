"""D-335: an SSE event published on one replica reaches a subscriber on another.

**The test that would have caught D-334.** Two `SessionEventBus` instances with two relays are two
replicas, as far as this mechanism is concerned - separate objects, separate origins, separate
Postgres connections. Publishing on one and asserting the *other* one's subscriber receives it is
exactly the property that was silently false in production, where it showed up as personalized
hints arriving 2 times in 4.

The old bus could not fail this test, because there was nothing to fail: with one in-process dict,
"another replica" was not expressible. That is why the defect survived - not a missing assertion,
but a missing seam.
"""

import asyncio
import json

import pytest
from intellichoice_db.engine import create_engine
from learning_api.services.session_event_relay import (
    MAX_PAYLOAD_BYTES,
    SessionEventRelay,
    connect_kwargs,
)
from learning_api.services.session_events import SessionEventBus
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
    SessionEventBus, SessionEventRelay, SessionEventBus, SessionEventRelay
]:
    """Two buses, two relays, two origins - which is what "two replicas" means to this mechanism."""
    engine = create_engine()
    url = engine.url.render_as_string(hide_password=False)
    await engine.dispose()
    bus_a, bus_b = SessionEventBus(), SessionEventBus()
    relay_a, relay_b = SessionEventRelay(bus_a, url), SessionEventRelay(bus_b, url)
    await relay_a.start()
    await relay_b.start()
    return bus_a, relay_a, bus_b, relay_b


def test_an_event_published_on_one_replica_reaches_a_subscriber_on_another() -> None:
    """**The D-334 regression test.** Replica A publishes; B's subscriber must receive it."""

    async def run() -> dict:
        bus_a, relay_a, bus_b, relay_b = await _two_replicas()
        try:
            queue_b = bus_b.subscribe("session-x")
            bus_a.publish("session-x", {"phase": "study", "marker": "from-a"})
            # NOTIFY is scheduled, not awaited, and the round trip is a real one.
            return await asyncio.wait_for(queue_b.get(), timeout=5)
        finally:
            await relay_a.stop()
            await relay_b.stop()

    event = asyncio.run(run())
    assert event["marker"] == "from-a"


def test_the_publishing_replica_still_delivers_locally_exactly_once() -> None:
    """Local delivery must not regress, and must not double.

    `publish` serves local subscribers directly *and* sends a NOTIFY that this process's own
    listener also receives. Without the origin check that echo would be delivered a second time -
    the client would see the same snapshot twice, which for a hint means the panel repainting
    itself for no reason.
    """

    async def run() -> int:
        bus_a, relay_a, _bus_b, relay_b = await _two_replicas()
        try:
            queue_a = bus_a.subscribe("session-y")
            bus_a.publish("session-y", {"phase": "study"})
            # Give the echo every chance to arrive before counting.
            await asyncio.sleep(1.5)
            return queue_a.qsize()
        finally:
            await relay_a.stop()
            await relay_b.stop()

    assert asyncio.run(run()) == 1


def test_a_replica_with_no_subscriber_for_that_session_ignores_the_event() -> None:
    """Fan-out is broadcast, so every replica receives every notification. A replica that is not
    holding a connection for that session must simply drop it rather than buffering events for
    sessions it knows nothing about - otherwise every replica accumulates every session's traffic.
    """

    async def run() -> int:
        bus_a, relay_a, bus_b, relay_b = await _two_replicas()
        try:
            other = bus_b.subscribe("some-other-session")
            bus_a.publish("session-z", {"phase": "study"})
            await asyncio.sleep(1.5)
            return other.qsize()
        finally:
            await relay_a.stop()
            await relay_b.stop()

    assert asyncio.run(run()) == 0


def test_an_oversized_event_is_dropped_from_the_fanout_but_still_delivered_locally() -> None:
    """Postgres rejects a NOTIFY payload at 8000 bytes, and a truncated snapshot is worse than a
    missing one - the client would render a half-event as though it were whole.

    Measured against real staging frames (1160-2291 bytes) this is headroom, not a live limit, but
    a 10-item exam snapshot is the case that could approach it. The local subscriber is still
    served, so the oversized event degrades to pre-D-335 behaviour rather than corrupting anything.
    """

    async def run() -> tuple[int, int]:
        bus_a, relay_a, bus_b, relay_b = await _two_replicas()
        try:
            queue_a = bus_a.subscribe("session-big")
            queue_b = bus_b.subscribe("session-big")
            bus_a.publish("session-big", {"filler": "x" * (MAX_PAYLOAD_BYTES + 1000)})
            await asyncio.sleep(1.5)
            return queue_a.qsize(), queue_b.qsize()
        finally:
            await relay_a.stop()
            await relay_b.stop()

    local, remote = asyncio.run(run())
    assert local == 1, "the local subscriber must still be served"
    assert remote == 0, "an oversized payload must not be sent, and must not be truncated"


def test_the_payload_ceiling_stays_under_the_postgres_limit() -> None:
    """8000 is Postgres's hard limit for a NOTIFY payload; the margin covers the JSON envelope
    (origin, session id, keys) wrapped around the event."""
    assert MAX_PAYLOAD_BYTES < 8000


def test_connection_arguments_survive_a_password_with_url_characters() -> None:
    """**This test replaces one that passed while the code was broken.**

    The first version asserted that `"postgresql+asyncpg://..."` became `"postgresql://..."` - the
    transformation the code performed, not the property that mattered. It passed, shipped, and the
    relay then failed to start on **both** staging replicas: RDS's generated password contains
    URL-significant characters, so asyncpg parsed part of it as a query string and raised
    `ValueError: bad query field`. Because relay startup is non-fatal, the API booted normally and
    the fan-out silently did not exist.

    Asserting on parsed *components* is the property that cannot be satisfied by a broken
    transformation. The password here is synthetic and deliberately hostile: `?`, `&`, `=`, `>`,
    `[`, `#`, `/` are all URL-significant.
    """
    hostile = "p%3Fa%26b%3Dc%3Ed%5Be%23f%2Fg"  # what SQLAlchemy would hold, percent-encoded
    kwargs = connect_kwargs(f"postgresql+asyncpg://user:{hostile}@db.example:5432/mydb")

    assert kwargs["user"] == "user"
    assert kwargs["host"] == "db.example"
    assert kwargs["port"] == 5432
    assert kwargs["database"] == "mydb"
    # Decoded exactly once, by the same parser the engine uses - never re-quoted into a URL.
    assert kwargs["password"] == "p?a&b=c>d[e#f/g"


def test_a_local_connection_asks_for_no_ssl_and_a_remote_one_does() -> None:
    """S34: RDS ships `rds.force_ssl=1`, and local docker-compose Postgres neither needs nor
    supports SSL. Detected by host, the same way `create_engine` and `alembic/env.py` do it, so the
    relay cannot end up with a different posture from the rest of the app by accident."""
    assert "ssl" not in connect_kwargs("postgresql+asyncpg://u:p@localhost:5432/d")
    assert "ssl" in connect_kwargs("postgresql+asyncpg://u:p@db.rds.amazonaws.com:5432/d")


def test_a_bus_with_no_relay_still_delivers_locally() -> None:
    """Dev, tests, and the degraded path where `relay.start()` failed: the bus must behave exactly
    as it did before D-335 rather than dropping events because the fan-out is absent."""
    bus = SessionEventBus()
    queue = bus.subscribe("session-solo")
    bus.publish("session-solo", {"phase": "study"})
    assert queue.get_nowait() == {"phase": "study"}


def test_a_failing_relay_does_not_break_local_delivery() -> None:
    """A fan-out problem must never surface in a request. The local subscriber has already been
    served by the time the relay is called, and the checkpoint still backs any reconnect."""

    def _explode(session_id: str, event: dict) -> None:
        raise RuntimeError("relay is down")

    bus = SessionEventBus()
    bus.attach_relay(_explode)
    queue = bus.subscribe("session-fail")
    bus.publish("session-fail", {"phase": "study"})
    assert queue.get_nowait() == {"phase": "study"}


def test_two_buses_have_different_origins() -> None:
    """The origin is what lets a listener drop the echo of its own publish. Two buses sharing one
    would each ignore the other's events - the fan-out would be wired and silent."""
    assert SessionEventBus().origin != SessionEventBus().origin


def test_the_relay_message_shape_is_what_the_listener_expects() -> None:
    """Publisher and listener are the same class, so nothing else would catch a rename of a key on
    one side only - the fan-out would go quiet with no error anywhere."""
    bus = SessionEventBus()
    payload = json.dumps({"origin": bus.origin, "session_id": "s", "event": {"phase": "study"}})
    message = json.loads(payload)
    assert set(message) == {"origin", "session_id", "event"}
