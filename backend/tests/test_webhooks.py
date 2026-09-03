"""Twilio webhook pipeline tests (Phase 4 gate).

Covers the plan's pipeline: signature verification, tenant routing by `To`
number, lead identification, idempotent persistence (MessageSid), status
callbacks, and the fast-ack + background-processing contract.
"""

import base64
import hashlib
import hmac
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import create_app
from app.models import Lead, Message
from app.models.enums import MessageChannel
from tests.conftest import OrgContext

WEBHOOK_URL = "http://testserver/api/v1/webhooks/twilio"
TWILIO_TOKEN = "test-twilio-signing-secret"


def sign(url: str, params: dict[str, str], token: str) -> str:
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    digest = hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


class FakeProcessor:
    """Records enqueued jobs instead of running the AI."""

    def __init__(self) -> None:
        self.jobs: list[Any] = []

    async def process(self, job: Any) -> None:
        self.jobs.append(job)


@pytest.fixture
def twilio_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, FakeProcessor]]:
    """Client with Twilio signature enforcement on and a recording processor."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", TWILIO_TOKEN)
    get_settings.cache_clear()
    fake = FakeProcessor()
    app = create_app()
    app.state.message_processor = fake
    with TestClient(app) as client:
        yield client, fake
    get_settings.cache_clear()


def post_webhook(client: TestClient, form: dict[str, str], *, signature: str | None = None) -> Any:
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if signature is not None:
        headers["X-Twilio-Signature"] = signature
    return client.post("/api/v1/webhooks/twilio", data=form, headers=headers)


def inbound_form(to: str, *, sid: str | None = None, **extra: str) -> dict[str, str]:
    return {
        "MessageSid": sid or f"SM{uuid.uuid4().hex[:20]}",
        "From": "whatsapp:+923301234567",
        "To": to,
        "Body": "I need a house in DHA Lahore",
        "ProfileName": "Ali Hassan",
        **extra,
    }


class TestSignature:
    def test_valid_signature_processes(
        self, twilio_client: tuple[TestClient, FakeProcessor], org_context: OrgContext
    ) -> None:
        client, fake = twilio_client
        form = inbound_form(org_context.org.twilio_whatsapp_from or "")
        response = post_webhook(client, form, signature=sign(WEBHOOK_URL, form, TWILIO_TOKEN))

        assert response.status_code == 200
        assert "<Response>" in response.text
        assert len(fake.jobs) == 1

    def test_invalid_signature_is_403(
        self, twilio_client: tuple[TestClient, FakeProcessor], org_context: OrgContext
    ) -> None:
        client, fake = twilio_client
        form = inbound_form(org_context.org.twilio_whatsapp_from or "")
        response = post_webhook(client, form, signature="forged-signature")

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "http_403"
        assert fake.jobs == []

    def test_missing_signature_is_403(
        self, twilio_client: tuple[TestClient, FakeProcessor], org_context: OrgContext
    ) -> None:
        client, _ = twilio_client
        form = inbound_form(org_context.org.twilio_whatsapp_from or "")
        response = post_webhook(client, form)  # no header at all

        assert response.status_code == 403

    def test_tampered_body_invalidates_signature(
        self, twilio_client: tuple[TestClient, FakeProcessor], org_context: OrgContext
    ) -> None:
        client, _ = twilio_client
        form = inbound_form(org_context.org.twilio_whatsapp_from or "")
        signature = sign(WEBHOOK_URL, form, TWILIO_TOKEN)
        form["Body"] = "tampered after signing"
        response = post_webhook(client, form, signature=signature)

        assert response.status_code == 403


class TestRoutingAndPersistence:
    def test_creates_lead_and_message_in_routed_org(
        self,
        twilio_client: tuple[TestClient, FakeProcessor],
        org_context: OrgContext,
        other_org_context: OrgContext,
    ) -> None:
        client, fake = twilio_client
        to = org_context.org.twilio_whatsapp_from or ""
        form = inbound_form(to)
        response = post_webhook(client, form, signature=sign(WEBHOOK_URL, form, TWILIO_TOKEN))

        assert response.status_code == 200
        job = fake.jobs[0]
        assert job.organization_id == org_context.org.id
        assert str(job.lead_id) != ""

    async def test_lead_fields_and_channel(
        self,
        twilio_client: tuple[TestClient, FakeProcessor],
        db_session: AsyncSession,
        org_context: OrgContext,
    ) -> None:
        client, _ = twilio_client
        form = inbound_form(org_context.org.twilio_whatsapp_from or "")
        post_webhook(client, form, signature=sign(WEBHOOK_URL, form, TWILIO_TOKEN))

        from app.core.database import with_tenant

        async with with_tenant(db_session, org_context.org.id):
            lead = (
                await db_session.execute(select(Lead).where(Lead.phone == "+923301234567"))
            ).scalar_one()
            assert lead.name == "Ali Hassan"  # ProfileName captured
            assert lead.organization_id == org_context.org.id
            message = (
                await db_session.execute(select(Message).where(Message.lead_id == lead.id))
            ).scalar_one()
            assert message.channel == MessageChannel.WHATSAPP
            assert message.external_message_id == form["MessageSid"]
            assert message.content == form["Body"]

    def test_sms_channel_detected(
        self, twilio_client: tuple[TestClient, FakeProcessor], org_context: OrgContext
    ) -> None:
        client, _ = twilio_client
        form = inbound_form(org_context.org.twilio_sms_from or "", From="+923301234567")
        response = post_webhook(client, form, signature=sign(WEBHOOK_URL, form, TWILIO_TOKEN))
        assert response.status_code == 200

    def test_unknown_number_without_fallback_is_404(
        self, twilio_client: tuple[TestClient, FakeProcessor]
    ) -> None:
        client, fake = twilio_client
        form = inbound_form("whatsapp:+19999999999")
        response = post_webhook(client, form, signature=sign(WEBHOOK_URL, form, TWILIO_TOKEN))
        assert response.status_code == 404
        assert fake.jobs == []

    def test_slug_fallback_routes_shared_number(
        self,
        monkeypatch: pytest.MonkeyPatch,
        twilio_client: tuple[TestClient, FakeProcessor],
        org_context: OrgContext,
    ) -> None:
        client, fake = twilio_client
        monkeypatch.setenv("DEFAULT_ORGANIZATION_SLUG", org_context.org.slug)
        get_settings.cache_clear()
        form = inbound_form("whatsapp:+1888-shared-number")
        response = post_webhook(client, form, signature=sign(WEBHOOK_URL, form, TWILIO_TOKEN))
        get_settings.cache_clear()

        assert response.status_code == 200
        assert fake.jobs[0].organization_id == org_context.org.id


class TestIdempotency:
    def test_duplicate_sid_not_reprocessed(
        self, twilio_client: tuple[TestClient, FakeProcessor], org_context: OrgContext
    ) -> None:
        client, fake = twilio_client
        form = inbound_form(org_context.org.twilio_whatsapp_from or "")
        signature = sign(WEBHOOK_URL, form, TWILIO_TOKEN)

        first = post_webhook(client, form, signature=signature)
        second = post_webhook(client, form, signature=signature)

        assert first.status_code == second.status_code == 200
        assert len(fake.jobs) == 1  # processed exactly once


class TestStatusCallbacks:
    def test_delivery_receipt_acked_without_processing(
        self, twilio_client: tuple[TestClient, FakeProcessor], org_context: OrgContext
    ) -> None:
        client, fake = twilio_client
        form = {
            "MessageSid": f"SM{uuid.uuid4().hex[:20]}",
            "MessageStatus": "delivered",
            "SmsStatus": "delivered",
            "From": org_context.org.twilio_sms_from or "",
            "To": "+923301234567",
        }
        response = post_webhook(client, form, signature=sign(WEBHOOK_URL, form, TWILIO_TOKEN))

        assert response.status_code == 200
        assert fake.jobs == []


class TestDevAndProductionModes:
    def test_no_token_in_dev_mode_allowed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        org_context: OrgContext,
    ) -> None:
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        get_settings.cache_clear()
        app = create_app()
        fake = FakeProcessor()
        app.state.message_processor = fake
        with TestClient(app) as client:
            form = inbound_form(org_context.org.twilio_whatsapp_from or "")
            response = post_webhook(client, form)
        get_settings.cache_clear()

        assert response.status_code == 200
        assert len(fake.jobs) == 1

    def test_no_token_in_production_refused(
        self,
        monkeypatch: pytest.MonkeyPatch,
        org_context: OrgContext,
    ) -> None:
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        get_settings.cache_clear()
        app = create_app()
        with TestClient(app) as client:
            form = inbound_form(org_context.org.twilio_whatsapp_from or "")
            response = post_webhook(client, form)
        get_settings.cache_clear()

        assert response.status_code == 503
