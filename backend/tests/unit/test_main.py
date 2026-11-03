"""Unit tests for FastAPI application factory, metadata, and health probes."""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import app, create_application


def test_app_imports_successfully() -> None:
    """Verify that the FastAPI app instance imports cleanly."""
    assert app is not None
    assert app.title == "AgentGuard AI"


def test_create_application_metadata() -> None:
    """Verify application metadata and version settings."""
    custom_settings = Settings(
        app_name="Custom AgentGuard",
        app_version="1.2.3",
        environment="testing",
        secret_key=SecretStr("custom-secret-key-for-testing-32-chars!"),
    )
    custom_app = create_application(settings=custom_settings)

    assert custom_app.title == "Custom AgentGuard"
    assert custom_app.version == "1.2.3"


def test_production_disables_docs_urls() -> None:
    """Verify that OpenAPI documentation endpoints are disabled in production."""
    prod_settings = Settings(
        environment="production",
        secret_key=SecretStr("super-secure-production-key-length-32-chars!"),
        debug=False,
    )
    prod_app = create_application(settings=prod_settings)

    assert prod_app.docs_url is None
    assert prod_app.redoc_url is None
    assert prod_app.openapi_url is None


def test_liveness_probe_returns_http_200(client: TestClient) -> None:
    """Verify that GET /health/live returns HTTP 200 with process status."""
    response = client.get("/health/live")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "alive"
    assert data["app"] == "AgentGuard AI Test"
    assert data["version"] == "0.1.0-test"
    assert data["environment"] == "testing"


def test_cors_headers_applied(client: TestClient) -> None:
    """Verify that configured CORS allowed origins receive proper response headers."""
    response = client.get(
        "/health/live",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"
