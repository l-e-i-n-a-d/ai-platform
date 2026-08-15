# Kubernetes Integration

**Status:** Future. Not a V1 requirement.

Kubernetes is a possible **second implementation of the execution interface**
([ADR-0003](../decisions/0003-execution-interface-contract.md)), not the V1 execution
environment. V1 executes locally, in containers, on the developer's machine
([ADR-0006](../decisions/0006-local-execution-isolation-and-credentials.md)).

## Conditions for adoption

A Kubernetes executor becomes worth building when it provides demonstrated advantages the
local executor cannot — stronger isolation, resource control, parallel execution, centralized
execution, or workload scheduling. It requires its own ADR.

## Constraints if adopted

- It implements the existing execution interface. Graph, agent and tool semantics do not
  change.
- Kubernetes-specific scheduling, networking, isolation and lifecycle concerns stay inside the
  executor. Kubernetes concepts must never appear in graph definitions, agent logic or the tool
  layer.
- Substitutability depends on V1 respecting the contract rules of ADR-0003: opaque workspace
  IDs, argv arrays, explicit environment allowlists, artifacts as references, no shared
  filesystem assumption, and asynchronous submit/await.
- Security boundaries are enforced by the platform's capability model and the executor's
  isolation, not by trusting agent behaviour. Identity mechanisms are a hosted-phase decision
  and must not be assumed.

Helm would be the packaging mechanism for a hosted deployment.
