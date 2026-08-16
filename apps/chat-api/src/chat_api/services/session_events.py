"""Per-session pub/sub backing the SPEC §5.14.1-style SSE stream for the Q&A app.

Same shape as `learning_api.services.session_events.SessionEventBus`, kept as its own copy
since the two apps are independently deployed (CLAUDE.md) and neither depends on the other.
Since D-349 that includes the cross-replica relay hooks, for the reason recorded there: the
in-process bus is a defect that only appears at two or more replicas, and chat-api's
autoscaling policy can produce those at any time.

**Local delivery still happens directly, and that is deliberate.** `publish` serves this
process's subscribers *first*, then relays. If the relay is down, behaviour degrades to
exactly what it was before rather than breaking the same-replica case that already worked.

The checkpoint remains the source of truth: a subscriber that was never connected still gets
the current snapshot on (re)connect, since `routers/stream.py` reads it fresh from the graph,
and it subscribes *before* that read (AUD-F-36) so an event published during the read is
queued rather than lost. This bus only carries the "something changed, here's the new
snapshot" push - it is not durable and does not need to be.
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import Callable

logger = logging.getLogger(__name__)


class ChatSessionEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        # Identifies *this process's* bus so the relay can drop the echo of its own NOTIFY.
        # Without it every local publish would be delivered twice: once directly, once when
        # this process's own listener receives the notification it just sent.
        self.origin = uuid.uuid4().hex
        self._relay: Callable[[str, dict], None] | None = None

    def attach_relay(self, relay: Callable[[str, dict], None]) -> None:
        """Wired in the app lifespan once the Postgres listener is connected.

        A plain callable rather than the relay object, so this module stays free of any
        database import and remains unit-testable with no connection at all.
        """
        self._relay = relay

    def subscribe(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(session_id)
        if subs is None:
            return
        if queue in subs:
            subs.remove(queue)
        if not subs:
            self._subscribers.pop(session_id, None)

    def deliver_local(self, session_id: str, event: dict) -> None:
        """Hand an event to this process's subscribers only. The relay calls this for events
        that arrived from another replica; `publish` calls it for locally-produced ones."""
        for queue in self._subscribers.get(session_id, []):
            queue.put_nowait(event)

    def publish(self, session_id: str, event: dict) -> None:
        """Deliver here, then fan out to the other replicas.

        Local delivery is not conditional on the relay succeeding - a relay failure must not
        take down the same-process path that worked before D-349.
        """
        self.deliver_local(session_id, event)
        if self._relay is None:
            return
        try:
            self._relay(session_id, event)
        except Exception:
            # Never let a fan-out problem surface in a request. The local subscriber has
            # already been served, and the checkpoint still backs any reconnect.
            logger.warning("chat_session_event_relay_publish_failed", exc_info=True)
