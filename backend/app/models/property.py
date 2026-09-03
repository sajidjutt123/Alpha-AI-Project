"""Property model — a real-estate listing (prices in PKR, area in sq ft)."""

import uuid

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UuidPkMixin
from app.models.enums import PropertyAvailability, PropertyType


class Property(UuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "properties"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType, name="property_type", create_type=False, native_enum=True),
        nullable=False,
    )
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    area: Mapped[int | None] = mapped_column(Integer)  # square feet
    availability: Mapped[PropertyAvailability] = mapped_column(
        Enum(
            PropertyAvailability,
            name="property_availability",
            create_type=False,
            native_enum=True,
        ),
        default=PropertyAvailability.AVAILABLE,
        nullable=False,
    )
    image_url: Mapped[str | None] = mapped_column(String)

    def __repr__(self) -> str:
        return f"Property(id={self.id!r}, title={self.title!r}, price={self.price!r})"
