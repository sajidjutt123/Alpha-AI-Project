"""Lead repository."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lead, LeadStatus
from app.repositories.base import BaseRepository


class LeadRepository(BaseRepository[Lead]):
    model = Lead

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_or_create_by_phone(
        self,
        *,
        organization_id: uuid.UUID,
        phone: str,
        name: str | None = None,
    ) -> tuple[Lead, bool]:
        """Return the lead for (organization, phone), creating it if absent.

        Race-safe: a duplicate INSERT (webhook retry / concurrent message)
        degrades to a SELECT via ON CONFLICT DO NOTHING. Used by the Twilio
        webhook to identify leads (Phase 4).
        """
        stmt = (
            insert(Lead)
            .values(organization_id=organization_id, phone=phone, name=name)
            .on_conflict_do_nothing(index_elements=[Lead.organization_id, Lead.phone])
            .returning(Lead.id)
        )
        result = await self.session.execute(stmt)
        lead_id = result.scalar_one_or_none()

        if lead_id is None:
            existing = await self.session.execute(
                select(Lead).where(Lead.organization_id == organization_id, Lead.phone == phone)
            )
            return existing.scalar_one(), False

        lead = await self.get(lead_id)
        if lead is None:  # pragma: no cover - defensive
            raise RuntimeError("lead vanished immediately after insert")
        return lead, True

    async def list_for_organization(
        self,
        *,
        organization_id: uuid.UUID,
        status: LeadStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Lead]:
        stmt = (
            select(Lead)
            .where(Lead.organization_id == organization_id)
            .order_by(Lead.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_fields(self, lead: Lead, **fields: Any) -> Lead:
        """Apply a partial update (e.g. AI-extracted requirements)."""
        for key, value in fields.items():
            setattr(lead, key, value)
        await self.session.flush()
        return lead
