"""FastAPI application factory and entrypoint for AgentGuard AI.

Initializes application metadata, structured logging, CORS middleware,
and root health probe endpoints.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


class HealthCheckResponse(BaseModel):
    """Payload returned by the process liveness probe."""

    status: str
    app: str
    version: str
    environment: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycles."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info(
        "AgentGuard AI backend initialized",
        extra={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "api_prefix": settings.api_v1_prefix,
        },
    )
    yield
    logger.info("AgentGuard AI backend shutting down")


def create_application(settings: Settings | None = None) -> FastAPI:
    """Factory function for building the FastAPI application instance."""
    if settings is None:
        settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AgentGuard AI — Autonomous AI Agent Testing, Evaluation & "
            "Observability Platform API"
        ),
        docs_url=f"{settings.api_v1_prefix}/docs" if settings.environment != "production" else None,
        redoc_url=f"{settings.api_v1_prefix}/redoc" if settings.environment != "production" else None,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing (CORS) Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Process Liveness Health Check Probe
    @application.get(
        "/health/live",
        response_model=HealthCheckResponse,
        tags=["Health & Diagnostics"],
        summary="Process Liveness Probe",
        description=(
            "Confirms that the FastAPI application process is running and accepting "
            "HTTP traffic. Does not verify external database or cache connectivity."
        ),
    )
    async def liveness_probe() -> HealthCheckResponse:
        return HealthCheckResponse(
            status="alive",
            app=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
        )

    # Versioned API Router Scaffolding (Prepared for Milestone 1.3+)
    api_v1_router = APIRouter(prefix=settings.api_v1_prefix)
    application.include_router(api_v1_router)

    return application


# Global application instance for ASGI servers (Uvicorn)
app = create_application()
