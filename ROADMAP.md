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
- Quarkus control plane
- Python agent runtime
- model gateway
- basic graph execution
- local executor
- Cosmos DB persistence
- Blob Storage artifact handling
- basic Jira integration
- basic Confluence integration
- basic GitHub integration

Success criterion:

A developer can run a complete small engineering workflow locally.

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

## Phase 3 — Observability

Introduce:

- OpenTelemetry
- Prometheus
- Loki
- Grafana
- Alertmanager

Add:

- metrics
- logs
- traces
- dashboards
- alerts

The platform should already have stable correlation IDs before this phase.

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

Support:

- repository discovery
- repository-specific instructions
- cross-repository changes
- coordinated pull requests
- cross-repository context

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
- centralized secret management
- execution scheduling
- operational ownership

Microsoft Entra ID is intentionally deferred rather than assumed.
