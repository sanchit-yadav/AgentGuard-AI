"""Standalone integration verification script for AgentGuard AI.

Executes direct socket, database, Redis, and health check validations
against live infrastructure services (127.0.0.1:5432 and 127.0.0.1:6379).

Reports exact diagnostic status, timing, and error traces without mocks.
"""

import asyncio
import socket
import time

from fastapi.testclient import TestClient
from redis.asyncio import ConnectionPool, Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import database, redis
from app.core.config import get_settings
from app.main import create_application


def check_tcp_port(host: str, port: int, timeout_sec: float = 2.0) -> tuple[bool, str]:
    """Test raw TCP socket connectivity to the target service."""
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_sec)
    try:
        sock.connect((host, port))
        sock.close()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return True, f"Connected in {elapsed_ms:.1f}ms"
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return False, f"Failed ({type(exc).__name__}: {exc}) in {elapsed_ms:.1f}ms"


async def validate_postgres() -> dict[str, str]:
    """Run end-to-end integration checks against PostgreSQL."""
    settings = get_settings()
    results = {}

    # 1. TCP Port Check
    tcp_ok, tcp_msg = check_tcp_port("127.0.0.1", 5432)
    results["tcp_port_5432"] = tcp_msg
    if not tcp_ok:
        results["status"] = "BLOCKED: PostgreSQL port 5432 is not accepting connections"
        return results

    # 2. Asyncpg Engine & SELECT 1
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT 1"))
            assert res.scalar() == 1
        results["select_1"] = "PASSED: Query returned 1"

        # 3. Transaction Commit & Rollback
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS _val_test (id INT PRIMARY KEY, val TEXT);"
                )
            )
            await conn.execute(text("DELETE FROM _val_test;"))

        # Explicit Commit
        async with session_factory() as session:
            await session.execute(
                text("INSERT INTO _val_test (id, val) VALUES (10, 'verified');")
            )
            await session.commit()

        async with session_factory() as session:
            verify_res = await session.execute(
                text("SELECT val FROM _val_test WHERE id = 10;")
            )
            assert verify_res.scalar() == "verified"
        results["explicit_commit"] = "PASSED: Record persisted across sessions"

        # Explicit Rollback
        async with session_factory() as session:
            await session.execute(
                text("INSERT INTO _val_test (id, val) VALUES (20, 'reverted');")
            )
            await session.rollback()

        async with session_factory() as session:
            verify_res2 = await session.execute(
                text("SELECT val FROM _val_test WHERE id = 20;")
            )
            assert verify_res2.scalar() is None
        results["explicit_rollback"] = "PASSED: Uncommitted write was reverted"

        # Cleanup
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS _val_test;"))

        results["status"] = "HEALTHY: All PostgreSQL checks passed"
    except Exception as exc:
        results["status"] = f"FAILED: {type(exc).__name__}: {exc}"
    finally:
        await engine.dispose()

    return results


async def validate_redis() -> dict[str, str]:
    """Run end-to-end integration checks against Redis."""
    settings = get_settings()
    results = {}

    # 1. TCP Port Check
    tcp_ok, tcp_msg = check_tcp_port("127.0.0.1", 6379)
    results["tcp_port_6379"] = tcp_msg
    if not tcp_ok:
        results["status"] = "BLOCKED: Redis port 6379 is not accepting connections"
        return results

    pool = ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    client = Redis(connection_pool=pool)

    try:
        # PING
        pong = await client.ping()
        assert pong is True
        results["ping_pong"] = "PASSED: Redis responded with PONG"

        # Write, Read, Delete
        await client.set("agentguard:val:test", "active", ex=10)
        val = await client.get("agentguard:val:test")
        assert val == "active"
        await client.delete("agentguard:val:test")
        results["rw_cycle"] = "PASSED: SET, GET, and DEL verified"

        results["status"] = "HEALTHY: All Redis checks passed"
    except Exception as exc:
        results["status"] = f"FAILED: {type(exc).__name__}: {exc}"
    finally:
        await client.aclose()
        await pool.disconnect()

    return results


def validate_fastapi_endpoints() -> dict[str, str]:
    """Verify live behavior of /health/live and /health/ready without mocks."""
    results = {}
    database._engine = None
    database._session_factory = None
    redis._redis_pool = None

    app = create_application()
    with TestClient(app) as client:
        # /health/live
        live_res = client.get("/health/live")
        results["health_live"] = f"Status {live_res.status_code}: {live_res.json()}"

        # /health/ready
        ready_res = client.get("/health/ready")
        results["health_ready"] = f"Status {ready_res.status_code}: {ready_res.json()}"

    return results


async def main() -> None:
    print("=" * 70)
    print("AgentGuard AI — Milestone 1.2 Infrastructure Integration Validator")
    print("=" * 70)

    print("\n[1/3] Validating PostgreSQL (127.0.0.1:5432)...")
    pg_results = await validate_postgres()
    for k, v in pg_results.items():
        print(f"  - {k}: {v}")

    print("\n[2/3] Validating Redis (127.0.0.1:6379)...")
    redis_results = await validate_redis()
    for k, v in redis_results.items():
        print(f"  - {k}: {v}")

    print("\n[3/3] Validating FastAPI Application Endpoints (No Mocks)...")
    api_results = validate_fastapi_endpoints()
    for k, v in api_results.items():
        print(f"  - {k}: {v}")

    print("\n" + "=" * 70)
    print("Infrastructure Validation Summary Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
