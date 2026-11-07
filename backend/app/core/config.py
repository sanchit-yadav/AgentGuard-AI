"""Application configuration management using Pydantic Settings.

Reads configuration from environment variables and root/local .env files.
Enforces strict type validation and security policies (e.g., forbidding
insecure default secret keys in production).
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate repository root and backend directory for .env resolution
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Core application settings for AgentGuard AI."""

    model_config = SettingsConfigDict(
        env_file=(
            str(REPO_ROOT / ".env"),
            str(BACKEND_DIR / ".env"),
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Metadata
    app_name: str = Field(
        default="AgentGuard AI", description="Application service name"
    )
    app_version: str = Field(default="0.1.0", description="SemVer version tag")
    environment: Literal["development", "testing", "staging", "production"] = Field(
        default="development",
        description="Deployment environment runtime profile",
    )
    debug: bool = Field(default=False, description="Debug mode flag")
    api_v1_prefix: str = Field(
        default="/api/v1", description="Prefix for v1 REST API routes"
    )

    # Security & CORS
    secret_key: SecretStr = Field(
        default=SecretStr("insecure-dev-secret-key-change-in-production-1234567890"),
        description="Cryptographic secret key for signing sessions and JWTs",
    )
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origin hosts for frontend web applications",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Global application log severity threshold",
    )

    # Database Configuration
    database_url: str = Field(
        default="postgresql+asyncpg://agentguard:agentguard_dev_password@127.0.0.1:5432/agentguard_db",
        description="SQLAlchemy async database connection URL",
    )
    database_pool_size: int = Field(
        default=10,
        description="Maximum steady-state database connection pool size",
    )
    database_max_overflow: int = Field(
        default=5,
        description="Maximum overflow connections allowed above pool size",
    )

    # Redis & Task Queue
    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis connection URL for caching and task brokering",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        """Support comma-separated string format from environment variables."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        raise ValueError(
            "allowed_origins must be a list of strings or comma-separated string"
        )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: Any) -> str:
        """Normalize log level string to uppercase."""
        if isinstance(value, str):
            return value.strip().upper()
        return str(value)

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforce strict security standards in production environments."""
        if self.environment == "production":
            raw_key = self.secret_key.get_secret_value()
            if "insecure-dev" in raw_key or len(raw_key) < 32:
                raise ValueError(
                    "Production environment requires a secure, non-default SECRET_KEY "
                    "with at least 32 characters."
                )
            if self.debug:
                raise ValueError("Debug mode must be disabled in production.")
        return self

    def safe_dict(self) -> dict[str, Any]:
        """Return a dictionary of configuration with sensitive values masked."""
        data = self.model_dump()
        # Explicitly mask SecretStr fields
        data["secret_key"] = "[REDACTED]"
        return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
