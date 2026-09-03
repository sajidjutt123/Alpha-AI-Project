"""Lead endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AgentDep, TenantDb
from app.models.enums import LeadStatus
from app.schemas.leads import (
    LeadCreate,
    LeadDetail,
    LeadOut,
    LeadUpdate,
    MatchedProperty,
    TranscriptMessage,
)
from app.schemas.pagination import Page
from app.services import LeadService

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=Page[LeadOut])
async def list_leads(
    db: TenantDb,
    agent: AgentDep,
    lead_status: Annotated[LeadStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[LeadOut]:
    items, total = await LeadService(db).list_leads(
        agent.organization_id,
        status=lead_status,
        query=q,
        limit=limit,
        offset=offset,
    )
    return Page(
        items=[LeadOut.model_validate(i) for i in items], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(payload: LeadCreate, db: TenantDb, agent: AgentDep) -> LeadOut:
    lead, _ = await LeadService(db).create_lead(agent.organization_id, payload)
    return LeadOut.model_validate(lead)


@router.get("/{lead_id}", response_model=LeadDetail)
async def get_lead(lead_id: uuid.UUID, db: TenantDb, agent: AgentDep) -> LeadDetail:
    lead, transcript, matches = await LeadService(db).get_lead_detail(
        agent.organization_id, lead_id
    )
    return LeadDetail(
        **LeadOut.model_validate(lead).model_dump(),
        messages=[TranscriptMessage.model_validate(m) for m in transcript],
        matched_properties=[
            MatchedProperty(
                property_id=prop.id,
                title=prop.title,
                price=prop.price,
                location=prop.location,
                property_type=prop.property_type,
                bedrooms=prop.bedrooms,
                match_score=match.match_score,
                reason=match.reason,
            )
            for prop, match in matches
        ],
    )


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: uuid.UUID, payload: LeadUpdate, db: TenantDb, agent: AgentDep
) -> LeadOut:
    lead = await LeadService(db).update_lead(agent.organization_id, lead_id, payload)
    return LeadOut.model_validate(lead)
