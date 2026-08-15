# Control Plane

**Technology:** Java / Quarkus
**Decisions:** [ADR-0004](../decisions/0004-control-plane-agent-runtime-boundary.md),
[ADR-0005](../decisions/0005-tool-contract-and-authorization-choke-point.md),
[ADR-0007](../decisions/0007-operational-persistence-and-local-first-storage.md),
[ADR-0008](../decisions/0008-graph-execution-semantics-and-durability.md)

---

## Responsibilities

- API surface (CLI in V1; UI later)
- work and run lifecycle
- durable state ownership
- graph orchestration
- policy enforcement and authorization
- approvals
- context construction
- model access
- integration contracts
- observability metadata

Contained components: graph engine, context engine, tool layer, model gateway, integrations,
persistence port, execution interface.

---

## Two invariants

1. **All durable state transitions are written by the control plane.** No other component
   writes run state.
2. **All tool invocations pass through the control-plane tool layer.** No component invokes a
   tool by any other path.

Everything else in the architecture is negotiable. These two are not: together they are what
make policy enforcement, audit and durability real rather than advisory.

---

## Boundaries

Agent execution is **not** embedded in the control plane. The Python agent runtime executes one
node attempt at a time and holds no durable state, no credentials and no egress other than back
to the control plane (ADR-0004).

The control plane is not a general command execution environment. Commands reach a workspace
only as named, repository-declared command profiles dispatched through the tool layer and the
execution interface (ADR-0005, ADR-0006).

The control plane does not trust what the agent runtime reports: output is schema-validated,
usage and cost come from the model gateway's records, and side effects are known from the tool
layer's records.
