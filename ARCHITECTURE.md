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
Local operational store
    -> durable run and workflow state

Local artifact store
    -> large artifacts (transcripts, diffs, logs)
```

V1 persistence is local and requires no cloud account. Azure Cosmos DB and Azure Blob Storage
are the documented target for a future hosted deployment, not V1 components.
See [ADR-0007](docs/decisions/0007-operational-persistence-and-local-first-storage.md).

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

Two invariants define the architecture:

1. All durable state transitions are written by the control plane.
2. All tool invocations pass through the control-plane tool layer.

See [ADR-0004](docs/decisions/0004-control-plane-agent-runtime-boundary.md).

### Python Agent Runtime

Executes exactly **one node attempt** of one agent, then returns. It is stateless and freely
restartable; killing it costs at most one attempt.

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

The runtime holds no durable state, no provider or integration credentials, and no network
egress other than back to the control plane. It receives tool *descriptors*, not
implementations. The control plane validates its output rather than trusting it.

### Graph Engine

Represents workflows as explicit, versioned execution graphs, and is the **sole orchestrator**
— no agent, tool or runtime advances a run.

Capabilities:

- sequence
- branching
- loops
- retries
- checkpoints
- timeouts
- approvals
- recovery
- resumability

Definitions are declarative, immutable and content-addressed; a run pins its definition for
its whole life. The node taxonomy is closed, and edge conditions are a restricted language
over validated structured output. Only the holder of the run lease may transition state, and
each transition is a single atomic write.

Graphs are workflow semantics, not a requirement for a graph database.
See [ADR-0008](docs/decisions/0008-graph-execution-semantics-and-durability.md).

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

The single path through which any side effect occurs, and therefore the platform's
authorization choke point: registry, schema validation, capability-grant authorization, scope
enforcement, approval gating, idempotency, write-ahead intent, dispatch and audit.

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

Capabilities are granted per node attempt and cannot escalate. Models never author commands:
command execution is limited to named, repository-declared command profiles with typed
parameters and no shell.
See [ADR-0005](docs/decisions/0005-tool-contract-and-authorization-choke-point.md).

### Repository Registry

The platform's record of which repositories exist, what they are, and how much authority the
platform may exercise in each: stable identity, trust level, capability ceiling, command
profiles, tool image, network allowlist, context policy and required verification checks.

Registry records are version-controlled configuration in this repository, reviewed like code,
and are **never read from the target repository**. Every layer of the precedence chain may only
narrow capabilities. Repository-resident instruction files are context, not policy.

See [ADR-0014](docs/decisions/0014-repository-registry-and-instruction-precedence.md).

### Local Executor

The V1 execution backend, implementing the execution interface
([ADR-0003](docs/decisions/0003-execution-interface-contract.md)).

Every execution runs in a container: non-root, all capabilities dropped, read-only root
filesystem, explicit environment allowlist, resource limits, and network default-deny. The
workspace container holds no credentials — materialisation and publishing happen outside it
([ADR-0006](docs/decisions/0006-local-execution-isolation-and-credentials.md)).

Workspace state is always a function of `(repoRef, baseSHA, ordered patch series)`, which is
what makes workspaces disposable, resume possible and a remote executor substitutable.

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

All persistence is accessed through a **persistence port**. No component outside the
persistence adapters may reference a storage SDK type.

**V1:** an embedded local operational store (SQLite) and a content-addressed local artifact
store. No cloud account, container runtime or emulator is required.

Operational state:

- work items
- graph definitions
- graph runs
- nodes
- checkpoints
- leases
- agent executions
- tool executions
- model invocations
- approvals
- idempotency records
- policies
- evaluation results

Large artifacts — transcripts, diffs, build and CI logs, reports — are written to the
artifact store and referenced from operational state. Any payload above 100 KB is offloaded.

**Future (hosted deployment):** Azure Cosmos DB and Azure Blob Storage adapters, implemented
when a shared operational store is demonstrably required. That decision is coupled to the
identity decision and must be taken together with it.

See [docs/architecture/persistence.md](docs/architecture/persistence.md) and
[ADR-0007](docs/decisions/0007-operational-persistence-and-local-first-storage.md).

Do not introduce PostgreSQL, and do not introduce another store without an ADR.

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
