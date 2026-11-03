"""Asynchronous Redis client and connection pool management using redis.asyncio.

Provides:
- Non-blocking Redis connection pool.
- FastAPI dependency injection (get_redis) yielding Redis client instances.
- Lightweight connectivity check (check_redis_health) via PING.
- Graceful connection pool shutdown during application lifespan.
"""

import asyncio
from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global singleton connection pool handle
_redis_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    """Return the global Redis ConnectionPool singleton, initializing if necessary."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            decode_responses=True,
        )
        logger.debug("Initialized Redis connection pool", extra={"max_connections": 20})
    return _redis_pool


def get_redis_client() -> Redis:
    """Return an asynchronous Redis client bound to the global connection pool."""
    pool = get_redis_pool()
    return Redis(connection_pool=pool)


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency yielding a scoped asynchronous Redis client instance."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()


async def close_redis() -> None:
    """Disconnect all active connections in the Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        logger.info("Disconnecting Redis connection pool")
        await _redis_pool.disconnect()
        _redis_pool = None


async def check_redis_health(timeout_seconds: float = 2.0) -> bool:
    """Perform a lightweight Redis ping connectivity check.

    Args:
        timeout_seconds: Maximum seconds to wait before marking check as failed.

    Returns:
        True if Redis responds with PONG within the timeout, False otherwise.
    """
    client = get_redis_client()
    try:
        coro = client.ping()
        result = await asyncio.wait_for(coro, timeout=timeout_seconds)
        return bool(result)
    except Exception as exc:
        logger.warning(
            "Redis connectivity check failed",
            extra={
                "error_type": type(exc).__name__,
                "timeout_seconds": timeout_seconds,
            },
        )
        return False
    finally:
        await client.aclose()
