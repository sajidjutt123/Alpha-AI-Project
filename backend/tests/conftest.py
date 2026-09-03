"""Pytest fixtures shared across backend tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force deterministic settings for every test.

    `get_settings` is cached, so clear the cache after mutating the
    environment to guarantee a fresh `Settings` instance per test.
    """
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """HTTP client bound to a freshly built app instance."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
