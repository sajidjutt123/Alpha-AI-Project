"""Application entrypoint.

`create_app()` is the factory used by tests and by `uvicorn app.main:app`.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import api_router
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.logging import setup_logging
from app.workers.messaging import InlineMessageProcessor


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="AI Real-Estate Lead Qualification & Sales Automation Platform",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"http_{exc.status_code}",
                    "message": str(exc.detail),
                }
            },
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Queue seam: the webhook enqueues jobs on this processor. Swap it for a
    # Redis/Arq-backed implementation in Phase 8 without touching the webhook.
    app.state.message_processor = InlineMessageProcessor()

    return app


app = create_app()
