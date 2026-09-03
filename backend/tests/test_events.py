"""Event bus + deferred publish tests (Phase 8 realtime core)."""

import asyncio
import uuid

from app.core.events import EventBus, defer_publish, flush_deferred


class TestEventBus:
    async def test_publish_reaches_org_subscriber(self) -> None:
        bus = EventBus()
        org = uuid.uuid4()
        queue = bus.subscribe(org)

        bus.publish(org, "message.created", {"lead_id": "x"})

        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event == {"type": "message.created", "payload": {"lead_id": "x"}}
        bus.unsubscribe(org, queue)

    async def test_events_never_cross_organizations(self) -> None:
        bus = EventBus()
        org_a, org_b = uuid.uuid4(), uuid.uuid4()
        queue_a = bus.subscribe(org_a)
        queue_b = bus.subscribe(org_b)

        bus.publish(org_a, "lead.created", {"lead_id": "secret"})

        assert await asyncio.wait_for(queue_a.get(), timeout=1)
        assert queue_b.empty()  # org B never receives org A's events
        bus.unsubscribe(org_a, queue_a)
        bus.unsubscribe(org_b, queue_b)

    async def test_unsubscribe_stops_delivery(self) -> None:
        bus = EventBus()
        org = uuid.uuid4()
        queue = bus.subscribe(org)
        bus.unsubscribe(org, queue)

        bus.publish(org, "lead.created", {"lead_id": "x"})

        assert queue.empty()
        assert org not in bus._subscribers

    async def test_full_queue_drops_instead_of_blocking(self) -> None:
        bus = EventBus()
        org = uuid.uuid4()
        queue = bus.subscribe(org)

        for _ in range(300):  # MAX_QUEUE is 256
            bus.publish(org, "ping", {})

        assert queue.qsize() == 256  # publisher never blocked, overflow dropped
        bus.unsubscribe(org, queue)

    async def test_publish_without_subscribers_is_noop(self) -> None:
        bus = EventBus()
        bus.publish(uuid.uuid4(), "lead.created", {"x": 1})  # must not raise


class TestSseGenerator:
    async def test_stream_emits_connected_then_events(self) -> None:
        from app.api.routes.realtime import sse_generator
        from app.core.events import bus

        org = uuid.uuid4()
        generator = sse_generator(org)

        first = await asyncio.wait_for(generator.__anext__(), timeout=1)
        assert first == b": connected\n\n"

        # deliver an event from "another worker"
        await asyncio.sleep(0)
        bus.publish(org, "handoff.requested", {"lead_id": "abc"})

        chunk = await asyncio.wait_for(generator.__anext__(), timeout=1)
        assert b"event: handoff.requested" in chunk
        assert b'"lead_id": "abc"' in chunk

        await generator.aclose()
        assert org not in bus._subscribers  # cleaned up


class TestDeferredPublish:
    async def test_defer_until_flush(self, db_session) -> None:
        from app.core.events import bus

        org = uuid.uuid4()
        queue = bus.subscribe(org)

        defer_publish(db_session, org, "lead.updated", {"score": 88})
        assert queue.empty()  # nothing before commit

        flush_deferred(db_session)
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event["type"] == "lead.updated"
        assert event["payload"] == {"score": 88}
        bus.unsubscribe(org, queue)

    async def test_flush_without_deferrals_is_noop(self, db_session) -> None:
        flush_deferred(db_session)  # must not raise
