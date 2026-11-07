"""Integration tests verifying FastAPI health and readiness endpoints against live services.

Covers:
- GET /health/live without mocks.
- GET /health/ready when live dependencies are running (200 OK).
- GET /health/ready when database is pointed to an unreachable port (503 Service Unavailable).
- GET /health/ready when Redis is pointed to an unreachable port (503 Service Unavailable).
"""

import pytest
from fastapi.testclient import TestClient

from app.core import database, redis
from app.core.config import Settings
from app.main import create_application


@pytest.mark.integration
def test_live_probe_against_application() -> None:
    """Verify /health/live functions without external dependencies."""
    app = create_application()
    with TestClient(app) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


@pytest.mark.integration
def test_ready_probe_all_healthy_live_services() -> None:
    """Verify /health/ready returns HTTP 200 when live Postgres and Redis respond."""
    app = create_application()
    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert data["redis"] == "connected"


@pytest.mark.integration
def test_ready_probe_returns_503_when_database_unreachable() -> None:
    """Verify /health/ready returns HTTP 503 when pointing to an unreachable PostgreSQL port."""
    bad_db_settings = Settings(
        database_url="postgresql+asyncpg://agentguard:wrong@127.0.0.1:5433/agentguard_db",
    )
    # Reset singleton engine
    database._engine = None
    database._session_factory = None

    app = create_application(settings=bad_db_settings)
    try:
        with TestClient(app) as client:
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["database"] == "unreachable"
    finally:
        database._engine = None
        database._session_factory = None


@pytest.mark.integration
def test_ready_probe_returns_503_when_redis_unreachable() -> None:
    """Verify /health/ready returns HTTP 503 when pointing to an unreachable Redis port."""
    bad_redis_settings = Settings(
        redis_url="redis://127.0.0.1:6380/0",
    )
    # Reset singleton redis pool
    redis._redis_pool = None

    app = create_application(settings=bad_redis_settings)
    try:
        with TestClient(app) as client:
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["redis"] == "unreachable"
    finally:
        redis._redis_pool = None
