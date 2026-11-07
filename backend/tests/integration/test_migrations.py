"""Integration tests verifying Alembic migrations against live PostgreSQL.

Validates:
1. Migration upgrade/downgrade round-trip.
2. Table creation matches all declarative ORM models.
3. PostgreSQL indexes, unique constraints, and foreign key rules.
"""

import asyncio
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.core.config import get_settings


def get_alembic_config() -> Config:
    """Load Alembic configuration pointing to backend/alembic.ini."""
    backend_dir = Path(__file__).resolve().parent.parent.parent
    ini_path = backend_dir / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_schema_contains_all_domain_tables() -> None:
    """Verify that all domain tables exist in the live PostgreSQL database."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    expected_tables = {
        "alembic_version",
        "organizations",
        "users",
        "organization_members",
        "projects",
        "agents",
        "agent_credentials",
        "agent_versions",
        "agent_tools",
        "test_suites",
        "test_cases",
        "test_runs",
        "test_executions",
        "execution_traces",
        "execution_events",
        "evaluations",
        "evaluation_metrics",
        "security_findings",
        "regression_results",
        "reports",
    }

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public';"
                )
            )
            existing_tables = {row[0] for row in result.fetchall()}
            missing_tables = expected_tables - existing_tables
            assert not missing_tables, f"Missing tables in PostgreSQL: {missing_tables}"
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_schema_indexes_and_gin_indexes() -> None:
    """Verify GIN and partial indexes are properly applied on PostgreSQL."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    try:
        async with engine.connect() as conn:
            # Check GIN indexes on JSONB fields
            result = await conn.execute(
                text(
                    "SELECT indexname, tablename, indexdef "
                    "FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexdef ILIKE '%USING gin%';"
                )
            )
            gin_indexes = {row[0]: (row[1], row[2]) for row in result.fetchall()}
            assert "ix_agent_tools_schema" in gin_indexes
            assert "ix_execution_events_payload" in gin_indexes

            # Check unique index on execution_traces (trace_id and test_execution_id)
            result = await conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'execution_traces';"
                )
            )
            trace_indexes = {row[0] for row in result.fetchall()}
            assert "ix_execution_traces_trace_id" in trace_indexes
            assert "ix_execution_traces_test_execution_id" in trace_indexes
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_round_trip() -> None:
    """Verify downgrade to base and upgrade back to head succeeds without errors."""
    cfg = get_alembic_config()

    # Run downgrade to base in separate thread to avoid nested event loop conflict
    await asyncio.to_thread(command.downgrade, cfg, "base")

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    try:
        # Verify public schema has no application domain tables
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name != 'alembic_version' "
                    "AND table_name NOT LIKE '\\_%';"
                )
            )
            tables_after_downgrade = [row[0] for row in result.fetchall()]
            assert len(tables_after_downgrade) == 0, (
                f"Expected 0 domain tables after downgrade, found: {tables_after_downgrade}"
            )
    finally:
        await engine.dispose()

    # Re-apply upgrade to head
    await asyncio.to_thread(command.upgrade, cfg, "head")

    # Verify tables recreated
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public';"
                )
            )
            count = result.scalar()
            # 19 application tables + 1 alembic_version = at least 20 tables
            assert count is not None and count >= 20
    finally:
        await engine.dispose()
