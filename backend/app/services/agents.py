"""Agent service — team directory."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import Agent
from app.repositories import AgentRepository


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self.agents = AgentRepository(session)

    async def list_agents(self, organization_id: uuid.UUID) -> Sequence[Agent]:
        return await self.agents.list_for_organization(organization_id)

    async def get_agent(self, organization_id: uuid.UUID, agent_id: uuid.UUID) -> Agent:
        agent = await self.agents.get_for_organization(agent_id, organization_id)
        if agent is None:
            raise NotFoundError(f"Agent {agent_id} not found")
        return agent
