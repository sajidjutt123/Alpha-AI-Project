"""Organization repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create(
        self,
        *,
        name: str,
        slug: str,
        organization_id: uuid.UUID | None = None,
        twilio_whatsapp_from: str | None = None,
        twilio_sms_from: str | None = None,
    ) -> Organization:
        """Create an organization.

        RLS note: the caller must bind the tenant context to the NEW
        organization's id before insert (see services/tests) — supplying
        `organization_id` explicitly makes that possible.
        """
        organization = Organization(
            id=organization_id,
            name=name,
            slug=slug,
            twilio_whatsapp_from=twilio_whatsapp_from,
            twilio_sms_from=twilio_sms_from,
        )
        return await self.add(organization)

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.session.execute(select(Organization).where(Organization.slug == slug))
        return result.scalar_one_or_none()
