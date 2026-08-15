# Persistence

**Status:** Planned (design agreed, not yet implemented)
**Applies to:** V1 (local-first)
**Decision:** [ADR-0007](../decisions/0007-operational-persistence-and-local-first-storage.md)

---

## 1. Responsibilities

The persistence layer owns durable platform state and large artifacts. It is the only place
in the platform aware of a storage technology.

**Responsible for**

- durable run and workflow state
- optimistic concurrency and atomic state transitions
- orchestrator leases
- idempotency records for side-effecting operations
- record expiry
- offloading large payloads to the artifact store

**Not responsible for**

- deciding when a transition is legal — that is the graph engine
- policy, authorization or approval semantics
- telemetry (state documents carry correlation identifiers, but emit nothing)
- caching of external system data — that is the context engine

---

## 2. Architecture

```text
        Control plane services (graph engine, tool layer, approvals, ...)
                                   |
                                   v
                        +----------------------+
                        |   Persistence Port   |    domain interfaces only
                        +----------+-----------+
                                   |
              +--------------------+--------------------+
              |                                         |
              v                                         v
     +-----------------+                    +-------------------------+
     | SQLite Adapter  |  V1                | Cosmos DB Adapter       | hosted phase
     | (embedded)      |                    | (not implemented)       |
     +-----------------+                    +-------------------------+
              |                                         |
              v                                         v
     ~/.ai-platform/state.db                   Azure Cosmos DB (NoSQL)

     +-----------------+                    +-------------------------+
     | Filesystem      |  V1                | Azure Blob Storage      | hosted phase
     | Artifact Store  |                    | (not implemented)       |
     +-----------------+                    +-------------------------+
```

No storage SDK type may appear above the port. No component outside the persistence adapters
may open a database connection.

---

## 3. Port interfaces

Expressed in domain terms:

```text
GraphDefinitionStore   put(definition) -> contentHash        (immutable)
                       getByHash(hash)
                       getLatest(graphId)

RunStore               createRun(run)
                       getRun(runId)
                       appendDocuments(runId, documents[])   (atomic, single partition)
                       transition(runId, expectedVersion, changes[])
                       queryRuns(status[], mode, limit)

ApprovalStore          request(approval)
                       decide(approvalId, expectedVersion, decision)
                       listPending(runId?)

LeaseStore             acquire(runId, ownerId, ttl) -> Lease | Conflict
                       renew(leaseId, expectedVersion, ttl)
                       release(leaseId)
                       get(runId)

IdempotencyStore       putIntent(key, descriptor)
                       recordOutcome(key, expectedVersion, outcome)
                       get(key)

RepositoryStore        upsert(repository)
                       get(repositoryId)
                       list()

ArtifactStore          put(bytes, contentType) -> ArtifactRef
                       open(ArtifactRef) -> stream
                       delete(ArtifactRef)
```

Every mutating operation that changes an existing record takes an expected version and fails
with a typed conflict error if it does not match. There is no unconditional overwrite.

---

## 4. Storage model

The physical model deliberately mirrors the Azure Cosmos DB model so a future adapter is a
direct mapping rather than a redesign. Every document is addressed by:

```text
(container, partitionKey, id)
```

### Containers and partition keys

| Container | Partition key | Contents | Expiry |
|---|---|---|---|
| `graph_definitions` | `graphId` | immutable, content-addressed versions | none |
| `run_state` | `runId` | all run-scoped documents | none |
| `approvals` | `runId` | approval requests and decisions | none |
| `leases` | `runId` | orchestrator ownership | short |
| `idempotency` | `idempotencyKey` | side-effect deduplication | medium |
| `repositories` | `repositoryId` | repository registry | none |
| `work_items` | `workItemKey` | work item to run index | none |
| `evaluations` | `evaluationId` | evaluation results | policy |

`run_state` holds every run-scoped document type, discriminated by `type`: `run`,
`node_execution`, `checkpoint`, `agent_execution`, `tool_invocation`, `model_invocation`,
`context_bundle_ref`, `event`. Co-partitioning by `runId` is what allows a state transition
and its event append to be written atomically.

### Document envelope

Present on every document:

```json
{
  "id": "...",
  "partitionKey": "...",
  "type": "node_execution",
  "schemaVersion": 1,
  "version": 7,
  "createdAt": "...",
  "updatedAt": "...",
  "expiresAt": null,
  "traceId": "...",
  "spanId": "...",
  "actor": "local:daniel",
  "mode": "operational",
  "payload": { }
}
```

`version` is the concurrency token. In the SQLite adapter it is a monotonically increasing
integer; in a Cosmos DB adapter it maps to `_etag`. Callers treat it as opaque.

`mode` is `operational` or `evaluation` and is mandatory, so evaluation data never pollutes
operational queries, metrics or cost reporting.

### Payload size

Any payload above **100 KB** is written to the artifact store and replaced inline by a
reference:

```json
{ "uri": "...", "sha256": "...", "sizeBytes": 0, "contentType": "...", "redacted": true }
```

This keeps documents far below the 2 MB item limit that a Cosmos DB adapter would impose, and
keeps transcripts, diffs and CI logs out of the operational store.

---

## 5. SQLite adapter (V1)

A single file, `~/.ai-platform/state.db`, in WAL mode.

```sql
CREATE TABLE documents (
  container     TEXT    NOT NULL,
  partition_key TEXT    NOT NULL,
  id            TEXT    NOT NULL,
  type          TEXT    NOT NULL,
  version       INTEGER NOT NULL,
  expires_at    INTEGER,
  created_at    INTEGER NOT NULL,
  updated_at    INTEGER NOT NULL,
  body          TEXT    NOT NULL,   -- JSON
  PRIMARY KEY (container, partition_key, id)
);
```

Queried fields are exposed as indexed generated columns rather than by scanning JSON, so that
every supported query is index-backed and has an equivalent Cosmos DB index:

```sql
ALTER TABLE documents ADD COLUMN status TEXT
  GENERATED ALWAYS AS (json_extract(body, '$.payload.status')) VIRTUAL;

CREATE INDEX idx_documents_type_status ON documents (container, type, status);
CREATE INDEX idx_documents_expiry      ON documents (expires_at)
  WHERE expires_at IS NOT NULL;
```

**Concurrency.** Compare-and-swap is a conditional update:

```sql
UPDATE documents SET body = ?, version = version + 1, updated_at = ?
 WHERE container = ? AND partition_key = ? AND id = ? AND version = ?;
```

Zero affected rows is a conflict, surfaced as a typed error. The caller re-reads and retries;
it never overwrites blindly.

**Atomic transitions.** `appendDocuments` and `transition` run inside a single SQLite
transaction. The port requires that all documents in one call share a container and partition
key, so the same operation maps onto a Cosmos DB transactional batch without change.

**Expiry.** Records carry `expires_at`. Reads filter expired rows explicitly; correctness —
in particular lease expiry — must never depend on the background sweeper. A periodic sweep
deletes expired rows to reclaim space only.

**Leases.** Acquisition is an insert-or-conditional-update guarded by expiry:

```text
acquire(runId, ownerId, ttl):
  read lease for runId
  if none                      -> insert (version 1)
  else if expires_at <= now    -> CAS update to new owner, bump epoch
  else if owner == ownerId     -> CAS renew
  else                         -> Conflict
```

Only the lease holder may transition run state. This is what prevents two orchestrators from
advancing the same run and producing duplicated external side effects.

---

## 6. Artifact store (V1)

Content-addressed on the local filesystem:

```text
~/.ai-platform/artifacts/<sha256[0:2]>/<sha256>
```

Content addressing gives deduplication and integrity verification, and makes artifact
references stable and immutable — which is what allows context bundles and checkpoints to be
replayed for evaluation.

Artifacts must pass the redaction pipeline before being written. Retention is by artifact
type; audit-relevant artifacts are immutable.

---

## 7. Portability rules

The port is restricted to the intersection of an embedded store and Cosmos DB. The following
are forbidden in the port and in calling code:

- change feed or any store-side eventing
- stored procedures and server-side functions
- unbounded cross-partition queries
- server-side joins and foreign-key constraints
- transactions spanning more than one partition key
- any query not backed by a declared index
- returning storage SDK types above the port

These rules exist to keep a future adapter a mapping exercise. They are enforced in review.

---

## 8. Contract tests

One suite defines correct behaviour; every adapter must pass it unmodified:

- compare-and-swap conflict detection under concurrent writers
- atomicity of multi-document transitions, including partial-failure rollback
- expiry semantics, including reads that must ignore expired records
- lease acquisition, renewal, expiry takeover and conflict
- idempotency intent-then-outcome, including the indeterminate case where an intent has no
  recorded outcome
- crash and resume: interrupt mid-transition, reopen, verify no torn state

This suite is the reason a hosted-phase Cosmos DB adapter is a contained piece of work.

---

## 9. Future: hosted deployment

Cosmos DB and Blob Storage adapters will be implemented when a shared operational store is
demonstrably required. That is the same point at which centralized identity must be
reconsidered, because a shared store without identity-bound access reintroduces the problem
ADR-0007 was written to remove. The two decisions must be taken together.

Triggers that reopen ADR-0007:

- a shared operational store across developers
- a centrally hosted, always-on orchestrator
- multi-user tenancy
- cross-developer approval workflows
