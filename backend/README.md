# AgentGuard AI — Backend Service

Autonomous AI Agent Testing & Evaluation Platform Backend, built with FastAPI, SQLAlchemy 2.x (asyncpg), Redis (`redis.asyncio`), Pydantic v2, and Python 3.11+.

## Architecture & Layout

* `app/`: Application package.
* `app/core/`: Configuration, logging, database engine, Redis connection pool, and security foundations.
* `app/models/`: Declarative base models, dual-tier UUIDv4 mixin, and UTC timestamp audit mixins.
* `app/main.py`: FastAPI entrypoint, lifespan management, and concurrent health/readiness endpoints.
* `scripts/`: Operational tools and infrastructure verification scripts.
* `tests/unit/`: Fast, isolated unit test suite (mocked I/O, no running daemon required).
* `tests/integration/`: Infrastructure integration test suite (targets live PostgreSQL and Redis).

## Transaction Management & Domain Service Policy

In accordance with Staff-level engineering standards:
* **Connection Lifecycle vs. Transaction Boundary:** The FastAPI dependency `get_db()` manages session instantiation and guaranteed closure (`finally: await session.close()`). It does **NOT** auto-commit business transactions upon endpoint return.
* **Explicit Mutation Control:** Mutating services must explicitly define transactional boundaries using:
  ```python
  # Idiomatic SQLAlchemy 2.0 block (auto-commits on exit, rolls back on error)
  async with session.begin():
      session.add(entity)
  ```
  or explicit `try: await session.commit() except: await session.rollback(); raise`.
* **Exception Safety:** If an unhandled exception escapes the endpoint, `get_db()` automatically rolls back any active uncommitted transaction to prevent state leakage.
* **Read-Only Efficiency:** Read queries incur zero transaction commit overhead.

## Entity Model Semantics (`base.py`)

* **Dual-Tier UUIDv4:** Models utilize Python-side `default=uuid.uuid4` for instant in-memory ID availability prior to flushing, paired with PostgreSQL-side `server_default=func.gen_random_uuid()` for raw SQL inserts.
* **Immutability:** Primary keys are application-level immutable (domain models provide no setter interfaces). Direct SQL mutations outside the application are not prevented without explicit database triggers.
* **Timestamps:** `created_at` and `updated_at` are timezone-aware UTC. Note that SQLAlchemy's `onupdate` hook executes exclusively inside Python ORM flushes and is not equivalent to a database-level trigger for raw SQL updates.

## Quickstart (Milestone 1.2 Hardened)

### 1. Set Up Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -e ".[dev]"
```

### 3. Spin Up Local Infrastructure (PostgreSQL & Redis)

Services are strictly bound to loopback `127.0.0.1` to prevent LAN exposure:
```powershell
docker compose -f ../infrastructure/docker-compose.yml up -d
```

### 4. Run Development Server

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Health & Diagnostics Endpoints

* **Process Liveness Probe** (Process health, no external dependency check):
  ```powershell
  curl http://localhost:8000/health/live
  ```
* **Concurrent Readiness Probe** (Checks PostgreSQL via `SELECT 1` and Redis via `PING` in parallel):
  ```powershell
  curl http://localhost:8000/health/ready
  ```

### 6. Run Quality Checks & Test Suites

```powershell
# 1. Run unit tests (fast, isolated, 0 external dependencies)
pytest tests/unit -v

# 2. Run live infrastructure integration tests (requires Docker containers running)
pytest tests/integration -v

# 3. Run standalone infrastructure validation report
python scripts/validate_infrastructure.py

# 4. Code quality & type safety
ruff check app tests scripts
ruff format --check app tests scripts
mypy app tests scripts --config-file pyproject.toml
```
