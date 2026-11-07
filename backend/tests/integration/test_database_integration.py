"""Integration tests verifying live PostgreSQL operations.

Covers:
- Connection establishment to PostgreSQL 16.
- SELECT 1 health probe query.
- Async session lifecycle.
- Explicit transaction commit.
- Explicit transaction rollback.
- Engine disposal and connection cleanup.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import check_database_health


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_live_connection_and_select_1() -> None:
    """Verify live connection establishment and SELECT 1 query against PostgreSQL."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            scalar = result.scalar()
            assert scalar == 1
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_session_commit_and_rollback() -> None:
    """Verify explicit transaction commit and rollback behavior on PostgreSQL."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        # Create a persistent table in test db for validating commit vs rollback
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS _integration_tx_test ("
                    "  id INT PRIMARY KEY,"
                    "  name TEXT NOT NULL"
                    ");"
                )
            )
            await conn.execute(text("DELETE FROM _integration_tx_test;"))

        # 1. Test explicit transaction commit
        async with session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO _integration_tx_test (id, name) VALUES (1, 'committed_record');"
                )
            )
            await session.commit()

        # Verify record exists in a fresh session
        async with session_factory() as session:
            res = await session.execute(
                text("SELECT name FROM _integration_tx_test WHERE id = 1;")
            )
            assert res.scalar() == "committed_record"

        # 2. Test explicit transaction rollback
        async with session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO _integration_tx_test (id, name) VALUES (2, 'rolled_back_record');"
                )
            )
            await session.rollback()

        # Verify rolled-back record does NOT exist
        async with session_factory() as session:
            res = await session.execute(
                text("SELECT name FROM _integration_tx_test WHERE id = 2;")
            )
            assert res.scalar() is None

        # Clean up test table
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS _integration_tx_test;"))
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_check_database_health_against_live_postgres() -> None:
    """Verify check_database_health helper executes against live database."""
    healthy = await check_database_health(timeout_seconds=3.0)
    assert healthy is True
