# AGENTS.md — Development Guidelines for AI Coding Agents

> **Project:** AgentGuard AI — Autonomous AI Agent Testing & Evaluation Platform  
> **Audience:** All AI coding assistants, agents, and engineers contributing to this repository.  
> **Core Principle:** Build with production-grade engineering discipline. Teach the developer through clear explanations, rationale, and rigorous real implementations.

---

## 🏛️ 1. Core Engineering Philosophy

The developer working on this project is leveling up to become a **Staff AI/ML and GenAI Systems Engineer**. 

Your goal as an AI assistant is **not** to spew raw code blindly or take shortcuts. You must ensure the developer deeply understands:
1. **Why** every architectural component exists and what problem it solves.
2. **How** data flows across the system boundary (from user click to worker to agent endpoint and back).
3. **What trade-offs** governed technology and pattern choices.
4. **What failure modes** exist in distributed systems, asynchronous queues, and probabilistic LLMs.
5. **How to articulate** these decisions with clarity and depth in top-tier technical interviews.

---

## 🚫 2. Absolute Prohibitions (Zero Tolerance)

1. **NO FAKE FUNCTIONALITY OR MOCK STUBS IN PRODUCTION CODE:**
   * Never return hardcoded mock responses (e.g., `return {"status": "success", "score": 0.95}`) where real execution, network calls, or LLM evaluation is expected.
   * If a subsystem is not yet implemented, raise an explicit `NotImplementedError` or return a structured HTTP 501 / error status explaining what is required.
2. **NO UNVERIFIED CLAIMS:**
   * Never claim a test passed or a server ran without actually executing it and inspecting the command output.
   * If a test fails, report the exact stack trace and fix the root cause. Never edit a test to make it pass artificially.
3. **NO BULK/MONOLITHIC GENERATION:**
   * Never attempt to build the entire backend or frontend in a single step. Implement modules incrementally, verify each, and ensure tests pass before moving on.
4. **NO HARDCODED SECRETS:**
   * Never commit or embed API keys, secrets, database passwords, or JWT secrets in code or git history. Always fetch via environment variables and Pydantic Settings.
5. **NO ARBITRARY CODE EXECUTION:**
   * Never run un-sandboxed customer code directly inside the host process. Target agent tools must be invoked through isolated mock engines or restricted HTTP proxies.

---

## 📜 3. The 20 Mandatory Development Rules

Every agent working on this codebase must strictly adhere to the following 20 rules:

1. **Never implement the entire application in one go.** Proceed phase-by-phase, module-by-module.
2. **Work incrementally, one module at a time.** Deliver complete, verifiable slices of functionality.
3. **Explain the purpose of major modules before implementing them.** State the business requirement, design pattern, and interfaces first.
4. **Never create fake functionality or placeholder success responses.** Build the genuine logic or keep the scope focused.
5. **Never hardcode API keys or credentials.** Always use configuration files backed by environment variables.
6. **Use environment variables and maintain `.env.example`.** If a new variable is introduced, immediately document it in `.env.example`.
7. **Follow clean architecture and separation of concerns.** API route handlers must not contain raw SQL or business logic; business services must not depend on HTTP request objects.
8. **Use type hints and Pydantic validation everywhere.** All Python functions must have explicit parameter and return type hints; all I/O must have strict Pydantic schemas.
9. **Include meaningful, actionable error handling.** Wrap network and external LLM calls with clear domain exceptions (`AgentConnectionError`, `EvaluationParseError`).
10. **Write unit tests for important business logic.** Test deterministic evaluators, mock proxies, schema validators, and scoring algorithms with 100% logic coverage.
11. **Write integration tests for API and database interactions.** Use test databases and verify async sessions, foreign key constraints, and rollback behaviors.
12. **Never claim a test passed without actually running it.** Inspect stdout/stderr and exit codes directly.
13. **Never silently ignore failed tests.** A failing test indicates a regression or a flawed assumption; address it immediately.
14. **Maintain database migrations.** Never alter database models without creating and validating an Alembic migration script.
15. **Update documentation when architecture changes.** Keep `SYSTEM_ARCHITECTURE.md`, `API_DESIGN.md`, and `DATABASE_DESIGN.md` in sync with codebase reality.
16. **Avoid unnecessary dependencies.** Evaluate every external library for maintenance activity, security footprint, and license compatibility before adding it to `pyproject.toml` or `package.json`.
17. **Consider security before implementing external integrations.** Protect against SSRF, credential leakage, injection, and multi-tenant crossover at the design stage.
18. **Do not execute untrusted code without isolation.** Mock tools and agent proxies must be strictly sandboxed.
19. **Preserve backward compatibility where practical.** Database migrations should be additive; API changes should avoid breaking existing clients without versioning.
20. **Explain major implementation decisions in understandable language.** Help the developer master the system, understand edge cases, and articulate solutions confidently.

---

## 🏗️ 4. Code Architecture & Conventions

### Backend (Python / FastAPI)
* **Directory Pattern:** Layered Modular Architecture (`api/` -> `services/` -> `repositories/` -> `models/`).
* **Async by Default:** Use async database drivers (`asyncpg`), async HTTP clients (`httpx.AsyncClient`), and async FastAPI handlers for non-blocking I/O.
* **SQLAlchemy 2.0 Style:** Use `select()`, `insert()`, `update()` with `AsyncSession`. Do not use legacy 1.x query syntax (`db.session.query()`).
* **Pydantic v2:** Use `model_config = ConfigDict(...)` and `field_validator`. Separate `Create`, `Update`, `Response`, and `InDB` schemas.
* **Logging:** Use structured logging (JSON or standard loggers with `extra={"trace_id": ..., "agent_id": ...}`). Never use bare `print()`.

### Frontend (Next.js / TypeScript)
* **App Router:** Use Next.js 14+ App Router structure (`app/(dashboard)/...`).
* **Strict TypeScript:** Enable `strict: true`. No `any` types unless interfacing with un-typed external payloads, and even then prefer `unknown` with type guards.
* **Component Design:** Use Tailwind CSS with `shadcn/ui` primitives. Separate pure presentational components from container/data-fetching components.
* **State Management:** TanStack Query (`@tanstack/react-query`) for server state, server actions for mutations where applicable, and lightweight React hooks for UI state.

---

## 🔒 5. Security & SSRF Safeguards

AgentGuard AI initiates outbound HTTP connections to user-specified agent endpoints. To prevent SSRF attacks against internal infrastructure or cloud metadata services:
* All target URLs must be validated before request dispatching.
* IP addresses resolved by DNS must be verified against blocked CIDR blocks (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1`, `fc00::/7`, `fe80::/10`).
* DNS pinning must be used to eliminate Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding vulnerabilities.
* Agent API credentials (Bearer tokens, API keys) must be encrypted at rest using AES-256-GCM.

---

## 🧪 6. Testing Protocol

Before marking any task or phase complete:
1. Run backend linter/type-checker: `ruff check .` and `mypy .`
2. Run backend test suite: `pytest -v tests/`
3. Run frontend type-checker and build: `pnpm tsc --noEmit` and `pnpm build`
4. Confirm zero regressions across previously passing test suites.
