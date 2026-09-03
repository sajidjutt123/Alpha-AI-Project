"""Notification endpoints (bell dropdown)."""

from fastapi import APIRouter

from app.api.deps import AgentDep, TenantDb
from app.repositories import NotificationRepository
from app.schemas.notifications import NotificationList, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def list_notifications(db: TenantDb, agent: AgentDep) -> NotificationList:
    repo = NotificationRepository(db)
    items = await repo.list_recent(agent.organization_id)
    unread = await repo.unread_count(agent.organization_id, agent.agent_id)
    return NotificationList(
        items=[
            NotificationOut(
                id=item.id,
                lead_id=item.lead_id,
                type=item.type,
                title=item.title,
                body=item.body,
                created_at=item.created_at,
                read=agent.agent_id in item.read_by,
            )
            for item in items
        ],
        unread_count=unread,
    )


@router.post("/read-all")
async def mark_all_read(db: TenantDb, agent: AgentDep) -> dict[str, int]:
    marked = await NotificationRepository(db).mark_all_read(agent.organization_id, agent.agent_id)
    return {"marked": marked}
