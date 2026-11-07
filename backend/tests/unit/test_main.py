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
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    )
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_readiness_probe_returns_200_when_all_healthy(client: TestClient) -> None:
    """Verify GET /health/ready returns HTTP 200 when database and Redis are reachable."""
    from unittest.mock import patch

    with (
        patch("app.main.check_database_health", return_value=True),
        patch("app.main.check_redis_health", return_value=True),
    ):
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert data["redis"] == "connected"
        assert data["app"] == "AgentGuard AI Test"
        assert data["version"] == "0.1.0-test"
        assert data["environment"] == "testing"


def test_readiness_probe_returns_503_when_database_fails(client: TestClient) -> None:
    """Verify GET /health/ready returns HTTP 503 when the database check fails."""
    from unittest.mock import patch

    with (
        patch("app.main.check_database_health", return_value=False),
        patch("app.main.check_redis_health", return_value=True),
    ):
        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "unreachable"
        assert data["redis"] == "connected"


def test_readiness_probe_returns_503_when_redis_fails(client: TestClient) -> None:
    """Verify GET /health/ready returns HTTP 503 when the Redis check fails."""
    from unittest.mock import patch

    with (
        patch("app.main.check_database_health", return_value=True),
        patch("app.main.check_redis_health", return_value=False),
    ):
        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "connected"
        assert data["redis"] == "unreachable"


def test_readiness_probe_returns_503_when_both_fail(client: TestClient) -> None:
    """Verify GET /health/ready returns HTTP 503 when both services are unreachable."""
    from unittest.mock import patch

    with (
        patch("app.main.check_database_health", return_value=False),
        patch("app.main.check_redis_health", return_value=False),
    ):
        response = client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "unreachable"
        assert data["redis"] == "unreachable"


def test_lifespan_closes_database_and_redis() -> None:
    """Verify application lifespan manager disposes database and redis pools on shutdown."""
    from unittest.mock import AsyncMock, patch

    mock_close_db = AsyncMock()
    mock_close_redis = AsyncMock()

    with (
        patch("app.main.close_db", mock_close_db),
        patch("app.main.close_redis", mock_close_redis),
    ):
        test_settings = Settings(
            secret_key=SecretStr("lifespan-test-secret-key-at-least-32-chars!"),
            environment="testing",
        )
        test_app = create_application(settings=test_settings)
        with TestClient(test_app):
            pass

        mock_close_db.assert_awaited_once()
        mock_close_redis.assert_awaited_once()


def test_lifespan_continues_redis_cleanup_when_db_fails() -> None:
    """Verify application lifespan manager executes Redis cleanup even if database disposal throws."""
    from unittest.mock import AsyncMock, patch

    mock_close_db = AsyncMock(side_effect=RuntimeError("Database disposal failure"))
    mock_close_redis = AsyncMock()

    with (
        patch("app.main.close_db", mock_close_db),
        patch("app.main.close_redis", mock_close_redis),
    ):
        test_settings = Settings(
            secret_key=SecretStr("lifespan-test-secret-key-at-least-32-chars!"),
            environment="testing",
        )
        test_app = create_application(settings=test_settings)
        with TestClient(test_app):
            pass

        mock_close_db.assert_awaited_once()
        mock_close_redis.assert_awaited_once()
