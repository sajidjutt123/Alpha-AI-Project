"""Background message processing — queue-shaped from day one.

The webhook validates, persists, and enqueues an `InboundMessageJob`, then
returns 200 to Twilio within milliseconds (plan §10). The MVP "queue" is
FastAPI BackgroundTasks; swapping in Redis/Arq later means implementing
`MessageProcessor` again — the webhook code does not change.

The inline processor owns its own session/transaction (it outlives the
request) and re-binds the tenant context via `with_tenant`.
"""

import logging
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from app.agents.conversation import ConversationAgent, UnconfiguredAgent
from app.core.database import get_session_factory, with_tenant
from app.models import Message
from app.models.enums import MessageChannel, SenderType
from app.repositories import LeadRepository, MessageRepository
from app.services.twilio import MessageSender, build_sender

logger = logging.getLogger(__name__)


class InboundMessageJob(BaseModel):
    """Everything the processor needs to run after the webhook acks."""

    organization_id: UUID
    lead_id: UUID
    message_id: UUID


class MessageProcessor(Protocol):
    async def process(self, job: InboundMessageJob) -> None: ...


class InlineMessageProcessor:
    """MVP processor: runs in-process after the HTTP response is sent."""

    def __init__(
        self,
        agent: ConversationAgent | None = None,
        sender: MessageSender | None = None,
    ) -> None:
        self.agent: ConversationAgent = agent or UnconfiguredAgent()
        self.sender: MessageSender = sender or build_sender()

    async def process(self, job: InboundMessageJob) -> None:
        factory = get_session_factory()
        async with factory() as session, with_tenant(session, job.organization_id):
            lead = await LeadRepository(session).get(job.lead_id)
            if lead is None:
                logger.error("job_lead_missing", extra={"job": job.model_dump()})
                return
            messages = MessageRepository(session)
            history = list(await messages.list_for_lead(job.lead_id))
            reply = await self.agent.respond(lead, history)
            if reply is None:
                return
            channel = _reply_channel(history)
            sid = await self.sender.send(to=lead.phone, body=reply, channel=channel)
            await messages.add_message(
                lead_id=lead.id,
                sender_type=SenderType.AI,
                content=reply,
                channel=channel,
                external_message_id=sid,
            )


def _reply_channel(history: Sequence[Message]) -> MessageChannel:
    """Reply on the channel the customer last used (default WhatsApp)."""
    for message in reversed(history):
        if message.sender_type == SenderType.CUSTOMER:
            return MessageChannel(message.channel)
    return MessageChannel.WHATSAPP


__all__ = ["InboundMessageJob", "InlineMessageProcessor", "MessageProcessor"]
