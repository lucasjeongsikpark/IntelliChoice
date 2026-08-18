"""Per-session pub/sub backing the SPEC §5.14.1 SSE stream.

**This bus was in-process only, and D-334 measured what that cost.** The original docstring here
read *"a single in-memory dict is enough - this app runs as one Uvicorn worker in dev"*. It was
true of dev and false of every deployment: `learning-api` runs **2 ECS tasks**, an SSE connection
is pinned to whichever replica the ALB gave it, and the request that spawns a background task is
routed independently. A background publish on the other replica reached nobody.

Measured on staging: a probe that waited instead of clicking on saw the personalized hint arrive in
**2 of 4 runs** - the ~50% two replicas predict. It affects every background-published event, not
just hints: D-217's deferred stage narratives ride the same bus, and anything added later inherits
it. The failure rate *rises* as the service scales out, which is the opposite of how capacity is
supposed to behave.

**The fix is a fan-out relay, not a queue** (D-335). The semantics needed are "every replica sees
every event, and the one holding the connection delivers it" - which is what Postgres
`LISTEN`/`NOTIFY` does natively. A work queue like SQS has competing-consumer semantics: one
message goes to exactly one poller, so with two replicas polling it would land on the wrong one
about half the time - the same 50%, with a queue to operate.

**Local delivery still happens directly, and that is deliberate.** `publish` delivers to this
process's subscribers *first*, then relays. If the relay is down, behaviour degrades to exactly
what it was before this change rather than breaking the same-replica case that already worked.

The checkpoint remains the source of truth: a subscriber that was never connected still gets the
current snapshot on (re)connect, since `routers/stream.py` reads it fresh from the graph, and it
subscribes *before* that read (AUD-F-36) so an event published during the read is queued rather
than lost. This bus only carries the "something changed, here's the new snapshot" push - it is not
durable and does not need to be.
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import Callable

from intellichoice_observability.metrics import (
    SSE_CONNECTIONS,
    SSE_EVENTS_DELIVERED,
    SSE_RELAY_FAILURES,
)

logger = logging.getLogger(__name__)


class SessionEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        # Identifies *this process's* bus so the relay can drop the echo of its own NOTIFY.
        # Without it every local publish would be delivered twice: once directly, once when this
        # process's own listener receives the notification it just sent.
        self.origin = uuid.uuid4().hex
        self._relay: Callable[[str, dict], None] | None = None

    def attach_relay(self, relay: Callable[[str, dict], None]) -> None:
        """Wired in the app lifespan once the Postgres listener is connected.

        A plain callable rather than the relay object, so this module stays free of any database
        import and remains unit-testable with no connection at all.
        """
        self._relay = relay

    def subscribe(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        SSE_CONNECTIONS.inc()
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(session_id)
        if subs is None:
            return
        if queue in subs:
            subs.remove(queue)
            # Inside the `if`, not beside it: an unsubscribe for a queue that is not there is a
            # no-op everywhere else in this method, and decrementing anyway would let a double
            # unsubscribe drive the gauge negative - which reads on a dashboard as a bug in the
            # thing being measured rather than in the measurement.
            SSE_CONNECTIONS.dec()
        if not subs:
            self._subscribers.pop(session_id, None)

    def deliver_local(self, session_id: str, event: dict) -> None:
        """Hand an event to this process's subscribers only. The relay calls this for events that
        arrived from another replica; `publish` calls it for locally-produced ones."""
        for queue in self._subscribers.get(session_id, []):
            queue.put_nowait(event)
            SSE_EVENTS_DELIVERED.inc()

    def publish(self, session_id: str, event: dict) -> None:
        """Deliver here, then fan out to the other replicas.

        Local delivery is not conditional on the relay succeeding - a relay failure must not take
        down the same-process path that worked before D-335.
        """
        self.deliver_local(session_id, event)
        if self._relay is None:
            return
        try:
            self._relay(session_id, event)
        except Exception:
            # Never let a fan-out problem surface in a request. The local subscriber has already
            # been served, and the checkpoint still backs any reconnect.
            SSE_RELAY_FAILURES.labels(reason="publish_failed").inc()
            logger.warning(
                "session_event_relay_publish_failed",
                extra={"session_id": session_id},
                exc_info=True,
            )
