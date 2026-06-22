"""Build the runner's ``emit`` callback: persist event + publish to the bus."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.repositories.events import append_event
from app.events.bus import EventBus


def make_emitter(
    sessionmaker: async_sessionmaker, bus: EventBus, review_id: str
) -> Callable[[str, dict], Awaitable[None]]:
    async def emit(event_type: str, payload: dict) -> None:
        # Persist durably (its own short transaction so SSE sees it immediately),
        # then notify any live subscribers.
        async with sessionmaker() as session:
            event = await append_event(session, review_id, event_type, payload)
            event_id, seq = event.id, event.seq
        bus.publish(
            review_id,
            {"id": event_id, "seq": seq, "type": event_type, "payload": payload},
        )

    return emit
