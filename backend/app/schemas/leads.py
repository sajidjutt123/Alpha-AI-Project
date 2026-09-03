"""Lead API contracts."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import LeadIntent, LeadStatus, PropertyType

Phone = Annotated[str, Field(pattern=r"^\+?[0-9]{8,15}$")]


class LeadCreate(BaseModel):
    phone: Phone
    name: str | None = None
    email: EmailStr | None = None
    intent: LeadIntent | None = None
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    preferred_location: str | None = None
    property_type: PropertyType | None = None
    bedrooms: int | None = Field(default=None, ge=1, le=20)
    assigned_agent_id: uuid.UUID | None = None


class LeadUpdate(BaseModel):
    """Partial update. `status` goes through transition validation."""

    name: str | None = None
    email: EmailStr | None = None
    status: LeadStatus | None = None
    intent: LeadIntent | None = None
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    preferred_location: str | None = None
    property_type: PropertyType | None = None
    bedrooms: int | None = Field(default=None, ge=1, le=20)
    summary: str | None = None
    assigned_agent_id: uuid.UUID | None = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    phone: str
    email: str | None
    status: LeadStatus
    intent: LeadIntent | None
    budget_min: int | None
    budget_max: int | None
    preferred_location: str | None
    property_type: PropertyType | None
    bedrooms: int | None
    urgency_score: int | None
    qualification_score: int | None
    summary: str | None
    assigned_agent_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class MatchedProperty(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    property_id: uuid.UUID
    title: str
    price: int
    location: str
    property_type: PropertyType
    bedrooms: int | None
    match_score: int
    reason: str | None


class TranscriptMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender_type: str
    content: str
    channel: str
    created_at: datetime


class LeadDetail(LeadOut):
    messages: list[TranscriptMessage]
    matched_properties: list[MatchedProperty]
