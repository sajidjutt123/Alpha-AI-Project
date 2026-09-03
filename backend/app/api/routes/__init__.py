"""HTTP API routes.

Every route module exposes an `APIRouter`; `routes.__init__` aggregates them
into a single `api_router` that `app.main` mounts under the versioned prefix
(`/api/v1`). Adding a new resource = new module + one line here.
"""

from fastapi import APIRouter

from app.api.routes import agents, analytics, health, leads, properties

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(leads.router)
api_router.include_router(properties.router)
api_router.include_router(agents.router)
api_router.include_router(analytics.router)

__all__ = ["api_router"]
