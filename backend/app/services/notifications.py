"""Notification service — creation fans out to the realtime bus."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import defer_publish
from app.models import Notification
from app.repositories import NotificationRepository

logger = logging.getLogger(__name__)

NEW_LEAD = "NEW_LEAD"
HANDOFF = "HANDOFF"
HOT_LEAD = "HOT_LEAD"


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.notifications = NotificationRepository(session)

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        type: str,
        title: str,
        body: str | None = None,
        lead_id: uuid.UUID | None = None,
    ) -> Notification:
        """Persist a notification and push it to live dashboard subscribers."""
        notification = await self.notifications.create(
            organization_id=organization_id,
            type=type,
            title=title,
            body=body,
            lead_id=lead_id,
        )
        defer_publish(
            self.session,
            organization_id,
            "notification.created",
            {
                "id": str(notification.id),
                "type": type,
                "title": title,
                "body": body,
                "lead_id": str(lead_id) if lead_id else None,
            },
        )
        logger.info(
            "notification_created",
            extra={"type": type, "organization_id": str(organization_id)},
        )
        return notification
