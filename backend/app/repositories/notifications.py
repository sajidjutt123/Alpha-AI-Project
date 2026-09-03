"""Notification repository."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        type: str,
        title: str,
        body: str | None = None,
        lead_id: uuid.UUID | None = None,
    ) -> Notification:
        return await self.add(
            Notification(
                organization_id=organization_id,
                type=type,
                title=title,
                body=body,
                lead_id=lead_id,
            )
        )

    async def list_recent(
        self, organization_id: uuid.UUID, *, limit: int = 30
    ) -> Sequence[Notification]:
        result = await self.session.execute(
            select(Notification)
            .where(Notification.organization_id == organization_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def unread_count(self, organization_id: uuid.UUID, agent_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.organization_id == organization_id,
                ~Notification.read_by.contains([agent_id]),
            )
        )
        return int(result.scalar_one())

    async def mark_all_read(self, organization_id: uuid.UUID, agent_id: uuid.UUID) -> int:
        """Append the agent to read_by on every unread org notification."""
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.organization_id == organization_id,
                ~Notification.read_by.contains([agent_id]),
            )
            .values(read_by=func.array_append(Notification.read_by, agent_id))
        )
        return int(getattr(result, "rowcount", 0) or 0)
