"""
In-process event bus for SSE fan-out.

The durable ``review_event`` table is the source of truth (it backs replay and
``Last-Event-ID``); this bus only delivers live events to currently-connected
SSE subscribers within the process. For a multi-process deployment this is the
one component you'd swap for Redis pub/sub — the rest of the design is unchanged.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, review_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[review_id].add(queue)
        return queue

    def unsubscribe(self, review_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(review_id)
        if subs:
            subs.discard(queue)
            if not subs:
                self._subscribers.pop(review_id, None)

    def publish(self, review_id: str, event: dict) -> None:
        for queue in list(self._subscribers.get(review_id, ())):
            queue.put_nowait(event)


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
