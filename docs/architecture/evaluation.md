# Evaluation

**Status:** Planned (model agreed, not yet implemented)
**Location:** Reads the control plane's durable records; runs outside the execution path
**Decisions:** [ADR-0020](../decisions/0020-canonical-serialisation-and-hashing.md),
[ADR-0021](../decisions/0021-noderun-identity-iteration-and-attempt.md),
[ADR-0022](../decisions/0022-agent-definition-versioning-and-pinning.md),
[ADR-0017](../decisions/0017-artifact-classification-retention-and-redaction.md),
[ADR-0008](../decisions/0008-graph-execution-semantics-and-durability.md)

This document describes what the V1 contracts must already record so that evaluation is possible
later. It does not specify an evaluation platform, a scoring service or a benchmark harness — those
are [ROADMAP](../../ROADMAP.md) M7 and beyond. The V1 obligation is narrower and harder to retrofit:
**a run that has finished must remain explicable and comparable after the fact.**

`EVALUATION.md` at the repository root states *what* the platform should eventually measure. This
document states *what execution must already record* for those measurements to be computable at all.

---

## 1. Evaluation is a reader, never a participant

Evaluation observes runs. It does not schedule them, does not influence node selection, does not
write to run state, and no execution path may block on it.

This is a boundary rather than a preference. An evaluator that can affect the run it measures cannot
be used to compare two configurations, because it becomes part of both configurations. It also
becomes a new failure mode on the critical path — a scoring bug would then be able to stall a
pull request.

The consequence for V1 is a constraint on the contracts, not on evaluation code: **everything an
evaluator needs must be durable in Cosmos DB or the artifact store, and none of it may need to be
recomputed by re-running the workflow.** If answering "why did this run cost twice as much as that
one?" requires re-execution, the record was incomplete.

---

## 2. Reproducibility is bounded, and the boundary is stated

Model inference is not deterministic, and V1 does not pretend otherwise. Three distinct properties
are often conflated; the platform commits to the first two and explicitly declines the third.

| Property | Meaning | V1 |
|---|---|---|
| **Identity reproducibility** | The same logical inputs produce the same identifiers and hashes | Guaranteed |
| **Replay** | The recorded run can be reconstructed and inspected exactly | Guaranteed |
| **Behavioural determinism** | Re-running produces the same model outputs | Not guaranteed |

Identity reproducibility comes from ADR-0020: the same logical object canonicalises to the same
bytes and therefore hashes identically in Java and Python. Replay comes from recording every input
and output at the boundary. Behavioural determinism is a property of providers, not of this
platform, and claiming it would be false.

What follows is that **evaluation compares recorded runs, and repeated measurement means repeated
runs rather than repeated scoring of one run.** A single run is an observation, not a measurement.

---

## 3. Run and node identity are the join key

Every evaluation record joins to execution through the identity of ADR-0021:

```text
runId
  └── nodeId
        └── iteration      the loop round (1-based)
              └── attempt  the retry within that round (1-based)
```

The four-part key is what makes the interesting questions answerable:

- *How often does the repair loop succeed on its second round?* — group by `iteration`.
- *How much of our spend is retries rather than work?* — sum cost where `attempt > 1`.
- *Which failures are transient and which are real?* — compare `lastFailureCategory` across
  attempts of the same `iteration`.

A three-part key collapses the first and second questions into each other, which is precisely why
ADR-0021 separated them. Any evaluation record that references execution carries all four parts,
never a prefix.

`GraphRun` additionally carries `graphVersionHash` and `agentPins`. A comparison that does not hold
these fixed is not comparing what it thinks it is comparing.

---

## 4. What must be durable for evaluation to be possible

The following already exist in the V1 contracts. This section states the evaluation reason each one
exists, so that a future change which weakens one is recognisable as a change to evaluation rather
than a tidy-up.

### 4.1 Model execution records

Per model invocation, keyed by the four-part identity:

- resolved provider, model identifier and provider-side version
- the selector that was requested, alongside what it resolved to — a shift in resolution is
  otherwise indistinguishable from a shift in model behaviour
- prompt and completion, stored as artifacts (`PROMPT`, `COMPLETION`) rather than inline
- input, output and, where reported, reasoning token counts
- cost units, latency, and whether the response was truncated
- the failure and retry history of the call itself

Token counts and cost are recorded as reported by the gateway at the time of the call. Recomputing
cost later from a price list produces a number that never corresponded to anything.

### 4.2 Tool execution records

Per `ToolRequest`/`ToolResult` pair:

- `toolId`, `toolVersion`, `sideEffectClass`
- the `idempotencyKey` of ADR-0021 §5, which is what distinguishes a suppressed duplicate from work
  that never happened
- input and output as artifacts where they exceed the inline threshold
- status — including `AWAITING_APPROVAL`, which is a first-class outcome and not a failure
- duration, and the capability grant under which it ran

Tool effectiveness is one of the harder dimensions in `EVALUATION.md`, and it is unmeasurable
without per-call outcomes. An aggregate success count cannot distinguish a tool that is rarely
useful from one that is frequently misused.

### 4.3 Checkpoints

`Checkpoint` records `(afterNodeId, afterIteration, afterAttempt)` and a `workspaceStateRef` that
reconstructs every repository from `(repoRef, baseSha, ordered patch series)`.

For evaluation this is what makes the *intermediate* states of a run inspectable, not merely its
outcome. "The change was correct at round two and regressed at round three" is a checkpoint
question. Storing only the final workspace answers outcome questions and no process questions.

### 4.4 Artifacts and their classification

ADR-0017 classifies every artifact at write time with a `retentionTier`. Two tiers are load-bearing
here:

- `REPRODUCIBILITY` — patches, prompts, completions, context bundles. Retained long enough to
  re-examine a run after the fact.
- `AUDIT` — approval subjects and audit exports, retained independently on the audit schedule.

`EPHEMERAL` and `RUN_LIFECYCLE` artifacts will not be there when an evaluator looks. Classifying an
artifact into a tier that expires before evaluation runs is the quiet way to make a run
unevaluable, and it will not be noticed until someone asks a question months later.

### 4.5 Context provenance

`ContextBundle` is content-addressed and carries, per item, its source, the retrieval method and a
relevance score, along with what was dropped when the budget bound.

Context quality is an explicit evaluation dimension, and it cannot be assessed from the assembled
prompt alone: the prompt shows what was included and is silent about what was available and
rejected. `NodeRun.contextBundleRef` is the join back to execution.

### 4.6 Agent version references

Per ADR-0022, `GraphRun.agentPins` resolves each `agentId` to an `agentVersionHash` once, at run
creation, and the run uses that definition throughout.

This is the difference between "agent X improved" and "we changed agent X and the runs before and
after are not comparable". An evaluation that references an agent by `agentId` alone has recorded
a moving target. Every evaluation record therefore references `(agentId, agentVersionHash)`.

---

## 5. Evaluation inputs

An evaluation case is a durable definition, versioned and content-addressed in the same way as a
`Graph`, comprising:

- the task — for V1, a work item reference or a fixture equivalent to one
- the repositories and their exact commits, so the starting state is fixed
- the graph and its version
- the agent pins to be used
- the model policy under test
- deterministic verification: the commands whose exit status decides success, and the expected
  outcome
- budget and deadline bounds

Deterministic verification is deliberately load-bearing. Where a build, a test suite or a static
check can decide correctness, it decides correctness. Model-graded judgement is a fallback for
dimensions with no mechanical check, is recorded as such, and never silently replaces a check that
exists. `PRINCIPLES.md` states this preference; the point here is that the *case definition* must
make which one was used visible in the result.

---

## 6. Evaluation outputs

An evaluation result references the `GraphRun` it measured and records:

- the case identity and version, and the run identity
- per-dimension outcomes: task completion, deterministic verification, cost, latency, recovery
  behaviour, security compliance
- the derived aggregates that motivated the recording in §4 — retry ratio, loop rounds to success,
  tool call outcomes, approval waits distinguished from execution time
- the configuration that was fixed: `graphVersionHash`, `agentPins`, model policy resolution
- artifacts produced by the evaluation itself, classified `EVALUATION`

Results are immutable. Re-evaluating produces a new result rather than updating an old one, for the
same reason a retry produces a new `NodeRun`: the sequence is the evidence.

---

## 7. Comparison

Comparison across runs is the reason for everything above, and it is the part V1 does not build.
What V1 must not do is make it impossible.

A comparison is valid only when the configuration difference is the single dimension under study.
The recorded fields make the difference computable rather than assumed:

| Comparing | Held fixed | Varied |
|---|---|---|
| Two models | graph version, agent pins, case, repositories | model policy |
| Two agent versions | graph version, model policy, case | one `agentVersionHash` |
| Two graph versions | agent pins, model policy, case | `graphVersionHash` |
| Harness changes | everything in the case | platform version |

The last row is the one that motivates the platform's existence, and the one most easily lost. When
graph, agent, tool and context definitions are versioned and pinned, a change in outcome is
attributable to the harness change. When they are not, the platform can only report that things got
better or worse without saying why — which is the failure mode `EVALUATION.md` opens by warning
about.

Because model inference is non-deterministic (§2), comparison over a single pair of runs is not
evidence. Repeated runs and a stated variance are required before a difference is reported as real.
V1 records enough to compute this later; it does not perform the statistics.

---

## 8. What V1 does not include

Not in V1, and not blocking M3:

- an evaluation runner, scheduler or benchmark suite
- a scoring service or model-graded judging
- a results UI or dashboards
- regression gates in CI
- a benchmark corpus

These are ROADMAP M7+. The `EvaluationCase` and `EvaluationResult` contracts are deliberately
described here in prose and **not** frozen as V1 schemas: their fields depend on dimensions that
have not yet been exercised, and freezing them now would be inventing a contract ahead of its
requirement.

The V1 commitment is only this: execution records the identity, provenance and pinning that make
those contracts writable later, so that the first evaluation does not require re-instrumenting the
platform.

---

## 9. Decisions deferred to M7

Two questions are genuinely undecided and are recorded here so that their absence reads as a
deferral rather than an oversight. Neither is a V1 contract question, and neither blocks M3.

- **Evaluation storage and lifecycle.** Whether `EvaluationResult` documents live in the
  operational Cosmos DB containers or in a store of their own, and how long they are retained.
  The answer depends on volume and query shape, neither of which is known until an evaluation
  suite exists. Deciding now would be sizing a container for a workload nobody has run.
- **The V1 benchmark corpus.** Which repositories and tasks form the initial set, and whether they
  are synthetic fixtures or real work items. Fixtures are reproducible and unrepresentative; real
  work items are representative and move underneath the measurement. This is a trade-off worth
  making deliberately, with evidence, rather than by default.

Both must be resolved before the first evaluation runs. Neither changes a V1 contract, which is
why they are deferred rather than forced.

Related open questions tracked in [the V1 contract specification](../contracts/v1-domain-contracts.md):
**OQ-11** (per-integration reconciliation procedures) affects the completeness of tool execution
records for external writes, and should be resolved before external-write tools are evaluated.
