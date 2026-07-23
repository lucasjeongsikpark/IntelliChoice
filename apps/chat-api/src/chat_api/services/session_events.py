"""In-process per-session pub/sub backing the SPEC §5.14.1-style SSE stream for the Q&A
app - identical shape to `learning_api.services.session_events.SessionEventBus`, kept as
its own copy since the two apps are independently deployed (CLAUDE.md) and neither
depends on the other.
"""

import asyncio
from collections import defaultdict


class ChatSessionEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

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

    def publish(self, session_id: str, event: dict) -> None:
        for queue in self._subscribers.get(session_id, []):
            queue.put_nowait(event)
