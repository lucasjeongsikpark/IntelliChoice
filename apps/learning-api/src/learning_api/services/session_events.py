"""In-process per-session pub/sub backing the SPEC §5.14.1 SSE stream.

A single in-memory dict is enough - this app runs as one Uvicorn worker in dev, and the
`AsyncPostgresSaver` checkpoint is the actual source of truth: a subscriber that misses an
event (or was never connected) still gets the current snapshot on (re)connect, since
`routers/stream.py` reads it fresh from the graph before replaying published events. This
bus only carries the "something changed, here's the new snapshot" push - it is not
durable and does not need to be.
"""

import asyncio
from collections import defaultdict


class SessionEventBus:
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
