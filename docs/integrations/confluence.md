# Confluence Integration

Confluence is the system of record for product and engineering knowledge.

**Decisions:** [ADR-0012](../decisions/0012-github-actor-identity-and-write-back.md),
[ADR-0013](../decisions/0013-context-bundle-contract.md)

---

## Identity

Retrieval authenticates as **the developer running the platform**. A shared privileged service
account is forbidden.

This matters more for Confluence than anywhere else: spaces routinely contain HR, security,
legal and commercial content that is deliberately restricted. A privileged retrieval account
would turn the platform into a permission-laundering channel for exactly that material.

---

## Canonical model

Confluence maps onto a canonical `KnowledgeDocument`. Storage-format markup is normalised in the
adapter and never reaches graph or agent logic.

Retrieved concerns:

- page retrieval
- relevant-space discovery
- architecture documentation
- ADRs
- documentation relationships

Every item records the page id and the version observed, so context is pinned for the run.

---

## Write-back

**Every publication and edit requires human approval.** There are no unattended Confluence
writes in V1.

All platform-authored pages and sections carry machine-readable provenance markers.

---

## The feedback loop

Confluence content later becomes agent context. Without marking and down-weighting, the platform
reads its own unreviewed output back as authoritative knowledge, and confident errors compound
quietly across runs.

The context engine therefore treats platform-authored content as **lower trust** than
human-authored content. This is the integration failure mode that gets worse the longer it goes
unnoticed, which is why approval-gated publication is not negotiable in V1.

---

## Trust

All retrieved page content is **untrusted** (ADR-0013 §5). Documentation may describe how work
should be done; it can never grant a capability.
