"""Fans chat SSE events across replicas with Postgres `LISTEN`/`NOTIFY` (D-349).

The chat twin of `learning_api.services.session_event_relay`, deliberately copied rather than
shared: the two apps are independently deployed and neither imports the other. The channel
name differs so the two fan-outs cannot cross-deliver on the shared database.

**Why chat needs it even though the carry-over called it low value.** chat-api's only
publishers are on the request path, so the client that made the POST already has the answer in
the HTTP response - true, and the reason this waited. It is not true of the `/stream`
connection, which is what a *reloaded tab*, a second device, or a recovering client depends
on, and which the ALB pins to whichever replica it chose. chat-api's `autoscaling_max_capacity`
is 3 with **ALB p95 latency** step scaling (AUD-F-14), so the trigger for scaling out is a slow
turn - and a slow turn is exactly when someone reloads. D-334 measured the same shape at 50%
loss on learning-api.

**Why `LISTEN`/`NOTIFY` and not a queue.** The semantics needed are *broadcast to every
replica*, where the one holding the connection delivers and the rest discard. `NOTIFY` is
exactly that. A work queue (SQS) has competing-consumer semantics - one message to exactly one
poller - so with two replicas polling it would land on the wrong one about half the time,
reproducing the bug with more infrastructure to operate.

**Why no new dependency:** Postgres is already required, `asyncpg` is already installed, and
RDS supports `LISTEN`/`NOTIFY` natively.

### What is deliberately accepted

- **Fire-and-forget.** A replica that is not listening at publish time misses the event. Already
  true of the in-process bus, so not a regression, and the checkpoint still backs every
  reconnect - `routers/stream.py` reads the current snapshot fresh.
- **A dedicated connection, outside the SQLAlchemy pool.** `LISTEN` binds to a session; a pooled
  connection returned between requests would silently stop listening.
- **A 7000-byte payload ceiling**, under Postgres's 8000-byte `NOTIFY` limit. An event that does
  not fit is **not truncated** - a half-snapshot would render as though it were whole. It is
  dropped from the fan-out, logged, and the local subscriber is still served.
"""

import asyncio
import json
import logging
from typing import Any

import asyncpg
from intellichoice_db.engine import ssl_connect_args
from intellichoice_observability.metrics import SSE_RELAY_FAILURES
from sqlalchemy.engine import make_url

from chat_api.services.session_events import ChatSessionEventBus

logger = logging.getLogger(__name__)

CHANNEL = "chat_session_events"

MAX_PAYLOAD_BYTES = 7_000


def connect_kwargs(database_url: str) -> dict[str, Any]:
    """Discrete asyncpg connect arguments, parsed rather than string-munged.

    **learning-api's first version of this shipped broken and started on neither replica**
    (D-335). It did `database_url.replace("postgresql+asyncpg://", "postgresql://")` and handed
    the result to `asyncpg.connect`. RDS's generated password contains URL-significant
    characters, so asyncpg's parser hit them as a query string and died with
    `ValueError: bad query field: '48>k['`. The relay was non-fatal by design, so the API booted
    green and the fan-out silently did not exist. Its *test* passed, because it asserted the
    transformation the code performed rather than the property that mattered.

    Passing parsed components sidesteps quoting entirely - there is no URL left to mis-parse.
    `test_session_event_relay.py` asserts the parsed components against a password full of
    URL-significant characters, which is the assertion that would have caught it.

    **SSL is not optional on RDS** (S34): its default parameter group ships `rds.force_ssl=1`.
    `ssl_connect_args` returns asyncpg's own `ssl` kwarg, so both connection paths keep the same
    posture rather than one being stricter by accident.
    """
    url = make_url(database_url)
    kwargs: dict[str, Any] = {
        "user": url.username,
        "password": url.password,
        "host": url.host,
        "port": url.port or 5432,
        "database": url.database,
    }
    kwargs.update(ssl_connect_args(database_url))
    return kwargs


class ChatSessionEventRelay:
    """Owns one listening connection and one publishing connection for this process."""

    def __init__(self, bus: ChatSessionEventBus, database_url: str) -> None:
        self._bus = bus
        self._connect_kwargs = connect_kwargs(database_url)
        self._listener: asyncpg.Connection | None = None
        self._publisher: asyncpg.Connection | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        # D-395, and see `learning_api.services.session_event_relay.__init__` for the full
        # reasoning - this class is a deliberate copy of that one, so a fix to one that skipped
        # the other would be the D-347 "fixed in one direction" shape the 08-16 audit named as
        # the finding behind its findings.
        #
        # `_pending` keeps a strong reference to each scheduled notify, because the event loop
        # holds only a weak one and a fire-and-forget task can be collected mid-execution.
        # `_publish_lock` serializes the single publisher connection, which asyncpg otherwise
        # refuses to use twice at once - measured on learning-api at four of five events lost in
        # a five-event burst, every one swallowed.
        self._pending: set[asyncio.Task[None]] = set()
        self._publish_lock: asyncio.Lock | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        # Bound to the running loop, so it cannot be created in `__init__`.
        self._publish_lock = asyncio.Lock()
        listener = await asyncpg.connect(**self._connect_kwargs)
        # Separate from the listener: a connection blocked in LISTEN should not also be the one
        # issuing NOTIFY, and asyncpg's callback runs on the listener's own read path.
        self._publisher = await asyncpg.connect(**self._connect_kwargs)
        await listener.add_listener(CHANNEL, self._on_notify)
        self._listener = listener
        self._bus.attach_relay(self.publish)
        logger.info("chat_session_event_relay_started", extra={"origin": self._bus.origin})

    async def stop(self) -> None:
        # Drain first, or in-flight notifies find their connection closed and each logs a failure
        # indistinguishable from a real dropped event. Bounded so a hung notify cannot hold up
        # shutdown.
        if self._pending:
            await asyncio.wait(set(self._pending), timeout=2.0)
        for conn, name in ((self._listener, "listener"), (self._publisher, "publisher")):
            if conn is None:
                continue
            try:
                await conn.close()
            except Exception:
                logger.warning(
                    "chat_session_event_relay_close_failed", extra={"conn": name}, exc_info=True
                )
        self._listener = None
        self._publisher = None

    def _on_notify(self, _conn: Any, _pid: int, _channel: str, payload: str) -> None:
        """asyncpg calls this synchronously on its read path, so it must not block or raise."""
        try:
            message = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("chat_session_event_relay_bad_payload")
            return
        # Drop the echo of our own publish. Every listener on the channel receives every
        # notification, including the process that sent it - without this, a locally-published
        # event would be delivered twice to the same subscriber.
        if message.get("origin") == self._bus.origin:
            return
        session_id = message.get("session_id")
        event = message.get("event")
        if not isinstance(session_id, str) or not isinstance(event, dict):
            logger.warning("chat_session_event_relay_malformed_message")
            return
        self._bus.deliver_local(session_id, event)

    def publish(self, session_id: str, event: dict) -> None:
        """Called by the bus after it has already served this process's own subscribers.

        Schedules the NOTIFY rather than awaiting it: `publish` is called from a request path
        that must not block on a database round trip to fan out a push the local client has
        already received in its response body.
        """
        if self._publisher is None or self._loop is None:
            return
        payload = json.dumps({"origin": self._bus.origin, "session_id": session_id, "event": event})
        if len(payload.encode()) > MAX_PAYLOAD_BYTES:
            # Not truncated: a half-snapshot would render as though it were whole.
            SSE_RELAY_FAILURES.labels(reason="payload_too_large").inc()
            logger.warning(
                "chat_session_event_relay_payload_too_large",
                extra={"payload_bytes": len(payload.encode()), "session_id": session_id},
            )
            return
        task = self._loop.create_task(self._notify(payload, session_id))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _notify(self, payload: str, session_id: str) -> None:
        try:
            if self._publisher is None or self._publish_lock is None:
                return
            # One connection, so one notify at a time - see `__init__`.
            async with self._publish_lock:
                # `pg_notify` rather than a NOTIFY statement so the payload is a bound parameter
                # and never needs quoting into SQL.
                await self._publisher.execute("SELECT pg_notify($1, $2)", CHANNEL, payload)
        except Exception:
            # With the session id: a fan-out failure means a reloaded tab or a second device
            # silently misses this turn's update, and that question needs a session to answer.
            # The counter is the other half - a warning is only found by someone already
            # looking (D-396).
            SSE_RELAY_FAILURES.labels(reason="notify_failed").inc()
            logger.warning(
                "chat_session_event_relay_notify_failed",
                extra={"session_id": session_id},
                exc_info=True,
            )
