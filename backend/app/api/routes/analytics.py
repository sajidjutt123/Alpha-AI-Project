"""Analytics endpoints."""

from fastapi import APIRouter

from app.api.deps import AgentDep, TenantDb
from app.schemas.analytics import AnalyticsOverview
from app.services import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(db: TenantDb, agent: AgentDep) -> AnalyticsOverview:
    return await AnalyticsService(db).overview(agent.organization_id)
