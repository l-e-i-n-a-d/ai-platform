# Architecture Decision Records

Use ADRs for decisions that affect multiple components, infrastructure, system-of-record boundaries, security, interfaces or major technology choices.

Naming:

`0001-short-title.md`

Statuses:

- Proposed
- Accepted
- Superseded
- Rejected

Template:

```markdown
# ADR-XXXX: Title

## Status
Proposed

## Context

## Decision

## Alternatives

## Consequences

## Security / Operational Impact

## Follow-up
```

---

## Index

Numbering follows the planned decision set below, not creation order. All eighteen decisions
identified by the 2026-08-15 architecture review are now recorded.

| # | Title | Status |
|---|---|---|
| 0001 | [Local-first V1 execution model](0001-local-first-v1-execution-model.md) | **Accepted** |
| 0002 | [Deferral of Microsoft Entra ID](0002-deferral-of-entra-id.md) | **Accepted** |
| 0003 | [Execution interface contract and executor substitutability](0003-execution-interface-contract.md) | **Accepted** |
| 0004 | [Control plane / agent runtime boundary and protocol](0004-control-plane-agent-runtime-boundary.md) | **Accepted** |
| 0005 | [Tool contract, capability grants and authorization choke point](0005-tool-contract-and-authorization-choke-point.md) | **Accepted** |
| 0006 | [Local execution isolation and credential handling](0006-local-execution-isolation-and-credentials.md) | **Accepted** |
| 0007 | [Operational persistence and local-first storage](0007-operational-persistence-and-local-first-storage.md) | **Accepted** |
| 0008 | [Graph execution semantics, versioning and durability](0008-graph-execution-semantics-and-durability.md) | **Accepted** |
| 0009 | [Human approval model and authorization without central identity](0009-human-approval-model.md) | **Accepted** |
| 0010 | [Model gateway interface and provider neutrality](0010-model-gateway-interface.md) | **Accepted** |
| 0011 | [Model credentials, cost control and egress redaction](0011-model-credentials-cost-and-egress-redaction.md) | **Accepted** |
| 0012 | [GitHub actor identity and write-back semantics](0012-github-actor-identity-and-write-back.md) | **Accepted** |
| 0013 | [Context bundle contract, budgets and provenance](0013-context-bundle-contract.md) | **Accepted** |
| 0014 | [Repository registry and instruction precedence](0014-repository-registry-and-instruction-precedence.md) | **Accepted** |
| 0015 | [Telemetry contracts, correlation and collection model](0015-telemetry-contracts-and-collection-model.md) | **Accepted** |
| 0016 | [Audit model and attribution limits without central identity](0016-audit-model-and-attribution-limits.md) | **Accepted** |
| 0017 | [Artifact classification, retention and redaction](0017-artifact-classification-retention-and-redaction.md) | **Accepted** |
| 0018 | [Developer entry surface: CLI in V1, UI deferred](0018-developer-entry-surface-cli.md) | **Accepted** |

Deferred questions, documented but not yet decided: eventing mechanism; Kubernetes executor;
hosted multi-user identity; Key Vault adoption; webhook ingestion; evaluation gating
thresholds.
