# DATABASE DESIGN & SCHEMA ARCHITECTURE

## 📌 Document Overview
* **Product:** AgentGuard AI — Autonomous AI Agent Testing & Evaluation Platform
* **Database Engine:** PostgreSQL 16
* **ORM:** SQLAlchemy 2.0 (Async) + Alembic
* **Version:** 1.0 (Phase 0 Baseline)
* **Author:** Principal Database Architect & Backend Lead

---

## 1. Design Principles & Strategy

The AgentGuard AI database schema must address two competing structural requirements:
1. **Strict Relational Integrity:** Organizations, users, projects, agents, test suites, and test runs require absolute referential integrity, ACID transactional guarantees, foreign key cascades, and unique constraints.
2. **Semi-Structured Observability & LLM Data:** External agents, tool schemas, conversational turns, tool call arguments, mock responses, and evaluation metric payloads are inherently dynamic and schema-flexible.

To achieve this without compromising query performance, we leverage **PostgreSQL with JSONB**:
* Core entities, foreign keys, timestamps, statuses, and searchable flags use strongly typed relational columns with B-Tree indexes.
* Tool parameter schemas (JSON Schema), raw agent payloads, dynamic mock fixtures, and arbitrary evaluation breakdown criteria use PostgreSQL `JSONB` columns, paired with GIN indexes where deep querying is required.

---

## 2. Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    organizations ||--o{ organization_members : contains
    users ||--o{ organization_members : joins
    organizations ||--o{ projects : owns
    projects ||--o{ agents : configures
    agents ||--o{ agent_versions : tracks
    agents ||--o{ agent_credentials : secures
    agents ||--o{ agent_tools : defines
    projects ||--o{ test_suites : organizes
    test_suites ||--o{ test_cases : groups
    projects ||--o{ test_runs : executes
    test_runs ||--o{ test_executions : spawns
    test_cases ||--o{ test_executions : evaluated_in
    agent_versions ||--o{ test_runs : tested_by
    test_executions ||--|| execution_traces : records
    execution_traces ||--o{ execution_events : contains
    test_executions ||--o{ evaluations : scored_by
    evaluations ||--o{ evaluation_metrics : details
    test_executions ||--o{ security_findings : discovers
    test_runs ||--o{ regression_results : compares
    test_runs ||--o{ reports : summarized_in

    organizations {
        uuid id PK
        varchar name
        varchar slug UK
        timestamptz created_at
    }

    users {
        uuid id PK
        varchar email UK
        varchar hashed_password
        varchar full_name
        boolean is_active
        timestamptz created_at
    }

    projects {
        uuid id PK
        uuid organization_id FK
        varchar name
        varchar slug
        text description
        timestamptz created_at
    }

    agents {
        uuid id PK
        uuid project_id FK
        varchar name
        text description
        varchar endpoint_url
        varchar status
        timestamptz created_at
    }

    agent_versions {
        uuid id PK
        uuid agent_id FK
        varchar version_tag
        text system_prompt
        jsonb model_config
        timestamptz created_at
    }

    agent_tools {
        uuid id PK
        uuid agent_id FK
        varchar name
        text description
        jsonb parameters_schema
        boolean is_active
    }

    test_suites {
        uuid id PK
        uuid project_id FK
        varchar name
        text description
        timestamptz created_at
    }

    test_cases {
        uuid id PK
        uuid test_suite_id FK
        varchar title
        varchar test_type
        jsonb conversation_turns
        jsonb expected_tool_calls
        jsonb mock_environment_fixtures
        int max_turns
        int timeout_seconds
    }

    test_runs {
        uuid id PK
        uuid project_id FK
        uuid test_suite_id FK
        uuid agent_version_id FK
        varchar status
        int total_tests
        int passed_tests
        int failed_tests
        int duration_ms
        timestamptz started_at
        timestamptz completed_at
    }

    test_executions {
        uuid id PK
        uuid test_run_id FK
        uuid test_case_id FK
        varchar status
        boolean passed
        int duration_ms
        int total_tokens
        numeric estimated_cost_usd
        varchar failure_category
        text failure_summary
    }

    execution_traces {
        uuid id PK
        uuid test_execution_id FK
        uuid trace_id UK
        int turn_count
        timestamptz started_at
        timestamptz ended_at
    }

    execution_events {
        uuid id PK
        uuid execution_trace_id FK
        int event_index
        varchar event_type
        jsonb payload
        int latency_ms
        timestamptz timestamp
    }

    evaluations {
        uuid id PK
        uuid test_execution_id FK
        varchar evaluator_type
        varchar evaluator_name
        boolean passed
        float score
        float confidence
        text reasoning
    }
```

---

## 3. Detailed Entity Specifications

### 3.1 Organization & User Management

#### `organizations`
* **Purpose:** Multi-tenant boundary. All projects, billing, and resources belong to an organization.
* **Columns:**
  * `id`: `UUID` (PK, default `gen_random_uuid()`)
  * `name`: `VARCHAR(255)` NOT NULL
  * `slug`: `VARCHAR(100)` NOT NULL UNIQUE (URL-safe slug for organization routing)
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** `CREATE UNIQUE INDEX ix_organizations_slug ON organizations (slug);`

#### `users`
* **Purpose:** Platform user accounts and authentication profiles.
* **Columns:**
  * `id`: `UUID` (PK)
  * `email`: `VARCHAR(255)` NOT NULL UNIQUE
  * `hashed_password`: `VARCHAR(255)` NOT NULL
  * `full_name`: `VARCHAR(255)` NOT NULL
  * `is_active`: `BOOLEAN` NOT NULL DEFAULT TRUE
  * `is_verified`: `BOOLEAN` NOT NULL DEFAULT FALSE
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** `CREATE UNIQUE INDEX ix_users_email ON users (email);`

#### `organization_members`
* **Purpose:** Associates users with organizations and defines role-based access control (RBAC).
* **Columns:**
  * `id`: `UUID` (PK)
  * `organization_id`: `UUID` NOT NULL REFERENCES `organizations(id)` ON DELETE CASCADE
  * `user_id`: `UUID` NOT NULL REFERENCES `users(id)` ON DELETE CASCADE
  * `role`: `VARCHAR(50)` NOT NULL (e.g., `'OWNER'`, `'ADMIN'`, `'MEMBER'`, `'VIEWER'`)
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** `CREATE UNIQUE INDEX ix_org_members_user ON organization_members (organization_id, user_id);`

---

### 3.2 Project & Agent Entities

#### `projects`
* **Purpose:** Logical workspace containing AI agents, test suites, and execution runs.
* **Columns:**
  * `id`: `UUID` (PK)
  * `organization_id`: `UUID` NOT NULL REFERENCES `organizations(id)` ON DELETE CASCADE
  * `name`: `VARCHAR(255)` NOT NULL
  * `slug`: `VARCHAR(100)` NOT NULL
  * `description`: `TEXT` NULL
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** `CREATE UNIQUE INDEX ix_projects_org_slug ON projects (organization_id, slug);`

#### `agents`
* **Purpose:** Represents a registered target AI agent under test.
* **Columns:**
  * `id`: `UUID` (PK)
  * `project_id`: `UUID` NOT NULL REFERENCES `projects(id)` ON DELETE CASCADE
  * `name`: `VARCHAR(255)` NOT NULL
  * `description`: `TEXT` NULL
  * `endpoint_url`: `VARCHAR(1024)` NOT NULL (HTTP endpoint target)
  * `status`: `VARCHAR(50)` NOT NULL DEFAULT `'HEALTHY'` (`'HEALTHY'`, `'UNREACHABLE'`, `'DISABLED'`)
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** `CREATE INDEX ix_agents_project_id ON agents (project_id);`

#### `agent_credentials`
* **Purpose:** Stores encrypted authentication credentials used when AgentGuard calls the agent.
* **Columns:**
  * `id`: `UUID` (PK)
  * `agent_id`: `UUID` NOT NULL UNIQUE REFERENCES `agents(id)` ON DELETE CASCADE
  * `auth_type`: `VARCHAR(50)` NOT NULL (`'BEARER_TOKEN'`, `'API_KEY_HEADER'`, `'CUSTOM_HEADERS'`, `'NONE'`)
  * `encrypted_payload`: `TEXT` NOT NULL (AES-256-GCM ciphertext containing token or key headers)
  * `key_id`: `VARCHAR(50)` NOT NULL (Identifies the master KMS key used for encryption)
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`

#### `agent_versions`
* **Purpose:** Tracks revisions of agent prompts, model configurations, and tool bindings to support regression testing.
* **Columns:**
  * `id`: `UUID` (PK)
  * `agent_id`: `UUID` NOT NULL REFERENCES `agents(id)` ON DELETE CASCADE
  * `version_tag`: `VARCHAR(50)` NOT NULL (e.g., `'v1.0.0'`, `'gpt-4o-prompt-v2'`)
  * `system_prompt`: `TEXT` NULL
  * `model_config`: `JSONB` NOT NULL DEFAULT '{}'::jsonb (e.g., `{"model": "gpt-4o", "temperature": 0.2}`)
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** `CREATE UNIQUE INDEX ix_agent_versions_tag ON agent_versions (agent_id, version_tag);`

#### `agent_tools`
* **Purpose:** Catalog of tools exposed by the agent, including expected parameter JSON schemas.
* **Columns:**
  * `id`: `UUID` (PK)
  * `agent_id`: `UUID` NOT NULL REFERENCES `agents(id)` ON DELETE CASCADE
  * `name`: `VARCHAR(100)` NOT NULL (e.g., `'create_refund'`, `'get_order_details'`)
  * `description`: `TEXT` NOT NULL
  * `parameters_schema`: `JSONB` NOT NULL (Standard JSON Schema object describing properties and required fields)
  * `is_active`: `BOOLEAN` NOT NULL DEFAULT TRUE
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** 
  * `CREATE UNIQUE INDEX ix_agent_tools_name ON agent_tools (agent_id, name);`
  * `CREATE INDEX ix_agent_tools_schema ON agent_tools USING GIN (parameters_schema);`

---

### 3.3 Test Definition Entities

#### `test_suites`
* **Purpose:** A curated collection of test cases evaluating a specific capability (e.g., "Customer Support Edge Cases", "Prompt Injection Red Team").
* **Columns:**
  * `id`: `UUID` (PK)
  * `project_id`: `UUID` NOT NULL REFERENCES `projects(id)` ON DELETE CASCADE
  * `name`: `VARCHAR(255)` NOT NULL
  * `description`: `TEXT` NULL
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** `CREATE INDEX ix_test_suites_project ON test_suites (project_id);`

#### `test_cases`
* **Purpose:** Individual test scenario containing user prompt turns, expected tool invocations, and synthetic mock fixtures.
* **Columns:**
  * `id`: `UUID` (PK)
  * `test_suite_id`: `UUID` NOT NULL REFERENCES `test_suites(id)` ON DELETE CASCADE
  * `title`: `VARCHAR(255)` NOT NULL
  * `test_type`: `VARCHAR(50)` NOT NULL (`'FUNCTIONAL'`, `'TOOL_VALIDATION'`, `'SECURITY'`, `'RELIABILITY'`, `'PERFORMANCE'`)
  * `conversation_turns`: `JSONB` NOT NULL (Array of dialog turns: `[{"role": "user", "content": "I want a refund for order #101"}]`)
  * `expected_tool_calls`: `JSONB` NOT NULL DEFAULT '[]'::jsonb (Expected tool names, required arguments, and ordering constraints)
  * `mock_environment_fixtures`: `JSONB` NOT NULL DEFAULT '{}'::jsonb (Pre-configured return data for mock tools, e.g., `{"orders": {"101": {"status": "DELIVERED", "total": 45.00}}}`)
  * `max_turns`: `INT` NOT NULL DEFAULT 8
  * `timeout_seconds`: `INT` NOT NULL DEFAULT 45
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `updated_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** 
  * `CREATE INDEX ix_test_cases_suite ON test_cases (test_suite_id);`
  * `CREATE INDEX ix_test_cases_type ON test_cases (test_type);`

---

### 3.4 Test Execution & Tracing Entities

#### `test_runs`
* **Purpose:** Top-level batch execution representing a test suite executed against an agent version.
* **Columns:**
  * `id`: `UUID` (PK)
  * `project_id`: `UUID` NOT NULL REFERENCES `projects(id)` ON DELETE CASCADE
  * `test_suite_id`: `UUID` NOT NULL REFERENCES `test_suites(id)` ON DELETE CASCADE
  * `agent_version_id`: `UUID` NOT NULL REFERENCES `agent_versions(id)` ON DELETE RESTRICT
  * `status`: `VARCHAR(50)` NOT NULL DEFAULT `'PENDING'` (`'PENDING'`, `'RUNNING'`, `'COMPLETED'`, `'FAILED'`, `'CANCELLED'`)
  * `total_tests`: `INT` NOT NULL DEFAULT 0
  * `passed_tests`: `INT` NOT NULL DEFAULT 0
  * `failed_tests`: `INT` NOT NULL DEFAULT 0
  * `duration_ms`: `INT` NULL
  * `started_at`: `TIMESTAMPTZ` NULL
  * `completed_at`: `TIMESTAMPTZ` NULL
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** 
  * `CREATE INDEX ix_test_runs_project ON test_runs (project_id, created_at DESC);`
  * `CREATE INDEX ix_test_runs_suite ON test_runs (test_suite_id);`

#### `test_executions`
* **Purpose:** The execution of a single `test_case` within a `test_run`.
* **Columns:**
  * `id`: `UUID` (PK)
  * `test_run_id`: `UUID` NOT NULL REFERENCES `test_runs(id)` ON DELETE CASCADE
  * `test_case_id`: `UUID` NOT NULL REFERENCES `test_cases(id)` ON DELETE RESTRICT
  * `status`: `VARCHAR(50)` NOT NULL DEFAULT `'PENDING'` (`'PENDING'`, `'RUNNING'`, `'EVALUATING'`, `'COMPLETED'`, `'FAILED'`, `'TIMEOUT'`)
  * `passed`: `BOOLEAN` NULL
  * `duration_ms`: `INT` NULL
  * `total_tokens`: `INT` NOT NULL DEFAULT 0
  * `estimated_cost_usd`: `NUMERIC(10, 6)` NOT NULL DEFAULT 0.000000
  * `failure_category`: `VARCHAR(100)` NULL (`'TOOL_SELECTION_ERROR'`, `'PARAMETER_TYPE_MISMATCH'`, `'HALLUCINATED_CLAIM'`, `'TIMEOUT_OR_LOOP'`, `'SECURITY_VIOLATION'`)
  * `failure_summary`: `TEXT` NULL
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `completed_at`: `TIMESTAMPTZ` NULL
* **Indexes:** 
  * `CREATE INDEX ix_test_executions_run ON test_executions (test_run_id);`
  * `CREATE INDEX ix_test_executions_passed ON test_executions (passed);`
  * `CREATE INDEX ix_test_executions_failure ON test_executions (failure_category) WHERE failure_category IS NOT NULL;`

#### `execution_traces`
* **Purpose:** OpenTelemetry-compatible trace header linking all discrete events for a single test execution.
* **Columns:**
  * `id`: `UUID` (PK)
  * `test_execution_id`: `UUID` NOT NULL UNIQUE REFERENCES `test_executions(id)` ON DELETE CASCADE
  * `trace_id`: `UUID` NOT NULL UNIQUE (W3C standard trace identifier)
  * `turn_count`: `INT` NOT NULL DEFAULT 0
  * `started_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
  * `ended_at`: `TIMESTAMPTZ` NULL
* **Indexes:** `CREATE UNIQUE INDEX ix_execution_traces_trace_id ON execution_traces (trace_id);`

#### `execution_events`
* **Purpose:** Append-only chronological stream of observable events occurring during agent execution.
* **Columns:**
  * `id`: `UUID` (PK)
  * `execution_trace_id`: `UUID` NOT NULL REFERENCES `execution_traces(id)` ON DELETE CASCADE
  * `event_index`: `INT` NOT NULL (0-indexed order of event within trace)
  * `event_type`: `VARCHAR(50)` NOT NULL (`'USER_PROMPT'`, `'AGENT_RAW_RESPONSE'`, `'TOOL_CALL_INVOKED'`, `'MOCK_TOOL_RESULT'`, `'AGENT_ERROR'`, `'EVALUATOR_VERDICT'`)
  * `payload`: `JSONB` NOT NULL (Structured event data: tool name, arguments, raw headers, response tokens)
  * `latency_ms`: `INT` NOT NULL DEFAULT 0
  * `timestamp`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** 
  * `CREATE INDEX ix_execution_events_trace_idx ON execution_events (execution_trace_id, event_index ASC);`
  * `CREATE INDEX ix_execution_events_type ON execution_events (event_type);`
  * `CREATE INDEX ix_execution_events_payload ON execution_events USING GIN (payload);`

---

### 3.5 Evaluation & Findings Entities

#### `evaluations`
* **Purpose:** Graded assessment generated by a specific evaluator for a test execution.
* **Columns:**
  * `id`: `UUID` (PK)
  * `test_execution_id`: `UUID` NOT NULL REFERENCES `test_executions(id)` ON DELETE CASCADE
  * `evaluator_type`: `VARCHAR(50)` NOT NULL (`'DETERMINISTIC'`, `'LLM_JUDGE'`, `'SECURITY'`)
  * `evaluator_name`: `VARCHAR(100)` NOT NULL (e.g., `'tool_schema_validator'`, `'groundedness_judge'`)
  * `passed`: `BOOLEAN` NOT NULL
  * `score`: `FLOAT` NOT NULL (Normalized 0.0 to 1.0)
  * `confidence`: `FLOAT` NOT NULL DEFAULT 1.0
  * `reasoning`: `TEXT` NOT NULL
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
* **Indexes:** 
  * `CREATE INDEX ix_evaluations_execution ON evaluations (test_execution_id);`
  * `CREATE INDEX ix_evaluations_name ON evaluations (evaluator_name);`

#### `evaluation_metrics`
* **Purpose:** Sub-metric scores breakdown supporting the parent evaluation record.
* **Columns:**
  * `id`: `UUID` (PK)
  * `evaluation_id`: `UUID` NOT NULL REFERENCES `evaluations(id)` ON DELETE CASCADE
  * `metric_name`: `VARCHAR(100)` NOT NULL (e.g., `'argument_type_match'`, `'latency_budget'`, `'hallucination_index'`)
  * `score`: `FLOAT` NOT NULL
  * `threshold`: `FLOAT` NOT NULL
  * `passed`: `BOOLEAN` NOT NULL
  * `details`: `JSONB` NOT NULL DEFAULT '{}'::jsonb

#### `security_findings`
* **Purpose:** Explicit vulnerability or prompt-injection compliance flags uncovered during execution.
* **Columns:**
  * `id`: `UUID` (PK)
  * `test_execution_id`: `UUID` NOT NULL REFERENCES `test_executions(id)` ON DELETE CASCADE
  * `severity`: `VARCHAR(50)` NOT NULL (`'CRITICAL'`, `'HIGH'`, `'MEDIUM'`, `'LOW'`, `'INFO'`)
  * `vulnerability_type`: `VARCHAR(100)` NOT NULL (`'DIRECT_PROMPT_INJECTION'`, `'UNAUTHORIZED_TOOL_INVOCATION'`, `'SYSTEM_PROMPT_LEAK'`)
  * `description`: `TEXT` NOT NULL
  * `remediation`: `TEXT` NOT NULL
  * `raw_evidence`: `JSONB` NOT NULL
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`

---

### 3.6 Regression & Reporting Entities

#### `regression_results`
* **Purpose:** Stores delta analysis comparing a base test run against a candidate test run.
* **Columns:**
  * `id`: `UUID` (PK)
  * `base_run_id`: `UUID` NOT NULL REFERENCES `test_runs(id)` ON DELETE CASCADE
  * `candidate_run_id`: `UUID` NOT NULL REFERENCES `test_runs(id)` ON DELETE CASCADE
  * `newly_failed_count`: `INT` NOT NULL DEFAULT 0 (Passed in base, failed in candidate)
  * `newly_passed_count`: `INT` NOT NULL DEFAULT 0 (Failed in base, passed in candidate)
  * `summary`: `JSONB` NOT NULL (Detailed list of test case IDs with changed statuses)
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`

#### `reports`
* **Purpose:** Exportable summaries and quality-gate sign-offs for CI/CD pipelines.
* **Columns:**
  * `id`: `UUID` (PK)
  * `test_run_id`: `UUID` NOT NULL REFERENCES `test_runs(id)` ON DELETE CASCADE
  * `title`: `VARCHAR(255)` NOT NULL
  * `report_format`: `VARCHAR(50)` NOT NULL DEFAULT `'JSON'` (`'JSON'`, `'MARKDOWN'`, `'PDF'`)
  * `content`: `JSONB` NOT NULL
  * `created_at`: `TIMESTAMPTZ` NOT NULL DEFAULT `NOW()`
