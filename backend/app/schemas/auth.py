"""Auth API contracts."""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import AgentRole


class DevLoginRequest(BaseModel):
    email: EmailStr


class SessionAgent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: AgentRole
    organization_id: uuid.UUID


class TokenResponse(BaseModel):
    token: str
    agent: SessionAgent
