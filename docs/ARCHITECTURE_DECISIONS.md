# ARCHITECTURE DECISION RECORDS (ADR)

## 📌 Document Overview
* **Product:** AgentGuard AI — Autonomous AI Agent Testing & Evaluation Platform
* **Format:** Lightweight Architecture Decision Record (ADR) based on Michael Nygard's format
* **Status:** Phase 0 Approved

---

## 📋 ADR Index

| ADR ID | Title | Status | Date |
| :--- | :--- | :--- | :--- |
| **ADR-001** | Modular Monolith vs. Microservices Architecture for MVP | Accepted | 2026-11-02 |
| **ADR-002** | PostgreSQL with JSONB vs. Pure NoSQL Database | Accepted | 2026-11-02 |
| **ADR-003** | Asynchronous Distributed Task Queue (Celery + Redis) | Accepted | 2026-11-02 |
| **ADR-004** | Interception & Mocking Topology for Black-Box HTTP Agents | Accepted | 2026-11-02 |
| **ADR-005** | Cascading Multi-Tier Evaluation: Deterministic Fast-Fail + LLM-as-a-Judge | Accepted | 2026-11-02 |
| **ADR-006** | Egress SSRF Defense via Pre-Flight DNS Pinning & AES-256-GCM Encryption | Accepted | 2026-11-02 |
| **ADR-007** | Frontend Stack: Next.js 14 App Router with TanStack Query & shadcn/ui | Accepted | 2026-11-02 |
| **ADR-008** | Immutable Agent Versioning via Configuration & Tool Snapshots | Accepted | 2026-11-03 |
| **ADR-009** | Scoped Mock Tool Gateway with Ephemeral Capability Tokens | Accepted | 2026-11-03 |

---

## ADR-001: Modular Monolith vs. Microservices Architecture for MVP

### Status: Accepted
### Context
Building a developer platform to test AI agents requires multiple functional subsystems: agent registration, test generation, test execution, trace collection, deterministic evaluation, LLM judging, and dashboard reporting. We must decide whether to structure these components as independent microservices or as a cohesive modular monolith.

### Considered Alternatives
1. **Microservices Architecture:** Separate standalone services for API, Test Runner, Evaluation Engine, and Report Generator, communicating over gRPC or RabbitMQ.
2. **Modular Monolith:** A single FastAPI application repository organized into strictly bounded domain packages (`services/`, `engines/`, `repositories/`, `models/`), sharing a database and running background jobs via workers.

### Decision Outcome
**Chosen Option: Modular Monolith.**
* **Rationale:** Microservices introduce immense operational friction (independent deployments, distributed tracing, network serialization latency, eventual consistency, complex local debugging) without providing value at the MVP stage. A modular monolith enforces clean code boundaries while allowing in-memory method calls, atomic database transactions, and simple single-command development environments. If a specific subsystem (e.g., the execution runner) requires dedicated auto-scaling later, its modular boundary allows easy extraction into a standalone worker or service.

### Consequences
* **Positive:** Rapid feature iteration; zero cross-service RPC overhead; trivial local developer setup with Docker Compose; atomic ACID transactions across entities.
* **Negative:** Scaling requires running the monolith container across multiple nodes (though Celery workers scale independently).

---

## ADR-002: PostgreSQL with JSONB vs. Pure NoSQL Database

### Status: Accepted
### Context
AgentGuard AI manages two distinct data structures:
1. Strict relational data: Organizations, users, permissions, projects, test suites, and regression diffs.
2. Highly dynamic, semi-structured data: Agent tool JSON schemas, conversational message turns, mock environment fixtures, and evaluation metrics.

### Considered Alternatives
1. **Pure NoSQL (MongoDB / DynamoDB):** Store all documents in collections.
2. **Dual-Database Polyglot (PostgreSQL + MongoDB):** Relational data in PostgreSQL; traces and tool calls in MongoDB.
3. **Single PostgreSQL 16 with JSONB:** Relational tables for core entities, with `JSONB` columns for semi-structured payloads.

### Decision Outcome
**Chosen Option: Single PostgreSQL 16 with JSONB.**
* **Rationale:** A dual-database setup adds double the maintenance, backups, and operational cost, and prevents cross-entity transactional integrity. PostgreSQL 16 provides enterprise-grade relational integrity (foreign keys, cascading deletes, unique constraints) alongside world-class `JSONB` support with GIN indexing and binary storage.

### Consequences
* **Positive:** Single database to manage, back up, and monitor; ACID transactions across test runs and executions; fast GIN-indexed JSON queries.
* **Negative:** Complex nested JSON queries require learning PostgreSQL JSON operators (`->`, `->>`, `@>`).

---

## ADR-003: Asynchronous Distributed Task Queue (Celery + Redis)

### Status: Accepted
### Context
Executing an AI agent test suite involves multiple external HTTP calls, model inference latencies (often 2–10 seconds per turn), and multi-turn loops. Running these synchronously inside FastAPI request handlers would block threads, breach HTTP gateway timeouts (typically 30–60s), and degrade platform responsiveness.

### Considered Alternatives
1. **FastAPI BackgroundTasks:** In-process asyncio background tasks.
2. **Redis + Celery:** Distributed task queue with dedicated worker processes.
3. **Async Native Task Queue (ARQ):** Python asyncio-native queue backed by Redis.

### Decision Outcome
**Chosen Option: Redis + Celery.**
* **Rationale:** FastAPI `BackgroundTasks` run inside the web server process; if the web container restarts or crashes, all in-flight test runs are permanently lost with no retry mechanism. Celery provides battle-tested distributed worker processes, task persistence in Redis, configurable worker pools, task revocation, retry policies with exponential backoff, and independent worker scaling.

### Consequences
* **Positive:** Robust fault tolerance; test runs survive web server restarts; independent horizontal scaling of compute workers.
* **Negative:** Requires running Redis and separate Celery worker processes alongside the FastAPI web server.

---

## ADR-004: Interception & Mocking Topology for Black-Box HTTP Agents

### Status: Accepted
### Context
AgentGuard AI must test external AI agents over HTTP without requiring internal access to model weights or proprietary agent codebases. We must intercept tool calls and inject mock data deterministically.

### Considered Alternatives
1. **SDK-Only Instrumentation:** Require users to install an AgentGuard Python/TS library inside their agent codebase.
2. **HTTP Client Protocol Interception:** AgentGuard acts as the client, sending standard conversational prompts (`POST /chat`) and intercepting structured tool call responses (`tool_calls: [...]`), executing synthetic mocks, and returning tool results.
3. **Mock Gateway Proxy:** Expose an HTTP gateway that agents invoke when executing external tools.

### Decision Outcome
**Chosen Option: Hybrid Client Protocol Interception + Mock Gateway Proxy.**
* **Rationale:** Top-tier LLMs (OpenAI, Anthropic, Gemini, Mistral) and modern frameworks (LangChain, LlamaIndex, AutoGen) natively support the turn-based tool-call protocol where the model requests a tool call and the client supplies the output. Supporting this gives zero-friction agent onboarding without requiring code modification. For agents that execute tools internally, our scoped Mock Gateway (`/mock/tools/{execution_id}/{tool_name}`) provides a drop-in synthetic backend.

### Consequences
* **Positive:** Zero code changes required for standards-compliant agents; complete control over mock environment data and latency simulation.
* **Negative:** Agent must expose an HTTP endpoint compatible with standard conversational/tool JSON schemas.

---

## ADR-005: Cascading Multi-Tier Evaluation: Deterministic Fast-Fail + LLM-as-a-Judge

### Status: Accepted
### Context
Evaluating an agent's response on every turn via an LLM judge (such as GPT-4o) introduces significant latency (1–3s) and cost (\$0.01–\$0.05 per test). Furthermore, LLM judges can suffer from non-deterministic grading and prompt injection susceptibility.

### Considered Alternatives
1. **100% Deterministic Testing:** Only check string matches, regexes, and JSON schemas (misses semantic qualities and hallucination).
2. **100% LLM-as-a-Judge:** Send all results to an LLM evaluator (slow, expensive, susceptible to grading drift).
3. **Cascading Multi-Tier Evaluation:** Deterministic checks first; only proceed to LLM judge if structural checks pass.

### Decision Outcome
**Chosen Option: Cascading Multi-Tier Evaluation.**
* **Rationale:** Deterministic evaluators run in microseconds and cost nothing. If an agent fails to call a mandatory tool, passes malformed JSON arguments, or exceeds turn/latency budgets, it is failed immediately. Calibrated LLM-as-a-Judge is reserved exclusively for qualitative dimensions: groundedness (factuality vs. mock data), helpfulness, and prompt injection refusal.

### Consequences
* **Positive:** Minimizes evaluation cost by up to 60–80%; sub-millisecond diagnosis of structural errors; high confidence and reproducibility.
* **Negative:** Requires maintaining two distinct evaluation logic engines.

---

## ADR-006: Outbound Egress Security via DNS-Pinned SSRF Shield & AES-256-GCM Encryption

### Status: Accepted
### Context
Allowing users to connect arbitrary HTTP endpoints introduces severe Server-Side Request Forgery (SSRF) risks against internal databases and cloud metadata services (`169.254.169.254`). Additionally, storing customer agent API credentials poses a data breach risk.

### Considered Alternatives
1. **Naive Regex URL Filtering:** String checks for "localhost" or private IPs (vulnerable to DNS rebinding and decimal IP encodings).
2. **Comprehensive Egress Shield:** Pre-flight DNS resolution, CIDR range verification, DNS socket pinning, disabled redirects, and AES-256-GCM encryption for stored secrets.

### Decision Outcome
**Chosen Option: Comprehensive Egress Shield & AES-256-GCM Encryption.**
* **Rationale:** Naive regex checks fail against sophisticated attacks like DNS Rebinding (TOCTOU). Pinning the socket to the pre-verified IP address guarantees that outbound requests cannot be redirected to internal infrastructure. AES-256-GCM ensures confidentiality and tamper detection for stored credentials.

### Consequences
* **Positive:** Enterprise-grade security posture; complete immunity against cloud metadata theft and private network port probing.
* **Negative:** Slightly higher latency on initial connection due to explicit DNS pre-flight checks (mitigated by DNS caching for validated hosts).

---

## ADR-007: Frontend Stack: Next.js 14 App Router with TanStack Query & shadcn/ui

### Status: Accepted
### Context
The user interface must render complex data: real-time test run progress, multi-turn conversational waterfalls, JSON schema viewers, and regression charts.

### Considered Alternatives
1. **Vite + React SPA:** Client-side single page app.
2. **Next.js 14+ App Router:** Server-side rendered framework with React Server Components, Tailwind CSS, shadcn/ui, and TanStack Query.

### Decision Outcome
**Chosen Option: Next.js 14+ App Router with TanStack Query & shadcn/ui.**
* **Rationale:** Next.js provides excellent initial page load performance, clean nested layouts for workspace context (`/projects/[id]/...`), and first-class TypeScript integration. `shadcn/ui` provides unstyled, accessible Radix UI primitives with full design control via Tailwind CSS. TanStack Query manages asynchronous server state, automatic background polling of running tests, and optimistic UI updates without complex Redux boilerplate.

### Consequences
* **Positive:** Clean enterprise UX; robust polling and cache invalidation; accessible component library.
* **Negative:** Developers must understand React Server Component (RSC) vs Client Component boundaries.

---

## ADR-008: Immutable Agent Versioning via Configuration & Tool Snapshots

### Status: Accepted
### Context
AI agents evolve constantly through prompt engineering, model upgrades, and tool schema additions. If an agent's configuration is modified in-place, past test runs become un-reproducible and audit trails become invalid. We need a versioning mechanism that ensures 100% reproducibility of historical test evaluations.

### Considered Alternatives
1. **Mutable In-Place Updates:** Directly update `agents` and `agent_tools` table records. (Destroys auditability; past test runs cannot be re-verified).
2. **Event Sourcing for Configuration:** Store every keystroke and change as an event log. (High complexity for simple configuration states).
3. **Immutable Snapshot Versioning (`agent_versions` with `tools_snapshot`):** Every test run binds to a frozen version record. Once executed, `is_immutable = true`. Modifying prompt, model parameters, or tool schemas creates a new version record.

### Decision Outcome
**Chosen Option: Immutable Snapshot Versioning (`agent_versions`).**
* **Rationale:** By freezing the system prompt, model configuration, endpoint URL, auth type, and complete tool definitions (`tools_snapshot` JSONB) into an immutable record, any test run can be audited or re-run against the exact agent state that existed when the test was conducted.

### Consequences
* **Positive:** Absolute audit reproducibility; transparent regression diffing between version tags (e.g., `v1.0.0` vs `v1.1.0`); zero risk of retroactive data corruption.
* **Negative:** Requires creating new version records whenever prompts or tools are modified.

---

## ADR-009: Scoped Mock Tool Gateway with Ephemeral Capability Tokens

### Status: Accepted
### Context
When testing autonomous AI agents, agents may execute external tools that mutate real-world systems (e.g., creating a refund on Stripe, dispatching emails, deleting database records). Even in testing, if an agent uses an internal HTTP client rather than client-side tool calling, it could accidentally trigger real side effects if not securely intercepted.

### Considered Alternatives
1. **Require Agent Developers to Write Test Flags:** Require users to implement `if is_test: do_mock()` in their own agent code. (Error-prone; developers forget or leak test flags).
2. **Reverse Proxy Mock Gateway with Ephemeral Tokens:** Provide a scoped mock tool endpoint (`POST /mock-gateway/{execution_id}/tools/{tool_name}`) authenticated by a short-lived HMAC capability token, reading strictly from test case fixtures with zero outbound network egress.

### Decision Outcome
**Chosen Option: Scoped Mock Tool Gateway with Ephemeral Capability Tokens.**
* **Rationale:** Guarantees that agent tool calls hit an isolated, air-gapped test environment. The HMAC capability token restricts access to the lifespan of that specific test execution. Tool allowlists and forbidden operation checks catch unauthorized actions instantly. Zero outbound network egress in the gateway physically prevents accidental production mutations.

### Consequences
* **Positive:** Absolute safety against accidental production side effects; automatic latency simulation and fixture injection; granular trace logging.
* **Negative:** For agents executing tools internally, their tool base URLs must be configured to point to AgentGuard's mock gateway.

---

## ADR-010: Explicit Business Transaction Boundaries vs. Dependency Auto-Commit

### Status: Accepted
### Context
In web frameworks like FastAPI, database sessions are typically provisioned via dependency injection (`get_db()`). An initial approach committed the transaction automatically inside `get_db()` upon return from the route handler. However, this creates several failure modes:
1. Constraint violations or commit failures surface *after* the endpoint handler finishes and serialization begins, often causing 500 Internal Server Errors where a domain-specific 409 Conflict should have been returned.
2. Read-only endpoints (`GET`) incur unnecessary transaction commit overhead and write-ahead log (WAL) synchronization.
3. Multi-repository orchestration within a service cannot cleanly establish a Unit of Work across distributed steps or roll back selectively before triggering compensating actions.

### Considered Alternatives
1. **Implicit Dependency Commit:** `get_db()` executes `await session.commit()` in a post-yield block.
2. **Explicit Transaction Management:** `get_db()` manages session creation and guaranteed closure (`finally: await session.close()`). Domain services explicitly control transactions using `async with session.begin():` or `await session.commit()`.

### Decision Outcome
**Chosen Option: Explicit Transaction Management.**
* **Rationale:** Enforces clean separation of concerns: dependencies manage resource lifecycles (connection acquisition/closure), while domain services manage business transaction boundaries. Commit errors are caught within the business logic where proper domain exceptions and HTTP error mappings can occur. Read endpoints remain zero-overhead.

### Consequences
* **Positive:** Explicit transactional clarity, proper error mapping before response dispatch, zero commit overhead on reads, compatibility with multi-step workflows.
* **Negative:** Mutating service methods must remember to begin/commit transactions explicitly (enforced via unit test fixtures).

---

## ADR-011: Structured Concurrency for Readiness Probes & Isolated Shutdown

### Status: Accepted
### Context
Production deployments on Kubernetes or AWS ECS require independent liveness (`/health/live`) and readiness (`/health/ready`) probes. In Phase 1.2, `/health/ready` sequentially probed PostgreSQL and Redis. If both services were unresponsive, probe latency doubled ($T_{DB} + T_{Redis} \ge 4.0\text{s}$), exceeding standard orchestrator probe timeouts (typically 2-3s). Furthermore, during server shutdown (`lifespan`), sequential disposal without error isolation meant a failure closing the database engine would crash the shutdown sequence and leave Redis connections unclosed.

### Considered Alternatives
1. **Sequential Checks & Linear Shutdown:** Probe DB then Redis sequentially; dispose DB then Redis sequentially. (Vulnerable to timeouts and cascading cleanup failures).
2. **Concurrent Checks & Isolated Shutdown Blocks:** Use `asyncio.gather(..., return_exceptions=True)` to evaluate DB and Redis in parallel, cutting worst-case probe latency to $\max(T_{DB}, T_{Redis})$. Use independent `try/except` blocks during lifespan shutdown so failure to dispose one resource cannot block disposal of the other.

### Decision Outcome
**Chosen Option: Concurrent Checks & Isolated Shutdown Blocks.**
* **Rationale:** Guarantees predictable, bounded probe execution time well within Kubernetes timeout windows. Ensures robust cleanup of all resource pools during SIGTERM/SIGINT events without leaking sockets.

### Consequences
* **Positive:** Halved worst-case readiness latency; resilient, leak-free server shutdown; structured JSON reporting without credential exposure.
* **Negative:** Requires careful handling of parallel coroutine task exceptions.
