"""Realtime + notifications API tests (Phase 8)."""

import uuid
from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import with_tenant
from app.core.events import bus
from app.models import Notification
from tests.conftest import OrgContext
from tests.fakes import ScriptedLLM, analysis_result, reply_result


def _post_webhook(client: TestClient, org: OrgContext, phone: str, body: str) -> Any:
    form = {
        "MessageSid": f"SM{uuid.uuid4().hex[:20]}",
        "From": f"whatsapp:{phone}",
        "To": org.org.twilio_whatsapp_from or "",
        "Body": body,
        "ProfileName": "Notifier",
    }
    return client.post("/api/v1/webhooks/twilio", data=form)


class TestRealtimeStream:
    def test_stream_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/realtime/stream")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unknown_agent_forbidden(self, client: TestClient) -> None:
        from tests.conftest import make_token

        token = make_token(str(uuid.uuid4()))
        response = client.get(
            "/api/v1/realtime/stream", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestWebhookNotifications:
    def test_new_lead_creates_notification(
        self, client: TestClient, org_context: OrgContext
    ) -> None:
        response = _post_webhook(
            client, org_context, "+923001239999", "first contact from a new buyer"
        )
        assert response.status_code == 200

        listed = client.get("/api/v1/notifications", headers=org_context.headers)
        assert listed.status_code == 200
        body = listed.json()
        assert body["unread_count"] >= 1
        newest = body["items"][0]
        assert newest["type"] == "NEW_LEAD"
        assert "first contact" in (newest["body"] or "")
        assert newest["read"] is False

    def test_existing_lead_no_new_notification(
        self, client: TestClient, org_context: OrgContext
    ) -> None:
        _post_webhook(client, org_context, "+923001238888", "hello again")
        before = client.get("/api/v1/notifications", headers=org_context.headers).json()

        _post_webhook(client, org_context, "+923001238888", "still here")

        after = client.get("/api/v1/notifications", headers=org_context.headers).json()
        assert after["unread_count"] == before["unread_count"]

    def test_read_all_marks_for_this_agent_only(
        self, client: TestClient, org_context: OrgContext
    ) -> None:
        _post_webhook(client, org_context, "+923001237777", "hi")
        marked = client.post("/api/v1/notifications/read-all", headers=org_context.headers)
        assert marked.status_code == 200
        assert marked.json()["marked"] >= 1

        body = client.get("/api/v1/notifications", headers=org_context.headers).json()
        assert body["unread_count"] == 0
        assert all(item["read"] for item in body["items"])

    def test_notifications_are_tenant_scoped(
        self, client: TestClient, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        _post_webhook(client, org_context, "+923001236666", "org A lead")
        theirs = client.get("/api/v1/notifications", headers=other_org_context.headers).json()
        titles = [item["title"] for item in theirs["items"]]
        assert all("+923001236666" not in title for title in titles)


class TestGraphNotifications:
    async def test_hot_lead_triggers_notification(
        self, db_session: AsyncSession, org_context: OrgContext, client: TestClient
    ) -> None:
        from app.agents.graph import ConversationPipelineAgent

        lead = org_context.leads[3]  # unscored
        llm = ScriptedLLM(
            analysis_result(
                {
                    "intent": "BUY",
                    "budget_min": 20_000_000,
                    "budget_max": 30_000_000,
                    "preferred_location": "DHA Lahore",
                    "property_type": "HOUSE",
                    "bedrooms": 4,
                    "urgency_score": 9,
                    "sentiment": "POSITIVE",
                }
            ),
            reply_result("Here is a great DHA option within budget."),
        )
        agent = ConversationPipelineAgent(llm)
        from app.models import Message
        from app.models.enums import MessageChannel, SenderType

        history = [
            Message(
                lead_id=lead.id,
                sender_type=SenderType.CUSTOMER,
                content="need a house",
                channel=MessageChannel.WHATSAPP,
            )
        ]
        async with with_tenant(db_session, org_context.org.id):
            await agent.respond(db_session, lead, history)
            rows = (
                (
                    await db_session.execute(
                        select(Notification).where(Notification.lead_id == lead.id)
                    )
                )
                .scalars()
                .all()
            )
            types = {row.type for row in rows}
            await db_session.rollback()
        assert "HOT_LEAD" in types

    async def test_warm_lead_no_hot_notification(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        from app.agents.graph import ConversationPipelineAgent
        from app.models import Message
        from app.models.enums import MessageChannel, SenderType

        lead = org_context.leads[3]
        llm = ScriptedLLM(
            analysis_result({"intent": "BUY"}),
            reply_result("What is your budget?"),
        )
        agent = ConversationPipelineAgent(llm)
        history = [
            Message(
                lead_id=lead.id,
                sender_type=SenderType.CUSTOMER,
                content="hi",
                channel=MessageChannel.WHATSAPP,
            )
        ]
        async with with_tenant(db_session, org_context.org.id):
            await agent.respond(db_session, lead, history)
            rows = (
                (
                    await db_session.execute(
                        select(Notification).where(Notification.lead_id == lead.id)
                    )
                )
                .scalars()
                .all()
            )
            types = {row.type for row in rows}
            await db_session.rollback()
        assert "HOT_LEAD" not in types


class TestWorkerFanout:
    async def test_processor_publishes_after_commit(
        self, db_session: AsyncSession, org_context: OrgContext
    ) -> None:
        """AI reply events reach the bus only after the transaction commits."""

        from app.agents.graph import ConversationPipelineAgent
        from app.models.enums import MessageChannel, SenderType
        from app.repositories import MessageRepository
        from app.workers.messaging import InboundMessageJob, InlineMessageProcessor

        queue = bus.subscribe(org_context.org.id)
        try:
            lead = org_context.leads[3]
            async with with_tenant(db_session, org_context.org.id):
                stored = await MessageRepository(db_session).add_message(
                    lead_id=lead.id,
                    sender_type=SenderType.CUSTOMER,
                    content="anyone there?",
                    channel=MessageChannel.WHATSAPP,
                )

            llm = ScriptedLLM(
                analysis_result({"intent": "BUY"}),
                reply_result("Yes! What are you looking for?"),
            )
            processor = InlineMessageProcessor(agent=ConversationPipelineAgent(llm))
            await processor.process(
                InboundMessageJob(
                    organization_id=org_context.org.id,
                    lead_id=lead.id,
                    message_id=stored.id,
                )
            )

            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
            types = [event["type"] for event in events]
            assert "lead.updated" in types
            assert "message.created" in types
            ai_event = next(
                event
                for event in events
                if event["type"] == "message.created" and event["payload"]["sender_type"] == "AI"
            )
            assert ai_event["payload"]["preview"].startswith("Yes!")
        finally:
            bus.unsubscribe(org_context.org.id, queue)
