"""Lead service — business rules for lead management.

Status transitions are domain logic (not the LLM's, not the client's):
a lead moves through NEW → CONTACTED → QUALIFIED → CONVERTED, with LOST
reachable from any active stage and reopen paths for re-engagement.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Lead, LeadPropertyMatch, LeadStatus, Message, Property
from app.models.enums import MessageChannel, SenderType
from app.repositories import AgentRepository, LeadRepository, MessageRepository
from app.schemas.leads import LeadCreate, LeadUpdate

ALLOWED_TRANSITIONS: dict[LeadStatus, frozenset[LeadStatus]] = {
    LeadStatus.NEW: frozenset({LeadStatus.CONTACTED, LeadStatus.QUALIFIED, LeadStatus.LOST}),
    LeadStatus.CONTACTED: frozenset({LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.LOST}),
    LeadStatus.QUALIFIED: frozenset({LeadStatus.CONTACTED, LeadStatus.CONVERTED, LeadStatus.LOST}),
    LeadStatus.CONVERTED: frozenset(),
    LeadStatus.LOST: frozenset({LeadStatus.NEW, LeadStatus.CONTACTED}),
}


class LeadService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.agents = AgentRepository(session)
        self.messages = MessageRepository(session)

    async def create_lead(
        self, organization_id: uuid.UUID, payload: LeadCreate
    ) -> tuple[Lead, bool]:
        """Create a lead manually. Returns (lead, created).

        Raises ConflictError when the phone number already has a lead in
        this organization — agents should edit the existing record instead.
        """
        from sqlalchemy import select

        stmt = select(Lead).where(
            Lead.organization_id == organization_id, Lead.phone == payload.phone
        )
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ConflictError(
                f"A lead with phone {payload.phone} already exists in this organization"
            )

        if payload.assigned_agent_id is not None and (
            await self.agents.get_for_organization(payload.assigned_agent_id, organization_id)
            is None
        ):
            raise BusinessRuleError(
                "assigned_agent_id must be an active agent of this organization"
            )

        lead = Lead(
            organization_id=organization_id,
            phone=payload.phone,
            name=payload.name,
            email=payload.email,
            intent=payload.intent,
            budget_min=payload.budget_min,
            budget_max=payload.budget_max,
            preferred_location=payload.preferred_location,
            property_type=payload.property_type,
            bedrooms=payload.bedrooms,
            assigned_agent_id=payload.assigned_agent_id,
        )
        await self.leads.add(lead)
        return lead, True

    async def list_leads(
        self,
        organization_id: uuid.UUID,
        *,
        status: LeadStatus | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Lead], int]:
        items = await self.leads.list_for_organization(
            organization_id=organization_id,
            status=status,
            query=query,
            limit=limit,
            offset=offset,
        )
        total = await self.leads.count_for_organization(
            organization_id=organization_id, status=status, query=query
        )
        return list(items), total

    async def get_lead(self, organization_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
        lead = await self.leads.get_for_organization(lead_id, organization_id)
        if lead is None:
            raise NotFoundError(f"Lead {lead_id} not found")
        return lead

    async def get_lead_detail(
        self, organization_id: uuid.UUID, lead_id: uuid.UUID
    ) -> tuple[Lead, Sequence[Message], Sequence[tuple[Property, LeadPropertyMatch]]]:
        """(lead, transcript, (property, match) pairs) for the detail view."""
        lead = await self.get_lead(organization_id, lead_id)
        transcript = list(await self.messages.list_for_lead(lead.id))
        matches = list(await self.leads.matches_for_lead(lead.id))
        return lead, transcript, matches

    async def update_lead(
        self, organization_id: uuid.UUID, lead_id: uuid.UUID, payload: LeadUpdate
    ) -> Lead:
        lead = await self.get_lead(organization_id, lead_id)

        if payload.status is not None and payload.status != lead.status:
            await self._validate_transition(lead.status, payload.status)

        if (
            payload.assigned_agent_id is not None
            and payload.assigned_agent_id != lead.assigned_agent_id
            and await self.agents.get_for_organization(payload.assigned_agent_id, organization_id)
            is None
        ):
            raise BusinessRuleError(
                "assigned_agent_id must be an active agent of this organization"
            )

        fields = payload.model_dump(exclude_unset=True, exclude_none=True)
        if fields:
            await self.leads.update_fields(lead, **fields)
        return lead

    async def record_agent_message(
        self, organization_id: uuid.UUID, lead_id: uuid.UUID, content: str
    ) -> Lead:
        """Agent takeover note from the dashboard (Phase 7 live chat)."""
        lead = await self.get_lead(organization_id, lead_id)
        await self.messages.add_message(
            lead_id=lead.id,
            sender_type=SenderType.AGENT,
            content=content,
            channel=MessageChannel.DASHBOARD,
        )
        if lead.status == LeadStatus.NEW:
            await self.leads.update_fields(lead, status=LeadStatus.CONTACTED)
        return lead

    @staticmethod
    async def _validate_transition(current: LeadStatus, target: LeadStatus) -> None:
        allowed = ALLOWED_TRANSITIONS[current]
        if target not in allowed:
            raise BusinessRuleError(f"Illegal status transition {current.value} -> {target.value}")
