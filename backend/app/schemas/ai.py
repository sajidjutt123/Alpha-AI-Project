"""Structured AI outputs (plan §7).

The analysis step returns THIS shape — validated by Pydantic before any of
it touches the database. Unknown or malformed fields are dropped/rejected
here, which is also the first line of defense against prompt injection.
"""

import enum

from pydantic import BaseModel, Field, model_validator

from app.models.enums import LeadIntent, PropertyType


class Sentiment(enum.StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    FRUSTRATED = "FRUSTRATED"


class ConversationAnalysis(BaseModel):
    """Complete current state of the customer's requirements (not a delta).

    The model re-reports every field each turn; the backend overwrites the
    lead's requirement fields with this snapshot. This handles customers
    changing their mind ("actually, Bahria not DHA") without merge logic.
    """

    intent: LeadIntent = LeadIntent.UNKNOWN
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    preferred_location: str | None = Field(default=None, max_length=200)
    property_type: PropertyType | None = None
    bedrooms: int | None = Field(default=None, ge=1, le=20)
    urgency_score: int | None = Field(default=None, ge=1, le=10)
    sentiment: Sentiment = Sentiment.NEUTRAL

    @model_validator(mode="after")
    def _budget_order(self) -> "ConversationAnalysis":
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError("budget_min must not exceed budget_max")
        return self
