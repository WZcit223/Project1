"""Integration test: the Application API starts and answers /health (Gate 1)."""

from fastapi.testclient import TestClient

import industrial_ai
from industrial_ai.api.app import create_app
from industrial_ai.core.config import Settings


def make_client() -> TestClient:
    return TestClient(create_app(Settings(env="test")))


def test_health_returns_ok_and_version() -> None:
    response = make_client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": industrial_ai.__version__}


def test_openapi_schema_is_served_under_api() -> None:
    response = make_client().get("/api/openapi.json")
    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


def test_app_keeps_injected_settings() -> None:
    settings = Settings(env="test", api_port=9100)
    assert create_app(settings).state.settings is settings
