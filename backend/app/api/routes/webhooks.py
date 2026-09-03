"""Twilio inbound webhook — the plan's Phase 4 pipeline.

    POST /api/v1/webhooks/twilio   (application/x-www-form-urlencoded)
      1. verify Twilio signature (HMAC-SHA1, constant-time)
      2. route `To` -> organization (per-org numbers, slug fallback)
      3. identify lead by phone (get-or-create, org-scoped)
      4. store the message (idempotent on MessageSid)
      5. enqueue AI processing and return 200 immediately (TwiML)

No JWT auth here — this endpoint is authenticated by the Twilio signature.
In production (ENVIRONMENT=production) a missing TWILIO_AUTH_TOKEN refuses
traffic outright; dev/test may run without it while wiring things up.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db, with_tenant
from app.core.errors import NotFoundError
from app.core.events import defer_publish, flush_deferred
from app.core.rate_limit import rate_limit
from app.core.twilio_security import validate_signature
from app.models.enums import MessageChannel, SenderType
from app.repositories import LeadRepository, MessageRepository
from app.services.notifications import NEW_LEAD, NotificationService
from app.workers.messaging import InboundMessageJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


async def _resolve_organization_id(db: AsyncSession, to_number: str) -> UUID | None:
    """Route the inbound `To` number to an organization (see 004 migration)."""
    result = await db.execute(
        text("SELECT organization_id FROM app_org_id_by_twilio_to(:to)"),
        {"to": to_number},
    )
    org_id = result.scalar_one_or_none()
    if org_id is not None:
        await db.rollback()  # release the implicit routing transaction
        return UUID(str(org_id))

    settings = get_settings()
    if settings.default_organization_slug:
        result = await db.execute(
            text("SELECT organization_id FROM app_org_id_by_slug(:slug)"),
            {"slug": settings.default_organization_slug},
        )
        org_id = result.scalar_one_or_none()
        await db.rollback()
        if org_id is not None:
            return UUID(str(org_id))
    return None


def _parse_phone(raw: str) -> str:
    """Strip the WhatsApp prefix; store bare E.164."""
    return raw.removeprefix("whatsapp:")


@router.post("/twilio", dependencies=[Depends(rate_limit("webhook"))])
async def twilio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    settings = get_settings()

    if request.headers.get("content-type", "") != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    form = {key: str(value) for key, value in (await request.form()).items()}

    # --- 1. Signature ------------------------------------------------------
    token = settings.twilio_auth_token
    signature = request.headers.get("X-Twilio-Signature", "")
    if token:
        if not signature or not validate_signature(request, form, signature, token):
            logger.warning("twilio_signature_rejected")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    elif settings.environment == "production":
        logger.error("twilio_webhook_without_token_in_production")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    else:
        logger.warning("twilio_signature_skipped_dev_mode")

    # --- 2. Status callbacks (no Body) are acked and ignored ----------------
    message_sid = form.get("MessageSid")
    from_raw = form.get("From")
    body = form.get("Body")
    if not message_sid and not form.get("SmsSid"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
    if body is None or from_raw is None:
        # delivery receipts & status callbacks: nothing to converse about
        return Response(content=EMPTY_TWIML, media_type="application/xml")
    if message_sid is None:
        # a conversational message must carry a Sid (idempotency key)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    # --- 3. Tenant routing ---------------------------------------------------
    to_number = form.get("To", "")
    organization_id = await _resolve_organization_id(db, to_number)
    if organization_id is None:
        logger.warning("twilio_webhook_unroutable", extra={"to": to_number})
        raise NotFoundError(
            f"No organization routes messages to {to_number or 'unknown number'}",
        )

    channel = (
        MessageChannel.WHATSAPP
        if from_raw.startswith("whatsapp:") or to_number.startswith("whatsapp:")
        else MessageChannel.SMS
    )
    phone = _parse_phone(from_raw)

    # --- 4. Persist + enqueue (single tenant transaction) --------------------
    async with with_tenant(db, organization_id):
        leads = LeadRepository(db)
        lead, created = await leads.get_or_create_by_phone(
            organization_id=organization_id,
            phone=phone,
            name=form.get("ProfileName") or None,
        )
        messages = MessageRepository(db)
        if await messages.get_by_external_id(message_sid) is not None:
            # Twilio retry — already processed; ack without re-enqueueing.
            return Response(content=EMPTY_TWIML, media_type="application/xml")

        message = await messages.add_message(
            lead_id=lead.id,
            sender_type=SenderType.CUSTOMER,
            content=body,
            channel=channel,
            external_message_id=message_sid,
        )
        if created:
            await NotificationService(db).create(
                organization_id=organization_id,
                type=NEW_LEAD,
                title=f"New lead: {lead.name or lead.phone}",
                body=f"First message via {channel.value}: {body[:80]}",
                lead_id=lead.id,
            )
            defer_publish(
                db,
                organization_id,
                "lead.created",
                {"lead_id": str(lead.id), "name": lead.name, "phone": lead.phone},
            )
        defer_publish(
            db,
            organization_id,
            "message.created",
            {
                "lead_id": str(lead.id),
                "message_id": str(message.id),
                "sender_type": "CUSTOMER",
                "preview": body[:80],
            },
        )
    # transaction committed — now fan realtime events out
    flush_deferred(db)

    # --- 5. Ack fast; AI runs after the response is sent ---------------------
    job = InboundMessageJob(
        organization_id=organization_id,
        lead_id=lead.id,
        message_id=message.id,
    )
    background_tasks.add_task(request.app.state.message_processor.process, job)
    return Response(content=EMPTY_TWIML, media_type="application/xml")
