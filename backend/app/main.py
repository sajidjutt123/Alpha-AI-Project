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
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.workers.messaging import InlineMessageProcessor


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    setup_logging(settings.log_level)

    # Optional error monitoring — a no-op without SENTRY_DSN (Phase 10).
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            send_default_pii=False,  # never ship tenant data with events
        )

    # Interactive docs stay available in development/staging; a production
    # API must not advertise its surface (Phase 9 hardening).
    docs_enabled = settings.environment not in ("production",)
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="AI Real-Estate Lead Qualification & Sales Automation Platform",
        docs_url=f"{settings.api_v1_prefix}/docs" if docs_enabled else None,
        redoc_url=f"{settings.api_v1_prefix}/redoc" if docs_enabled else None,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json" if docs_enabled else None,
    )

    # Middleware order: last added runs first — CORS outermost, then security
    # headers (applied to every response, including CORS-generated and the
    # 413 below), then the body-size gate. Both are pure-ASGI so the SSE
    # realtime stream passes through untouched.
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_body_bytes=settings.max_request_body_bytes,
    )
    app.add_middleware(SecurityHeadersMiddleware, api_prefix=settings.api_v1_prefix)
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
            headers=exc.headers,  # e.g. Retry-After (429), WWW-Authenticate (401)
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Queue seam: the webhook enqueues jobs on this processor. Swap it for a
    # Redis/Arq-backed implementation in Phase 8 without touching the webhook.
    app.state.message_processor = InlineMessageProcessor()

    return app


app = create_app()
