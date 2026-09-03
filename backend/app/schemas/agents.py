"""Agent API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AgentRole


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    role: AgentRole
    is_active: bool
    created_at: datetime


class MeOut(AgentOut):
    organization_id: uuid.UUID
