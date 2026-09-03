"""Health endpoint contract tests (Phase 1 gate)."""

from fastapi import status
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"
    assert isinstance(body["version"], str)
    assert isinstance(body["timestamp"], str)


def test_health_schema_is_stable(client: TestClient) -> None:
    """Guard the public contract — dashboard and uptime checks rely on it."""
    body = client.get("/api/v1/health").json()

    assert set(body) == {"status", "version", "environment", "timestamp"}


def test_unknown_route_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_openapi_is_published(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["info"]["title"] == "Alpha AI"
