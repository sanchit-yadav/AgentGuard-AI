# TECHNICAL GLOSSARY & CONCEPTS GUIDE

## 📌 Document Overview
* **Product:** AgentGuard AI — Autonomous AI Agent Testing & Evaluation Platform
* **Purpose:** Educational reference guide for engineers mastering GenAI evaluation, systems architecture, and agent observability.
* **Author:** Staff AI Engineer & Mentor

---

## 1. Autonomous AI Agent Concepts

### Autonomous AI Agent
An AI system powered by one or more Large Language Models (LLMs) that has agency to perceive user goals, formulate multi-step plans, interact with external environments via **tools**, observe the results of those tool executions, and adjust its actions iteratively until a task is completed.
* *Contrast with Chatbot:* A standard chatbot merely produces a textual reply based on input tokens. An agent decides *whether* to execute code, query an external database, or mutate state in the real world.

### Tool / Function Calling
A structured protocol where an LLM is provided with metadata (names, descriptions, parameter schemas) describing functions it can execute. Rather than outputting conversational text, the model generates a structured JSON object specifying the function to call and the arguments to pass.
* *Example in AgentGuard AI:* The customer support agent outputs `{"name": "get_order_details", "arguments": {"order_id": "ORD-123"}}`. The runtime intercepts this, executes the function, and injects the output back into the model's context.

### Non-Determinism
The phenomenon where identical input prompts produce varied outputs across runs. In LLMs, this stems from probabilistic token generation controlled by sampling parameters (temperature, top_p, top_k).
* *Impact on Testing:* Traditional unit tests assert exact output equality (`assert response == "Order shipped"`). In agent testing, non-determinism requires evaluating **semantic intent**, **tool selection validity**, and **parameter conformity** rather than string equivalence.

---

## 2. Evaluation & Observability Concepts

### Deterministic Evaluation
An automated testing check that evaluates system outputs using strict, non-probabilistic code rules (such as JSON schema validation, regex matching, numerical threshold verification, and boolean logic).
* *Characteristics:* 100% reproducible, sub-millisecond execution, zero token cost.
* *Example in AgentGuard AI:* Verifying that `create_refund` was passed an `amount` of type float greater than 0.0, or verifying that the agent completed within 4 turns.

### LLM-as-a-Judge
The practice of using a high-capability Large Language Model (such as GPT-4o, Claude 3.5 Sonnet, or Gemini 1.5 Pro) to evaluate the quality, safety, or accuracy of another model's output based on a structured rubric.
* *Characteristics:* Capable of understanding nuance, tone, and semantic alignment, but introduces its own latency, token cost, and potential evaluation bias.
* *Mitigation in AgentGuard AI:* We use structured JSON outputs, strict few-shot rubrics, and confidence thresholds, reserving LLM judges only for semantic properties that cannot be validated deterministically.

### Groundedness & Hallucination
* **Hallucination:** An assertion made by an LLM that is factually false or unsupported by the provided context.
* **Groundedness:** A metric measuring the degree to which an agent's claims are directly substantiated by the data returned by its tool calls.
* *Example in AgentGuard AI:* If `get_order_details` returns `status: "BACKORDERED"`, but the agent responds *"Great news, your item was delivered this morning!"*, the groundedness score is 0.0, and a hallucination failure is recorded.

### Execution Trace & Span
* **Trace:** The complete, end-to-end chronological record of an agent's execution from initial user prompt to final completion.
* **Span / Event:** A single unit of contiguous work within a trace, such as a model inference call, a tool execution, or a network transit.
* *Standard:* AgentGuard AI models traces after the **OpenTelemetry (OTel)** specification, ensuring interoperability with enterprise observability tools.

### Root Cause Analysis (RCA)
An automated diagnostic process that traverses the execution trace of a failed test to isolate the initial event where system behavior diverged from expectations.
* *Example in AgentGuard AI:* Rather than simply reporting "Test Failed", RCA identifies: *"Failure occurred at Event #2: Agent attempted to invoke `create_refund` with string 'fifty' instead of float 50.0, triggering schema rejection."*

### Regression Testing in GenAI
The process of executing a standardized benchmark suite against new versions of an agent (after modifying system prompts, switching LLM providers, or altering tool schemas) to ensure previously passing capabilities have not broken.

---

## 3. Systems & Security Concepts

### Server-Side Request Forgery (SSRF)
A web security vulnerability where an attacker manipulates a server into making unauthorized HTTP requests to internal resources, loopback interfaces (`127.0.0.1`), or cloud metadata endpoints (`169.254.169.254`).
* *SSRF in AgentGuard AI:* Because users provide external agent URLs, an attacker could supply `http://169.254.169.254/latest/meta-data/` to steal cloud IAM credentials. AgentGuard neutralizes this via DNS pre-flight verification, strict CIDR blacklisting, and socket pinning.

### DNS Rebinding (TOCTOU Attack)
A technique where an attacker's DNS server initially returns a benign public IP address (to pass a validation check), but upon immediate subsequent request returns an internal private IP (`127.0.0.1`).
* *Defense:* AgentGuard pins the resolved IP address to the outbound socket, preventing secondary DNS lookups.

### AES-256-GCM (Authenticated Encryption)
A symmetric block cipher providing both confidentiality and integrity verification. AgentGuard AI uses AES-256-GCM to encrypt agent API tokens at rest, ensuring that tampering or corruption is detected via an authentication tag.

### Modular Monolith
A software architecture style where an entire application is packaged and deployed as a single runtime service, but internally enforces strict boundaries, decoupled domain modules, and clear dependency hierarchies.
* *Why Chosen for AgentGuard AI:* Provides the simplicity, fast developer iteration, and single-process debugging of a monolith, while preserving clean architectural seams that allow individual engines (such as workers or evaluators) to be extracted into microservices if scale demands.
