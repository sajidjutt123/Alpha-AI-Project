"""Authentication middleware tests."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.conftest import TEST_AUTH_SECRET, make_token


def test_missing_token_is_401(client: TestClient) -> None:
    response = client.get("/api/v1/leads")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    body = response.json()
    assert body["error"]["code"] == "http_401"


def test_garbage_token_is_401(client: TestClient) -> None:
    response = client.get("/api/v1/leads", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_wrong_secret_token_is_401(client: TestClient) -> None:
    from app.core.auth import issue_dev_token

    forged = issue_dev_token("some-user", "attacker-secret-that-is-long-enough-32b")
    response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_expired_token_is_401(client: TestClient) -> None:
    expired = make_token("some-user")
    # exp was valid at minting; force an already-expired token instead:
    from app.core.auth import issue_dev_token

    expired = issue_dev_token("some-user", TEST_AUTH_SECRET, expires_in=-120)
    response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_valid_token_but_unknown_agent_is_403(client: TestClient) -> None:
    token = make_token("00000000-0000-4000-8000-000000000000")
    response = client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["code"] == "http_403"


def test_health_needs_no_token(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == status.HTTP_200_OK
