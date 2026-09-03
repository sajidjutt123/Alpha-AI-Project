"""Shared Pydantic response/request schemas (API contracts).

Schemas are grouped by domain and filled in as phases land:
- Phase 3: leads, properties, agents
- Phase 4: webhook payloads
- Phase 5: AI intent/extraction/qualification
"""

from app.schemas.health import HealthResponse

__all__ = ["HealthResponse"]
