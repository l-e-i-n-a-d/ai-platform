# ADR-0025: Approval Expiry, Re-Request and Non-Decision Outcomes

## Status

Accepted — 2026-08-15

Closes OQ-06 from `docs/contracts/v1-domain-contracts.md`. Refines the approval model of ADR-0009
and the retry semantics of ADR-0008 §11 and ADR-0021 §2.

---

## Context

A node suspended on an approval can end in three ways, and the current contracts treat two of them
identically.

`APPROVAL_REJECTED` means a human looked at the subject and said no. It is terminal for the node,
and retrying it would mean asking someone to keep saying no until they slip.

`APPROVAL_EXPIRED` means nobody decided anything. The clock ran out. On a local-first platform
where the approver is a developer with a laptop, this is not an exceptional condition — it is what
a weekend looks like. A run started on Friday afternoon that pauses for consent will routinely
expire before Monday.

The `Graph` schema permits neither category in `retryableCategories`, so today both permanently
fail the run. The rejected case is correct. The expired case means a developer returns from
holiday to a dead run whose only recovery is starting over, discarding every checkpoint, every
completed node and every unit of spend that got the run to the approval point. That is the
opposite of what ADR-0008's durability model exists to provide.

The complication is that "retry an expired approval" is not the same operation as "retry a failed
node". Retrying a node re-runs work. Re-requesting an approval must not re-run the work that
produced the subject — it must present *the same subject* to a human again. If a retry silently
re-executed the node, the subject the second approver sees could differ from the one the first
approver ignored, and the approval record would attest to something nobody chose to approve.

There is a third outcome the contracts do not name at all: an approval that was granted and then
**revoked** before the node consumed it. ADR-0009 permits revocation; nothing says what the
waiting node does.

---

## Decision

### 1. Non-decision is a distinct outcome from refusal

Approval outcomes divide by *whether a human decided*, not by whether the run may proceed:

| Outcome | A human decided | Node result | Retryable |
|---|---|---|---|
| `APPROVED` | yes | proceeds | n/a |
| `APPROVAL_REJECTED` | yes | `APPROVAL_REJECTED` | **never** |
| `APPROVAL_EXPIRED` | no | `APPROVAL_EXPIRED` | by policy |
| `APPROVAL_REVOKED` | yes, twice | `APPROVAL_REVOKED` | **never** |

`APPROVAL_REJECTED` and `APPROVAL_REVOKED` are permanently terminal for the node and may not
appear in `retryableCategories`. Publication rejects a graph that lists either. A refusal that a
policy can retry around is not a refusal.

`APPROVAL_EXPIRED` is permitted in `retryableCategories`. It is **not** retryable by default: a
graph that wants an expired approval re-requested must say so, because silently re-prompting on
every consequential action is its own kind of nuisance.

### 2. Retrying an expired approval means re-requesting, never re-executing

When a node fails with `APPROVAL_EXPIRED` and the category is retryable, the engine allocates a
new attempt per ADR-0021 §7 and that attempt performs exactly one operation: **create a new
`Approval` over the recorded subject of the expired one.**

The new `Approval`:

- carries a fresh `approvalId` and a fresh `expiresAt`
- copies `subjectHash` and `subjectRef` from the expired approval unchanged
- recomputes `renderingHash` from the subject, and the recomputed rendering must reproduce the
  recorded `renderingHash`

The node does not re-run. No tool is invoked. No model is called. The work that produced the
subject is not repeated, because repeating it could change what is being approved.

If the subject artifact is no longer retrievable, the attempt fails `DEFINITION_UNAVAILABLE` and
is not retryable. Approval subjects are classified `AUDIT` retention by ADR-0017 precisely so that
this does not happen, but an approval over a subject the platform can no longer show a human is
not an approval.

### 3. Expiry is bounded by the run, not only by the approval

Each re-request resets the approval clock, so an unbounded retry policy would let a run wait
forever, holding a workspace lease and a slot. Two bounds apply:

- the node's ordinary retry budget for the iteration (ADR-0021 §2) limits how many times an
  approval is re-requested
- when that budget is exhausted, the node fails `APPROVAL_EXPIRED` terminally and the run reaches
  a terminal state

A run may also declare `approvalDeadline`. Once passed, `APPROVAL_EXPIRED` stops being retryable
regardless of remaining budget. This is the bound that stops a forgotten run holding a lease
indefinitely.

### 4. Suspension is not failure, and the distinction is durable

A node waiting on an approval is `SUSPENDED`, and the run is `SUSPENDED`. Neither is a failure
state, neither consumes an attempt, and neither counts against the retry budget while waiting.

The attempt fails only at the moment expiry is observed. Time spent waiting for a human is
recorded separately from time spent executing, because a platform that reports a four-day p99
because someone was on holiday has learned nothing about itself. ADR-0015's duration metrics
exclude approval wait; §6 of `docs/architecture/evaluation.md` requires the same separation.

### 5. Revocation of a granted approval

An `Approval` that reaches `APPROVED` and is then revoked before the node consumes it fails the
node with `APPROVAL_REVOKED`, terminally, exactly as a rejection does. A human changed their mind,
which is a decision.

Revocation after the node has consumed the approval does not retroactively fail the node — the
action has already happened, and pretending otherwise would misrepresent what occurred. It is
audited, and any compensation is a workflow concern rather than a state-machine one.

---

## Consequences

Runs survive weekends. This is the whole point.

`retryableCategories` gains a validation rule at publication: `APPROVAL_REJECTED` and
`APPROVAL_REVOKED` are rejected, `APPROVAL_EXPIRED` is accepted. This is enforceable in the schema
for the two forbidden values and is stated as an invariant for the re-request semantics, which no
schema can express.

The graph engine gains a branch: an attempt whose predecessor failed `APPROVAL_EXPIRED` is a
re-request rather than an execution. This is the implementation risk of this ADR — an engine that
forgets the distinction re-runs the node and produces an approval over a subject that no human
selected. The invariant is testable: for any two attempts of the same `(runId, nodeId, iteration)`
where the earlier failed `APPROVAL_EXPIRED`, the `subjectHash` of the later approval equals the
earlier one.

Approval subjects must outlive their approvals, which ADR-0017's `AUDIT` tier already provides.

An operator can still be surprised: a run may re-request approval several times before failing.
The `Approval` records make the sequence visible, and `approvalDeadline` gives a way to bound it.

---

## Alternatives considered

**Make `APPROVAL_EXPIRED` terminal (status quo).** Simplest, and wrong for the deployment model.
Local-first means the approver has a life outside the run.

**Make it retryable by default.** Rejected. Consequential actions that silently re-prompt train
people to approve without reading, which is the failure mode the approval model exists to prevent.

**Never expire approvals.** Removes the problem by removing the bound. But an approval with no
expiry is a standing authorisation over a subject whose context has moved on, and a run holding a
lease indefinitely is a resource leak with no operator signal.

**Treat re-request as an ordinary retry that re-executes the node.** Rejected in §2. The subject
could change between attempts, and the approval record would then attest to something the human
did not see.
