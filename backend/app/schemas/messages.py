"""Message API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MessageChannel, SenderType


class AgentMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    sender_type: SenderType
    content: str
    channel: MessageChannel
    external_message_id: str | None = None
    created_at: datetime
