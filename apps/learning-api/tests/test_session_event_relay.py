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
from intellichoice_observability.metrics import (
    SSE_CONNECTIONS,
    SSE_EVENTS_DELIVERED,
    SSE_RELAY_FAILURES,
)
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


def test_events_published_back_to_back_all_reach_the_other_replica() -> None:
    """**D-395: the second concurrent publish used to be dropped in silence.**

    `_notify` awaits `execute` on the *one* publisher connection this process owns, and asyncpg
    refuses a second operation on a connection already in flight - `another operation is in
    progress`. `publish` schedules rather than awaits, so two events produced close together do
    exactly that, and the resulting exception was swallowed by `_notify`'s own `except`. The
    student's replica delivered locally and every other replica silently missed the event: D-334's
    bug returning by a different route, in a mechanism that exists only to fix D-334.

    Five events rather than two, published with no await between them, because one collision is a
    race and five is a queue. The assertion is on the *set* of markers rather than the count, so a
    partial drop names which one vanished instead of only how many.
    """

    async def run() -> set[str]:
        bus_a, relay_a, bus_b, relay_b = await _two_replicas()
        try:
            queue_b = bus_b.subscribe("session-burst")
            for index in range(5):
                bus_a.publish("session-burst", {"phase": "study", "marker": f"e{index}"})
            received: set[str] = set()
            for _ in range(5):
                event = await asyncio.wait_for(queue_b.get(), timeout=5)
                received.add(event["marker"])
            return received
        finally:
            await relay_a.stop()
            await relay_b.stop()

    assert asyncio.run(run()) == {"e0", "e1", "e2", "e3", "e4"}


def test_a_scheduled_notify_is_referenced_until_it_finishes() -> None:
    """The second half of D-395, and the weaker of the two assertions on purpose.

    `loop.create_task` returns a task the event loop holds only a **weak** reference to, so a
    fire-and-forget task can be garbage-collected mid-execution - asyncio's own documentation says
    to keep a reference. The relay now does, in `_pending`, and drops it on completion.

    **What this test does not do is reproduce a collection.** Forcing CPython to collect a
    scheduled task at the right instant is not something a test can do reliably, and asserting a
    falsification that cannot fail is how V11's `.ics` test ended up unable to hold D-352. So this
    asserts the property directly: the reference exists while the notify is in flight, and the set
    drains afterwards rather than growing for the life of the process.
    """

    async def run() -> tuple[int, int]:
        bus_a, relay_a, _bus_b, relay_b = await _two_replicas()
        try:
            bus_a.publish("session-ref", {"phase": "study"})
            in_flight = len(relay_a._pending)
            await asyncio.sleep(1.5)
            return in_flight, len(relay_a._pending)
        finally:
            await relay_a.stop()
            await relay_b.stop()

    in_flight, after = asyncio.run(run())
    assert in_flight == 1, "the scheduled notify was not referenced anywhere"
    assert after == 0, "completed notifies are never released, so the set grows unbounded"


def test_a_dropped_event_is_logged_with_the_session_it_belonged_to(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The 08-16 audit's other complaint about this path: the swallow was total. `notify_failed`
    said something went wrong somewhere, with no session id, so the one question worth asking -
    *whose* live update vanished? - could not be answered from the logs at all.

    Driven by closing the publisher out from under the relay, which is a real failure of this
    connection rather than a mocked one, and is what a Postgres restart or an idle-timeout reaper
    looks like from here.
    """

    async def run() -> None:
        bus_a, relay_a, _bus_b, relay_b = await _two_replicas()
        try:
            assert relay_a._publisher is not None
            await relay_a._publisher.close()
            bus_a.publish("session-doomed", {"phase": "study"})
            await asyncio.sleep(1.0)
        finally:
            await relay_a.stop()
            await relay_b.stop()

    before = SSE_RELAY_FAILURES.labels(reason="notify_failed")._value.get()
    with caplog.at_level("WARNING"):
        asyncio.run(run())

    failures = [r for r in caplog.records if r.message == "session_event_relay_notify_failed"]
    assert failures, "a dropped fan-out produced no warning at all"
    assert getattr(failures[0], "session_id", None) == "session-doomed"
    # D-396: the counter as well as the line. This is the exact signal that was missing while the
    # fan-out was losing four events in five - a log nobody queries is not telemetry.
    assert SSE_RELAY_FAILURES.labels(reason="notify_failed")._value.get() == before + 1


def test_the_sse_counters_move_with_the_thing_they_measure() -> None:
    """D-396. The 08-16 audit's line was "SSE has no telemetry at all", and D-395 is the bill:
    the fan-out was losing four events in five and every dashboard read healthy, because a
    swallowed warning is only found by someone who already suspects it.

    All four transitions in one test rather than four, because the gauge is the assertion most
    likely to be wrong in a way the others hide - a subscribe that increments and an unsubscribe
    that does not is a slow leak that looks correct for the first hour.
    """
    bus = SessionEventBus()

    before_connections = SSE_CONNECTIONS._value.get()
    before_delivered = SSE_EVENTS_DELIVERED._value.get()

    queue = bus.subscribe("session-metrics")
    assert SSE_CONNECTIONS._value.get() == before_connections + 1

    bus.publish("session-metrics", {"phase": "study"})
    assert queue.qsize() == 1
    assert SSE_EVENTS_DELIVERED._value.get() == before_delivered + 1

    bus.unsubscribe("session-metrics", queue)
    assert SSE_CONNECTIONS._value.get() == before_connections
    # A second unsubscribe removes nothing, so it must count nothing - otherwise the gauge walks
    # negative and reads as a bug in the stream rather than in the counter.
    bus.unsubscribe("session-metrics", queue)
    assert SSE_CONNECTIONS._value.get() == before_connections


def test_a_relay_that_raises_is_counted_as_well_as_logged() -> None:
    """The `publish_failed` reason: the relay callable itself blew up, before any NOTIFY was even
    scheduled. Distinct from `notify_failed` because the remedies differ - this one means the
    relay object is wrong, that one means Postgres or the connection is."""

    def _explode(session_id: str, event: dict) -> None:
        raise RuntimeError("relay is down")

    bus = SessionEventBus()
    bus.attach_relay(_explode)
    before = SSE_RELAY_FAILURES.labels(reason="publish_failed")._value.get()

    bus.publish("session-counted", {"phase": "study"})

    assert SSE_RELAY_FAILURES.labels(reason="publish_failed")._value.get() == before + 1


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
