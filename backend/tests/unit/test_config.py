"""Unit tests for Pydantic Settings configuration."""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_default_settings_behavior() -> None:
    """Test that default configuration behaves as documented."""
    settings = Settings()

    assert settings.app_name == "AgentGuard AI"
    assert settings.app_version == "0.1.0"
    assert settings.environment in ("development", "testing")
    assert settings.api_v1_prefix == "/api/v1"
    assert isinstance(settings.allowed_origins, list)
    assert len(settings.allowed_origins) >= 1
    assert settings.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    assert isinstance(settings.secret_key, SecretStr)


def test_settings_safe_dict_masks_secrets() -> None:
    """Verify that safe_dict() never outputs secret keys in plaintext."""
    settings = Settings(
        secret_key=SecretStr("super-confidential-token-value-12345"),
    )

    safe_payload = settings.safe_dict()
    assert safe_payload["secret_key"] == "[REDACTED]"
    assert "super-confidential" not in str(safe_payload)


def test_settings_comma_separated_origins() -> None:
    """Verify that comma-separated origin strings are parsed into lists."""
    settings = Settings(
        allowed_origins="https://app.example.com, https://admin.example.com",  # type: ignore[arg-type]
    )

    assert settings.allowed_origins == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_settings_log_level_normalization() -> None:
    """Verify that log level strings are converted to uppercase."""
    settings = Settings(
        log_level="warning",  # type: ignore[arg-type]
    )
    assert settings.log_level == "WARNING"


def test_invalid_environment_fails_validation() -> None:
    """Verify that unsupported environment values fail validation clearly."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(environment="invalid_env_name")  # type: ignore[arg-type]

    assert "environment" in str(exc_info.value)


def test_invalid_log_level_fails_validation() -> None:
    """Verify that unsupported log levels fail validation clearly."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(log_level="TRACE")  # type: ignore[arg-type]

    assert "log_level" in str(exc_info.value)


def test_production_enforces_secure_secret_key() -> None:
    """Verify that production rejects default or short secret keys."""
    # Default insecure key should fail
    with pytest.raises(ValidationError, match="requires a secure, non-default SECRET_KEY"):
        Settings(
            environment="production",
            secret_key=SecretStr("insecure-dev-secret-key-change-in-production-1234567890"),
        )

    # Short key should fail
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            environment="production",
            secret_key=SecretStr("too-short-key"),
        )


def test_production_enforces_debug_disabled() -> None:
    """Verify that production rejects debug=True."""
    with pytest.raises(ValidationError, match="Debug mode must be disabled in production"):
        Settings(
            environment="production",
            secret_key=SecretStr("a" * 40),
            debug=True,
        )


def test_production_accepts_valid_configuration() -> None:
    """Verify that production accepts a fully compliant secure configuration."""
    settings = Settings(
        environment="production",
        secret_key=SecretStr("prod-secret-key-with-sufficient-entropy-9876543210"),
        debug=False,
    )
    assert settings.environment == "production"
    assert settings.debug is False
