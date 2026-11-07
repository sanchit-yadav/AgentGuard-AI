# AgentGuard AI — Backend Service

Autonomous AI Agent Testing & Evaluation Platform Backend, built with FastAPI, SQLAlchemy 2.x (asyncpg), Redis (`redis.asyncio`), Pydantic v2, and Python 3.11+.

## Architecture & Layout

* `app/`: Application package.
* `app/core/`: Configuration, logging, database engine, Redis connection pool, and security foundations.
* `app/models/`: Declarative base models, dual-tier UUIDv4 mixin, UTC timestamp audit mixins, and 15 domain models across 7 modules.
* `app/main.py`: FastAPI entrypoint, lifespan management, and concurrent health/readiness endpoints.
* `alembic/`: Alembic database migration environment and migration revisions.
* `scripts/`: Operational tools and infrastructure verification scripts.
* `tests/unit/`: Fast, isolated unit test suite (mocked I/O, no running daemon required).
* `tests/integration/`: Infrastructure integration test suite (targets live PostgreSQL and Redis).

## Domain Entities & Schema Design

AgentGuard AI implements 15 core domain models structured across 7 functional packages (`app/models/`):
1. **Multi-Tenancy & Access Control (`user.py`):** `Organization`, `User`, `OrganizationMember` (with role-based access control and unique tenant memberships).
2. **Project Scoping (`project.py`):** `Project` (scoped to organization with unique URL slugs).
3. **Agent Management (`agent.py`):** `Agent`, `AgentCredential` (1:1 with agent, encrypted payload), `AgentVersion` (immutable configuration snapshots), `AgentTool` (with GIN index on parameters schema).
4. **Test Suite Specification (`test_suite.py`):** `TestSuite`, `TestCase` (rich structured scenarios with turns, ordering constraints, forbidden tools, reference facts, assertions, and mock fixtures).
5. **Test Execution & Batch Runs (`test_run.py`):** `TestRun`, `TestExecution` (execution status, token usage, cost, RCA failure classification with partial index).
6. **Execution Tracing (`trace.py`):** `ExecutionTrace` (OTel-compliant UUIDv4 trace header), `ExecutionEvent` (append-only chronological events with GIN indexing on payload).
7. **Evaluation & Reporting (`evaluation.py`):** `Evaluation` (evaluation metadata and confidence), `EvaluationMetric` (sub-metric breakdown), `SecurityFinding` (vulnerability findings and injection evidence), `RegressionResult` (diffs between candidate and base runs), `Report` (exportable summary).

## Database Migrations (Alembic)

Database schema evolution is managed via Alembic using an asynchronous connection runner:

```powershell
# Apply latest migrations to the database
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback all migrations to empty base
alembic downgrade base

# Generate a new auto-detected migration revision
alembic revision --autogenerate -m "describe_changes"
```

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
ruff check app tests alembic scripts
ruff format --check app tests alembic scripts
mypy app tests alembic scripts --config-file pyproject.toml
```
