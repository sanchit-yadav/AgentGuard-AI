"""Database connection management and session factory using SQLAlchemy 2.x and asyncpg.

Provides:
- Asynchronous connection pool management via create_async_engine.
- Session factory configured for asynchronous execution (expire_on_commit=False).
- FastAPI dependency injection (get_db) with automatic commit/rollback semantics.
- Lightweight connectivity check (check_database_health) for readiness probes.
- Graceful shutdown resource disposal.
"""

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global singleton engine and session factory handles
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the global AsyncEngine singleton, initializing it if necessary."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            echo=settings.debug,
        )
        logger.debug(
            "Initialized database AsyncEngine",
            extra={
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
            },
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global async sessionmaker factory, initializing it if necessary."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def close_db() -> None:
    """Dispose of the database engine and close all pooled connections."""
    global _engine, _session_factory
    if _engine is not None:
        logger.info("Disposing database AsyncEngine connection pool")
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a managed asynchronous database session.

    Responsibilities:
    - Session lifecycle management (instantiation and guaranteed closure).
    - Exception boundary safety: automatically rolls back active uncommitted
      transactions if an unhandled exception escapes the route handler.

    Explicit Transaction Policy:
    - This dependency does NOT automatically commit transactions.
    - Mutating domain services and repositories MUST explicitly manage their
      transaction boundaries via `async with session.begin():` or explicit
      `await session.commit()`.
    - This ensures transaction commit failures (e.g. constraint violations)
      surface within the business logic before HTTP success responses are sent,
      and prevents unnecessary COMMIT statements on read-only endpoints.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health(timeout_seconds: float = 2.0) -> bool:
    """Perform a lightweight database liveness probe (SELECT 1).

    Args:
        timeout_seconds: Maximum seconds to wait before marking check as failed.

    Returns:
        True if the database responds within the timeout, False otherwise.
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            coro = session.execute(text("SELECT 1"))
            await asyncio.wait_for(coro, timeout=timeout_seconds)
            return True
    except Exception as exc:
        logger.warning(
            "Database connectivity check failed",
            extra={
                "error_type": type(exc).__name__,
                "timeout_seconds": timeout_seconds,
            },
        )
        return False
