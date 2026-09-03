"""Pure-ASGI security middleware (Phase 9).

Implemented as raw ASGI wrappers rather than `BaseHTTPMiddleware` so the
SSE realtime stream (`/realtime/stream`) passes through untouched — no
response buffering, no extra task, headers injected on `response.start`
only.

1. `SecurityHeadersMiddleware` — defensive response headers on every
   response (OWASP secure-header baseline), plus `Cache-Control: no-store`
   on API responses so tenants' lead data never sits in shared caches.

2. `BodySizeLimitMiddleware` — reject requests whose declared
   `Content-Length` exceeds `max_request_body_bytes` with 413 before the
   handler runs. Twilio webhook forms and dashboard JSON payloads are small;
   a cap keeps a single request from pinning memory. (Chunked bodies without
   a declared length are the reverse proxy's job — documented in
   docs/security-audit.md.)
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SECURITY_HEADERS = [
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]

MAX_BODY_DEFAULT = 1_048_576  # 1 MiB


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, api_prefix: str = "/api") -> None:
        self.app = app
        self.api_prefix = api_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *SECURITY_HEADERS]
                headers = MutableHeaders(scope=message)
                path = scope.get("path", "")
                if path.startswith(self.api_prefix):
                    # API responses are per-tenant and dynamic — never cache.
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_body_bytes: int = MAX_BODY_DEFAULT) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return

        content_length = MutableHeaders(scope=scope).get("content-length")
        if (
            content_length
            and content_length.isdigit()
            and int(content_length) > self.max_body_bytes
        ):
            await self._reject(scope, send)
            return

        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, send: Send) -> None:
        # Consume nothing; answer immediately so the client stops sending.
        start: Message = {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"connection", b"close"),
            ],
        }
        await send(start)
        body: Message = {
            "type": "http.response.body",
            "body": b'{"error":{"code":"http_413","message":"Request body too large"}}',
        }
        await send(body)
