"""Lead↔Property match model — an AI recommendation with explanation."""

import uuid

from sqlalchemy import ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UuidPkMixin


class LeadPropertyMatch(UuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "lead_property_matches"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0..100
    reason: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return (
            f"LeadPropertyMatch(lead_id={self.lead_id!r}, "
            f"property_id={self.property_id!r}, score={self.match_score!r})"
        )
