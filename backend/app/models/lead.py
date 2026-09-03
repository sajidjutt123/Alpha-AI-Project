"""Lead model — a prospect and their qualification state."""

import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UuidPkMixin
from app.models.enums import LeadIntent, LeadStatus, PropertyType


class Lead(UuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "leads"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status", create_type=False, native_enum=True),
        default=LeadStatus.NEW,
        nullable=False,
    )
    intent: Mapped[LeadIntent | None] = mapped_column(
        Enum(LeadIntent, name="lead_intent", create_type=False, native_enum=True),
    )

    # Captured requirements (AI-extracted, Phase 5)
    budget_min: Mapped[int | None] = mapped_column(BigInteger)
    budget_max: Mapped[int | None] = mapped_column(BigInteger)
    preferred_location: Mapped[str | None] = mapped_column(String)
    property_type: Mapped[PropertyType | None] = mapped_column(
        Enum(PropertyType, name="property_type", create_type=False, native_enum=True),
    )
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    urgency_score: Mapped[int | None] = mapped_column(Integer)

    # Qualification (deterministic scoring, Phase 5)
    qualification_score: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("agents.id", ondelete="SET NULL"),
    )

    # `updated_at` maintained by the trg_leads_set_updated_at trigger.
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "phone", name="uq_leads_organization_id_phone"),
    )

    def __repr__(self) -> str:
        return f"Lead(id={self.id!r}, phone={self.phone!r}, status={self.status!r})"
