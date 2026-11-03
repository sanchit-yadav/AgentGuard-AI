# PRODUCT REQUIREMENTS DOCUMENT (PRD)

## 📌 Document Overview
* **Product Name:** AgentGuard AI — Autonomous AI Agent Testing & Evaluation Platform
* **Version:** 1.0 (Phase 0 Architecture Foundation)
* **Status:** Approved for Architecture Planning
* **Author:** Senior Software Architect & Staff AI Engineer

---

## 1. Executive Summary & Vision

AI agents are transitioning from prototype chat interfaces to autonomous actors empowered with tool invocation, external API integrations, and database read/write permissions. However, LLM non-determinism, hallucinations, flawed tool selection, parameter type mismatches, and vulnerability to prompt injections introduce unacceptable risks to production deployments.

**AgentGuard AI** is a developer-focused automated testing, evaluation, and observability platform that runs comprehensive test suites against connected AI agents. AgentGuard AI acts as a specialized testing harness: generating edge cases, executing multi-turn dialogs, intercepting and mocking tool calls, validating responses deterministically and semantically, and providing evidence-backed Root Cause Analysis (RCA).

---

## 2. Target Audience & User Personas

| Role | Key Pain Points | Core Platform Use Cases |
| :--- | :--- | :--- |
| **AI/GenAI Engineer** | Wasting hours manually testing edge cases; fear that prompt changes break existing tool calls. | Connect agent endpoint; run automated regression suites on every git push or prompt tweak. |
| **QA / Test Automation Engineer** | Existing testing frameworks (PyTest, Jest) lack capabilities to evaluate probabilistic text and dynamic tool sequences. | Define multi-turn evaluation scenarios; configure deterministic assertions and LLM-as-a-Judge rubrics. |
| **Engineering Leader / Architect** | Lack of visibility into agent error rates, token usage costs, latency spikes, and security vulnerabilities. | Monitor test run pass rates; review Root Cause Analysis reports; enforce pre-deployment quality gates. |

---

## 3. Product Scope: Initial MVP vs. Future Horizons

### 3.1 Initial MVP Scope (Phase 1 – Phase 6)
The MVP targets single-agent, tool-augmented systems. To ground development in a realistic, high-impact enterprise scenario, the MVP provides an end-to-end benchmark against a **Customer Support AI Agent**.

The reference customer support agent possesses three enterprise tools:
1. `get_order_details(order_id: str) -> dict`: Fetches order status, tracking, items, and financial summary.
2. `get_customer_details(customer_id: str) -> dict`: Retrieves customer profile, loyalty tier, and contact information.
3. `create_refund(order_id: str, amount: float) -> dict`: Issues a financial refund against an order.

**Core MVP Capabilities:**
* **Agent Connectivity:** Connect agents exposing standard HTTP JSON interfaces.
* **Mock Tool Environment:** Intercept agent tool requests and return deterministic mock data without hitting live production systems.
* **Execution Tracing:** High-resolution capture of turns, prompt tokens, agent responses, tool calls, arguments, latency, and status codes.
* **Hybrid Evaluation:**
  * Deterministic validators (tool selection, parameter schema validation, execution order, latency thresholds).
  * Calibrated LLM-as-a-Judge (tone, relevance, groundedness/hallucination checks, basic prompt injection resistance).
* **Automated Scenario Generation:** Generate synthetic customer support edge cases from agent tool definitions and behavioral guidelines.
* **Basic Root Cause Analysis (RCA):** Automated failure classification based on trace evidence (e.g., parameter type mismatch vs. model hallucination vs. tool timeout).
* **Developer Dashboard:** Real-time test suite execution view, trace explorer, and version-to-version regression diffs.

### 3.2 Out-of-Scope for Initial MVP
* Arbitrary, unstandardized proprietary agent network protocols (MVP strictly supports OpenAI-compatible turn-based chat completions and Scoped Mock Gateway callbacks).
* Multi-agent conversation swarms (e.g., AutoGen/CrewAI inter-agent chatter evaluation).
* Complex visual UI automation (testing agents through headless browser DOM clicks).
* Autonomous zero-knowledge black-box fuzzing.
* Custom on-premise hardware deployments (MVP targets cloud Docker/Compose).
* Native IDE extensions (VS Code / JetBrains plugins).

---

## 4. User Roles & Permissions (RBAC)

1. **Organization Owner:** Complete administrative control, billing, project creation, and team member management.
2. **Project Admin:** Configures agent endpoints, credentials, encryption keys, and webhook alerts.
3. **Developer / Engineer:** Creates test suites, triggers runs, views traces, approves generated tests, and views RCA reports.
4. **Viewer:** Read-only access to dashboards, test run histories, and evaluation metrics.

---

## 5. Functional Requirements (FR)

### FR-1: Account, Project & Organization Management
* FR-1.1: System shall support email/password authentication with secure session handling (JWT / HTTP-only secure cookies).
* FR-1.2: Users shall be able to create Organizations and invite team members with assigned roles.
* FR-1.3: An Organization can house multiple isolated Projects.
* FR-1.4: Cross-tenant resource access attempts must be rejected with HTTP 404 (preventing resource ID enumeration).

### FR-2: Agent Registration & Immutable Version Management
* FR-2.1: Users shall register an agent by specifying:
  * Agent Name & Description.
  * System Prompt / Behavioral Guidelines.
  * HTTP Endpoint URL (strictly adhering to OpenAI-compatible turn-based chat completions or internal mock callback architecture; universal arbitrary protocol compatibility is not supported).
  * Authentication Type (Bearer Token, API Key header, or None).
  * Tool Definitions (JSON Schema defining tool names, descriptions, and argument schemas).
* FR-2.2: System shall validate agent connectivity via an automated health check probe with SSRF protection. Outbound connection testing will only be enabled after the egress security shield is verified.
* FR-2.3: Agent credentials must be encrypted at rest using AES-256-GCM with unique 12-byte nonces and envelope `key_id` metadata.
* FR-2.4: Egress requests to agent endpoints must pass through dual-stack DNS pre-flight filtering and CIDR blacklisting.
* FR-2.5: Any update to an agent's prompt, model settings, endpoint URL, or tool schema must create a new immutable `agent_version` record to guarantee past test runs remain 100% reproducible.

### FR-3: Automated Test Scenario Generation & Structured Authoring
* FR-3.1: System shall allow developers to upload or input agent tool definitions and prompt guidelines.
* FR-3.2: AI Generation Engine shall synthesize test scenarios across 4 key test archetypes:
  * **Happy Path:** Valid inputs triggering expected tool calls and helpful responses.
  * **Boundary / Invalid Input:** Missing parameters, malformed IDs, unexpected data types.
  * **Adversarial / Security:** Prompt injections attempting to trigger unauthorized refunds or reveal internal prompts.
  * **Tool Failure / Recovery:** Simulated tool errors or timeouts testing agent resilience.
* FR-3.3: Test cases must capture rich structured metadata:
  * `expected_outcome`: Terminal status, terminal role, and behavioral summary.
  * `expected_tool_calls`: Tool names with argument matching specifications (exact, partial, schema).
  * `ordering_constraints`: Strict sequence, dependency DAG, or unordered.
  * `forbidden_tool_calls`: Restricted tools that must not be invoked.
  * `reference_data`: Required factual claims and forbidden hallucinated claims.
  * `deterministic_assertions`: Turn count limits, latency budgets, parameter schema validity.
  * `qualitative_criteria`: Groundedness, tone, and prompt-injection refusal metrics.
* FR-3.4: Test cases must support evaluating both successful completions and deliberate, policy-compliant refusals.

### FR-4: Test Execution Engine & Scoped Mock Tool Gateway
* FR-4.1: Test suites shall be dispatched asynchronously via background worker queues (Redis + Celery).
* FR-4.2: Execution Engine shall execute multi-turn conversations against the agent HTTP endpoint following turn-based tool interception.
* FR-4.3: Mock Tool Gateway shall scope executions via short-lived HMAC tokens, enforce tool allowlists, return synthetic scenario fixtures, and detect infinite retry loops.
* FR-4.4: The mock tool gateway must execute strictly in memory with zero outbound network calls, preventing accidental production side effects.
* FR-4.5: System shall enforce execution budgets: maximum turn limit (e.g., 10 turns) and timeout ceiling (e.g., 45 seconds per test case).

### FR-5: Execution Tracing & Observability
* FR-5.1: Every test execution must generate a unique `execution_id` and OpenTelemetry-compatible `trace_id`.
* FR-5.2: Trace collection shall record discrete chronologically ordered `execution_events`:
  * Prompt sent to agent.
  * Agent raw response received.
  * Tool call requested (tool name, parsed arguments, raw payload).
  * Mock tool execution response (returned data, simulated latency, mock status).
  * Evaluator judgments.
* FR-5.3: Traces must capture token usage (input tokens, output tokens) and wall-clock latency per turn.
* FR-5.4: Centralized sanitizers must scrub credentials from traces and application logs before persistence.

### FR-6: Multi-Tier Evaluation Engine & Reproducibility Audit Trail
* FR-6.1: **Tier 1 (Deterministic Evaluators):**
  * Exact tool selection match (did the agent call `get_order_details` when asked for order status?).
  * Argument schema validation (did the agent pass `{"order_id": "ORD-123"}` conforming to JSON Schema?).
  * Sequence validation (was `get_customer_details` invoked before `create_refund`?).
  * Forbidden tool invocation check (did the agent invoke `create_refund` without user confirmation?).
  * Latency and turn count limit checks.
* FR-6.2: **Tier 2 (LLM-as-a-Judge Semantic Evaluators):**
  * Groundedness / Hallucination: Are assertions made in the agent's text response strictly supported by mock tool data?
  * Helpfulness & Tone: Is the response polite, accurate, and aligned with support guidelines?
  * Prompt Injection Defense: Did the agent refuse malicious user instructions?
* FR-6.3: **Audit Trail & Reproducibility Metadata:**
  * Every evaluation must store evaluator code version, rubric version, pinned LLM model snapshot (e.g., `gpt-4o-2024-08-06`), temperature (0.0), seed (42), confidence score, structured event citations, latency, token usage, and calculated API cost.
  * Storing private black-box model chain-of-thought tokens is strictly prohibited; evaluators store concise structured explanations and observable evidence instead.

### FR-7: Root Cause Analysis (RCA) Engine
* FR-7.1: For any failing test execution, the RCA engine shall inspect trace events and assign a primary failure category:
  * `TOOL_SELECTION_ERROR`: Agent called wrong tool or omitted a required tool.
  * `PARAMETER_TYPE_MISMATCH`: Argument failed schema validation.
  * `HALLUCINATED_CLAIM`: Agent output factual claims not in tool output.
  * `TIMEOUT_OR_LOOP`: Agent repeated calls or exceeded latency threshold.
  * `SECURITY_VIOLATION`: Agent obeyed an injection prompt.
* FR-7.2: RCA engine shall provide an evidence-backed summary with direct references to trace event indices and recommendations.

### FR-8: Dashboard, Trace Explorer & Regression Comparison
* FR-8.1: Test run overview showing pass rate, execution duration, total cost estimate, and failure breakdown.
* FR-8.2: Trace Explorer visualizing step-by-step chat turns, tool parameters, raw JSON payloads, and evaluator verdicts.
* FR-8.3: Regression view comparing Run A (Agent v1.0) vs. Run B (Agent v1.1), highlighting tests that flipped from Pass to Fail.

---

## 6. Non-Functional Requirements (NFR)

* **NFR-1 (Performance & Scalability):** The backend must handle concurrent test executions across worker nodes without blocking API responsiveness. Background worker scaling must allow running a 50-test suite within < 3 minutes (assuming average external agent response time of 2s).
* **NFR-2 (Reliability & Fault Tolerance):** Worker failures or target agent crashes must not corrupt the test run state. Any failed worker job must be captured, marked with `CRASHED` or `TIMEOUT`, and recorded with traceback evidence.
* **NFR-3 (Data Integrity):** Relational integrity must be enforced via foreign keys with cascading rules. Test trace events must be stored in append-only logs in PostgreSQL using JSONB.
* **NFR-4 (Security & Confidentiality):**
  * Stored agent tokens must never be sent back in plaintext to the frontend.
  * All outbound HTTP traffic must reject loopback, link-local, and private RFC 1918 subnets (preventing SSRF).
  * System must sanitize sensitive credentials before writing to trace logs.
* **NFR-5 (Observability):** Structured JSON logs across all backend services containing `trace_id`, `project_id`, and `agent_id`.

---

## 7. Success Criteria & KPIs for MVP

1. **Successful Customer Support Benchmark:** Execute a complete 25-test suite against the reference Customer Support Agent measuring tool accuracy, argument validity, and refund security.
2. **Trace Completeness:** 100% of tool calls and conversational turns successfully indexed, displayed in the UI, and linked to evaluation metrics.
3. **RCA Precision:** Root Cause Analysis accurately categorizes intentional agent faults (e.g., parameter mismatch, prompt injection compliance) in synthetic test runs.
4. **Developer Usability:** A new developer can register an agent, approve tests, and inspect execution results in under 5 minutes.
