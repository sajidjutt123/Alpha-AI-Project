"""Property API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PropertyAvailability, PropertyType


class PropertyCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    price: int = Field(gt=0)
    location: str = Field(min_length=2, max_length=200)
    property_type: PropertyType
    bedrooms: int | None = Field(default=None, ge=0, le=20)
    bathrooms: int | None = Field(default=None, ge=0, le=20)
    area: int | None = Field(default=None, gt=0)
    availability: PropertyAvailability = PropertyAvailability.AVAILABLE
    image_url: str | None = None


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    price: int
    location: str
    property_type: PropertyType
    bedrooms: int | None
    bathrooms: int | None
    area: int | None
    availability: PropertyAvailability
    image_url: str | None
    created_at: datetime
