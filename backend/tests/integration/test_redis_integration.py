"""Integration tests verifying live Redis operations.

Covers:
- Connection establishment to Redis 7.
- PING / PONG round-trip.
- Key write, read, and delete round-trip.
- Client closure and connection pool shutdown.
- Redis health check probe against live server.
"""

import pytest
from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings
from app.core.redis import check_redis_health


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_live_connection_and_ping() -> None:
    """Verify live connection establishment and PING command against Redis."""
    settings = get_settings()
    pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    client = Redis(connection_pool=pool)

    try:
        pong = await client.ping()
        assert pong is True
    finally:
        await client.aclose()
        await pool.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_set_get_and_delete() -> None:
    """Verify read/write/delete operations on live Redis instance."""
    settings = get_settings()
    pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    client = Redis(connection_pool=pool)

    test_key = "agentguard:integration:test_key"
    test_value = "staff_level_engineering_verification"

    try:
        # Write
        await client.set(test_key, test_value, ex=30)

        # Read
        retrieved = await client.get(test_key)
        assert retrieved == test_value

        # Delete
        deleted = await client.delete(test_key)
        assert deleted == 1

        # Confirm gone
        assert await client.get(test_key) is None
    finally:
        await client.aclose()
        await pool.disconnect()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_redis_health_against_live_redis() -> None:
    """Verify check_redis_health probe returns True against live Redis."""
    healthy = await check_redis_health(timeout_seconds=3.0)
    assert healthy is True
