"""Shared Pydantic response/request schemas (API contracts)."""

from app.schemas.agents import AgentOut, MeOut
from app.schemas.analytics import AnalyticsOverview
from app.schemas.auth import DevLoginRequest, SessionAgent, TokenResponse
from app.schemas.health import HealthResponse
from app.schemas.leads import (
    LeadCreate,
    LeadDetail,
    LeadOut,
    LeadUpdate,
    MatchedProperty,
    TranscriptMessage,
)
from app.schemas.messages import AgentMessageRequest, MessageOut
from app.schemas.pagination import Page
from app.schemas.properties import PropertyCreate, PropertyOut

__all__ = [
    "AgentMessageRequest",
    "AgentOut",
    "AnalyticsOverview",
    "DevLoginRequest",
    "HealthResponse",
    "LeadCreate",
    "LeadDetail",
    "LeadOut",
    "LeadUpdate",
    "MatchedProperty",
    "MeOut",
    "MessageOut",
    "Page",
    "PropertyCreate",
    "PropertyOut",
    "SessionAgent",
    "TokenResponse",
    "TranscriptMessage",
]
