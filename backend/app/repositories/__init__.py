"""Data-access layer.

Repositories are the only code that talks to the database. Services call
repositories; routes call services. Every repository method is tenant-blind
by design — organization isolation is enforced by Row Level Security via the
bound tenant context (`app.core.database.with_tenant`).
"""

from app.repositories.agents import AgentRepository
from app.repositories.ai_runs import AIRunRepository
from app.repositories.analytics import AnalyticsRepository
from app.repositories.base import BaseRepository
from app.repositories.leads import LeadRepository
from app.repositories.messages import MessageRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.organizations import OrganizationRepository
from app.repositories.properties import PropertyRepository

__all__ = [
    "AIRunRepository",
    "AgentRepository",
    "AnalyticsRepository",
    "BaseRepository",
    "LeadRepository",
    "MessageRepository",
    "NotificationRepository",
    "OrganizationRepository",
    "PropertyRepository",
]
