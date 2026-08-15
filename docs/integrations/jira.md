# Jira Integration

Jira is the system of record for engineering work.

The platform integrates with Jira rather than replicating it as a second work-management system.

**Decisions:** [ADR-0012](../decisions/0012-github-actor-identity-and-write-back.md),
[ADR-0013 §4](../decisions/0013-context-bundle-contract.md)

---

## Identity

Retrieval authenticates as **the developer running the platform**, using their own token or
OAuth grant. A broadly privileged shared service account is forbidden: it would let any
developer obtain, through an agent, content from restricted projects they cannot open
themselves, and would misattribute the access in Jira's own audit log.

`ACCESS_DENIED` is a normal recorded outcome, never retried with something more privileged.

---

## Canonical model

Jira maps onto a canonical `WorkItem`. Jira shapes do not appear elsewhere in the platform.

Jira data models are irregular by nature — custom fields, per-project workflows, storage-format
markup. Leaking them into graph and agent logic would make every Jira configuration change a
platform change.

Retrieved concerns:

- issue retrieval
- requirements and acceptance criteria
- comments
- status
- links to repositories and documentation

Every retrieved item records the issue key and the version or updated-at observed, so a run's
context is pinned (ADR-0013 §6).

---

## Rate limiting and delivery

Polling only in V1 — webhooks need a reachable endpoint, which laptops do not have. Rate
limiting, pagination and retry are centralised in this adapter.

---

## Write-back

| Action | V1 |
|---|---|
| comment, clearly marked, idempotent, carrying the run id | unattended |
| status transition | requires approval |
| field edits | requires approval |

Unattended writes are idempotent, keyed by run and node, so a retry updates rather than
duplicates. Duplicate comments are the classic symptom of a durable system that forgot its
external effects are not transactional.

Unattended status transitions are gated because they disrupt a team's actual process and erode
trust in Jira as the system of record — which is a much more expensive loss than the
convenience gained.

All platform-authored content carries machine-readable provenance markers.

---

## Trust

Issue descriptions, comments and attachments are **untrusted content** (ADR-0013 §5). They may
inform an agent; they can never change what it is permitted to do.
