"""In-process sliding-window rate limiting (Phase 9 security hardening).

Keys are arbitrary strings — callers combine a route scope with the client
IP. A key is allowed while fewer than `limit` events fall inside the last
`window_seconds`; violations get HTTP 429 with a `Retry-After` header.

Single-instance by design (matching the Phase 8 event bus): every worker in
this process shares one registry, which is exactly the protection a
single-node MVP needs. The multi-instance swap is Redis behind this same
interface — `INCR` + `EXPIRE` (fixed window) or a sorted-set sliding window
per key — with no route-level changes (see docs/security-audit.md, finding
F1). Until then, a horizontally scaled deployment under-counts by node,
which is an acceptable degradation (each node still throttles locally).

The methods are synchronous on purpose: they run on the event loop, are
O(limit) at worst with tiny deques, and never await — no lock needed.
"""

import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

Event = float  # monotonic timestamp


class SlidingWindowLimiter:
    """Allow at most `limit` events per `window_seconds` per key."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[Event]] = {}

    def _prune(self, key: str, now: float) -> deque[Event]:
        window = self._events.setdefault(key, deque())
        cutoff = now - self.window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        return window

    def hit(self, key: str, *, now: float | None = None) -> bool:
        """Record an event for `key`; True when still within budget."""
        moment = time.monotonic() if now is None else now
        window = self._prune(key, moment)
        if len(window) >= self.limit:
            window.append(moment)  # rejected attempts still count
            return False
        window.append(moment)
        return True

    def retry_after(self, key: str, *, now: float | None = None) -> int:
        """Seconds until the oldest in-window event expires (>= 1)."""
        moment = time.monotonic() if now is None else now
        window = self._prune(key, moment)
        if not window:
            return 1
        return max(1, int(window[0] + self.window_seconds - moment) + 1)

    def reset(self) -> None:
        """Forget everything (tests only)."""
        self._events.clear()


# Registry keyed by (name, limit, window) so configuration changes create a
# fresh limiter instead of silently running with stale limits.
_limiters: dict[tuple[str, int, float], SlidingWindowLimiter] = {}


def get_limiter(name: str, limit: int, window_seconds: float) -> SlidingWindowLimiter:
    key = (name, limit, window_seconds)
    limiter = _limiters.get(key)
    if limiter is None:
        limiter = SlidingWindowLimiter(limit, window_seconds)
        _limiters[key] = limiter
    return limiter


def reset_limiters() -> None:
    """Clear all limiter state (tests only)."""
    _limiters.clear()


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    `request.client.host` is the socket peer — the connecting proxy, not the
    browser, when deployed behind one. We deliberately do NOT trust
    `X-Forwarded-For` here: it is client-settable, and a spoofed header must
    never buy an attacker a fresh budget. Platforms that terminate TLS in
    front of the API should set `--proxy-headers` / forward the real IP at
    the socket level (uvicorn `--forwarded-allow-ips`, see deployment docs).
    """
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str) -> Callable[[Request], None]:
    """FastAPI dependency factory: 429 (with Retry-After) past the budget.

    Limits come from settings so they are environment-tunable:
    `DEV_LOGIN_RATE_LIMIT` and `WEBHOOK_RATE_LIMIT` (requests per minute,
    per client IP). Set a limit to 0 to disable.
    """

    def dependency(request: Request) -> None:
        settings = get_settings()
        limit = {
            "dev-login": settings.dev_login_rate_limit,
            "webhook": settings.webhook_rate_limit,
        }.get(scope)
        if not limit:  # 0/None → disabled
            return
        limiter = get_limiter(scope, limit, 60.0)
        key = f"{scope}:{client_ip(request)}"
        if not limiter.hit(key):
            retry = limiter.retry_after(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — slow down and retry shortly",
                headers={"Retry-After": str(retry)},
            )

    return dependency
