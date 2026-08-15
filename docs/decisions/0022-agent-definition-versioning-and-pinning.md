# ADR-0022: Agent Definition, Versioning and Pinning

## Status

Accepted — 2026-08-15

Closes OQ-02 from `docs/contracts/v1-domain-contracts.md`. Gives `Agent` the treatment ADR-0008 §1
already gives `Graph`. Depends on ADR-0020 for content hashing and ADR-0019 for the name. Extends
the capability derivation chain of ADR-0014 §5 and the dispatch protocol of ADR-0004 §11.

---

## Context

`Agent` appears throughout the architecture as a first-class concept — the agent runtime executes
one, the graph references one by `agentId`, evaluation compares them — but it has no contract. In
the schemas it is a bare string:

```json
"agentId": { "type": "string", "minLength": 1 }
```

There is no `Agent` schema, no store, no version and no pin. `docs/architecture/agent-runtime.md`
§5 sketches the fields in prose; `agents/` is an empty directory with a stub README.

This produces a specific and serious hole. ADR-0008 §1 makes graphs immutable and
content-addressed, and a `GraphRun` pins `graphVersionHash` for its entire life, so that
"publishing a new definition never affects an in-flight run". That guarantee is void in practice,
because the graph pins only the *name* of the agent. Editing an agent's instructions changes the
behaviour of every in-flight run of an already-pinned graph.

The contract specification records four invariants (INV-22 through INV-25) about agent identity,
objectives, tools and output contracts. All four are listed as **unenforceable**, because there is
nothing to enforce them against.

Three capabilities depend on closing this:

- **Reproducibility.** "Re-run this exactly" is meaningless if the agent may have changed.
- **Evaluation.** `EVALUATION.md` requires comparing agents and harnesses, not only models. That
  comparison needs a stable identifier for "the agent that produced this result".
- **Incident analysis.** After a bad run, "what were the agent's instructions at the time?" must
  be answerable from durable state, not from whatever the file says today.

The instructions an agent carries are also a security boundary: ADR-0004's Security Impact makes
them platform-authored and forbids untrusted content from reaching them. An unversioned,
unpinned, mutable instruction set is a poor place to hold a security boundary.

---

## Decision

### 1. An Agent is an immutable, content-addressed definition

Agents get exactly the treatment graphs get in ADR-0008 §1. An `Agent` is declarative data —
never code — and is identified by two values:

```text
agentId            names the agent               e.g. repository-analyst
agentVersionHash   names the exact definition    sha256 of its canonical form (ADR-0020)
```

Editing an agent produces a new version. Definitions are never mutated in place, and a published
version is never deleted while any run references it (ADR-0017 §4 already ties retention to run
state rather than wall-clock).

### 2. Contents of an Agent

```text
schemaVersion
agentId
title, description

systemInstructions[]      platform-authored instruction blocks
                          ADR-0004: untrusted content must never appear here

defaultModelPolicy        selector or modelRef; a node may override
defaultBudgets            maxIterations, maxTokens, maxCostUnits
capabilityCeiling         allowedTools[], maxSideEffect, commandProfiles[]
outputContractStyle       STRUCTURED | FREEFORM
```

The `Agent` deliberately does **not** carry the objective or the output schema. Those are
per-node, live in the `Graph`, and are already pinned by `graphVersionHash`. An agent is reusable
behaviour; a node is a specific use of it. Duplicating the objective into the agent would create
two sources of truth for what a node is trying to do.

`capabilityCeiling` extends the derivation chain of ADR-0014 §5, which is monotonically
non-increasing at every step:

```text
platform policy ⊇ trust-level ceiling ⊇ registry record ⊇ agent ceiling ⊇ node request
```

An agent may only narrow what the registry permits, and a node may only narrow what the agent
permits. Nothing in the chain widens. Adding the agent as a link means a general-purpose agent
definition can be denied `IRREVERSIBLE` tools once, centrally, rather than in every node that
uses it.

### 3. A Graph references an agent by name; a GraphRun pins the version

```text
Graph      agentNode.agentId              which agent
GraphRun   agentPins[agentId] = hash      which exact version, resolved once at creation
```

Resolution happens exactly once, when the run is created, in the same durable write that pins
`graphVersionHash`. From that instant the run uses the pinned version for every node attempt,
every retry and every resume, for the rest of its life — including after a crash, a week-long
approval pause, or an edit to the agent in between.

This split is deliberate. Pinning the hash inside the graph would be marginally stronger but
would force a new graph version for every agent edit, so a typo fix in one agent would invalidate
every graph that mentions it. Resolving at run creation keeps graphs reusable while making runs
reproducible, and the guarantee that actually matters — *within a run, the agent never changes* —
is preserved either way.

### 4. Explicit pins for evaluation

Run creation accepts an optional `agentPins` override. Supplying it pins those agents to the
requested versions instead of the current ones.

This is what makes the comparison `EVALUATION.md` asks for possible: hold the graph, the context
bundles and the model constant, vary one agent version, and compare. Without an override the only
way to evaluate an agent change would be to publish it and hope nothing else moved.

An override may only *choose a version*. It cannot supply an inline definition, because an
unpublished, unhashed agent is not reproducible and would let a run execute instructions that
were never reviewed.

### 5. An unavailable definition fails the run, loudly and without retry

If a pinned `agentVersionHash` cannot be resolved at dispatch, the node attempt fails with a new
failure category:

```text
DEFINITION_UNAVAILABLE    a pinned Graph or Agent version cannot be resolved
```

It is **not retryable** and is not permitted in `retryPolicy.retryableCategories`. Retrying cannot
help: the definition is missing, and retrying would only obscure when it went missing.

The alternatives are worse in an instructive way. Falling back to the current version would
silently violate the pin — the exact failure this ADR exists to prevent — and would do so at the
moment least likely to be noticed. Proceeding without instructions would run an agent with no
system prompt and no capability ceiling.

The same category covers an unresolvable `graphVersionHash`, so operators have one signal for
"pinned definition missing" rather than two.

### 6. Storage and publication

Agents live in an `AgentStore`, alongside the graph store described in ADR-0007: immutable,
content-addressed, keyed by `agentVersionHash`, backed by SQLite locally. `agents/` in the
repository holds the authored definitions.

Publication validates the definition against the schema, computes `agentVersionHash` per
ADR-0020, and rejects a `capabilityCeiling` that exceeds platform policy — at publication, not at
dispatch, so an over-broad agent cannot be published and then discovered in production.

Graph publication additionally verifies that every referenced `agentId` resolves to at least one
published version, so a graph cannot be published against an agent that does not exist.

### 7. Agents are authored by humans

ADR-0008 §16 states that graphs are authored by humans and that no agent may author, mutate or
select a graph definition for a live run. The same rule applies to agent definitions, for the
same reason and more directly: an agent able to edit its own instructions or widen its own
capability ceiling has no meaningful ceiling.

An agent may propose a definition as a reviewable artifact. Publication is a human act.

---

## Alternatives Considered

**Pin `agentVersionHash` inside the graph node.** Strongest possible reproducibility, and
rejected for coupling: every agent edit would require a new version of every graph referencing it,
making a shared agent effectively unmaintainable. The within-run guarantee is identical under §3.

**Content-address the agent but resolve at each node dispatch.** Rejected outright — it is the
current broken behaviour with extra steps. An agent edited mid-run would take effect at the next
node, which is exactly what breaks reproducibility and in-flight determinism.

**Keep agents as configuration files with no version.** Rejected. It leaves INV-22 through INV-25
unenforceable, makes evaluation of agent changes impossible, and leaves a security boundary —
system instructions — in mutable, unattributable state.

**Store the full agent definition inside the `GraphRun`.** Reproducible, and rejected: it
duplicates definitions across every run, bloats operational state that ADR-0007 keeps small, and
loses the identity that makes "these two runs used the same agent" a cheap comparison rather than
a diff.

**Version agents with semver rather than a content hash.** Rejected for consistency and honesty.
`Graph`, `ContextBundle` and artifacts are all content-addressed; a hand-assigned version number
can be reused, edited or forgotten, and cannot detect an accidental modification. Semver remains
appropriate for tools, whose *interface* compatibility is the thing being communicated.

---

## Consequences

- A new `Agent` schema, a new store, and a publication step.
- `GraphRun` gains `agentPins`, a map from `agentId` to `agentVersionHash`, written at creation.
- `AgentExecutionRequest` gains `agentVersionHash`, so the runtime and its records name the exact
  definition executed.
- `failureCategory` gains `DEFINITION_UNAVAILABLE`, excluded from retryable categories.
- INV-22 through INV-25 become enforceable, and the "unenforceable today" row in the invariant
  traceability table disappears.
- Graph publication gains a referential check against the agent store.
- Evaluation can vary one agent version while holding everything else constant.
- Agent definitions become subject to review, because publishing one is now a distinct act with a
  durable, hashed result.

---

## Security / Operational Impact

`systemInstructions` is a security boundary. ADR-0004 requires instructions to be
platform-authored and untrusted content to reach the model only as data inside a context bundle.
Making the instruction set immutable, hashed, pinned per run and human-published means:

- an instruction change is attributable and reviewable rather than ambient;
- an in-flight run cannot have its instructions changed underneath it, which would otherwise be a
  practical way to alter the behaviour of a run already past its approval gate;
- after an incident, the exact instructions in force are recoverable from the pin.

`capabilityCeiling` adds a link to the authorization chain that is enforced at publication as well
as at grant-minting time. It can only narrow. It is not a substitute for the registry ceiling
(ADR-0014) or the grant (ADR-0005 §4); it is an additional upper bound, and the effective
authority remains the intersection of all of them.

`DEFINITION_UNAVAILABLE` is deliberately loud. A quiet fallback to the current definition would
be a straightforward way to get unreviewed instructions executed inside a run that a human already
approved.

---

## Follow-up

- Add `schemas/agent/agent.schema.json` and a published example.
- Add `agentPins` to `GraphRun` and `agentVersionHash` to `AgentExecutionRequest`.
- Add `DEFINITION_UNAVAILABLE` to `failureCategory`, and exclude it from retryable categories.
- Rewrite `agents/README.md` with the definition format and publication rules.
- Update `docs/architecture/agent-runtime.md` §5 to reference the schema instead of sketching it.
- Update `EVALUATION.md` with the agent-pin override as the mechanism for agent comparison.
- ADR-0014 §5 — the capability chain gains the agent ceiling.
