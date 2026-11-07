# SYSTEM ARCHITECTURE & TECHNICAL BLUEPRINT

## 📌 Document Overview
* **Product:** AgentGuard AI — Autonomous AI Agent Testing & Evaluation Platform
* **Version:** 1.0 (Architecture Baseline)
* **Status:** Final Architectural Specification
* **Author:** Staff AI Engineer & Principal Systems Architect

---

## 1. High-Level Architecture Overview

AgentGuard AI is designed as an asynchronous, event-driven **Modular Monolith** with decoupled background workers. This topology delivers enterprise-grade scalability and maintainability while avoiding premature microservice operational overhead (such as distributed transactions, network serialization bottlenecks, and complex container orchestration) during the MVP.

### 1.1 Architectural Topology Diagram

```mermaid
flowchart TD
    subgraph ClientLayer["Frontend Client (Next.js 14+ / TypeScript)"]
        UI["Dashboard & Trace Explorer"]
        ReactQuery["TanStack Query (Cache & Polling)"]
        UI --> ReactQuery
    end

    subgraph APILayer["FastAPI Application Gateway (Modular Monolith)"]
        Router["FastAPI Route Handlers (OpenAPI / Async)"]
        AuthMiddleware["Auth & RBAC Middleware"]
        PydanticLayer["Pydantic Validation & Serialization"]
        ServiceLayer["Domain Services (Agents, Suites, Runs)"]
        
        Router --> AuthMiddleware
        AuthMiddleware --> PydanticLayer
        PydanticLayer --> ServiceLayer
    end

    subgraph StorageLayer["Data & Cache Layer"]
        Postgres[(PostgreSQL 16: Relational + JSONB)]
        RedisCache[(Redis: Celery Broker + State Cache)]
    end

    subgraph WorkerPool["Distributed Background Workers (Celery)"]
        TestRunner["Test Execution Worker"]
        EvalWorker["Evaluation Engine Worker"]
        RCAWorker["Root Cause Analysis Worker"]
        GenWorker["Test Generation Worker"]
    end

    subgraph CoreEngines["Core Execution & Evaluation Subsystems"]
        SSRFClient["SSRF-Guarded Egress Client"]
        MockToolGateway["Mock Tool Environment / Interceptor"]
        DeterministicEval["Deterministic Rule Evaluator"]
        LLMJudge["LLM-as-a-Judge Evaluator"]
    end

    subgraph ExternalTargets["External Systems Under Test (SUT)"]
        TargetAgent["Customer Support AI Agent (HTTP API)"]
        LLMProviders["AI Providers (OpenAI / Anthropic / Gemini)"]
    end

    ReactQuery <-->|Async REST API / JSON| Router
    ServiceLayer <-->|SQLAlchemy 2.0 Async| Postgres
    ServiceLayer -->|Task Enqueue| RedisCache
    RedisCache --> WorkerPool

    TestRunner --> SSRFClient
    SSRFClient <-->|Turn-Based HTTP Interception| TargetAgent
    TargetAgent <-->|Tool Execution Callback| MockToolGateway
    
    TestRunner --> Postgres
    TestRunner --> EvalWorker
    EvalWorker --> DeterministicEval
    EvalWorker --> LLMJudge
    LLMJudge --> LLMProviders
    GenWorker --> LLMProviders
    EvalWorker --> RCAWorker
    RCAWorker --> Postgres
```

---

## 2. Core Architectural Subsystems

### 2.1 Frontend Architecture (Next.js 14+ App Router)
* **Framework:** Next.js 14+ with React Server Components (RSC) and Client Components for interactivity.
* **Component Library:** `shadcn/ui` built on Radix UI primitives and styled via Tailwind CSS.
* **State Management:**
  * **Server State:** TanStack Query (`@tanstack/react-query`) handles query caching, background polling of running tests, and optimistic updates.
  * **UI State:** Local React state and lightweight URL query parameters (for shareable filtered trace views).
* **Key Visual Interfaces:**
  * **Agent Registry:** View configured agent endpoints, registered tools, and connectivity status.
  * **Test Studio:** Interactive prompt-based test scenario generator with human-in-the-loop approval workflow.
  * **Live Test Runner:** Real-time polling showing test case execution progress, latency meters, and pass/fail counts.
  * **Trace Explorer:** Turn-by-turn inspector visualizing prompts, raw agent responses, parsed tool calls, mock responses, and evaluator scorecards.
  * **Regression Diff Viewer:** Side-by-side run comparison highlighting test status changes across agent versions.

### 2.2 API Layer (FastAPI Modular Monolith)
* **High Concurrency:** Built on ASGI (`uvicorn`) and `asyncio`, enabling non-blocking I/O when communicating with PostgreSQL and Redis.
* **Schema Validation:** Native Pydantic v2 schemas enforce strict input sanitization, type checking, and automated OpenAPI documentation.
* **Layered Separation:**
  * `api/v1/`: Routing, request unpacking, HTTP status code translation.
  * `services/`: Business logic, domain invariants, workflow orchestration.
  * `repositories/`: Encapsulated database operations using SQLAlchemy 2.0 AsyncSession.
  * `models/`: Declarative ORM models.

### 2.3 Background Task Execution Subsystem (Redis + Celery)
* **Task Queues:**
  * `test_execution_queue`: Handles network-bound conversational turns with external agents.
  * `evaluation_queue`: Runs deterministic validations and dispatches LLM-as-a-Judge queries.
  * `generation_queue`: Asynchronously synthesizes test scenarios from agent tools and instructions.
* **Concurrency Model:** Celery worker processes with `gevent` or `prefork` pools, preventing long-running agent timeouts from blocking internal operations.
* **Task Idempotency:** Each test execution task accepts an `execution_id` and tracks its state (`PENDING`, `RUNNING`, `EVALUATING`, `COMPLETED`, `FAILED`, `TIMEOUT`) in PostgreSQL.

### 2.4 Agent Integration Contract & Mock Tool Gateway

#### 2.4.1 Supported Agent Integration Contract (MVP Specification)
> **Engineering Scope & Boundary:** AgentGuard AI does **not** claim universal compatibility with arbitrary, unstandardized AI agent endpoints. For the MVP, AgentGuard AI strictly supports agents conforming to the **OpenAI-Compatible Turn-Based Tool Protocol** or agents configured to route tool executions through the **AgentGuard Scoped Mock Tool Gateway**.

##### A. Supported Outbound HTTP Request Format
AgentGuard AI dispatches conversational turns to the registered `endpoint_url` using an HTTP `POST` request with a JSON body adhering to the industry-standard chat completions format:
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Where is my order ORD-1042?"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_order_details",
        "description": "Fetch order status, items, carrier, and tracking information.",
        "parameters": {
          "type": "object",
          "properties": {
            "order_id": {
              "type": "string",
              "description": "The unique order identifier"
            }
          },
          "required": ["order_id"]
        }
      }
    }
  ],
  "stream": false,
  "temperature": 0.0
}
```

##### B. Supported Agent Response Format
The agent must return an HTTP `200 OK` with a JSON payload in one of two states:
1. **Tool Invocation Requested (Non-Terminal):**
```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_ord_98765",
      "type": "function",
      "function": {
        "name": "get_order_details",
        "arguments": "{\"order_id\": \"ORD-1042\"}"
      }
    }
  ]
}
```
2. **Terminal Natural Language Response:**
```json
{
  "role": "assistant",
  "content": "Your order ORD-1042 has shipped via FedEx with tracking number TRK987654.",
  "tool_calls": null
}
```

##### C. Tool Call Interception & Result Return
When the agent responds with `tool_calls`:
1. AgentGuard's execution engine pauses model execution and writes an `execution_event` (`TOOL_CALL_INVOKED`) containing the tool name, parsed JSON arguments, and execution timestamp.
2. The arguments are validated against the tool's registered JSON Schema in Tier 1 evaluation.
3. The mock tool engine retrieves the synthetic return fixture configured for this test case.
4. AgentGuard sends the subsequent HTTP `POST` request with the accumulated conversation history and the tool result:
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Where is my order ORD-1042?"
    },
    {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "call_ord_98765",
          "type": "function",
          "function": {
            "name": "get_order_details",
            "arguments": "{\"order_id\": \"ORD-1042\"}"
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_ord_98765",
      "name": "get_order_details",
      "content": "{\"order_id\": \"ORD-1042\", \"status\": \"SHIPPED\", \"carrier\": \"FedEx\", \"tracking_number\": \"TRK987654\"}"
    }
  ],
  "stream": false
}
```

##### D. Internal Tool Execution (Reverse Callback Proxy)
For agents that execute tools internally inside their own service container (rather than asking the client harness to execute them), the agent's external API integration settings must configure its internal tool endpoints to point to AgentGuard's **Scoped Mock Tool Gateway**:
`POST https://agentguard-host/api/v1/mock-gateway/{test_execution_id}/tools/{tool_name}`
When the agent calls this endpoint, AgentGuard validates the execution authorization token, logs the parameters, supplies the synthetic test fixture, and records the interaction in the trace.

##### E. Observability Boundary: What Can vs. Cannot Be Observed in Black-Box HTTP Testing
* **Observable (Captured in Trace):**
  * Exact HTTP request/response payloads, headers, and status codes.
  * Turn-by-turn round-trip latency and network duration.
  * Tool names requested, serialized arguments, and argument formatting errors.
  * Total tokens and prompt/completion token usage (when exposed via `usage` fields or response headers).
* **Unobservable (Private Internal State):**
  * Model internal chain-of-thought or reasoning scratchpads (unless explicitly emitted in public response fields).
  * In-memory agent state, prompt template resolution code, or local variable states.
  * Internal retry loops that occur within the agent service before an HTTP response is emitted.
  * Model weights, logits, or attention activations.

##### F. Future Framework-Specific Adapters (Post-MVP Roadmap)
Post-MVP phases will introduce dedicated adapters:
1. **LangGraph / LangServe Adapter:** Consumes LangGraph state snapshots and node transition events over streaming SSE (`text/event-stream`).
2. **CrewAI / AutoGen Adapter:** Captures multi-agent broadcast chatter and delegation message buses.
3. **AgentGuard Python SDK (`agentguard-sdk`):** Provides an OpenTelemetry-compatible decorator (`@agentguard.trace`) for users desiring white-box, in-process telemetry.

---

#### 2.4.2 Scoped Mock Tool Gateway Architecture
To guarantee that testing autonomous agents will **never** trigger unintended mutations in production (e.g., real Stripe refunds or live database deletions), all tool executions are mediated by the Scoped Mock Tool Gateway:
* **Execution-Specific Authorization:** Every test execution generates a cryptographically signed, short-lived HMAC token (`X-Mock-Execution-Token`). Only requests matching an active `test_execution_id` with a valid token are accepted.
* **Tool Allowlists:** Each test case explicitly registers allowed tools. Calling an undeclared tool returns HTTP 403 Forbidden and flags an immediate `UNAUTHORIZED_TOOL_INVOCATION` security violation.
* **Synthetic Fixtures Scoping:** Tool responses are strictly queried from the isolated `mock_environment_fixtures` JSONB structure defined in the `test_case`.
* **Idempotency & Infinite Loop Protection:** The gateway tracks the invocation count per tool per execution. If a tool call exceeds `max_occurrences` (e.g., repeated identical calls), the gateway terminates the run with a `TIMEOUT_OR_LOOP` fault.
* **Forbidden Operations Interception:** If a test case defines `forbidden_tool_calls` (e.g., `["create_refund"]`), any invocation attempt immediately aborts execution and marks the test as `FAILED`.
* **Zero Real-World Side Effects:** The mock gateway executes strictly in-memory within the test runner process. It contains zero network egress capabilities to live third-party APIs.

---

#### 2.4.3 Immutable Agent Versioning Strategy
To ensure that any historical test run can be audited, reproduced, and verified with 100% fidelity:
* **Immutable Snapshot:** The `agent_versions` entity represents a frozen point-in-time snapshot containing:
  * `system_prompt`: Exact text of the prompt used during the run.
  * `model_config`: Model provider, pinned model identifier (e.g., `gpt-4o-2024-08-06`), temperature, top_p, seeds.
  * `tools_snapshot`: Complete JSONB array of all registered tool schemas, parameter types, and descriptions at that revision.
  * `integration_protocol`: Endpoint URL, auth type, headers, and protocol mode.
  * `evaluation_config`: Default timeout, max turns, and metric thresholds.
* **Copy-on-Write / Version Immutability:** Once a test run has been executed against an `agent_version_id`, that version is permanently locked (`is_immutable = true`). Any subsequent modification to the system prompt, model settings, endpoint URL, or tool schema automatically creates a new `agent_version` record (e.g., `v1.0.1` or `v1.1.0`). Historical test runs remain permanently pinned to their original version snapshot.

### 2.5 Security-Guarded Egress Client (SSRF Shield)
Target agents are hosted on external, customer-controlled URLs. To prevent Server-Side Request Forgery (SSRF):
* Outbound HTTP requests are mediated through a custom `SafeAsyncClient` (wrapping `httpx.AsyncClient`).
* **Pre-Flight DNS Resolution:** Resolves target hostname to IP before socket connection.
* **CIDR Blacklist Verification:** Rejects private IP subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.0/8`), link-local / AWS/GCP metadata (`169.254.169.254`), and IPv6 equivalents.
* **DNS Pinning:** Connects directly to the verified IP with the original Host header to defeat DNS Rebinding (TOCTOU attacks).
* **Strict Timeouts & Payload Caps:** 30s timeout ceiling, 2MB max response payload.

### 2.6 Multi-Tier Evaluation Engine
Evaluations must balance **speed**, **cost**, **reproducibility**, and **semantic nuance**:

```mermaid
flowchart TD
    Trace[Completed Execution Trace] --> Tier1{Tier 1: Deterministic Engine}
    
    Tier1 -->|Schema / Regex / JSON Check| DetTool[Tool Call & Argument Validation]
    Tier1 -->|Sequence Check| DetSeq[Tool Order & Flow Verification]
    Tier1 -->|Budget Check| DetPerf[Turn Count & Latency Thresholds]
    
    DetTool --> Tier1Result[Deterministic Scorecard]
    DetSeq --> Tier1Result
    DetPerf --> Tier1Result
    
    Tier1Result --> CheckHardFail{Any Fatal Rule Broken?}
    CheckHardFail -->|Yes: Immediate Fail| RCA[Root Cause Analysis]
    CheckHardFail -->|No: Proceed| Tier2{Tier 2: Calibrated LLM-as-a-Judge}
    
    Tier2 --> JudgeGrounded[Groundedness & Hallucination vs Mock Data]
    Tier2 --> JudgeTone[Tone, Politeness & Support Policy Alignment]
    Tier2 --> JudgeSecurity[Prompt Injection Refusal Verification]
    
    JudgeGrounded --> FinalAggregation[Consolidated Score & Verdict]
    JudgeTone --> FinalAggregation
    JudgeSecurity --> FinalAggregation
    
    FinalAggregation --> RCA
    RCA --> Report[Persist in Database & Notify Dashboard]
```

* **Deterministic Fast-Fail:** If an agent calls `create_refund` with an invalid parameter type (e.g., negative amount or non-string ID) or invokes a forbidden tool, Tier 1 immediately fails the execution. This avoids expensive LLM evaluation calls for fundamentally broken runs.
* **LLM-as-a-Judge Calibration:**
  * Uses structured JSON outputs (`pass: bool`, `confidence: float [0.0 - 1.0]`, `reason: str`, `evidence: str`).
  * Evaluator prompts include few-shot examples and strict evaluation rubrics to eliminate grader drift.
  * Borderline evaluations (confidence < 0.75) are tagged for optional human verification.

#### 2.6.1 Evaluation Reproducibility & Audit Trail
To ensure evaluation results are legally and technically defensible, reproducible, and verifiable across model iterations:
* **Required Audit Metadata Recorded per Evaluation:**
  * `evaluator_name`: Identifier of the evaluator (e.g., `groundedness_judge`).
  * `evaluator_version`: Semantic code version of the evaluator engine (e.g., `v1.2.0`).
  * `rubric_version`: Pinned version tag of the evaluation rubric and scoring criteria (e.g., `rubric_customer_support_v2.1`).
  * `llm_provider`: Underlying AI provider used for evaluation (e.g., `openai`, `anthropic`, `gemini`).
  * `llm_model`: Explicit, pinned model snapshot identifier (e.g., `gpt-4o-2024-08-06`, **never** an unpinned alias like `gpt-4o`).
  * `generation_parameters`: Explicit sampling settings (e.g., `{"temperature": 0.0, "seed": 42, "max_tokens": 1200}`).
  * `confidence_score`: Float between `0.0` and `1.0` indicating evaluator certainty.
  * `structured_evidence`: Array of verifiable citations linking directly to trace event indices and verbatim text quotes.
  * `execution_latency_ms`: Time taken by the evaluator in milliseconds.
  * `token_usage`: Prompt tokens, completion tokens, and total tokens consumed.
  * `estimated_cost_usd`: Exact dollar cost calculated from provider token pricing.
* **Prohibition on Private Chain-of-Thought Storage:**
  * In compliance with enterprise security and LLM provider terms of service, AgentGuard AI **never** stores private, hidden chain-of-thought tokens from black-box LLMs.
  * Evaluators must produce concise, structured reasoning paragraphs and direct citation evidence instead.

---

### 2.7 Automated Root Cause Analysis (RCA) Engine
When an execution fails, developers need immediate diagnostic clarity. The RCA Engine processes the trace events through a rule-based decision tree:

1. **Parameter Mismatch:** Agent passed arguments violating the registered tool schema.
2. **Missing Tool Call:** Agent answered a factual query without invoking the prerequisite data tool.
3. **Execution Loop / Stalling:** Agent repeated the identical tool call 3+ times with identical arguments.
4. **Hallucination:** Agent made factual assertions (e.g., "Your package has been delivered") directly contradicted by the mock tool response payload.
5. **Security Breach:** Agent executed a tool or exposed instructions in response to a prompt injection attack.

The RCA engine generates a concise diagnostic markdown report with pointers to exact trace event IDs.

---

### 2.8 Multi-Tenant Isolation & Authorization Architecture

AgentGuard AI enforces absolute organization-level data isolation across all API endpoints, repositories, and worker tasks:

```mermaid
flowchart TD
    Request["Incoming API Request"] --> JWT["Verify User JWT & Active Status"]
    JWT --> OrgContext["Resolve Organization Context (organization_members)"]
    OrgContext --> ProjectScope["FastAPI Dependency: verify_project_access(project_id, org_id)"]
    ProjectScope -->|Unauthorized| Reject["Raise HTTP 404 Not Found (Prevent ID Enumeration)"]
    ProjectScope -->|Authorized| Repo["Execute Repository Query with Mandatory (project_id, org_id) Filter"]
    Repo --> DB[("PostgreSQL DB (Tenant-Scoped Data Access)")]
```

#### Multi-Tenant Security Rules
1. **Mandatory Tenant Context:** All projects belong to an `organization_id`. All agents, test suites, test runs, traces, and reports belong to a `project_id`.
2. **FastAPI Authorization Dependencies:** Every route handler requires dependency injection (`get_current_org_context`, `verify_project_access`) verifying that the authenticated user holds an active role (`OWNER`, `ADMIN`, `MEMBER`, or `VIEWER`) in the organization owning the target project.
3. **Defense-in-Depth Query Filtering:** Repositories never execute queries by entity ID alone. All lookups enforce composite tenant criteria:
   ```python
   # Mandatory pattern:
   stmt = (
       select(TestRun)
       .join(Project, TestRun.project_id == Project.id)
       .where(TestRun.id == run_id, Project.organization_id == current_org_id)
   )
   ```
4. **Information Leakage Prevention:** Unauthorized cross-tenant access attempts return HTTP `404 Not Found` (rather than `403 Forbidden`) to prevent malicious actors from enumerating resource UUIDs across tenants.

---

## 3. End-to-End Test Execution Lifecycle

The following sequence diagram details the complete lifecycle from user initiation to dashboard rendering:

```mermaid
sequenceDiagram
    autonumber
    actor User as Developer / QA
    participant Web as Next.js Dashboard
    participant API as FastAPI Gateway
    participant DB as PostgreSQL
    participant Queue as Redis / Celery
    participant Worker as Test Execution Worker
    participant Egress as SSRF-Guarded Client
    participant Agent as External AI Agent (SUT)
    participant Mock as Mock Tool Gateway
    participant Judge as Evaluation Engine

    User->>Web: Click "Run Test Suite"
    Web->>API: POST /api/v1/test-runs (suite_id, agent_version_id)
    API->>DB: INSERT INTO test_runs (status='PENDING')
    API->>DB: INSERT INTO test_executions (one per test_case, status='PENDING')
    API->>Queue: Enqueue execute_test_run(run_id)
    API-->>Web: 202 Accepted (run_id)
    Web-->>User: Display Live Test Progress Screen

    Queue->>Worker: Dispatch execute_test_case(execution_id)
    Worker->>DB: UPDATE test_executions SET status='RUNNING'
    Worker->>DB: INSERT INTO execution_traces (execution_id)

    loop Multi-Turn Interaction (up to max_turns)
        Worker->>Egress: POST agent_endpoint (messages, conversation_history)
        Egress->>Agent: HTTP POST (Validated Safe IP)
        Agent-->>Egress: 200 OK (Assistant message with tool_calls)
        Egress-->>Worker: Return Agent Response Payload
        Worker->>DB: INSERT INTO execution_events (AGENT_MESSAGE, tool_calls)

        alt Agent requests tool invocation
            Worker->>Mock: Validate & Execute Mock Tool (tool_name, arguments)
            Mock->>Mock: Check against Scenario Mock Fixture
            Mock-->>Worker: Return Synthetic Tool Response
            Worker->>DB: INSERT INTO execution_events (TOOL_RESULT, data)
        else Agent returns terminal answer
            Worker->>DB: INSERT INTO execution_events (TERMINAL_OUTPUT)
        end
    end

    Worker->>Queue: Enqueue evaluate_execution(execution_id)
    Worker->>DB: UPDATE test_executions SET status='EVALUATING'

    Queue->>Judge: Run Evaluation Pipeline
    Judge->>Judge: Run Deterministic Validators (Schema, sequence, limits)
    Judge->>Judge: Run LLM-as-a-Judge (Groundedness, Prompt Injection)
    Judge->>Judge: Run Root Cause Analysis (if failed)
    Judge->>DB: INSERT INTO evaluations & evaluation_metrics
    Judge->>DB: UPDATE test_executions SET status='COMPLETED', passed=true/false
    Judge->>DB: UPDATE test_runs (aggregate pass_count, fail_count, status='COMPLETED')

    Web->>API: GET /api/v1/test-runs/{run_id} (Polling / Query)
    API->>DB: Query run, executions, and evaluation summary
    DB-->>API: Return complete Run state
    API-->>Web: 200 OK (JSON)
    Web-->>User: Render Final Results, Trace Waterfall & RCA Diagnoses
```

---

## 4. Backend Module Architecture

The backend repository (`backend/`) follows a clean, layered Modular Monolith structure:

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application factory & lifespan
│   ├── core/                       # Cross-cutting foundational modules
│   │   ├── config.py               # Pydantic Settings (env parsing & validation)
│   │   ├── database.py             # SQLAlchemy AsyncEngine & sessionmaker
│   │   ├── redis.py                # Redis client pool connection
│   │   ├── security.py             # JWT token handling & AES-256-GCM encryption
│   │   ├── exceptions.py           # Domain-specific exception definitions
│   │   └── logging.py              # Structured JSON logging configuration
│   ├── models/                     # SQLAlchemy declarative ORM models
│   │   ├── base.py                 # DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin
│   │   ├── user.py                 # Users, Organizations, OrganizationMembers
│   │   ├── project.py              # Projects
│   │   ├── agent.py                # Agents, AgentVersions, AgentCredentials, AgentTools
│   │   ├── test_suite.py           # TestSuites, TestCases
│   │   ├── test_run.py             # TestRuns, TestExecutions
│   │   ├── trace.py                # ExecutionTraces, ExecutionEvents
│   │   └── evaluation.py           # Evaluations, EvaluationMetrics, SecurityFindings
│   ├── schemas/                    # Pydantic v2 data validation schemas
│   │   ├── common.py               # Pagination, sorting, generic response envelopes
│   │   ├── user.py                 # Auth, signup, user profiles
│   │   ├── agent.py                # Agent registration, tool schemas, credentials
│   │   ├── test_suite.py           # Test suite & test case creation/updates
│   │   ├── test_run.py             # Run triggers, execution status, summaries
│   │   ├── trace.py                # Event streaming, trace waterfall representations
│   │   └── evaluation.py           # Evaluation scores, metric criteria, RCA payloads
│   ├── repositories/               # Encapsulated data access layer (Async CRUD)
│   │   ├── base.py                 # Generic BaseRepository[Model, CreateSchema, UpdateSchema]
│   │   ├── agent_repo.py
│   │   ├── test_suite_repo.py
│   │   ├── test_run_repo.py
│   │   ├── trace_repo.py
│   │   └── evaluation_repo.py
│   ├── services/                   # Core business logic & orchestrations
│   │   ├── agent_service.py        # Agent registration, connectivity verification
│   │   ├── test_suite_service.py   # Suite curation, versioning
│   │   ├── execution_service.py    # Test run dispatching, lifecycle management
│   │   ├── trace_service.py        # Event recording, trace aggregation
│   │   └── report_service.py       # Metrics aggregation, regression comparisons
│   ├── engines/                    # Autonomous AI, Execution & Evaluation Engines
│   │   ├── agent_connector/        # Outbound HTTP agent dispatchers & protocol handlers
│   │   │   ├── base.py             # AbstractAgentConnector
│   │   │   ├── http_connector.py   # OpenAI-compatible / Turn-based HTTP client
│   │   │   └── egress_guard.py     # SSRF defense, IP validation & pinning
│   │   ├── mock_tools/             # Synthetic tool execution environment
│   │   │   ├── registry.py         # Mock tool dispatcher
│   │   │   └── customer_support.py # Order, customer, and refund mock fixtures
│   │   ├── test_generator/         # Automated scenario generation
│   │   │   ├── prompt_builder.py   # Edge case, adversarial & schema-driven prompts
│   │   │   └── generator.py        # LLM scenario synthesis engine
│   │   ├── evaluators/             # Multi-tier evaluation subsystem
│   │   │   ├── base.py             # AbstractEvaluator
│   │   │   ├── deterministic.py    # Schema, sequence, regex & latency evaluators
│   │   │   ├── llm_judge.py        # Groundedness, tone, security LLM-as-a-Judge
│   │   │   └── rca_engine.py       # Root Cause Analysis decision trees
│   │   └── ai_providers/           # Unified multi-model LLM abstraction
│   │       ├── base.py             # AbstractLLMClient
│   │       ├── openai_client.py
│   │       ├── gemini_client.py
│   │       └── anthropic_client.py
│   ├── api/                        # HTTP API Presentation Layer
│   │   ├── deps.py                 # FastAPI dependency injection (DB sessions, auth user)
│   │   └── v1/                     # Versioned REST endpoints
│   │       ├── router.py           # Aggregated v1 APIRouter
│   │       ├── auth.py
│   │       ├── projects.py
│   │       ├── agents.py
│   │       ├── test_suites.py
│   │       ├── test_runs.py
│   │       ├── traces.py
│   │       ├── evaluations.py
│   │       └── reports.py
│   └── workers/                    # Celery asynchronous worker tasks
│       ├── celery_app.py           # Celery configuration & Redis broker bindings
│       ├── execution_tasks.py      # Background test suite execution jobs
│       ├── evaluation_tasks.py     # Background evaluation & RCA jobs
│       └── generation_tasks.py     # Background scenario generation jobs
├── alembic/                        # Database migration scripts
│   ├── env.py
│   └── versions/
├── pyproject.toml                  # Project dependencies & build configuration
└── alembic.ini
```

### 2.5 Rationale for Layered Modular Structure
* **Separation of Concerns:** API route handlers never perform raw database queries or make external LLM calls. All business logic lives in `services/` and `engines/`.
* **Testability:** Every evaluator in `engines/evaluators/` can be unit-tested without spinning up a database or HTTP server.
* **Extensibility:** Adding a new evaluation metric (e.g., token-cost efficiency) requires adding a class extending `AbstractEvaluator` without touching existing route code.
* **Worker Reusability:** Celery worker tasks in `workers/` import the exact same domain services used by FastAPI, ensuring absolute consistency in business rules.

### 4.1 Database Infrastructure & Transaction Management Architecture
* **Connection Lifecycle vs. Transaction Boundaries:** The FastAPI dependency `get_db()` manages session instantiation and guaranteed closure (`finally: await session.close()`). It does NOT auto-commit business transactions upon endpoint return.
* **Explicit Mutation Policy:** Mutating services and repositories explicitly control their transactional boundaries using `async with session.begin():` (idiomatic SQLAlchemy 2.0) or explicit `await session.commit()`. This guarantees that database commit failures (such as unique constraint or foreign key violations) surface while still inside business logic, allowing translation to structured HTTP 409/422 responses before headers are committed.
* **Exception Safety:** Unhandled exceptions that escape route handlers trigger an automatic rollback in `get_db()`'s `except Exception:` block prior to session closure.
* **Dual-Tier UUID Generation:** Models inherit from `UUIDPrimaryKeyMixin`, which provides dual generation: Python-side `default=uuid.uuid4` for immediate in-memory ID access prior to flush, and PostgreSQL `server_default=func.gen_random_uuid()` for raw SQL inserts.
* **Timestamp Semantics:** `created_at` and `updated_at` are timezone-aware UTC. SQLAlchemy's `onupdate` hook executes during ORM session flushes and is documented as separate from database-level `BEFORE UPDATE` triggers.
* **Concurrent Diagnostics & Resilient Teardown:**
  * `GET /health/ready` evaluates PostgreSQL (`SELECT 1`) and Redis (`PING`) concurrently via `asyncio.gather(..., return_exceptions=True)`, bounding probe latency to $\max(T_{DB}, T_{Redis})$ and returning HTTP 503 if either dependency fails.
  * Application lifespan shutdown isolates database and Redis pool disposals in independent `try/except` blocks, preventing resource cleanup starvation.

---

## 5. Frontend Navigation & Screen Architecture

```text
/ (Root)
├── /login                          # Authentication & User Onboarding
├── /projects                       # Project Selection & Creation
└── /projects/[projectId]/          # Project Workspace Context
    ├── /dashboard                  # Executive Metrics, Pass Rates, Failure Trends
    ├── /agents                     # Connected Agents List
    │   ├── /new                    # Agent Registration Wizard (Endpoint, Tools, Keys)
    │   └── /[agentId]              # Agent Details, Tools, Health Status, Revisions
    ├── /test-studio                # Automated Test Generator & Scenario Editor
    ├── /test-suites                # Curated Test Suites & Test Cases
    │   └── /[suiteId]              # Suite Editor & Case Inspector
    ├── /runs                       # Test Run History & Execution Queue
    │   └── /[runId]                # Live Run Monitor & Result Summary
    │       └── /executions/[execId]# Deep-Dive Trace Explorer & Event Waterfall
    ├── /regressions                # Version-to-Version Comparative Diff
    └── /settings                   # Organization Members, API Keys, Webhooks
```
