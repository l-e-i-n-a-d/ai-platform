# AI Engineering Platform — Roadmap

## Phase 0 — Scaffold

**Status: Current**

Goals:

- establish architecture
- establish principles
- establish security guidance
- establish evaluation strategy
- establish terminology
- establish ADR process

No production implementation is required.

---

## Phase 1 — Local Platform Foundation

Goals:

- local developer startup
- **CLI entry surface** (see ADR-0018)
- Quarkus control plane
- Python agent runtime
- model gateway
- basic graph execution
- local executor
- local persistence (see ADR-0007)
- local artifact storage
- repository registry and capability ceilings (see ADR-0014)
- context bundles with budgets, pinning and provenance (see ADR-0013)
- OpenTelemetry instrumentation, trace propagation and structured logs (see ADR-0015)
- basic Jira integration
- basic Confluence integration
- basic GitHub integration

Success criterion:

A developer can run a complete small engineering workflow locally, and reach a first successful
run within thirty minutes of cloning the repository.

Example:

```text
Jira issue
 -> context
 -> plan
 -> human approval
 -> local code change
 -> tests
 -> Git branch
 -> GitHub PR
```

---

## Phase 2 — Durable Engineering Loops

Goals:

- checkpoints
- retries
- repair loops
- resumability
- cancellation
- deterministic verification
- structured agent outputs
- stronger tool policies

---

## Phase 3 — Observability Backends

Instrumentation already exists from Phase 1 (see ADR-0015): OpenTelemetry API spans, metrics and
structured logs, W3C trace context propagation across CLI, control plane, agent runtime and
executor, and `traceId`/`spanId` on every persisted document.

This phase deploys the stack that consumes it:

- OpenTelemetry Collector
- Prometheus
- Loki
- Grafana
- Alertmanager

Add:

- dashboards
- alerts, starting with the security signals (`platform_tool_denied_total`,
  `platform_egress_denied_total`)
- retention policies

Because business logic depends only on the OpenTelemetry API and exports OTLP to a collector,
this phase is configuration rather than code change.

---

## Phase 4 — Evaluation Platform

Build repeatable evaluations for:

- models
- agents
- graphs
- tools
- context strategies
- end-to-end engineering tasks

Track:

- correctness
- success rate
- recovery
- latency
- cost
- security

---

## Phase 5 — Multi-Repository Workflows

Repository identity, registration, capability ceilings and repository-scoped context are
delivered in Phase 1 (ADR-0014). This phase adds only the coordination problems:

- cross-repository changes
- coordinated pull requests
- cross-repository context
- repository discovery as a proposal mechanism

---

## Phase 6 — Optional Kubernetes Execution

Only pursue this phase if local execution reveals a concrete need.

Potential reasons:

- stronger isolation
- resource limits
- parallel execution
- reproducibility
- centralized execution
- scale

Kubernetes should implement the existing execution interface rather than changing graph or agent semantics.

---

## Phase 7 — Shared Hosted Platform

Only if required by the organization.

At this point revisit:

- authentication
- authorization
- multi-user tenancy
- shared operational persistence (Cosmos DB / Blob Storage adapters)
- centralized secret management
- execution scheduling
- operational ownership

Microsoft Entra ID is intentionally deferred rather than assumed.

Shared persistence and centralized identity must be decided together: a shared operational
store without identity-bound access reintroduces the problem ADR-0007 was written to remove.
