"""Agent endpoints."""

from fastapi import APIRouter

from app.api.deps import AgentDep, TenantDb
from app.schemas.agents import AgentOut, MeOut
from app.services import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/me", response_model=MeOut)
async def whoami(db: TenantDb, agent: AgentDep) -> MeOut:
    # Re-fetch through the tenant-bound transaction: same row, full fields,
    # and it doubles as a self-visibility check under RLS.
    full = await AgentService(db).get_agent(agent.organization_id, agent.agent_id)
    return MeOut.model_validate(full)


@router.get("", response_model=list[AgentOut])
async def list_agents(db: TenantDb, agent: AgentDep) -> list[AgentOut]:
    agents = await AgentService(db).list_agents(agent.organization_id)
    return [AgentOut.model_validate(a) for a in agents]
