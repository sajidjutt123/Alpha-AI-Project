"""SQLAlchemy ORM models mapping the database schema.

DDL is owned by SQL migrations (`database/migrations/`) — nothing here
creates or alters tables. Models exist for typed queries via repositories.
"""

from app.models.agent import Agent
from app.models.ai_run import AIRun
from app.models.base import Base
from app.models.enums import (
    AgentRole,
    LeadIntent,
    LeadStatus,
    MessageChannel,
    PropertyAvailability,
    PropertyType,
    SenderType,
)
from app.models.lead import Lead
from app.models.lead_property_match import LeadPropertyMatch
from app.models.message import Message
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.property import Property

__all__ = [
    "AIRun",
    "Agent",
    "AgentRole",
    "Base",
    "Lead",
    "LeadIntent",
    "LeadPropertyMatch",
    "LeadStatus",
    "Message",
    "MessageChannel",
    "Notification",
    "Organization",
    "Property",
    "PropertyAvailability",
    "PropertyType",
    "SenderType",
]
