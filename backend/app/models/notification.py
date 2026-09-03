"""Notification model — dashboard alerts with per-agent read state."""

import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UuidPkMixin


class Notification(UuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "notifications"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("leads.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    read_by: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), nullable=False, default=list, server_default="{}"
    )

    def __repr__(self) -> str:
        return f"Notification(id={self.id!r}, type={self.type!r}, title={self.title!r})"
