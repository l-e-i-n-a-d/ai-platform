# AI Engineering Platform — Architecture

## Status

**Phase:** Architectural scaffold / V1 design

**V1 execution model:** Local-first

**Future execution:** Kubernetes/AKS may be added as an alternative execution backend if justified.

---

## 1. Purpose

The AI Engineering Platform is a shared engineering platform for reliable AI-assisted software development across multiple repositories.

It coordinates:

- Jira work
- Confluence knowledge
- GitHub repositories and pull requests
- context retrieval
- AI agents
- model providers
- engineering tools
- local execution
- verification
- evaluation
- observability

The platform is designed as an engineering harness rather than a single autonomous agent.

---

## 2. V1 Architecture

```text
Developer
    |
    v
Local AI Engineering Platform
    |
    +------------------+------------------+
    |                  |                  |
    v                  v                  v
  Jira             Confluence          GitHub
    |                  |                  |
    +------------------+------------------+
                       |
                       v
                Context Engine
                       |
                       v
                  Graph Engine
                       |
                       v
                 Agent Runtime
                    Python
                       |
                       v
                 Model Gateway
                  /                      Claude Sonnet   GPT
                  \         /
                   \       /
                    v     v
                Local Executor
                       |
                       v
                Local Workspace
                       |
                       v
                    Git / CI
```

Supporting persistence:

```text
Azure Cosmos DB
    -> operational state

Azure Blob Storage
    -> large artifacts

Azure Key Vault
    -> optional future centralized secret management
```

---

## 3. Core Components

### Quarkus Control Plane

Responsible for:

- APIs
- run lifecycle
- durable execution state
- graph lifecycle
- policy enforcement
- human approvals
- integrations
- coordination
- telemetry metadata

It must not become an unrestricted command execution environment.

### Python Agent Runtime

Responsible for constrained agent execution.

Agents have explicit:

- objectives
- instructions
- context
- tools
- policies
- model configuration
- iteration limits
- timeouts
- output contracts

### Graph Engine

Represents workflows as explicit, versioned execution graphs.

Potential capabilities:

- sequence
- branching
- loops
- retries
- checkpoints
- timeouts
- approvals
- recovery
- resumability

Graphs are workflow semantics, not a requirement for a graph database.

### Context Engine

Builds relevant context from:

- Jira
- Confluence
- GitHub
- repositories
- CI
- architecture documentation
- execution history
- evaluations

Context must be relevance-driven and traceable.

### Model Gateway

Provides a provider-neutral model interface.

Initial providers:

- Anthropic Claude / Claude Sonnet
- OpenAI GPT

Provider-specific SDK details remain behind the gateway.

### Tool Layer

Exposes controlled capabilities to agents.

Examples:

- repository search
- file modification
- build
- tests
- Git
- GitHub
- Jira
- Confluence
- CI
- Kubernetes inspection for future deployments

### Local Executor

The V1 execution backend.

It provides controlled local workspaces for repository operations.

The graph and agent layers must depend on an execution abstraction, not directly on local shell behavior.

### Future Kubernetes Executor

A future implementation of the same execution interface.

```text
Graph / Agent
     |
     v
Execution Interface
   /               v               v
Local Executor   Kubernetes Executor
V1               Future
```

Kubernetes-specific concerns must remain inside the Kubernetes executor.

---

## 4. Persistence

Cosmos DB is the operational state store.

Potential data:

- work items
- graph definitions
- graph runs
- nodes
- checkpoints
- agent executions
- tool executions
- model invocations
- approvals
- policies
- evaluation results

Blob Storage is for large artifacts.

Do not introduce PostgreSQL.

---

## 5. External System Boundaries

### Jira

System of record for engineering work.

### Confluence

System of record for product and engineering documentation.

### GitHub

System of record for source code, branches, pull requests and CI.

The platform coordinates these systems; it does not replace them.

---

## 6. Security

V1 is local-first and does not require Microsoft Entra ID.

Security still requires:

- least privilege
- explicit tool capabilities
- repository boundaries
- command restrictions
- secret isolation
- credential protection
- human approvals
- auditability

If the platform becomes a centrally hosted multi-user service, authentication and authorization must be revisited as an explicit architectural decision.

---

## 7. Observability

The architecture is designed to support:

- OpenTelemetry
- Prometheus
- Loki
- Grafana
- Alertmanager

The complete stack is not a V1 deployment requirement.

Correlation identifiers should exist from the beginning:

- request ID
- work item ID
- run ID
- graph ID/version
- node ID
- agent ID
- workspace ID
- model invocation ID
- tool invocation ID

---

## 8. Architectural Constraint

Workflow semantics must remain independent of execution infrastructure.

This allows V1 to remain simple and local while preserving an upgrade path to Kubernetes if future evidence justifies it.
