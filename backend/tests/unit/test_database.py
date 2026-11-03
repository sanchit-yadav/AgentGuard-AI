"""Unit tests for asynchronous database engine, session factory, and lifecycle."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core import database


@pytest.fixture(autouse=True)
def reset_database_singletons() -> Generator[None, None, None]:
    """Ensure database singletons are reset before and after each test."""
    database._engine = None
    database._session_factory = None
    yield
    database._engine = None
    database._session_factory = None


def test_get_engine_initializes_singleton() -> None:
    """Verify get_engine creates and caches AsyncEngine with pool settings."""
    mock_engine = MagicMock(spec=AsyncEngine)

    with patch(
        "app.core.database.create_async_engine", return_value=mock_engine
    ) as mock_create:
        engine1 = database.get_engine()
        engine2 = database.get_engine()

        assert engine1 is mock_engine
        assert engine2 is mock_engine
        assert mock_create.call_count == 1
        _, kwargs = mock_create.call_args
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["pool_size"] == 10
        assert kwargs["max_overflow"] == 5


def test_get_session_factory_initializes_with_correct_options() -> None:
    """Verify get_session_factory configures expire_on_commit=False and binds to engine."""
    mock_engine = MagicMock(spec=AsyncEngine)
    mock_factory = MagicMock(spec=async_sessionmaker)

    with (
        patch("app.core.database.get_engine", return_value=mock_engine),
        patch(
            "app.core.database.async_sessionmaker", return_value=mock_factory
        ) as mock_sm_init,
    ):
        factory1 = database.get_session_factory()
        factory2 = database.get_session_factory()

        assert factory1 is mock_factory
        assert factory2 is mock_factory
        assert mock_sm_init.call_count == 1
        _, kwargs = mock_sm_init.call_args
        assert kwargs["bind"] is mock_engine
        assert kwargs["expire_on_commit"] is False
        assert kwargs["autoflush"] is False


@pytest.mark.asyncio
async def test_close_db_disposes_engine_and_clears_singletons() -> None:
    """Verify close_db awaits engine disposal and resets module variables."""
    mock_engine = AsyncMock(spec=AsyncEngine)
    database._engine = mock_engine
    database._session_factory = MagicMock(spec=async_sessionmaker)

    await database.close_db()

    mock_engine.dispose.assert_awaited_once()
    assert database._engine is None
    assert database._session_factory is None


@pytest.mark.asyncio
async def test_close_db_noop_when_not_initialized() -> None:
    """Verify close_db does not fail when called without prior initialization."""
    database._engine = None
    database._session_factory = None

    await database.close_db()

    assert database._engine is None
    assert database._session_factory is None


@pytest.mark.asyncio
async def test_get_db_commits_and_closes_on_success() -> None:
    """Verify get_db session dependency commits and closes the session on success."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None

    mock_factory = MagicMock(return_value=mock_context)

    with patch("app.core.database.get_session_factory", return_value=mock_factory):
        async for session in database.get_db():
            assert session is mock_session

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_rolls_back_and_closes_on_error() -> None:
    """Verify get_db rolls back the transaction and closes session on unhandled exception."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None

    mock_factory = MagicMock(return_value=mock_context)

    with patch("app.core.database.get_session_factory", return_value=mock_factory):
        gen = database.get_db()
        session = await anext(gen)
        assert session is mock_session

        with pytest.raises(ValueError, match="Database query error"):
            await gen.athrow(ValueError("Database query error"))

        mock_session.commit.assert_not_awaited()
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_database_health_returns_true_on_success() -> None:
    """Verify check_database_health returns True when SELECT 1 executes cleanly."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None

    mock_factory = MagicMock(return_value=mock_context)

    with patch("app.core.database.get_session_factory", return_value=mock_factory):
        is_healthy = await database.check_database_health(timeout_seconds=1.0)
        assert is_healthy is True
        mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_database_health_returns_false_on_exception() -> None:
    """Verify check_database_health returns False when database connection fails."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = ConnectionRefusedError("PostgreSQL port closed")

    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_context.__aexit__.return_value = None

    mock_factory = MagicMock(return_value=mock_context)

    with patch("app.core.database.get_session_factory", return_value=mock_factory):
        is_healthy = await database.check_database_health(timeout_seconds=1.0)
        assert is_healthy is False
