"""Agent repository."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent
from app.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    model = Agent

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_for_organization(
        self, organization_id: uuid.UUID, *, include_inactive: bool = False
    ) -> Sequence[Agent]:
        stmt = select(Agent).where(Agent.organization_id == organization_id)
        if not include_inactive:
            stmt = stmt.where(Agent.is_active)
        stmt = stmt.order_by(Agent.created_at.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_for_organization(
        self, agent_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Agent | None:
        result = await self.session.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.organization_id == organization_id,
                Agent.is_active,
            )
        )
        return result.scalar_one_or_none()
