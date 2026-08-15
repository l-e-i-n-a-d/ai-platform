# AI Engineering Platform — Principles

## 1. Local First

Every developer should be able to run the platform locally.

V1 must not require Kubernetes, AKS, a shared execution cluster or Microsoft Entra ID.

Local-first is not an excuse for weaker architecture. Workflow semantics stay independent of the
execution environment, no storage SDK type crosses the persistence port, and security
requirements are unchanged — removing central identity removes an *assurance mechanism*, not a
*requirement*, and every control affected states its honest limits rather than overclaiming.

See [ADR-0001](docs/decisions/0001-local-first-v1-execution-model.md) and
[ADR-0002](docs/decisions/0002-deferral-of-entra-id.md).

## 2. Execution Independence

Graphs and agents must not depend on a particular execution environment.

Execution is an abstraction:

```text
Execution Interface
    |
    +-- Local Executor
    |
    +-- Future Kubernetes Executor
```

## 3. Reliability Before Autonomy

A smaller reliable workflow is preferable to a highly autonomous but unpredictable agent.

Prioritize:

- deterministic verification
- checkpoints
- retries
- resumability
- observability
- human approval

## 4. Explicit Workflow Semantics

Complex workflows belong in graphs, not hidden inside prompts.

## 5. Provider Neutrality

Models are replaceable infrastructure.

Do not make the platform dependent on Claude or GPT-specific concepts.

## 6. Least Privilege

Agents receive only the capabilities required for their current task.

## 7. Human Control

Consequential actions may require human approval.

## 8. Evidence Over Assumptions

Do not add infrastructure because it is fashionable or common.

Add it when a demonstrated requirement justifies it.

## 9. System-of-Record Respect

Jira owns work.

Confluence owns product and engineering knowledge.

GitHub owns source and CI.

The AI platform coordinates these systems rather than replacing them.

## 10. Observable by Design

Every meaningful operation should eventually be traceable.

The platform should be compatible with OpenTelemetry, Prometheus, Loki, Grafana and Alertmanager.

## 11. Evaluate the Harness

Evaluate not only models but also:

- context
- tools
- graphs
- agents
- execution
- recovery
- cost
- latency

## 12. Incremental Architecture

Do not implement future phases prematurely.

V1 should prove useful local workflows before adding distributed infrastructure.
