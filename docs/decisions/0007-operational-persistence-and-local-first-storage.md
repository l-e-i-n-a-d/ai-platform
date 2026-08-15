# ADR-0007: Operational Persistence and Local-First Storage

## Status

Accepted — 2026-08-15

Supersedes the implicit assumption, present in earlier documentation, that Azure Cosmos DB is a V1 component.

## Context

Three stated platform goals interact badly:

1. **V1 is local-first.** Every developer must be able to run the platform on their own machine (`PRINCIPLES.md` §1).
2. **Azure Cosmos DB is the operational persistence layer.**
3. **Microsoft Entra ID is not part of V1** (`SECURITY.md`).

Cosmos DB's data plane offers exactly three authentication mechanisms:

- **account keys** — root-equivalent, not bound to any identity;
- **resource tokens** — scoped, but minted by a component holding the account key;
- **fine-grained RBAC** — which requires Microsoft Entra ID (OAuth 2.0) tokens.

With Entra excluded and a *shared* Cosmos account serving platform instances running on
developer laptops, the only workable mechanism is distributing an account key to every
machine. That key grants every developer full read/write access to all operational state:
other developers' runs, approvals, audit records and evaluation results. It makes the audit
trail forgeable, which contradicts the requirement that every consequential action be
attributable to a user, and it contradicts least privilege (`PRINCIPLES.md` §6).

Resource tokens do not avoid the problem: the minting broker is a central, always-on service
holding the master key, reintroducing exactly the central component that local-first was
adopted to avoid.

The Azure Cosmos DB vNext emulator (Linux/Docker, cross-platform) is a viable local option
and supports TTL, transactional batch, ETag concurrency and change feed. It does **not**
support Entra ID or RBAC under any configuration — it authenticates solely with a
well-known, publicly documented account key. For a loopback-only development instance that
is harmless.

This reframes the problem. The security exposure is not caused by Cosmos DB; it is caused by
a **shared account**. If V1 has no shared operational store, the exposure does not exist.

We therefore examined what the operational store must actually do. Derived from the run/node
state model:

| # | Requirement | Required in V1 |
|---|---|---|
| R1 | Atomic multi-document write within a single run | Yes — prevents torn state on crash |
| R2 | Compare-and-swap concurrency control | Yes — leases and state transitions |
| R3 | Record expiry | Yes — leases and idempotency keys |
| R4 | Query by status and time | Yes — active runs, pending approvals |
| R5 | JSON documents with schema evolution | Yes |
| R6 | Large-payload offload | Yes — transcripts, diffs, CI logs |
| R7 | Fully offline operation, no cloud account | Yes — goals of local-first |
| R8 | Multi-writer, geo-replication, change feed, horizontal scale | **No** |

R1–R7 are satisfied by any embedded transactional store. R8 is the only category that
requires Cosmos DB, and none of it is demonstrated by V1, which is single-developer and
single-orchestrator. Requiring Cosmos DB in V1 is therefore speculative infrastructure,
contrary to `PRINCIPLES.md` §8 (Evidence Over Assumptions) and §12 (Incremental
Architecture).

## Decision

**1. All persistence is accessed through a persistence port.**

The control plane defines storage interfaces in domain terms. No component outside the
persistence adapters may reference a storage SDK type. The port comprises:

```text
GraphDefinitionStore   immutable, content-addressed graph versions
RunStore               run, node_execution, checkpoint, agent_execution,
                       tool_invocation, model_invocation, event
ApprovalStore          approval requests and decisions
LeaseStore             orchestrator ownership of a run
IdempotencyStore       side-effect deduplication records
RepositoryStore        repository registry
ArtifactStore          large payloads, content-addressed
```

**2. SQLite is the V1 operational store.**

A single embedded database file under the platform home directory, in WAL mode. SQLite is a
library, not a server: it introduces no container, no daemon, no port, no credential and no
cloud account. It provides stronger local guarantees than the platform requires, including
real multi-statement transactions.

**3. The local filesystem is the V1 artifact store.**

Content-addressed by SHA-256 under the platform home. Azure Blob Storage is not a V1
dependency.

**4. Azure Cosmos DB and Azure Blob Storage remain the documented target for a hosted,
multi-user deployment.** They are not V1 components. Their adapters will be written when a
shared operational store is demonstrably required — which is the same point at which the
identity question must be reopened. These two decisions are coupled and will be taken
together.

**5. A storage contract test suite defines correct adapter behaviour.**

Covering compare-and-swap conflicts, atomic transitions, expiry, lease acquisition and
renewal, and crash-and-resume. Every adapter must pass it. This suite is what makes a future
Cosmos DB adapter a contained and provable piece of work rather than a migration.

**6. The port is restricted to the intersection of an embedded store and Cosmos DB.**

Explicitly forbidden in the port and in all calling code:

- change feed or any store-side eventing;
- stored procedures and server-side functions;
- unbounded cross-partition queries;
- server-side joins and foreign-key constraints;
- transactions spanning more than one partition key;
- any query not backed by a declared index.

Every document is addressed by `(container, partitionKey, id)`, mirroring the Cosmos DB
model, so that a future adapter is a direct mapping rather than a redesign.

## Alternatives

**A. Cosmos DB vNext emulator as the local default, cloud Cosmos later.**
Resolves the security problem equally well, since each developer runs an isolated instance,
and preserves Cosmos DB as the V1 store. Rejected because it requires Docker and roughly
1–2 GB of memory for every developer and every CI job, slows the test loop, and models a
distributed multi-writer database for a single-writer local application. It buys fidelity to
an architecture that V1 has not yet been shown to need. Remains available at low cost: the
port makes this adapter a contained piece of work if the team later wants continuous
portability proof in CI.

**B. Flat files or append-only JSONL.**
Rejected. Provides no compare-and-swap and no atomic multi-document write, so it fails R1 and
R2. Lease correctness and torn-state prevention cannot be built on it.

**C. Shared cloud Cosmos DB with Entra ID enabled for the data plane only.**
Would give genuine least privilege and identity-bound access. Rejected for V1 because it
reverses the deferral of Entra ID, requires network connectivity for all platform operation,
and makes offline local-first impossible. Reconsider in the hosted phase.

**D. Shared cloud Cosmos DB with a distributed account key.**
Rejected. This is the status quo assumption and the source of the problem: a root-equivalent
credential on every laptop, a forgeable audit trail, and no per-user least privilege.

**E. PostgreSQL.**
Not considered; excluded by platform policy. Noted here only to record that SQLite is not a
circumvention of that exclusion. The exclusion concerns introducing a database *server* as
infrastructure. SQLite is an embedded library with no process, no network surface and no
operational footprint.

## Consequences

**Positive**

- The shared-credential exposure is eliminated rather than mitigated: with no shared store,
  there is no shared key and no identity gap.
- V1 runs fully offline. No Azure subscription, container runtime or emulator is required to
  run the platform or its tests.
- Developer bootstrap improves materially; this directly supports the goal that a developer
  can go from clone to first run quickly.
- The Cosmos DB and identity decisions are deferred together, to the phase where both are
  actually driven by requirements.
- Tests exercising crash-and-resume become fast and hermetic, which matters because
  durability is the platform's core correctness property.

**Negative**

- A second adapter must be written when a hosted deployment arrives. The contract test suite
  bounds this cost.
- The port must be deliberately kept at the intersection of both storage models. Convenient
  SQL features (joins, foreign keys, cross-aggregate transactions) are unavailable by policy,
  and reviewers must enforce this.
- Local state is per-developer. Runs are not visible across machines. This is a consequence of
  local-first, not of this decision, but it becomes concrete here.
- Documentation asserting that Cosmos DB is the V1 persistence layer must be corrected.

**Neutral**

- The logical data model, partition-key strategy and document envelopes are unchanged; they
  were designed against the Cosmos DB model and are preserved deliberately so the mapping
  stays mechanical.

## Security / Operational Impact

- Removes the requirement to distribute any long-lived database credential to developer
  machines.
- The operational store is a local file, subject to the developer's own filesystem
  permissions. It should be treated as sensitive: it contains run metadata, context
  provenance and audit records. It must not be committed to version control.
- Platform-internal audit remains *developer-attested* and is not adversarial-grade. This
  limitation is inherent to local-first without central identity and is unchanged by this
  decision. High-consequence actions must continue to be anchored in systems that do have
  identity, by embedding run identifiers in commits, pull requests and Jira comments.
- Large payloads are written to the local artifact store and must pass the redaction pipeline
  before persistence, unchanged by this decision.
- No new network surface, listening port, container or daemon is introduced.

## Follow-up

- Add `docs/architecture/persistence.md` describing the port, the adapter and the data model.
- Correct `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `docs/integrations/azure.md`,
  `CLAUDE.md` and `.github/copilot-instructions.md`, which currently state that Cosmos DB and
  Blob Storage are V1 components.
- Implement the contract test suite alongside the first adapter, before the graph engine
  depends on it.
- Record the triggers that would reopen this decision: a shared operational store, a
  centrally hosted orchestrator, multi-user tenancy, or cross-developer approval workflows.
  Any of these requires reopening this ADR together with the identity decision.
