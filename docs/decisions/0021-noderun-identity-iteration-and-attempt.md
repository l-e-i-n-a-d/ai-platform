# ADR-0021: NodeRun Identity — Iteration and Attempt

## Status

Accepted — 2026-08-15

Closes OQ-04 from `docs/contracts/v1-domain-contracts.md`. Refines the node record and retry
semantics of ADR-0008 §7 and §11–12, and the idempotency key of ADR-0005 §7. Depends on ADR-0019
for the `NodeRun` name and ADR-0020 for the canonicalisation used by the idempotency key.

---

## Context

`NodeExecution` is currently keyed by `(runId, nodeId, attempt)`, with `iterations` stored as a
plain counter on the record. ADR-0008 §12 also defines `loop` nodes whose body executes up to
`maxIterations` times.

These two facts are incompatible. A loop body node executed twice, where the first execution also
failed once and was retried, produces this sequence:

```text
iteration 1, attempt 1     failed
iteration 1, attempt 2     succeeded
iteration 2, attempt 1     ...
```

Under `(runId, nodeId, attempt)` the third row collides with the second. The engine cannot tell
"the second attempt at the first iteration" from "the first attempt at the second iteration",
and one of the records must overwrite the other. ADR-0008 §7 states plainly that records are
never overwritten by a retry, "because evaluation depends on being able to see how failures
evolved". The current key makes that guarantee unenforceable.

The consequences reach past record-keeping:

- **Retry budgets are wrong.** `retryPolicy.maxAttempts` is meant to bound retries of one unit of
  work. With a shared counter, a loop of ten iterations exhausts a three-attempt budget during
  the first two iterations.
- **Idempotency is wrong in both directions.** ADR-0005 §7 derives the key from
  `(runId, nodeId, toolId, canonicalised input)`, deliberately excluding `attempt` so a retry
  cannot duplicate an external write. But a *loop iteration* is not a retry: iteration two is new
  work. Where two iterations submit identical input — posting a "build failed" comment each round
  — the current key silently suppresses the second, which is a correctness bug disguised as
  idempotency.
- **Resume is ambiguous.** After a crash mid-loop, the engine cannot determine which iteration it
  was in from the node records alone.

This is a data-model problem, and the cost of fixing it rises the moment anything is persisted.

---

## Decision

### 1. NodeRun identity is a four-part key

```text
NodeRun identity  =  (runId, nodeId, iteration, attempt)
```

Unique. No two `NodeRun` records may share all four values, and no record is ever mutated to
carry a different identity. This is the primary key in the operational store and the correlation
tuple in telemetry and audit.

### 2. Both counters are 1-based, and neither is ever reused

| Field | Base | Meaning | Increments when |
|---|---|---|---|
| `iteration` | 1 | which round of a bounded loop this is | the enclosing `loop` node begins another round |
| `attempt` | 1 | which try at *this* iteration this is | the previous attempt failed retryably |

`iteration` is 1 for every node not inside a loop. There is no zero and no "not applicable"
value: a uniform key is simpler to store, index, log and reason about than one with a magic
absent case, and a node outside a loop is honestly described as being on its first and only
iteration.

1-based numbering follows ADR-0008 §11 and the existing `attempt` definition, which is documented
as "1-based" with `minimum: 1`. Renumbering from zero would edit an accepted decision for no
functional gain.

The three cases that previously collided are now distinct:

```text
node_a, iteration 1, attempt 1      first try
node_a, iteration 1, attempt 2      retry of the first round
node_a, iteration 2, attempt 1      first try of the second round
```

### 3. Retry budgets are scoped per iteration

`retryPolicy.maxAttempts` bounds `attempt` **within a single `(nodeId, iteration)`**. Each
iteration starts again at `attempt = 1` with a full retry budget.

The overall bound remains finite and explicit: a loop cannot exceed `maxIterations`
(ADR-0008 §12, capped at 100), so worst-case work for a loop body is
`maxIterations × maxAttempts`. Both factors are declared in the pinned `Graph`, so the ceiling is
knowable before the run starts rather than discovered from a bill.

### 4. The loop node and its body have separate records

A `loop` node produces its own `NodeRun` — one per attempt at the loop as a whole, at the loop's
own `iteration` — recording how many rounds ran and why iteration stopped. The body nodes produce
their own `NodeRun` records carrying the loop's current round in their `iteration`.

`stopReason` on the loop's record states which bound ended it: `EXIT_CONDITION_MET`,
`MAX_ITERATIONS`, `BODY_FAILED`, `BUDGET_EXCEEDED`, `CANCELLED`, `DEADLINE_EXCEEDED`. ADR-0008 §12
requires a deterministic exit; recording which one fired is what makes "the loop burned the budget"
diagnosable without reading logs.

Loops do not nest in V1. A body node that is itself a `loop` is rejected at publication, so
`iteration` is unambiguously scalar. Nested loops would require an iteration *path* rather than a
number, and nothing has demonstrated the need.

### 5. Idempotency keys include iteration and still exclude attempt

```text
idempotencyKey = sha256(canonical([runId, nodeId, iteration, toolId, canonical(input)]))
```

with canonicalisation per ADR-0020.

The two exclusions and inclusions are deliberate and opposite:

- **`attempt` is excluded**, preserving ADR-0005 §7 exactly. A retry of a failed attempt must
  produce the *same* key, so that a write which may already have landed is not repeated. Adding
  `attempt` here would defeat the entire mechanism, and is the single most likely implementation
  error in the tool layer.
- **`iteration` is included.** A new loop round is new work, not a retry. Excluding it would make
  the platform silently drop the second of two legitimately repeated writes.

### 6. Checkpoints and audit records carry the full key

`Checkpoint` records the `NodeRun` it follows as `(afterNodeId, afterIteration, afterAttempt)`,
alongside the existing per-run monotonic `sequence` that orders checkpoints unambiguously.

The correlation block (ADR-0015 §7) gains `iteration`, so log records, spans and audit entries
carry the same four-part key as the store. It remains forbidden as a metric label for the reason
already given in ADR-0015 §7: unbounded cardinality.

### 7. Resume allocates a new attempt and never reuses one

On resume, the engine finds the highest `(iteration, attempt)` for the node and:

- if that attempt reached a terminal status, proceeds from it;
- if it did not, records the outcome as `INDETERMINATE` where a write-ahead intent exists with no
  matching outcome (ADR-0008 §7), and otherwise allocates `attempt + 1` for the same `iteration`.

An attempt number is never reused, so the record of what was tried survives the crash that
interrupted it.

### 8. V1 executes one node at a time; the key does not depend on that

V1 graph execution is sequential: `GraphRun.currentNodeId` is singular and a single lease admits
one orchestrator (ADR-0008 §8). Parallel branches are not part of V1.

The key is nevertheless chosen so that adding them later changes nothing about identity —
`(runId, nodeId, iteration, attempt)` is unique whether or not two nodes run concurrently,
because it contains no ordering assumption and no shared counter. What parallelism would require
is a join/barrier semantics decision, which is a separate ADR and not a re-keying exercise.

---

## Alternatives Considered

**Keep `(runId, nodeId, attempt)` and encode iteration into `nodeId`**, e.g. `fix_tests#2`.
Rejected. `nodeId` is defined by ADR-0008 as an identifier within the pinned graph definition;
synthesising values that do not appear in the definition breaks the correspondence between a run
and its graph, and makes edge conditions and telemetry unable to refer to "that node" as a stable
thing. It also silently changes what `nodeId` means for every consumer.

**A single monotonic `executionSequence` per node, merging iteration and attempt.** Simpler as a
key, and rejected because it destroys the distinction that makes retries and iterations behave
differently. Retry budgets, and the idempotency rule in §5, both need to know which of the two
happened. The information would have to be recovered from a side field, at which point the merged
counter has saved nothing.

**Make loop iterations separate `GraphRun`s (a sub-run per round).** Rejected as substantially
more machinery: lease, checkpoint, approval and cancellation semantics would all need a
parent/child model, and ADR-0008's single-lease guarantee would need re-deriving. Loops are a
node-level concern.

**Renumber both counters from zero, as the reviewing prompt illustrated.** Rejected because
`attempt` is defined as 1-based by ADR-0008 §11 and constrained `minimum: 1` in the existing
schema. The requirement is that the three cases be *distinguishable*, which 1-based numbering
satisfies; changing the base would edit an accepted decision to no end.

---

## Consequences

- `NodeRun` gains `iteration` as a required field; the store's primary key becomes four-part.
- `CapabilityGrant.subject` gains `iteration`: a grant is minted per attempt, and an attempt is
  now identified by four values. Without this, two grants in a loop would share a subject.
- `AgentExecutionRequest` gains `iteration`, so the runtime reports against the right record.
- The correlation block gains `iteration`, and telemetry, audit and CLI output carry it.
- `Checkpoint` gains `afterIteration` and `afterAttempt`.
- `retryPolicy.maxAttempts` is reinterpreted as per-iteration. Worst-case loop cost becomes
  `maxIterations × maxAttempts`, which should be stated in operator-facing documentation because
  it is larger than a casual reading of either bound suggests.
- Nested loops are rejected at graph publication and require an ADR to introduce.
- `NodeRun.iterations` (the old plain counter) is removed; the count is derivable from the records
  and no longer needs a denormalised copy that could disagree with them.

---

## Security / Operational Impact

The idempotency rule in §5 is the security-relevant part. `EXTERNAL_WRITE` and `IRREVERSIBLE`
tools depend on the key to avoid duplicate side effects — a second pull request, a second Jira
transition, a second published page. Both failure directions are consequential:

- including `attempt` would duplicate writes on every retry;
- excluding `iteration` would suppress writes that should have happened, which is quieter and
  therefore worse: nothing fails, and a comment simply never appears.

A dedicated test must cover both directions, because a single-direction test passes under either
error.

Per-iteration retry budgets raise the worst-case number of model invocations and tool calls for a
loop node. That is a cost and rate-limit consideration, not a new authority: the grant is still
minted per attempt, still monotonically non-increasing, and still expires at `notAfter`
(ADR-0005 §4).

Attempt numbers are never reused, so the audit trail of a crashed attempt is not overwritten by
the attempt that replaces it — which is what makes ADR-0016's attribution chain reconstructable
after a crash.

---

## Follow-up

- Add `iteration` to `NodeRun`, `CapabilityGrant.subject`, `AgentExecutionRequest`, the
  correlation block and `Checkpoint`.
- Remove the `iterations` counter from `NodeRun`.
- Reject nested `loop` nodes at graph publication.
- Add contract examples for a retry and for a loop iteration, which must differ only in the
  identity fields.
- Update `docs/architecture/graph-engine.md` with per-iteration retry budgets.
- ADR-0005 §7 — the idempotency key definition is superseded by §5 here.
