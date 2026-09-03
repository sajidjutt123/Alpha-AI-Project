"""In-process realtime event bus (single-instance pub/sub).

`subscribe()` hands an asyncio.Queue to a caller (the SSE stream) that is
scoped to one organization; `publish()` fans a domain event out to every
live subscriber of that org. Publish is synchronous and never blocks the
caller: a full queue drops the event (dashboards also poll on reconnect).

Scale path (documented in docs/architecture.md): when the backend runs
multiple instances, swap this bus for Redis pub/sub — subscribe/publish
keep their signatures, only the transport changes.
"""

import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MAX_QUEUE = 256
KEEPALIVE_SECONDS = 15.0


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, organization_id: UUID) -> "asyncio.Queue[dict[str, Any]]":
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=MAX_QUEUE)
        self._subscribers[organization_id].add(queue)
        logger.info(
            "sse_subscribed",
            extra={
                "organization_id": str(organization_id),
                "subscribers": len(self._subscribers[organization_id]),
            },
        )
        return queue

    def unsubscribe(self, organization_id: UUID, queue: "asyncio.Queue[dict[str, Any]]") -> None:
        self._subscribers[organization_id].discard(queue)
        if not self._subscribers[organization_id]:
            self._subscribers.pop(organization_id, None)

    def publish(self, organization_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        """Fan out one event to the org's live subscribers (drop-if-full)."""
        event = {"type": event_type, "payload": payload}
        for queue in list(self._subscribers.get(organization_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "sse_subscriber_overflow",
                    extra={"organization_id": str(organization_id)},
                )


bus = EventBus()


def defer_publish(
    session: "AsyncSession", organization_id: UUID, event_type: str, payload: dict[str, Any]
) -> None:
    """Queue an event on the session; flushed after the transaction commits.

    Publishing inside an open transaction would let dashboards refetch
    before the rows are visible. The unit-of-work owner (webhook, worker)
    calls `flush_deferred` right after commit.
    """
    session.info.setdefault("deferred_events", []).append((organization_id, event_type, payload))


def flush_deferred(session: "AsyncSession") -> None:
    """Publish everything deferred on this session (no-op when empty)."""
    for organization_id, event_type, payload in session.info.pop("deferred_events", []):
        bus.publish(organization_id, event_type, payload)
