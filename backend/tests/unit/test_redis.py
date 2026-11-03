"""Unit tests for asynchronous Redis client, connection pool, and lifecycle."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import ConnectionPool, Redis

from app.core import redis


@pytest.fixture(autouse=True)
def reset_redis_singleton() -> Generator[None, None, None]:
    """Ensure Redis pool singleton is reset before and after each test."""
    redis._redis_pool = None
    yield
    redis._redis_pool = None


def test_get_redis_pool_initializes_singleton() -> None:
    """Verify get_redis_pool creates and caches ConnectionPool singleton."""
    mock_pool = MagicMock(spec=ConnectionPool)

    with patch.object(
        ConnectionPool, "from_url", return_value=mock_pool
    ) as mock_from_url:
        pool1 = redis.get_redis_pool()
        pool2 = redis.get_redis_pool()

        assert pool1 is mock_pool
        assert pool2 is mock_pool
        assert mock_from_url.call_count == 1
        _, kwargs = mock_from_url.call_args
        assert kwargs["max_connections"] == 20
        assert kwargs["decode_responses"] is True


def test_get_redis_client_uses_pool() -> None:
    """Verify get_redis_client instantiates Redis with the managed connection pool."""
    mock_pool = MagicMock(spec=ConnectionPool)

    with (
        patch("app.core.redis.get_redis_pool", return_value=mock_pool),
        patch("app.core.redis.Redis") as mock_redis_cls,
    ):
        redis.get_redis_client()
        mock_redis_cls.assert_called_once_with(connection_pool=mock_pool)


@pytest.mark.asyncio
async def test_get_redis_yields_client_and_closes() -> None:
    """Verify get_redis dependency yields a client and calls aclose upon completion."""
    mock_client = AsyncMock(spec=Redis)

    with patch("app.core.redis.get_redis_client", return_value=mock_client):
        async for client in redis.get_redis():
            assert client is mock_client

        mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_redis_disconnects_pool_and_clears_singleton() -> None:
    """Verify close_redis calls pool disconnect and resets singleton."""
    mock_pool = AsyncMock(spec=ConnectionPool)
    redis._redis_pool = mock_pool

    await redis.close_redis()

    mock_pool.disconnect.assert_awaited_once()
    assert redis._redis_pool is None


@pytest.mark.asyncio
async def test_close_redis_noop_when_not_initialized() -> None:
    """Verify close_redis does not fail when called without prior initialization."""
    redis._redis_pool = None

    await redis.close_redis()

    assert redis._redis_pool is None


@pytest.mark.asyncio
async def test_check_redis_health_returns_true_on_pong() -> None:
    """Verify check_redis_health returns True when ping returns PONG."""
    mock_client = MagicMock(spec=Redis)
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.aclose = AsyncMock()

    with patch("app.core.redis.get_redis_client", return_value=mock_client):
        is_healthy = await redis.check_redis_health(timeout_seconds=1.0)

        assert is_healthy is True
        mock_client.ping.assert_awaited_once()
        mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_redis_health_returns_false_on_connection_error() -> None:
    """Verify check_redis_health returns False when ping raises an exception."""
    mock_client = MagicMock(spec=Redis)
    mock_client.ping = AsyncMock(
        side_effect=ConnectionRefusedError("Redis port 6379 unavailable")
    )
    mock_client.aclose = AsyncMock()

    with patch("app.core.redis.get_redis_client", return_value=mock_client):
        is_healthy = await redis.check_redis_health(timeout_seconds=1.0)

        assert is_healthy is False
        mock_client.aclose.assert_awaited_once()
