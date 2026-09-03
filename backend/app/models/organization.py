"""Organization model — the SaaS tenant root."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UuidPkMixin


class Organization(UuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    # Inbound Twilio routing (migration 004): the org that owns each number.
    twilio_whatsapp_from: Mapped[str | None] = mapped_column(String, unique=True)
    twilio_sms_from: Mapped[str | None] = mapped_column(String, unique=True)

    def __repr__(self) -> str:
        return f"Organization(id={self.id!r}, slug={self.slug!r})"
