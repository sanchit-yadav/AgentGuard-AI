# AgentGuard AI — Backend Service

Autonomous AI Agent Testing & Evaluation Platform Backend, built with FastAPI, SQLAlchemy 2.x (asyncpg), Redis (`redis.asyncio`), Pydantic v2, and Python 3.11+.

## Architecture & Layout

* `app/`: Application package.
* `app/core/`: Configuration, logging, database engine, Redis connection pool, and security foundations.
* `app/models/`: Declarative base models, UUIDv4 mixin, and UTC timestamp audit mixins.
* `app/main.py`: FastAPI entrypoint, lifespan management, and health/readiness endpoints.
* `tests/`: Automated unit and integration test suites.

## Quickstart (Milestone 1.2)

### 1. Set Up Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -e ".[dev]"
```

### 3. Spin Up Infrastructure (PostgreSQL & Redis)

```powershell
docker compose -f ../infrastructure/docker-compose.yml up -d
```

### 4. Run Development Server

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Health & Diagnostics Endpoints

* **Liveness Probe** (Process health, no external dependency check):
  ```powershell
  curl http://localhost:8000/health/live
  ```
* **Readiness Probe** (Verifies PostgreSQL via `SELECT 1` and Redis via `PING`):
  ```powershell
  curl http://localhost:8000/health/ready
  ```

### 6. Run Quality Checks

```powershell
pytest -v
ruff check app tests
ruff format --check app tests
mypy app tests --config-file pyproject.toml
```
