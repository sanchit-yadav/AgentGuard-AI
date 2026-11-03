# AgentGuard AI — Backend Service

Autonomous AI Agent Testing & Evaluation Platform Backend, built with FastAPI, Pydantic v2, and Python 3.11+.

## Architecture & Layout

* `app/`: Application package.
* `app/core/`: Configuration, logging, database, and security foundations.
* `app/main.py`: FastAPI entrypoint and lifespan management.
* `tests/`: Automated unit and integration test suites.

## Quickstart (Milestone 1.1)

### 1. Set Up Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -e ".[dev]"
```

### 3. Run Development Server

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Health Check

```powershell
curl http://localhost:8000/health/live
```

### 5. Run Quality Checks

```powershell
pytest -v
ruff check .
mypy app tests
```
