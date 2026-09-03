"""System health contract."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness signal consumed by uptime checks and the dashboard."""

    status: Literal["ok"]
    version: str
    environment: str
    timestamp: datetime
