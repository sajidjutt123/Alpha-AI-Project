"""Notification API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID | None
    type: str
    title: str
    body: str | None
    created_at: datetime
    read: bool = False


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread_count: int


class MarkReadResponse(BaseModel):
    marked: int
