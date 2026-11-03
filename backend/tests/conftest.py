"""Pytest fixtures and test environment setup."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_application


@pytest.fixture
def test_settings() -> Settings:
    """Provide a test-specific settings instance."""
    return Settings(
        app_name="AgentGuard AI Test",
        app_version="0.1.0-test",
        environment="testing",
        debug=True,
        secret_key=SecretStr("test-secret-key-for-unit-testing-only-32bytes"),
        allowed_origins=["http://testserver", "http://localhost:3000"],
        log_level="DEBUG",
        database_url="postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db",
        redis_url="redis://localhost:6379/15",
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Provide a synchronous TestClient for testing the FastAPI application."""
    test_app = create_application(settings=test_settings)
    with TestClient(test_app, base_url="http://testserver") as test_client:
        yield test_client
