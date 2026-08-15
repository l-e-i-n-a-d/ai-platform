# Graph Engine

**Status:** Planned (design agreed, not yet implemented)
**Location:** Control plane (Java / Quarkus)
**Decision:** [ADR-0008](../decisions/0008-graph-execution-semantics-and-durability.md)

---

## 1. Responsibility

The graph engine is the **sole orchestrator**. It represents engineering workflows explicitly
and versionably, and it is the only component that advances a run.

**Responsible for**

- interpreting the pinned graph definition
- selecting the next node
- applying retry, timeout and budget policy
- writing every state transition and checkpoint
- holding and renewing the run lease
- pausing for approval and resuming afterwards
- cancellation and recovery

**Not responsible for**

- agent internals or prompt construction
- tool semantics or authorization
- execution mechanics

Do not hide workflow logic inside an agent prompt. No agent may author, mutate or select a
graph definition for a live run.

---

## 2. Definitions and versioning

Graph definitions are declarative documents containing no code. They are immutable and
content-addressed; `graphId` names the workflow, `graphVersionHash` names the exact
definition.

A run pins `graphVersionHash` at creation and executes it for its whole life. New versions
never affect in-flight runs; to apply one, start a new run.

---

## 3. Node types

| Type | Model | Tools | Durable pause |
|---|---|---|---|
| `context` | no | no | no |
| `agent` | yes | via grant | no |
| `tool` | no | one, fixed | no |
| `approval` | no | no | **yes** |
| `decision` | no | no | no |
| `loop` | — | — | no (bounded) |
| `terminal` | no | no | — |

The taxonomy is closed; extending it requires an ADR. Prefer deterministic node types wherever
a model is not genuinely required.

Edge conditions and loop exits use a restricted language: comparison, boolean composition,
presence and set membership over **validated** output fields and run variables. No scripting,
no I/O, no reference to free-form model text.

---

## 4. State machines

```text
RUN
              +------------------------------------------+
              v                                          |
  PENDING --> RUNNING --+--> AWAITING_APPROVAL ----------+
                        +--> AWAITING_RETRY -------------+
                        +--> SUSPENDED (lease lost) -----+
                        +--> SUCCEEDED | FAILED | CANCELLED | TIMED_OUT   (terminal)

NODE
  PENDING -> SCHEDULED -> RUNNING -+-> SUCCEEDED
                                   +-> AWAITING_APPROVAL -> RUNNING
                                   +-> AWAITING_RETRY -> SCHEDULED (attempt+1)
                                   +-> FAILED | SKIPPED | CANCELLED
                                   \-> INDETERMINATE
```

`SUSPENDED` is what closing a laptop looks like — expected and recoverable.
`INDETERMINATE` means a side effect may or may not have occurred; it is never auto-retried.

---

## 5. Durability rules

- Only the lease holder may transition a run. Lease TTL, CAS renewal, `epoch` on takeover.
- Each transition writes node status + checkpoint + event as **one transactional batch** in the
  run partition (ADR-0007). Partial transitions are impossible.
- Every write is guarded by expected version and a lease check.
- A checkpoint is written at every node boundary, including
  `workspaceStateRef = (repoRef, baseSHA, ordered patch series)`.
- Retry policy lives in the definition; retry state lives on the node; retries are driven by
  **failure category**, never message text.
- Loops declare a maximum iteration count and a deterministic exit condition. A model never
  decides a loop is finished.
- Approvals release the lease, bind to a `subjectHash`, and expire. The hash is re-verified on
  resume.
- Resume continues from recorded state. Model calls are never replayed.
- Cancellation always stops new work; it is best-effort for work in flight.

---

## 6. Interfaces

```text
startRun(graphId, inputs)      -> RunId
advanceRun(runId)                          // lease-guarded scheduling step
resumeRun(runId)
cancelRun(runId)
recordApproval(approvalId, decision)
```

The engine consumes a node-executor abstraction and never learns whether execution is local or
remote.
