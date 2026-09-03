"""Security hardening tests (Phase 9).

Covers: response security headers, rate limiting (unit + endpoint), request
body-size cap, production-mode lockdown (docs off, dev-login off, unsigned
webhooks fail closed), JWT tamper/expiry rejection, and CORS scoping.
"""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import issue_dev_token
from app.core.config import get_settings
from app.core.rate_limit import SlidingWindowLimiter, reset_limiters
from app.main import create_app
from tests.conftest import TEST_AUTH_SECRET, OrgContext, seed_organization


@pytest.fixture
def hard_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """App with tight, test-friendly limits and a clean limiter registry."""
    monkeypatch.setenv("DEV_LOGIN_RATE_LIMIT", "3")
    monkeypatch.setenv("WEBHOOK_RATE_LIMIT", "3")
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "1024")
    get_settings.cache_clear()
    reset_limiters()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
    reset_limiters()


# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    def test_owasp_baseline_on_every_response(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in response.headers["permissions-policy"]
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    def test_api_responses_are_never_cached(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.headers["cache-control"] == "no-store"

    def test_headers_survive_error_responses(self, client: TestClient) -> None:
        response = client.get("/api/v1/leads")  # 401 — no token
        assert response.status_code == 401
        assert response.headers["x-content-type-options"] == "nosniff"


class TestCorsScoping:
    def test_allowed_origin_gets_acao_header(self, client: TestClient) -> None:
        response = client.get("/api/v1/health", headers={"Origin": "http://localhost:3000"})
        assert response.headers.get("access-control-allow-origin") == ("http://localhost:3000")

    def test_unknown_origin_gets_no_acao_header(self, client: TestClient) -> None:
        response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in response.headers

    def test_preflight_from_unknown_origin_is_rejected(self, client: TestClient) -> None:
        response = client.options(
            "/api/v1/leads",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in response.headers


class TestSlidingWindowLimiter:
    def test_allows_up_to_limit_then_rejects(self) -> None:
        limiter = SlidingWindowLimiter(limit=3, window_seconds=60)
        assert all(limiter.hit("k", now=100.0) for _ in range(3))
        assert not limiter.hit("k", now=100.5)

    def test_window_slides(self) -> None:
        limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
        assert limiter.hit("k", now=100.0)
        assert limiter.hit("k", now=110.0)
        # the t=100 event has left the window by t=161
        assert limiter.hit("k", now=161.0)

    def test_rejected_attempts_still_count(self) -> None:
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        assert limiter.hit("k", now=100.0)
        assert not limiter.hit("k", now=101.0)
        # the rejected attempt extended the budget-freeze
        assert not limiter.hit("k", now=130.0)

    def test_retry_after_is_positive_and_decreasing(self) -> None:
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        limiter.hit("k", now=100.0)
        assert limiter.retry_after("k", now=100.0) == 61
        assert limiter.retry_after("k", now=130.0) == 31
        assert limiter.retry_after("missing", now=100.0) == 1

    def test_keys_are_independent(self) -> None:
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        assert limiter.hit("a", now=100.0)
        assert limiter.hit("b", now=100.0)


class TestRateLimitedEndpoints:
    def test_dev_login_locks_out_after_budget(self, hard_client: TestClient) -> None:
        for _ in range(3):
            response = hard_client.post(
                "/api/v1/auth/dev-login", json={"email": "nobody@example.com"}
            )
            assert response.status_code == 401  # unknown email — but counted
        blocked = hard_client.post("/api/v1/auth/dev-login", json={"email": "nobody@example.com"})
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) >= 1
        assert blocked.json()["error"]["code"] == "http_429"

    def test_webhook_locks_out_after_budget(self, hard_client: TestClient) -> None:
        # Requests rejected by content-type still count — the limiter runs
        # before handler logic, so garbage floods cannot dodge the cap.
        for _ in range(3):
            response = hard_client.post(
                "/api/v1/webhooks/twilio",
                content=b"junk",
                headers={"Content-Type": "text/plain"},
            )
            assert response.status_code == 415
        blocked = hard_client.post(
            "/api/v1/webhooks/twilio",
            content=b"junk",
            headers={"Content-Type": "text/plain"},
        )
        assert blocked.status_code == 429

    def test_scopes_do_not_interfere(self, hard_client: TestClient) -> None:
        # exhaust the webhook budget…
        for _ in range(3):
            hard_client.post(
                "/api/v1/webhooks/twilio",
                content=b"junk",
                headers={"Content-Type": "text/plain"},
            )
        # …and dev-login still has its full budget.
        response = hard_client.post("/api/v1/auth/dev-login", json={"email": "nobody@example.com"})
        assert response.status_code == 401  # not 429

    def test_zero_disables_the_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEV_LOGIN_RATE_LIMIT", "0")
        get_settings.cache_clear()
        reset_limiters()
        app = create_app()
        with TestClient(app) as test_client:
            for _ in range(12):
                response = test_client.post(
                    "/api/v1/auth/dev-login", json={"email": "nobody@example.com"}
                )
                assert response.status_code == 401
        get_settings.cache_clear()


class TestBodySizeLimit:
    def test_oversized_declared_body_is_rejected(self, hard_client: TestClient) -> None:
        response = hard_client.post(
            "/api/v1/webhooks/twilio",
            content=b"x" * 2048,  # cap is 1024 in this fixture
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "http_413"

    def test_normal_bodies_pass(self, hard_client: TestClient) -> None:
        response = hard_client.post(
            "/api/v1/webhooks/twilio",
            content=b"x" * 32,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code in (403, 415, 422)  # reached the handler


class TestProductionLockdown:
    @pytest.fixture
    def prod_client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("AUTH_DEV_SECRET", TEST_AUTH_SECRET)
        get_settings.cache_clear()
        reset_limiters()
        app = create_app()
        with TestClient(app) as test_client:
            yield test_client
        get_settings.cache_clear()
        reset_limiters()

    def test_interactive_docs_are_off(self, prod_client: TestClient) -> None:
        assert prod_client.get("/api/v1/docs").status_code == 404
        assert prod_client.get("/api/v1/openapi.json").status_code == 404

    def test_dev_login_refuses(self, prod_client: TestClient) -> None:
        response = prod_client.post("/api/v1/auth/dev-login", json={"email": "owner@example.com"})
        assert response.status_code == 404

    def test_unsigned_webhook_fails_closed(self, prod_client: TestClient) -> None:
        response = prod_client.post(
            "/api/v1/webhooks/twilio",
            data={"MessageSid": "SM1", "From": "whatsapp:+923001234567", "Body": "hi"},
        )
        assert response.status_code == 503  # no token configured → refuse

    def test_headers_still_applied(self, prod_client: TestClient) -> None:
        response = prod_client.get("/api/v1/health")
        assert response.headers["x-content-type-options"] == "nosniff"


class TestTokenHardening:
    async def test_expired_token_is_rejected(self, client: TestClient, db_session) -> None:
        context = await seed_organization(db_session, name="TokenExpiryOrg")
        expired = issue_dev_token(
            str(context.owner.auth_user_id), TEST_AUTH_SECRET, expires_in=-120
        )
        response = client.get("/api/v1/agents/me", headers={"Authorization": f"Bearer {expired}"})
        assert response.status_code == 401

    async def test_wrong_secret_token_is_rejected(self, client: TestClient, db_session) -> None:
        context = await seed_organization(db_session, name="TokenTamperOrg")
        forged = issue_dev_token(
            str(context.owner.auth_user_id), "attacker-secret-0123456789ABCDEF0123"
        )
        response = client.get("/api/v1/agents/me", headers={"Authorization": f"Bearer {forged}"})
        assert response.status_code == 401

    async def test_alg_none_cannot_forgery(self, client: TestClient) -> None:
        # Hand-build an unsigned JWT (alg=none) — must never verify.
        import base64
        import json

        def b64(segment: bytes) -> str:
            return base64.urlsafe_b64encode(segment).rstrip(b"=").decode()

        header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        claims = b64(json.dumps({"sub": str(uuid.uuid4()), "exp": 4102444800}).encode())
        response = client.get(
            "/api/v1/agents/me", headers={"Authorization": f"Bearer {header}.{claims}."}
        )
        assert response.status_code == 401

    async def test_valid_token_still_works(self, client: TestClient, db_session) -> None:
        context: OrgContext = await seed_organization(db_session, name="TokenOkOrg")
        response = client.get("/api/v1/agents/me", headers=context.headers)
        assert response.status_code == 200


class TestRealtimeSecurity:
    async def test_stream_requires_auth(self, client: TestClient) -> None:
        with client.stream("GET", "/api/v1/realtime/stream") as response:
            assert response.status_code == 401

    async def test_events_never_leak_across_orgs(self, client: TestClient, db_session) -> None:
        """Two orgs streaming simultaneously see only their own events."""
        from app.core.events import bus

        org_a, org_b = uuid.uuid4(), uuid.uuid4()
        qa, qb = bus.subscribe(org_a), bus.subscribe(org_b)
        bus.publish(org_a, "lead.created", {"lead_id": "a-secret"})
        await asyncio.sleep(0)  # let queues settle
        assert qa.qsize() == 1
        assert qb.qsize() == 0
        bus.unsubscribe(org_a, qa)
        bus.unsubscribe(org_b, qb)
