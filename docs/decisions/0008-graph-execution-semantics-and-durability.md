# ADR-0008: Graph Execution Semantics, Versioning and Durability

## Status

Accepted — 2026-08-15

Depends on ADR-0007 (persistence port). Read together with ADR-0004 and ADR-0005.

---

## Context

`ARCHITECTURE.md` and `docs/architecture/graph-engine.md` list the capabilities a graph must
eventually have — branching, loops, retries, checkpoints, approvals, timeouts, versioning —
but define no semantics for any of them. There is no run state machine, no node state machine,
no statement of who may advance a run, no definition of what a checkpoint contains, and no
resume algorithm.

These are not details to be settled during implementation. They determine the data model, and
the data model is the expensive thing to change once runs exist.

The local-first constraint sharpens the problem. A hosted orchestrator can assume it stays
alive; this one cannot. Laptops sleep, batteries die, developers press Ctrl-C, and the platform
may be restarted in the middle of a workflow that has already opened a pull request. A run
that survives none of this is not durable in any useful sense.

There is also a standing temptation, in AI platforms specifically, to let the model plan the
workflow — to replace the graph with an agent that decides what to do next. That produces
workflows that cannot be versioned, resumed, evaluated or reviewed, and it is the single
change that would undermine every other decision in this repository.

---

## Decision

### 1. Graph definitions are declarative data, immutable and content-addressed

A graph definition is a document — nodes, edges, policies — validated against a schema. It
contains no code and no expressions beyond the restricted condition language of §4.

Definitions are immutable. Editing produces a new version, identified by the content hash of
its canonical form. `graphId` names the workflow; `graphVersionHash` names the exact
definition.

### 2. Runs pin their definition

A run records `graphVersionHash` at creation and is executed against that definition for its
entire life. Publishing a new version never affects an in-flight run.

This is what makes a run resumable after a week, and reproducible during evaluation. There is
no in-flight migration: to apply a new definition, start a new run.

### 3. A closed node taxonomy

| Node type | Model | Tools | Durable pause | Purpose |
|---|---|---|---|---|
| `context` | no | no | no | build an immutable context bundle |
| `agent` | yes | via grant | no | one bounded agent loop (ADR-0004) |
| `tool` | no | exactly one, fixed | no | a deterministic side effect |
| `approval` | no | no | **yes** | human decision |
| `decision` | no | no | no | pure branch over validated output |
| `loop` | — | — | no | bounded iteration with a deterministic exit |
| `terminal` | no | no | — | run outcome |

The taxonomy is closed: adding a node type requires an ADR. Deterministic node types are
preferred wherever a model is not genuinely required.

### 4. A restricted condition language

Edge conditions and loop exits are boolean expressions over (a) fields of **validated**
structured node output and (b) run variables. Permitted: comparison, boolean composition,
presence tests, set membership. Forbidden: arbitrary scripting, I/O, side effects, and any
reference to free-form model text.

Every condition must be total and evaluable from durable state alone. Conditions are therefore
replayable, testable in isolation, and cheap to review — and a run's branching decisions can
be explained after the fact without re-invoking a model.

### 5. Transitions are evaluated only on validated output

A node produces claimed output; the control plane validates it against the node's declared
output schema (ADR-0004 §9); only then may a transition be evaluated. A schema failure is a
node failure of category `INVALID_OUTPUT`, eligible for one bounded repair attempt, not a
transition input.

Workflow control never depends on prose.

### 6. Run state machine

```text
              +------------------------------------------+
              v                                          |
  PENDING --> RUNNING --+--> AWAITING_APPROVAL ----------+
                        +--> AWAITING_RETRY -------------+
                        +--> SUSPENDED (lease lost) -----+
                        |
                        +--> SUCCEEDED   (terminal)
                        +--> FAILED      (terminal)
                        +--> CANCELLED   (terminal)
                        \--> TIMED_OUT   (terminal)
```

Terminal states are immutable. `SUSPENDED` is the normal consequence of closing a laptop — an
expected, recoverable state, not a failure — and is resumed by an explicit operator action.

### 7. Node state machine

```text
PENDING -> SCHEDULED -> RUNNING -+-> SUCCEEDED
                                 +-> AWAITING_APPROVAL -> RUNNING
                                 +-> AWAITING_RETRY -> SCHEDULED (attempt+1)
                                 +-> FAILED
                                 +-> SKIPPED
                                 +-> CANCELLED
                                 \-> INDETERMINATE
```

`INDETERMINATE` is entered when a write-ahead intent record (ADR-0005 §7) exists with no
matching outcome: a side effect may or may not have occurred. It is **never auto-retried**. It
is resolved by reconciliation against the external system, or escalated to a human.

Most workflow engines omit this state and then discover they need it after posting two pull
requests for the same issue.

### 8. Exactly one orchestrator per run, enforced by a lease

Only the holder of the run's lease may transition its state. The lease has a TTL, is acquired
and renewed by compare-and-swap, and carries an `epoch` that is bumped on takeover. A run
whose lease expires becomes `SUSPENDED`.

The graph engine is the sole orchestrator. No agent, no tool and no runtime advances a run.
There is no nested planning loop with its own retry policy.

### 9. Every transition is a single atomic write

A transition writes the node status, any checkpoint, and the corresponding event as **one
transactional batch within the run's partition** (ADR-0007). Partial transitions are therefore
impossible; a crash lands either before or after, never inside.

Every write is guarded by both the expected version (CAS) and a lease check.

### 10. Checkpoints at every node boundary

```text
checkpointId, runId, afterNodeId, sequence,
graphVariablesRef, workspaceStateRef (repoRef + baseSHA + ordered patch series),
contextBundleRefs[], createdAt
```

Written in the same batch as the node's terminal status. `workspaceStateRef` is what makes a
workspace reconstructible rather than precious — the property that also permits a future
remote executor.

Intra-agent iteration checkpoints are explicitly out of scope: an agent attempt is the unit of
retry, and a partially completed agent loop is re-run, not resumed.

### 11. Retry: policy in the definition, state on the node, driven by category

Retry policy — max attempts, backoff, which categories are retryable — is part of the graph
definition and therefore versioned and pinned. Retry state — `attempt`, `nextAttemptAt`,
`lastFailureCategory` — lives on the node.

Failure categories: `TRANSIENT`, `MODEL_ERROR`, `BUDGET_EXCEEDED`, `INVALID_OUTPUT`,
`TOOL_DENIED`, `VERIFICATION_FAILED`, `EXECUTION_ERROR`, `INTEGRATION_ERROR`, `INDETERMINATE`,
`CANCELLED`, and — added by ADR-0009 — `APPROVAL_REJECTED` and `APPROVAL_EXPIRED`.

Retry is driven by **category, not message text**, which keeps definitions readable and
testable. Each attempt keeps its own execution record; records are never overwritten, because
evaluation depends on being able to see how failures evolved.

### 12. Loops must be bounded and must exit deterministically

Every `loop` node declares a maximum iteration count and an exit condition in the language of
§4. A model may not decide that a loop is finished; a deterministic verification step —
compile, test, lint, schema check — decides.

This is the repair loop the platform exists to run, and it is also the failure mode most
likely to burn a day's budget in ten minutes.

### 13. Approvals are durable pauses

On reaching an `approval` node the engine writes `AWAITING_APPROVAL`, **releases the lease**,
and stops. Nothing is held in memory. The approval record binds to `subjectHash` — the content
hash of exactly what was approved — and carries an expiry.

On resume the engine re-verifies `subjectHash` before proceeding. If the subject changed after
approval, the approval is void. Without this, an approval is a time-of-check/time-of-use bug
with a human in it.

### 14. Cancellation

`cancellationRequested` is set durably and the run `epoch` bumped. The lease holder stops
scheduling new nodes. In-flight agent attempts are cancelled cooperatively then terminated
(ADR-0004 §8). In-flight side-effecting tool invocations are allowed to complete, or recorded
as `INDETERMINATE`. Workspaces are quarantined, not deleted.

Guarantee: cancellation always stops new work, and is best-effort for work in flight. Stated
plainly because the opposite is routinely assumed.

### 15. Resume

1. Acquire the lease; fail if held elsewhere.
2. Load the run, its nodes and the latest checkpoint.
3. For each node in `RUNNING`: if a write-ahead intent has no outcome → `INDETERMINATE`;
   otherwise roll back to the last checkpoint and reschedule with `attempt+1`.
4. Rebuild the workspace from `(repoRef, baseSHA, patch series)`.
5. Re-verify the `subjectHash` of any pending approval.
6. Continue.

Resume means **continue from recorded state**. Model calls are never replayed to reconstruct
position; that would be non-deterministic, expensive, and would re-emit side effects.

### 16. The graph is authored by humans

Agents may propose a graph definition as a reviewable artifact. No agent may author, mutate or
select a graph definition for a live run. Workflow structure is reviewed like code.

---

## Alternatives

**A. Adopt a workflow engine (Temporal, Camunda) instead of building one.**
Genuinely attractive: durability, retries, timers and resumability are solved and battle-tested.
Rejected for V1 because every candidate requires server infrastructure, which contradicts the
local-first constraint, and because the platform's hard problems — capability grants, context
budgets, approval binding, evaluation — sit outside what such an engine provides. Worth
revisiting at the hosted phase, when the infrastructure cost is already being paid.

**B. Let an agent plan and execute the workflow.**
Rejected. It cannot be versioned, resumed, evaluated, reviewed or explained, and it makes
every other control in this repository advisory.

**C. Imperative graphs expressed as code.**
More expressive, and fatal to pinning: code cannot be content-addressed and replayed with the
same confidence, and reviewing a diff of control flow is much harder than reviewing a diff of
declared edges.

**D. Pure event sourcing with derived state.**
Elegant, and heavier than needed for single-node V1. The chosen model already writes an event
per transition in the same batch as the state change, so the audit trail exists without the
replay machinery.

**E. Checkpoint inside the agent loop.**
Rejected as premature: it complicates the protocol and the data model to save re-running an
attempt whose main cost is tokens, on a workload with no proven need.

---

## Consequences

**Accepted costs**

- The engine must be written and, more importantly, tested against crash injection. Milestone
  ordering should prove crash-and-resume on a trivial graph before any model is involved.
- Declarative graphs with a restricted condition language will feel limiting. That is the
  point; the escape hatch is a `tool` node, not a richer expression language.
- Pinning means long-running runs execute old definitions. This is correct and will
  occasionally be surprising.
- `INDETERMINATE` requires a human-facing reconciliation path in V1, not just an enum value.

**Gained**

- Runs survive process death, laptop suspension and restart.
- Every branch a run took can be explained from durable state.
- Runs are replayable for evaluation, which is a precondition for ADR-0015 and the evaluation
  work in `EVALUATION.md`.
- Retry, approval and cancellation are properties of the engine, so no agent needs to
  implement them and no agent may reinterpret them.

---

## Security / Operational Impact

- The lease is a security control, not only a correctness one: it prevents two orchestrators
  producing duplicate external side effects.
- Approval binding by content hash prevents approval of one thing being used to authorise
  another.
- `INDETERMINATE` must be visible to an operator. A silently swallowed indeterminate side
  effect is worse than a loud failure.
- Graph definitions are security-relevant inputs, because they determine capability grants
  (ADR-0005 §4). They must be reviewed and version-controlled, and must never be modified by
  an agent.

---

## Follow-up

- Update `docs/architecture/graph-engine.md` to the semantics above.
- Graph definition JSON Schema, including retry policy and condition language.
- Crash-injection test suite: kill the process at every transition point and assert no torn
  state and no duplicated side effect.
- ADR-0009 — approval model, including who may approve without central identity.
- ADR-0015 — telemetry contracts for run, node and transition events.
- Define the reconciliation procedure for `INDETERMINATE` per integration.
