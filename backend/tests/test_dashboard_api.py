"""Dashboard auth + live-chat endpoint tests (Phase 7)."""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import with_tenant
from app.models import Message
from app.models.enums import SenderType
from tests.conftest import OrgContext


class TestDevLogin:
    def test_login_returns_token_and_agent(
        self, client: TestClient, org_context: OrgContext
    ) -> None:
        response = client.post(
            "/api/v1/auth/dev-login",
            json={"email": org_context.owner.email},
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["agent"]["name"] == "Owner One"
        assert body["agent"]["organization_id"] == str(org_context.org.id)
        assert body["token"]

        # the token actually works on a protected endpoint
        me = client.get("/api/v1/agents/me", headers={"Authorization": f"Bearer {body['token']}"})
        assert me.status_code == status.HTTP_200_OK
        assert me.json()["email"] == org_context.owner.email

    def test_unknown_email_is_401(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/dev-login", json={"email": "nobody@example.com"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_body_is_422(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/dev-login", json={"email": "not-an-email"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_production_refuses_dev_login(
        self, monkeypatch, client: TestClient, org_context: OrgContext
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        get_settings.cache_clear()
        response = client.post("/api/v1/auth/dev-login", json={"email": org_context.owner.email})
        get_settings.cache_clear()
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgentMessages:
    def test_send_message_stores_and_transitions(
        self, client: TestClient, org_context: OrgContext
    ) -> None:
        lead_id = org_context.leads[3].id  # NEW
        response = client.post(
            f"/api/v1/leads/{lead_id}/messages",
            json={"content": "Assalam o Alaikum! This is Ahmed from Alpha Estates."},
            headers=org_context.headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["sender_type"] == "AGENT"
        assert body["channel"] == "DASHBOARD"
        assert body["external_message_id"]  # console sender sid in dev

        # NEW -> CONTACTED by the agent touch (business rule)
        detail = client.get(f"/api/v1/leads/{lead_id}", headers=org_context.headers)
        assert detail.json()["status"] == "CONTACTED"

    def test_message_requires_auth(self, client: TestClient, org_context: OrgContext) -> None:
        response = client.post(
            f"/api/v1/leads/{org_context.leads[0].id}/messages",
            json={"content": "hello"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_content_rejected(self, client: TestClient, org_context: OrgContext) -> None:
        response = client.post(
            f"/api/v1/leads/{org_context.leads[0].id}/messages",
            json={"content": ""},
            headers=org_context.headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_cross_tenant_lead_404(
        self, client: TestClient, org_context: OrgContext, other_org_context: OrgContext
    ) -> None:
        victim = other_org_context.leads[0].id
        response = client.post(
            f"/api/v1/leads/{victim}/messages",
            json={"content": "hello"},
            headers=org_context.headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_message_persisted_with_sid(
        self, db_session: AsyncSession, org_context: OrgContext, client: TestClient
    ) -> None:
        lead_id = org_context.leads[0].id
        client.post(
            f"/api/v1/leads/{lead_id}/messages",
            json={"content": "Following up on your DHA visit."},
            headers=org_context.headers,
        )
        async with with_tenant(db_session, org_context.org.id):
            agent_msgs = (
                (
                    await db_session.execute(
                        select(Message).where(
                            Message.lead_id == lead_id,
                            Message.sender_type == SenderType.AGENT,
                        )
                    )
                )
                .scalars()
                .all()
            )
            snapshots = [(m.channel, m.external_message_id) for m in agent_msgs]
            await db_session.rollback()
        assert snapshots and snapshots[0][1]  # delivered + sid recorded
