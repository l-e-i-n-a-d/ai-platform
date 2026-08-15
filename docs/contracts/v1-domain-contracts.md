# V1 Domain Contract Specification

## Status

**Proposed — 2026-08-15.** Not yet accepted. No component implements this.

This document specifies the V1 domain contracts implied by the eighteen accepted ADRs in
[`docs/decisions/`](../decisions/README.md). It is a *derivation*, not a new set of decisions:
where it states something the ADRs already decided, the ADR governs. Where it had to choose
something the ADRs left open, it says so explicitly and lists the choice in
[§10 Open questions](#10-open-questions-requiring-an-architectural-decision) rather than
quietly settling it.

Nothing here should surprise a reader of the ADRs. If something does, that is a finding.

---

## 1. Purpose and scope

The ADRs decide *why*. The JSON Schemas in [`schemas/`](../../schemas/README.md) fix *shape*.
Neither states the domain model: what each entity is responsible for, what states it moves
through, what may reference what, and which invariants must hold across entities.

That gap is where two implementations in two languages diverge. The control plane in Java and
the agent runtime in Python can both conform to every schema and still disagree about whether
a loop body's second iteration is a new attempt, or who owns a workspace's lifetime.

This document closes that gap for the sixteen V1 entities.

### What this document is not

- Not an API specification. Endpoint shapes are in ADR-0004 §11.
- Not a persistence schema. The storage mapping in §7 is indicative; ADR-0007 governs.
- Not an implementation plan. Sequencing is in `ROADMAP.md`.
- Not a licence to start coding. Several open questions in §10 change the data model.

### One correction to the stated premise

The V1 operational store is **SQLite**, not Cosmos DB. ADR-0007 decided this: Cosmos DB and
Blob Storage remain the documented target for a hosted multi-user deployment, but they are not
V1 components, and their adoption is coupled to reopening the identity question. The persistence
port is deliberately restricted to the *intersection* of an embedded store and Cosmos DB, so
this document describes entities in terms that map to both.

Where the older goal list said "Cosmos DB is the operational persistence layer", read it as
"the persistence port is Cosmos-shaped, and V1 implements it with SQLite".

---

## 2. Naming reconciliation

The domain vocabulary requested for this specification differs from the names currently used in
the ADRs and schemas. The mapping below is exact; §10 OQ-01 asks which set should win.

| This document | ADR / schema name | Artifact |
|---|---|---|
| `Graph` | GraphDefinition | [`schemas/graph/graph-definition.schema.json`](../../schemas/graph/graph-definition.schema.json) |
| `GraphRun` | Run | [`schemas/graph/run.schema.json`](../../schemas/graph/run.schema.json) |
| `GraphNode` | node (embedded in the definition) | `graph-definition.schema.json#/$defs/node` |
| `NodeRun` | NodeExecution | [`schemas/graph/node-execution.schema.json`](../../schemas/graph/node-execution.schema.json) |
| `Agent` | agent definition | **no schema** — see §5.5 and OQ-02 |
| `Tool` | ToolDescriptor | [`schemas/tools/tool-descriptor.schema.json`](../../schemas/tools/tool-descriptor.schema.json) |
| `ToolRequest` | — | **no schema** — see §5.7 and OQ-03 |
| `ToolResult` | — | **no schema** — see §5.8 and OQ-03 |
| `ContextBundle` | ContextBundle | [`schemas/context/context-bundle.schema.json`](../../schemas/context/context-bundle.schema.json) |
| `ModelRequest` | ModelRequest | [`schemas/model/model-request.schema.json`](../../schemas/model/model-request.schema.json) |
| `ModelResponse` | ModelResponse | [`schemas/model/model-response.schema.json`](../../schemas/model/model-response.schema.json) |
| `ExecutionRequest` | ExecutionRequest | [`schemas/execution/execution-request.schema.json`](../../schemas/execution/execution-request.schema.json) |
| `ExecutionResult` | ExecutionResult | [`schemas/execution/execution-result.schema.json`](../../schemas/execution/execution-result.schema.json) |
| `Checkpoint` | Checkpoint | [`schemas/graph/checkpoint.schema.json`](../../schemas/graph/checkpoint.schema.json) |
| `Approval` | ApprovalRecord | [`schemas/approval/approval-record.schema.json`](../../schemas/approval/approval-record.schema.json) |
| `Workspace` | WorkspaceSpec (creation input only) | [`schemas/execution/workspace-spec.schema.json`](../../schemas/execution/workspace-spec.schema.json) |

Three entities in this list have **no contract at all** today: `Agent`, `ToolRequest` and
`ToolResult`. A fourth, `Workspace`, has an input specification but no durable record. These are
the substantive gaps this exercise surfaced, and they are addressed in §5.

---

## 3. Entity map

Solid arrows are references held in durable state. `1..*` reads "one to many".

```text
                     Repository Registry
                     RepositoryRecord (ADR-0014)
                              |
                              | capability ceiling, command profiles, context policy
                              v
   Graph  (immutable, content-addressed)
     |  1..* GraphNode  (embedded, not independently addressable)
     |
     |  pinned by graphVersionHash
     v
   GraphRun ------------------ 1 ----------------> Workspace
     |   |   |                                        |
     |   |   +--- 1..* Checkpoint                     | one per run, exclusively leased
     |   |                                            v
     |   +------- 1..* Approval             ExecutionRequest -> ExecutionResult
     |                                            ^
     |  1..* NodeRun                              | via execution interface
     |        |                                   |
     |        +--- 0..1 ContextBundle             |
     |        +--- 0..1 CapabilityGrant           |
     |        |                                   |
     |        +--- 0..* ModelInvocation ---> ModelRequest / ModelResponse
     |        |
     |        +--- 0..* ToolInvocation ----> ToolRequest / ToolResult
     |                       |                       |
     |                       |                       +--> integration client (Jira/GitHub/Confluence)
     |                       |                       +--> execution interface (workspace)
     |                       v
     |                  AuditEntry (append-only, hash-chained)
     v
   ArtifactRef  (content-addressed; every large payload above)
```

`Agent` sits outside this graph deliberately: it is *configuration referenced by* a GraphNode,
not a runtime entity. It has no run-scoped state. See §5.5.

---

## 4. Conventions

### 4.1 Identifiers

| Kind | Form | Assigned by | Stability |
|---|---|---|---|
| `runId` | `run_<ULID>` | control plane at run creation | permanent |
| `nodeId` | author-chosen slug, unique within a Graph | graph author | permanent per graph version |
| `graphVersionHash` | SHA-256 of canonical definition | derived | content-addressed |
| `bundleRef` | SHA-256 of canonical bundle | derived | content-addressed |
| `workspaceId` | opaque token | executor | run-scoped |
| `executionHandle` | opaque token | executor | execution-scoped |
| `grantId` | opaque | control plane at attempt dispatch | attempt-scoped |
| `toolCallId` | provider-supplied, normalised | model gateway | invocation-scoped |
| `idempotencyKey` | derived, see §6.3 | tool layer | logical-operation-scoped |

**Opaque means opaque.** `workspaceId` and `executionHandle` carry no parseable structure.
ADR-0003 §3 states that anything parsing a workspace ID is a defect, because path-derived IDs
are the specific shortcut that ends executor portability.

ULIDs rather than UUIDs for `runId` because lexicographic ordering by creation time is useful in
a single-partition store and costs nothing.

### 4.2 Time

All timestamps are RFC 3339 UTC. **Wall-clock time is never used for ordering.** Ordering within
a run uses monotonic sequence numbers (`Checkpoint.sequence`, `AuditEntry.sequence`), because a
laptop's clock can move backwards across a suspend/resume — which is the normal case here, not
an edge case.

### 4.3 Hashing and canonicalisation

Content addressing requires one canonical serialisation. V1 uses JSON with lexicographically
sorted object keys, no insignificant whitespace, and UTF-8 encoding. Every hash is SHA-256,
lowercase hex.

This matters more than it looks: `graphVersionHash`, `bundleRef`, `subjectHash` and the audit
hash chain all depend on two languages producing byte-identical serialisations. It needs a
cross-language conformance test, not an assumption. (OQ-09.)

### 4.4 Versioning

| Entity | Versioning |
|---|---|
| Graph | content hash; immutable; runs pin |
| Tool | semantic version; descriptors immutable per version |
| Agent | semantic version; **pinning unresolved — OQ-02** |
| Protocol (ADR-0004) | `protocolVersion`, fail-fast at startup |
| Schemas | `v1` path segment |
| RepositoryRecord | `configHash` recorded on grants and audit entries |

### 4.5 Correlation

Every entity that crosses a component boundary carries `correlation`:

```text
runId, nodeId, attempt, agentId?, traceparent?
```

**These identifiers are forbidden as metric labels** (ADR-0015 §7). They belong on spans, logs
and durable records, never on a Prometheus series, because their cardinality is unbounded and
the failure is silent — the metric works fine in testing and takes the collector down in month
four.

---

## 5. Entity contracts

Each entity below states responsibility, lifecycle, key fields, relationships and invariants.
Invariants are numbered `INV-nn` and collected in §8.

### 5.1 Graph

**Responsibility.** Declare a workflow as data: nodes, edges, retry policy, variables. It is the
unit of review and the unit of reproducibility.

**Lifecycle.** Authored by a human → validated → canonicalised → hashed → stored immutably.
There is no update and no delete; editing produces a new version with a new hash. A version is
never garbage-collected while any run pins it.

```text
(draft, outside the platform)  ->  VALIDATED  ->  PUBLISHED
                                                    |
                                       (immutable, retained while pinned)
```

**Key fields.** `graphId`, `graphVersionHash`, `entryNodeId`, `variables`, `defaultRetryPolicy`,
`nodes[]`, `edges[]`.

**Relationships.** Contains GraphNodes (embedded). Referenced by GraphRun via
`graphVersionHash`. References Agents by `agentId` and Tools by `(toolId, toolVersion)`.

**Invariants.**

- **INV-01** A Graph is immutable once published. Its identity *is* its content hash.
- **INV-02** A Graph contains no executable code. Only the restricted condition language of
  ADR-0008 §4 appears in edges and loop exits.
- **INV-03** Outgoing edge conditions from any node must be **total** — some edge must match for
  every reachable state — so that evaluation never strands a run.
- **INV-04** Every `toolId` and `agentId` referenced must resolve at publish time. A graph that
  names a tool that does not exist is rejected at publication, not at 02:00 on node seven.
- **INV-05** No agent may author, mutate or select a Graph for a live run (ADR-0008 §16). An
  agent may *propose* one as a reviewable artifact.
- **INV-06** The node taxonomy is closed. Adding a node type requires an ADR.

### 5.2 GraphNode

**Responsibility.** Declare one unit of work and the authority it may exercise.

**Lifecycle.** None of its own. A GraphNode is a value embedded in a Graph, and shares that
Graph's immutability. It is *not* independently addressable or storable.

This is deliberate. A separately-stored node table invites mutation of one node under a pinned
graph, which would silently break INV-01.

**Key fields.** `id`, `type` ∈ {`context`, `agent`, `tool`, `approval`, `decision`, `loop`,
`terminal`}, `retryPolicy?`, `timeoutMs?`, plus type-specific fields.

The security-relevant field is `requestedCapabilities` on an `agent` node: `allowedTools`,
`maxSideEffect`, `commandProfiles`.

**Relationships.** Belongs to exactly one Graph version. Produces zero or more NodeRuns per
GraphRun — *zero* if skipped, *more than one* under retry, and (unresolved, OQ-04) more than one
under loop iteration.

**Invariants.**

- **INV-07** `requestedCapabilities` **requests**; it never grants. The effective grant is the
  intersection with the registry ceiling and platform policy (ADR-0014 §5). A node may only
  narrow.
- **INV-08** Every node with a model in the loop (`agent`) declares an `outputSchema`.
  Transitions are evaluated only on validated output (ADR-0008 §5).
- **INV-09** A `loop` node declares `maxIterations` and a deterministic `exitCondition`. A model
  may not decide that a loop is finished (ADR-0008 §12).
- **INV-10** A `tool` node names exactly one tool, fixed in the definition. It cannot select a
  tool at runtime.

### 5.3 GraphRun

**Responsibility.** Own the durable execution of one Graph version. It is the unit of
orchestration, the unit of leasing, the unit of cancellation, and the partition key for
essentially all run-scoped state.

**Lifecycle.**

```text
                +--------------------------------------------------+
                v                                                  |
  PENDING --> RUNNING --+--> AWAITING_APPROVAL --------------------+
                        +--> AWAITING_RETRY -----------------------+
                        +--> SUSPENDED  (lease lost) --------------+
                        |
                        +--> SUCCEEDED   terminal
                        +--> FAILED      terminal
                        +--> CANCELLED   terminal
                        \--> TIMED_OUT   terminal
```

`SUSPENDED` is the **normal** consequence of closing a laptop. It is an expected, recoverable
state and must not be presented to a developer as a failure. Resuming it is an explicit operator
action, not an automatic retry, because automatic resumption of a run that may have been
deliberately abandoned is worse than asking.

**Key fields.** `runId`, `version` (CAS token), `graphId`, `graphVersionHash`, `status`, `epoch`,
`lease`, `workItemRef?`, `repositories[]`, `workspaceId?`, `variables`,
`cancellationRequested`, `currentNodeId?`, `latestCheckpointId?`, `initiatedBy`, timestamps,
`failure?`.

**Relationships.** Pins one Graph version. Owns 0..1 Workspace, 1..* NodeRuns, 0..* Checkpoints,
0..* Approvals, and all AuditEntries carrying its `runId`.

**Invariants.**

- **INV-11** A GraphRun pins `graphVersionHash` at creation and executes against that definition
  for its entire life. There is no in-flight migration (ADR-0008 §2).
- **INV-12** Only the holder of the run's lease may transition its state (ADR-0008 §8). This is
  a security control, not only a correctness one: two orchestrators would produce duplicate
  external side effects.
- **INV-13** Terminal states are immutable. No transition leaves `SUCCEEDED`, `FAILED`,
  `CANCELLED` or `TIMED_OUT`.
- **INV-14** Every write is guarded by both the expected `version` (CAS) and a lease check.
- **INV-15** A run's `epoch` is bumped on lease takeover and on cancellation, so a stale
  orchestrator can detect that it no longer speaks for this run.
- **INV-16** `initiatedBy` is recorded at creation and is carried into every AuditEntry, so an
  action performed by an agent six nodes later remains attributable to a person.

### 5.4 NodeRun

**Responsibility.** Record one attempt at one GraphNode. It is the unit of retry, the unit of
capability granting, and the finest granularity at which the platform resumes.

**Lifecycle.**

```text
PENDING -> SCHEDULED -> RUNNING -+-> SUCCEEDED
                                 +-> AWAITING_APPROVAL -> RUNNING
                                 +-> AWAITING_RETRY -> SCHEDULED (attempt + 1)
                                 +-> FAILED
                                 +-> SKIPPED
                                 +-> CANCELLED
                                 \-> INDETERMINATE
```

`INDETERMINATE` is the state most workflow engines omit and then need. It is entered when a
write-ahead intent record exists with no matching outcome: a side effect **may or may not** have
occurred. It is never auto-retried. It is resolved by reconciliation against the external
system, or escalated to a human.

**Key fields.** `runId`, `nodeId`, `attempt`, `version`, `nodeType`, `status`,
`capabilityGrantId?`, `contextBundleRef?`, `claimedOutput?`, `validatedOutput?`, `outputValid?`,
`iterations?`, `stopReason?`, `failure?`, `nextAttemptAt?`, `lastFailureCategory?`,
`indeterminateReason?`, `deadline?`, `startedAt?`, `endedAt?`.

**Relationships.** Belongs to one GraphRun. References one GraphNode by `nodeId`. Owns 0..1
CapabilityGrant, 0..1 ContextBundle reference, 0..* ModelInvocations, 0..* ToolInvocations.

**Invariants.**

- **INV-17** Identity is `(runId, nodeId, attempt)`. Records are **never overwritten** by a
  retry; each attempt keeps its own record, because evaluation depends on seeing how failures
  evolved. *(This identity is insufficient for loop bodies — see OQ-04.)*
- **INV-18** `claimedOutput` is never authoritative. The control plane validates it against the
  node's declared `outputSchema` before any transition is evaluated (ADR-0004 §9). Only
  `validatedOutput` may be referenced by an edge condition.
- **INV-19** A retry receives a **fresh** CapabilityGrant. A failed attempt leaves no residual
  authority behind.
- **INV-20** `status = INDETERMINATE` requires `indeterminateReason`, and must be visible to an
  operator. A silently swallowed indeterminate side effect is worse than a loud failure.
- **INV-21** The agent runtime never sets NodeRun status. It returns a claimed result; the
  control plane decides.

### 5.5 Agent

> **This entity has no contract in the repository today.** ADR-0004 defines the *protocol* for
> invoking an agent and `docs/architecture/agent-runtime.md` §5 sketches the definition, but
> there is no schema, no store and no versioning rule. What follows is the minimum coherent
> contract; OQ-02 asks for the decision that would make it binding.

**Responsibility.** Declare a constrained AI execution unit as **configuration, not code**:
identity, objective, platform-authored instructions, permitted tools, output contract, model
policy and budgets.

**Lifecycle.** Authored by a human → versioned → referenced by GraphNodes. Like a Graph, an
Agent definition should be immutable per version. Unlike a Graph, nothing currently pins it.

**Key fields.** `agentId`, `version`, `objective`, `instructions[]`, `toolIds[]`, `outputSchema`,
`modelPolicy`, `budgets`.

**Relationships.** Referenced by `agent` GraphNodes. Materialised into an AgentExecutionRequest
per NodeRun. Has **no run-scoped state** — the runtime is stateless and freely restartable
(ADR-0004 §2).

**Invariants.**

- **INV-22** `instructions` are platform-authored. Untrusted content — repository files, issue
  descriptions, page bodies, PR comments — reaches the model through the ContextBundle as
  *data*, never through this field (ADR-0004 Security Impact).
- **INV-23** `toolIds` is a request, intersected with the node's CapabilityGrant. An agent
  definition cannot widen authority.
- **INV-24** Agents hold no credentials and no durable state.
- **INV-25** *(Proposed, currently unenforced.)* A GraphRun must pin the agent definition
  version alongside `graphVersionHash`. **Without this, INV-11 is not achieved**: a graph is
  pinned but the agent it invokes can change underneath it, so two runs of the "same" pinned
  definition are not reproducible. See OQ-02 — this is the most consequential gap in this
  document.

### 5.6 Tool

**Responsibility.** Declare, as data, one capability an agent may exercise: its input contract,
its output contract, its side-effect class, its idempotency semantics and its approval policy.

**Lifecycle.** Authored → versioned → registered. Descriptors are immutable per version. A tool
is deprecated by publishing a new version and ceasing to reference the old one; existing pinned
graphs continue to name the old version.

**Key fields.** `id`, `version`, `title`, `description`, `inputSchema`, `outputSchema`,
`sideEffectClass`, `scopeRequirements`, `idempotency`, `approvalPolicy`, `timeoutMs`, `costHint`.

**Relationships.** Referenced by GraphNodes, by CapabilityGrants and by AgentExecutionRequests
(as descriptors only). Implemented by the control-plane tool layer; **never** by the agent
runtime.

**Invariants.**

- **INV-26** `inputSchema` is closed (`additionalProperties: false`). Undeclared fields are
  rejected, not ignored, so a model cannot smuggle a field past validation into an integration
  client.
- **INV-27** `sideEffectClass` is declared on the tool and is **not negotiable per call**. A
  grant may narrow the permitted classes; nothing may widen them.
- **INV-28** `IRREVERSIBLE` always requires human approval, regardless of graph or grant.
- **INV-29** `EXTERNAL_WRITE` and `IRREVERSIBLE` require an idempotency key (`NATURAL` or
  `KEYED`).
- **INV-30** No tool accepts a shell string or a free-form argv array from a model. Command
  execution is reachable only via `workspace.run_profile(profileId, parameters)` against a
  named, repository-declared CommandProfile.
- **INV-31** The agent runtime holds descriptors, never implementations, and has neither
  credentials nor egress to invoke one by another path.

### 5.7 ToolRequest

> **No contract exists today.** ADR-0005 §7 defines the *pipeline* and ADR-0004 §11 names the
> callback endpoint, but the message body is unspecified. OQ-03.

**Responsibility.** Carry one authorization-and-execution request from the agent runtime to the
control-plane tool layer. It is the **only** channel by which an agent causes an effect.

**Lifecycle.** Created per model tool-call → authorized → possibly suspended for approval →
dispatched → resolved. It is a message, not a stored entity; the durable record of it is a
ToolInvocation (§7).

**Proposed key fields.**

```text
protocolVersion
callbackToken        resolves to the CapabilityGrant; the runtime never sees the grant itself
toolCallId           normalised from the provider's tool-use protocol; correlates the result
                     back into the model conversation
toolId, toolVersion
input                validated against the tool's closed inputSchema
correlation          runId, nodeId, attempt, traceparent
```

**Relationships.** Originates from a ModelResponse `toolCall`. Resolves to exactly one
ToolResult. Produces exactly one AuditEntry whether allowed or denied. May produce an
ExecutionRequest (workspace tools) or an integration call (Jira/GitHub/Confluence).

**Invariants.**

- **INV-32** Authority is resolved from `callbackToken`, never from anything in the request
  body. The runtime cannot widen its own authority by asking differently.
- **INV-33** Every request passes the full ADR-0005 §7 pipeline in order: resolve grant →
  resolve descriptor → validate input → check scope → check budget and denial breaker →
  approval gate → idempotency check → write-ahead intent → dispatch → outcome + audit.
- **INV-34** `EXTERNAL_WRITE` and `IRREVERSIBLE` requests write a **write-ahead intent record
  before dispatch** and an outcome record after. An intent with no outcome is exactly what a
  crash mid-side-effect looks like, and is the only way to distinguish "it did not happen" from
  "it may have happened".
- **INV-35** A request naming a tool absent from the grant is denied without contacting anything.

### 5.8 ToolResult

> **No contract exists today.** OQ-03.

**Responsibility.** Return the outcome of a ToolRequest to the agent loop as **data**.

**Lifecycle.** Produced once per ToolRequest. Recorded durably before being returned.

**Proposed key fields.**

```text
toolCallId
outcome              ALLOWED | DENIED | INDETERMINATE
status               SUCCEEDED | FAILED           (when ALLOWED)
denialReason         NOT_AUTHORIZED | UNKNOWN_TOOL | INVALID_INPUT | OUT_OF_SCOPE
                     | BUDGET_EXHAUSTED | APPROVAL_REQUIRED | APPROVAL_REJECTED
output               validated against the tool's outputSchema
outputRef            ArtifactRef when the payload exceeds the inline threshold
outputPreview        bounded inline preview
externalRefs[]       PR number, commit SHA, issue key, page version
idempotencyOutcome   EXECUTED | DEDUPLICATED
```

**Invariants.**

- **INV-36** **A denial is a structured result, not a transport error.** The model can then
  adapt rather than the node collapsing. Every denial is simultaneously an audit event.
- **INV-37** Results are **untrusted content**. They are inserted into model context as data,
  are never interpreted as platform directives, and can never alter a grant, a budget, an
  approval or a graph transition.
- **INV-38** Results above the size threshold are offloaded to the artifact store and passed by
  reference with a truncated preview. This is a context-budget control as much as a storage one.
- **INV-39** Repeated denials consume the grant's `maxDenials` budget; exhausting it trips the
  circuit breaker and fails the node with `TOOL_DENIED`. This surfaces a wrong grant instead of
  letting a model burn its budget rediscovering that it may not do something.
- **INV-40** A ToolRequest whose prior intent exists without an outcome resolves to
  `INDETERMINATE` and is **not re-executed**.

### 5.9 ContextBundle

**Responsibility.** Be the immutable, content-addressed, fully-attributed set of material an
agent was given — and the record of what it was *not* given, and why.

**Lifecycle.** Assembled by a `context` node → canonicalised → hashed → stored → referenced by
NodeRuns. Never mutated; a refresh produces a new bundle whose `supersedes` names the previous
one.

**Key fields.** `bundleRef`, `runId`, `nodeId`, `createdAt`, `supersedes?`, `budget{limit, used,
policyId}`, `pins{repositories[], issues[], pages[]}`, `items[]`, `excluded[]`.

Per item: `sourceSystem`, `sourceId`, `revision`, `retrievedAt`, `retrievedAs`, `strategy`,
`relevanceScore`, `tokenCount`, `inclusionReason`, `trustClass`, `contentRef`.

**Relationships.** Produced by the context engine. Referenced by NodeRun and Checkpoint. Fetched
by the agent runtime by reference over the callback channel, never inlined into the request.

**Invariants.**

- **INV-41** Every item records **why** it was included and **how** it was found. The platform
  must be able to explain why an agent saw a given piece of content.
- **INV-42** `excluded[]` is populated, not dropped. Without it, a missing-context failure is
  indistinguishable from a reasoning failure — which is the single most common way an AI
  platform misdiagnoses itself.
- **INV-43** **Retrieval identity ≠ action identity** (ADR-0012 §5). `retrievedAs` records the
  developer credential used for retrieval. The GitHub App *acts*; it does not *read* on the
  developer's behalf. Retrieving with the App's broader reach would let the platform surface
  material the requesting developer cannot see.
- **INV-44** Every item is `trustClass: UNTRUSTED` unless platform-authored, and untrusted items
  are never rendered where the protocol expects a platform-controlled field.
- **INV-45** `pins` fix exact revisions. A re-run against a moved branch or an edited page is a
  different experiment and must be visible as one.
- **INV-46** `budget.used ≤ budget.limit`. Eviction is recorded in `excluded[]` with reason
  `EVICTED_BUDGET`.

### 5.10 ModelRequest

**Responsibility.** Express a model call in **provider-neutral** terms.

**Lifecycle.** Constructed per agent-loop iteration → submitted to the gateway → translated to a
provider call. Not durable in itself; the durable record is a ModelInvocation, with prompt and
completion offloaded to artifacts.

**Key fields.** `modelRef`, `system[]`, `messages[]`, `tools[]`, `toolChoice`, `outputContract?`,
`params`, `budgets`, `providerOptions?`, `correlation`.

**Relationships.** Issued by the agent runtime via callback. Handled by the model gateway.
Produces one ModelResponse.

**Invariants.**

- **INV-47** `modelRef` is a **logical name resolved by the gateway**, never a provider model id.
  Callers never name a concrete provider model.
- **INV-48** Provider-specific SDK calls exist only behind the gateway. Nothing else imports a
  provider SDK — the agent runtime is explicitly forbidden from doing so.
- **INV-49** **The gateway does not run the tool-calling loop.** It normalises tool calls into
  requests; the tool layer decides and executes. Most agent frameworks put the loop here, so
  this is the default that must be actively resisted.
- **INV-50** `providerOptions` is a narrow, explicitly-labelled escape hatch. Anything placed
  there is by definition not portable, and the field name says so.
- **INV-51** `system[]` is platform-authored and never assembled from retrieved content.
- **INV-52** Credentials never appear in a ModelRequest. The gateway holds them; the runtime
  never has them.
- **INV-87** The assistant's own tool-call turn is representable in `messages[]`, via a
  self-contained `TOOL_CALL` content block, and appears **before** the corresponding
  `TOOL_RESULT`. A `TOOL_CALL` block on a `USER` or `TOOL_RESULT` message is rejected: only the
  assistant makes tool calls, and permitting the block elsewhere would let assembled or
  tool-returned content present itself to the provider as a prior model decision.
- **INV-88** A `TOOL_RESULT` message carries the `toolCallId` of the call it answers. With
  several calls outstanding in one iteration, the pairing is otherwise a guess.

### 5.11 ModelResponse

**Responsibility.** Return a normalised model result, plus the **authoritative** usage, cost and
latency measurements.

**Lifecycle.** Produced per ModelRequest. Recorded durably as a ModelInvocation before being
returned.

**Key fields.** `modelInvocationId`, `content[]`, `toolCalls[]`, `finishReason`, `usage`,
`providerModelId`, `latencyMs`, `cost`, `error?`.

**Invariants.**

- **INV-53** Usage and cost recorded here are the gateway's own measurements and are
  authoritative. They are **never** taken from the agent runtime's self-report (ADR-0004 §9).
- **INV-54** `providerModelId` records the concrete model that actually served the request. A
  logical `modelRef` may resolve differently over time, and an evaluation result is meaningless
  without knowing what answered.
- **INV-55** `toolCalls` are **requests only**. Nothing in a ModelResponse has been authorised or
  executed.
- **INV-56** `CONTENT_FILTER` is recorded and never silently swallowed.
- **INV-57** Error categories are fixed and drive retryability. The provider's message text does
  not.

### 5.12 ExecutionRequest

**Responsibility.** Ask the execution interface to run one command in one workspace, under
explicit limits.

**Lifecycle.** Constructed by the tool layer from a CommandProfile → submitted → handle returned
→ awaited or polled → resolved. Each execution is independent; no interactive session persists
between calls.

**Key fields.** `argv[]`, `cwd`, `envAllowlist{}`, `timeoutMs`, `resourceLimits`, `networkPolicy`,
`stdinRef?`, `correlation`.

**Invariants.**

- **INV-58** `argv` is an array, never a shell string. No shell is involved at any layer. This
  removes shell injection as a category.
- **INV-59** `argv` is resolved by the platform from a named CommandProfile. A model selects a
  profile; it never authors a command.
- **INV-60** `envAllowlist` is explicit. The parent environment is never inherited, so ambient
  developer credentials cannot reach executed commands.
- **INV-61** `cwd` is workspace-relative. **No host path ever crosses this boundary.**
- **INV-62** `timeoutMs`, `resourceLimits` and `networkPolicy` are all mandatory. Connectivity is
  a decision, never a default; the default is `NONE`.
- **INV-63** `correlation` is carried for telemetry and **never interpreted**. The executor knows
  nothing of graphs, agents, runs or tools.

### 5.13 ExecutionResult

**Responsibility.** Report what happened, by reference.

**Key fields.** `status`, `exitCode?`, `stdoutRef`, `stderrRef`, previews, `durationMs`,
`resourceUsage`, `networkDenials[]`.

**Invariants.**

- **INV-64** **A non-zero exit code is a result, not an error.** A failing test is the normal
  case in a repair loop. The error taxonomy is reserved for the executor failing to run the
  command at all.
- **INV-65** stdout and stderr are returned as ArtifactRefs, always. Inline content is a bounded
  preview for human display only.
- **INV-66** The executor does not decide retryability. It reports a status; ADR-0008 categories
  govern.
- **INV-67** `networkDenials` is a security and supply-chain signal, not debug output, and
  deserves an alert once alerting exists.
- **INV-68** Everything produced by an execution — files, stdout, stderr, artifacts — is
  untrusted output. It is secret-scanned before persistence and never interpreted as a platform
  instruction.

### 5.14 Checkpoint

**Responsibility.** Make a GraphRun resumable from a node boundary, and make its workspace
**reconstructible rather than precious**.

**Lifecycle.** Written at every node boundary, in the **same transactional batch** as the node's
terminal status. Immutable. Retained while the run can still resume.

**Key fields.** `checkpointId`, `runId`, `afterNodeId`, `sequence`, `graphVariablesRef`,
`workspaceStateRef{repoRef, baseSha, patchSeries[]}`, `contextBundleRefs[]`, `createdAt`.

**Invariants.**

- **INV-69** Written atomically with the node status transition. A crash lands either before or
  after a checkpoint, never inside one.
- **INV-70** `workspaceStateRef` is sufficient to rebuild the workspace from scratch. This is the
  load-bearing invariant of the whole architecture: it is simultaneously what makes resume work
  and what makes a future remote executor a drop-in.
- **INV-71** Checkpoints are node-boundary only. **Intra-agent-loop checkpointing is explicitly
  out of scope** — an agent attempt is the unit of retry, and a partially completed loop is
  re-run, not resumed.
- **INV-72** Resume means *continue from recorded state*. Model calls are never replayed to
  reconstruct position: that would be non-deterministic, expensive, and would re-emit side
  effects.

### 5.15 Approval

**Responsibility.** Bind a human decision to **exactly** the content that was decided upon.

**Lifecycle.**

```text
PENDING --+--> APPROVED  --> (consumed by resume, subjectHash re-verified)
          +--> REJECTED  --> node fails with APPROVAL_REJECTED
          +--> EXPIRED   --> node fails with APPROVAL_EXPIRED
          \--> REVOKED
```

On reaching an `approval` node the engine writes `AWAITING_APPROVAL`, **releases the lease**, and
stops. Nothing is held in memory — which is what allows a run to wait six weeks across laptop
restarts.

**Key fields.** `approvalId`, `runId`, `nodeId`, `kind`, `requiredKind`, `subjectHash`,
`subjectRef`, `renderingHash`, `status`, `decidedBy?`, `decidedAt?`, `expiresAt`, `interactive`,
`externalRef?`, `rationale?`.

**Invariants.**

- **INV-73** `requiredKind` is the **strictest** of the tool's side-effect class, the repository
  trust level and the graph node definition. Any layer may require a stronger kind; none may
  require a weaker one. (This is the dual of the capability monotonicity rule.)
- **INV-74** `subjectHash` is re-verified on resume. If the subject changed after approval, the
  approval is **void**. Without this, an approval is a time-of-check/time-of-use bug with a human
  in it.
- **INV-75** `renderingHash` records what the human was actually *shown*, separately from what
  was approved. Approving a rendering that differs from the subject is the failure this pair
  exists to detect.
- **INV-76** No agent may create, approve, or influence an approval. An agent cannot author the
  rendering it will be judged on.
- **INV-77** `interactive: false` is recorded, not forbidden. A batch-approved run must remain
  visibly distinguishable in the audit trail from one a human actually looked at.
- **INV-78** `EXTERNAL_ATTESTATION` requires an `externalRef`. Without something another system
  can corroborate, it is `LOCAL_OPERATOR_CONSENT` wearing a stronger label.

### 5.16 Workspace

> **The durable record has no contract today.** `WorkspaceSpec` describes creation input only.
> OQ-05.

**Responsibility.** Provide an isolated, reconstructible, credential-free filesystem for one
GraphRun.

**Proposed lifecycle.**

```text
CREATING -> READY -> LEASED -+-> RELEASED -> DESTROYED
                             +-> QUARANTINED -> DESTROYED   (failed run, bounded retention)
                             \-> EXPIRED (lease lost) -> reclaimable
```

**Proposed key fields.** `workspaceId`, `runId`, `status`, `toolImageDigest`, `repositories[]`,
`lease{holderId, expiresAt}`, `executionMode` (`container` | `unsafe-host-exec`),
`quotaBytes`, `lastUsedAt`, `createdAt`.

**Invariants.**

- **INV-79** **One workspace per run**, not per node. Per-node materialisation of a large
  repository makes the platform feel unusable.
- **INV-80** Exclusively leased. Two runs never share a checkout; a run cannot reach another
  run's workspace; and no run can reach the developer's own repositories.
- **INV-81** **The workspace container holds no credentials.** No GitHub, Jira, Confluence or
  model credential, and no git credential helper. Untrusted code executing there has nothing to
  steal and nowhere to push.
- **INV-82** Materialisation and publishing both happen **outside** the container. `git fetch`
  and `git push` are never executed inside a workspace; publishing applies the snapshot
  host-side using the run's scoped short-lived token.
- **INV-83** Container defaults are non-negotiable: non-root, `no-new-privileges`, all
  capabilities dropped, read-only root filesystem, workspace-only host mount, digest-pinned
  image, default-deny network.
- **INV-84** `destroy` is always safe, because of INV-70.
- **INV-85** `unsafe-host-exec` is disabled by default, requires a configuration change rather
  than a run flag, is recorded on the run and every audit entry, forces approval for
  `EXTERNAL_WRITE` and `IRREVERSIBLE`, and marks evaluation results as excluded from comparison.
- **INV-86** Symlinks escaping the workspace are refused at materialisation and rejected at write
  time.

---

## 6. Cross-cutting concerns

### 6.1 Graph / run / node state transitions

Three state machines, at three different lifetimes, with one rule that ties them together:

| Machine | Lifetime | Who may transition |
|---|---|---|
| Graph | permanent, immutable | nobody — publication only |
| GraphRun | hours to weeks | the lease holder, exclusively |
| NodeRun | seconds to hours | the lease holder, exclusively |

**Every transition is a single atomic write.** A transition writes the node status, any
checkpoint, and the corresponding event as **one transactional batch within the run's
partition**. Partial transitions are therefore impossible.

The composition rule that is easy to get wrong:

```text
NodeRun terminal status  ==>  checkpoint written in the same batch
                         ==>  transition evaluated on validatedOutput only
                         ==>  GraphRun.currentNodeId advanced
```

If a crash occurs anywhere in that sequence, recovery observes either the whole batch or none of
it. There is no "node succeeded but no checkpoint" state to reason about, which removes the
largest single source of resume bugs.

**Transitions are never evaluated on prose.** A node produces claimed output; it is validated;
only then may an edge condition read it. A schema failure is a node failure of category
`INVALID_OUTPUT`, eligible for one bounded repair attempt — it is not a transition input.

### 6.2 Durability and resumability

The durability contract, stated as a single sentence: **killing any process at any instant loses
at most one node attempt.**

That holds because of four decisions acting together:

1. The agent runtime holds **no durable state** and is freely restartable.
2. Durable state is authoritative; the dispatch HTTP call is an optimisation, not the record.
3. Every transition is atomic within the run partition.
4. Workspace state is a **function of** `(repoRef, baseSha, ordered patch series)`, all durable.

The resume algorithm:

```text
1. Acquire the lease; fail if held elsewhere.
2. Load the run, its nodes, and the latest checkpoint.
3. For each node in RUNNING:
     write-ahead intent with no outcome  -> INDETERMINATE (never auto-retried)
     otherwise                           -> roll back to last checkpoint, reschedule attempt+1
4. Rebuild the workspace from (repoRef, baseSha, patchSeries).
5. Re-verify subjectHash of any pending approval.
6. Continue.
```

Step 3 is where most implementations go wrong by treating a `RUNNING` node as simply retryable.
It is not: whether it is retryable depends on whether a side effect may already have escaped.

**Retention is bounded by run state, not wall-clock age.** A run paused awaiting approval for six
weeks must still resume, so a naive time-based artifact sweep would routinely turn resumable runs
into unrecoverable ones.

### 6.3 Idempotency

Idempotency applies to `EXTERNAL_WRITE` and `IRREVERSIBLE` tools. The key is derived from:

```text
idempotencyKey = H(runId, nodeId, toolId, canonicalised input)
```

**`attempt` is deliberately excluded.** A retry of the same logical operation must deduplicate
rather than double-post. Including `attempt` would produce a fresh key per retry and defeat the
entire mechanism — this is the single most likely implementation error in the tool layer.

The protocol around the key:

```text
prior success recorded          -> return the recorded result, do not re-execute
prior intent, no outcome        -> INDETERMINATE, do not re-execute
no prior record                 -> write intent, dispatch, write outcome
```

Where the external system offers native idempotency or a natural key — a branch name, an existing
PR for a head ref — the integration must **prefer detect-and-adopt over blind create**.

The acceptance criterion is concrete and testable: *run the same node twice and leave one branch,
one pull request and one comment.*

> Unresolved: this key is stable across **loop iterations** as well as attempts, so a loop that
> legitimately wants to post a comment per iteration would silently deduplicate. See OQ-04.

### 6.4 Correlation identifiers

One correlation block propagates end-to-end:

```text
Jira issue -> GraphRun -> NodeRun -> ContextBundle
                            |
                            +-> ModelInvocation -> provider request
                            +-> ToolInvocation  -> ExecutionRequest -> container
                                     |
                                     +-> AuditEntry -> external ref (PR, commit, issue)
```

Rules:

- `traceparent` is W3C Trace Context and crosses **every** boundary, including the loopback HTTP
  hop to the Python runtime, where it propagates natively.
- The executor **carries** correlation and never interprets it.
- `runId` is the partition key, so correlation and data locality coincide.
- **High-cardinality identifiers are forbidden as metric labels.** They belong on spans, logs and
  durable records. This fails silently at small scale and is expensive to unwind later.

### 6.5 Tool authorization

One choke point, in the control plane, with no bypass:

```text
agent runtime --(callback, the only channel)--> TOOL LAYER --+--> integration clients
                                                             \--> execution interface
```

Authority flows downward and may only narrow:

```text
platform policy  >=  trust-level ceiling  >=  registry record  >=  graph node definition
                                    |
                                    v
                        effective CapabilityGrant  (per node attempt)
```

Repository-resident files affect **context only** and have zero capability effect. This is what
stops a repository the platform is editing from rewriting the configuration that governs editing
it.

Five independent layers must all fail for a prompt injection to reach the outside world:

1. the grant bounds what the model may request (ADR-0005)
2. the runtime's only network peer is the control plane (ADR-0004 §4)
3. workspace containers are credential-free and network-default-deny (ADR-0006)
4. target-repository config cannot rewrite the config that produces grants (ADR-0014)
5. approval is the last gate, and an agent cannot influence its own approval (ADR-0009)

No single layer is sufficient. Removing any one of them makes the others advisory.

### 6.6 Execution isolation

Isolation is enforced by the executor, not requested by the caller:

| Boundary | Mechanism |
|---|---|
| Process | container, non-root, all capabilities dropped, `no-new-privileges` |
| Filesystem | read-only root; workspace mount and size-limited `/tmp` only |
| Host | workspace mount only — never the home directory, never the container socket |
| Environment | explicit allowlist; never inherited |
| Network | default deny; allowlist mediated by a local egress proxy so it is *enforced*, not advertised |
| Image | platform-maintained, digest-pinned; no agent may select or build one |
| Resources | CPU, memory, PID and disk quotas on every execution |
| Credentials | none, ever, inside the workspace |

Containerising **locally** is not overhead for its own sake: it means the local and future
Kubernetes executors share one mental model — image, argv, limits, network policy — rather than
two, which is what makes the later migration contained.

### 6.7 Model-provider neutrality

Neutrality is achieved by three rules, not by an adapter interface alone:

1. Callers name a **logical `modelRef`**, never a provider model id.
2. Provider SDKs are imported only inside the gateway. The agent runtime may not import one.
3. **The gateway does not own the tool-calling loop.** It normalises provider-native tool-use
   into `toolCalls[]`; the tool layer authorises and executes; results return as
   `TOOL_RESULT` messages.

Rule 3 is the one that actually preserves neutrality. If the gateway ran the loop, tool dispatch
would sit inside the provider integration, coupling authorization semantics to whichever provider
was implemented first — and bypassing the choke point entirely.

`providerOptions` exists as an escape hatch and is deliberately named so that its use is visible
in review.

### 6.8 Human approval

Approval is a **durable pause**, not a blocking call. The engine writes the state, releases the
lease, and stops. Correctness comes from binding rather than from timing:

- bind to `subjectHash` — *what* was approved
- bind to `renderingHash` — what the human was *shown*
- re-verify on resume; a changed subject voids the approval
- expire, because an indefinitely valid approval on a run resumed weeks later approves something
  nobody is still thinking about

Without central identity, V1 approval is honest about its own strength: `LOCAL_OPERATOR_CONSENT`
attests that *someone at the keyboard* consented, not *who*. `EXTERNAL_ATTESTATION` borrows
identity from a system that has it, and is stronger precisely because the platform is not the one
asserting it.

### 6.9 Error and retry semantics

**Retry is driven by category, never by message text.** Categories:

| Category | Retryable | Notes |
|---|---|---|
| `TRANSIENT` | yes | |
| `MODEL_ERROR` | yes | rate limits, provider transients |
| `BUDGET_EXCEEDED` | policy | retrying without raising the budget usually repeats the failure |
| `INVALID_OUTPUT` | yes, bounded | one repair attempt |
| `TOOL_DENIED` | policy | usually indicates a wrong grant, not a transient fault |
| `VERIFICATION_FAILED` | yes | the normal repair-loop case |
| `EXECUTION_ERROR` | yes | executor could not run the command |
| `INTEGRATION_ERROR` | yes | |
| `INDETERMINATE` | **never** | reconcile or escalate |
| `CANCELLED` | no | |
| `APPROVAL_REJECTED` | no | a human said no; retrying is not a repair |
| `APPROVAL_EXPIRED` | **unresolved** | see OQ-06 |

Policy lives in the Graph (versioned, pinned); state lives on the NodeRun (`attempt`,
`nextAttemptAt`, `lastFailureCategory`). Each attempt keeps its own record.

The layering rule: **no layer below the graph engine decides retryability.** The executor reports
a status, the gateway reports an error category, the runtime reports a failure category — the
graph engine alone decides what happens next.

### 6.10 Local-first execution

Every entity above is designed for a machine that sleeps, loses network and gets `Ctrl-C`'d:

- no server-based operational store — SQLite is a library, not a daemon
- no central identity — authority is per-attempt and locally minted
- no shared execution cluster — one workspace, one lease, one laptop
- `SUSPENDED` is a first-class expected state, not an error path
- artifacts are content-addressed on the local filesystem
- the whole platform starts with one command, hiding the two-process split

The reversibility rules that keep this from becoming a dead end: workflow semantics stay behind
the execution interface, no storage SDK type crosses the persistence port, and security
requirements are never relaxed merely because execution is local.

---

## 7. Persistence mapping

Indicative, not normative — ADR-0007 governs. Every document is addressed by
`(container, partitionKey, id)`, mirroring the Cosmos DB model so a future adapter is a mapping
rather than a redesign.

| Container | Partition key | id | Entity |
|---|---|---|---|
| `graph_definitions` | `graphId` | `graphVersionHash` | Graph |
| `runs` | `runId` | `runId` | GraphRun |
| `node_executions` | `runId` | `nodeId:attempt` | NodeRun |
| `checkpoints` | `runId` | `checkpointId` | Checkpoint |
| `agent_executions` | `runId` | `nodeId:attempt` | agent attempt record |
| `tool_invocations` | `runId` | `invocationId` | ToolRequest + ToolResult, durably |
| `model_invocations` | `runId` | `invocationId` | ModelRequest + ModelResponse, durably |
| `events` | `runId` | `sequence` | transition events |
| `approvals` | `runId` | `approvalId` | Approval |
| `leases` | `runId` | `runId` | orchestrator ownership |
| `idempotency` | `runId` | `idempotencyKey` | intent + outcome |
| `repositories` | `repositoryId` | `repositoryId` | RepositoryRecord |
| `audit` | `runId` | `sequence` | AuditEntry |
| `workspaces` | `runId` | `workspaceId` | Workspace *(proposed)* |

`runId` as the partition key for almost everything is deliberate: it makes the atomic transition
of §6.1 a single-partition transactional batch, which is the one thing Cosmos DB supports and the
port therefore permits.

Forbidden throughout, per ADR-0007 §6: change feed or store-side eventing, stored procedures,
unbounded cross-partition queries, server-side joins, cross-partition transactions, and any query
not backed by a declared index.

**Large payloads never live in the operational store.** Prompts, completions, transcripts, patch
series, logs, tool output and bundle item bodies are ArtifactRefs.

Two consequences worth stating because they are easy to miss:

- `repositories` and `graph_definitions` are partitioned **outside** `runId`, so no transaction
  may span a run and its registry record. Registry lookups are reads, resolved into the grant at
  mint time and recorded by `configHash`.
- An `audit` container partitioned by `runId` cannot answer "everything this developer did last
  month" without a cross-partition query. V1 answers it by export instead. (OQ-08.)

---

## 8. Invariant traceability

The 88 invariants in §5 are the testable form of the ADRs. Grouped by where they must be
enforced:

| Enforced in | Invariants | Test approach |
|---|---|---|
| Graph publication | INV-01..06, INV-08..10 | schema + static validation, condition totality checking |
| Graph engine | INV-11..16, INV-17..21, INV-69..72 | crash-injection at every transition point |
| Tool layer | INV-07, INV-26..40 | authorization matrix; idempotency double-run tests |
| Model gateway | INV-47..57, INV-87..88 | two-provider conformance suite against one recorded scenario |
| Executor | INV-58..68, INV-79..86 | executor contract suite + remote-simulation mode |
| Context engine | INV-41..46 | provenance completeness assertions |
| Approval component | INV-73..78 | subject-mutation and expiry tests |
| **Unenforceable today** | INV-22..25 | no Agent contract exists — see OQ-02 |

Three mechanisms deserve particular emphasis because they are self-enforcing rather than
review-dependent:

- **Remote-simulation CI mode** — run the local executor with artifact-reference-only access,
  path access refused, and injected latency. Portability violations then surface the day they are
  written rather than in the Kubernetes phase.
- **Crash-injection suite** — kill the process at every transition point; assert no torn state and
  no duplicated side effect. This should pass on a trivial graph *before any model is involved*.
- **Idempotency double-run** — execute the same node twice; assert one branch, one PR, one
  comment.

---

## 9. Defects found in existing contracts

Two problems in the current schemas were surfaced by writing this specification. Neither is a
consequence of a decision being wrong; both are places where the schemas fail to express what the
ADRs already imply. DEF-01 has been fixed. DEF-02 turns out not to be fixable in isolation.

### DEF-01 — ModelRequest cannot represent an assistant turn containing tool calls

**Severity: High. Blocks the agent loop. Fixed — no ADR required.**

`ModelRequest.messages[].content[]` permits only `TEXT` and `ARTIFACT` blocks, and the role enum
is `USER | ASSISTANT | TOOL_RESULT`. There is therefore **no way to represent the assistant's own
tool-call turn in conversation history**.

Both major providers require that turn to be present before the corresponding tool result: an
agent loop of more than one iteration cannot be expressed. The gateway would be forced to
reconstruct or drop it, and dropping it changes what the model sees between iteration one and
iteration two.

**Correction applied.** `ModelRequest.messages[].content[]` now admits a self-contained
`TOOL_CALL` block — `{ type, toolCallId, name, arguments }` — mirroring
`ModelResponse.toolCalls[]`. It is self-contained rather than a reference into a sibling array
because a request carries no `toolCalls[]` to refer to.

Two adjacent constraints were added at the same time, because a tool-call turn that cannot be
attributed or correlated does not solve the problem:

- A `TOOL_CALL` block is rejected on `USER` and `TOOL_RESULT` messages. Only the assistant makes
  tool calls; permitting the block elsewhere would let assembled or tool-returned content present
  itself to the provider as a prior model decision.
- A `TOOL_RESULT` message must carry `toolCallId`. With several calls outstanding in one
  iteration, the pairing is otherwise a guess.

All three are covered by examples under `schemas/examples/`, and each was verified by mutation:
removing any one of them makes the example suite fail.

### DEF-02 — `pathScope` is ambiguous in multi-repository runs

**Severity: Medium. Open — resolve with OQ-07, which requires an ADR.**

`GraphRun.repositories[]` and `WorkspaceSpec.repositories[]` are both lists, but
`CapabilityGrant.pathScope` is a flat set of globs over a single workspace-relative namespace.
With two repositories materialised into one workspace, `src/**` is ambiguous, and a grant intended
to permit writes in one repository silently permits them in the other.

**Correction, not yet applied.** The fix is to define the workspace layout — the natural choice is
a `<repositoryId>/` prefix per repository — and require `pathScope` globs to be rooted at it.

This was originally classified as a pure correction. That was wrong: the layout it depends on is
not implied by any accepted ADR, and choosing one here would be inventing the answer to OQ-07
rather than recording it. It is left open deliberately, and should be fixed in the same change
that resolves OQ-07.

---

## 10. Open questions requiring an architectural decision

These were **not** invented away. Each changes the data model or a security boundary, so each
needs a decision before implementation.

### OQ-01 — Domain vocabulary: which names win? *(Low risk, high friction if deferred)*

The ADRs say `GraphDefinition` / `Run` / `NodeExecution`; the domain language here says `Graph` /
`GraphRun` / `NodeRun`. Both are defensible. What is not defensible is shipping both, which is
where the Java and Python sides start naming the same thing differently.

*Recommendation:* adopt the domain names (`Graph`, `GraphRun`, `GraphNode`, `NodeRun`) and rename
the schemas now, while renaming is free. **Affects V1. ADR not strictly required — a recorded
decision in this document would suffice.**

### OQ-02 — Agent definition: contract, storage and pinning *(the most consequential gap)*

There is no Agent schema, no store and no versioning rule. The critical consequence:

> A GraphRun pins `graphVersionHash`, but the agent definitions that graph invokes are **not**
> pinned. Editing an agent's instructions changes the behaviour of every in-flight run of an
> already-pinned graph, and makes two runs of the "same" definition non-comparable.

This defeats INV-11 and undermines the reproducibility that ADR-0008 §2 and the whole evaluation
strategy depend on.

Options: (a) pin agent versions in the Graph definition, so the graph hash covers them
transitively; (b) resolve agents at run creation and record the resolved set on the GraphRun;
(c) treat agent definitions as content-addressed like graphs and reference by hash.

*Recommendation:* (c), with (a) as the reference mechanism — it is consistent with how graphs
already work and needs no new concept. **Affects V1. ADR required.**

### OQ-03 — ToolRequest / ToolResult wire contract *(blocks the tool layer)*

§5.7 and §5.8 propose shapes; nothing in the ADRs fixes them. Specific undecided points:

- Is a denial an HTTP 200 with `outcome: DENIED`? ADR-0005 §6 says a denial is a result rather
  than a transport error, which implies yes — but it is inferred, not stated.
- Does the request carry the provider's `toolCallId`? It must, to correlate the result back into
  the conversation, but nothing says so.
- Does a suspended-for-approval invocation hold the HTTP call open, or return a
  `PENDING_APPROVAL` result and end the attempt? These have very different runtime consequences,
  and approvals can take days.

*Recommendation:* end the attempt on approval suspension. Holding a connection open for days
contradicts the durable-pause model. **Affects V1. ADR required** — the third point is a
semantic decision, not a detail.

### OQ-04 — Loop iteration identity *(data-model change)*

`NodeRun` identity is `(runId, nodeId, attempt)`. A `loop` node executes its body repeatedly, so a
body node executed five times, each with its own retries, **collides**: iteration 2 attempt 1 is
indistinguishable from iteration 1 attempt 2.

This also affects idempotency (§6.3): the key excludes `attempt` but has no notion of iteration,
so a tool call with identical input in two iterations deduplicates — which may be right for
"create the PR" and wrong for "post a progress comment".

Options: add `iteration` to NodeRun identity; or flatten loops at publication into distinct
`nodeId`s; or forbid side-effecting tools inside loop bodies.

*Recommendation:* add `iteration` to the identity tuple and to the idempotency key, defaulting to
0. Flattening looks tempting but destroys the readability of the definition that ADR-0008 §1
exists to protect. **Affects V1. ADR required.**

### OQ-05 — Workspace as a durable entity *(recovery correctness)*

Only `WorkspaceSpec` exists. Undecided: the state machine, whether the record is durable at all,
who reclaims an expired lease, how quarantine retention is bounded, and how LRU eviction
interacts with a `SUSPENDED` run that will need its workspace back.

The interaction is the real question. Because of INV-70 a workspace can always be rebuilt, so
eviction is *safe* — but rebuilding a large repository on resume is slow enough that a developer
will notice, and "safe but surprising" is how local-first platforms lose users.

*Recommendation:* make Workspace durable with the §5.16 state machine; never evict a workspace
belonging to a non-terminal run without an explicit operator action. **Affects V1. ADR required.**

### OQ-06 — Is `APPROVAL_EXPIRED` retryable?

`APPROVAL_REJECTED` is clearly terminal for the node — a human said no. `APPROVAL_EXPIRED` is
different: nobody decided anything, the clock simply ran out, which on a local-first platform is
the *expected* outcome of a holiday.

The current graph-definition schema permits neither in `retryableCategories`, which means an
expired approval permanently fails a run that a developer would reasonably expect to be able to
re-request.

*Recommendation:* make `APPROVAL_EXPIRED` retryable by policy, where a retry means *re-request
the approval* with a fresh `subjectHash` verification — not silently proceeding. **Affects V1.
ADR required**, because "retry" meaning "ask again" is a genuinely different operation from
"retry" meaning "run again".

### OQ-07 — Multi-repository workspace layout *(also DEF-02)*

`repositories[]` is plural everywhere, but no document states how multiple repositories are laid
out in one workspace, how `cwd` is rooted, how `pathScope` is qualified, or how a patch series is
attributed per repository at checkpoint time.

Cross-repository change is an explicit platform goal, so this cannot be deferred to "when we need
it" — the checkpoint format depends on it.

*Recommendation:* `<repositoryId>/` prefix; `pathScope` globs rooted at the workspace; patch
series already per-repository in the Checkpoint schema, which is consistent with this.
**Affects V1. ADR required.**

### OQ-08 — Cost units and budget aggregation

`maxCostUnits` appears on grants, node budgets and registry ceilings, but "cost unit" is never
defined, while `ModelResponse.cost` is `{amount, currency}`. Undecided: are cost units currency,
normalised tokens, or provider-neutral credits? And who enforces a **run-level** total, given
budgets are declared per node and per grant?

Without a run-level ceiling, a bounded loop of bounded nodes is still an unbounded spend.

*Recommendation:* cost units are currency-denominated with an explicit currency; add a run-level
budget enforced by the graph engine before each node dispatch. **Affects V1. ADR required.**

### OQ-09 — Canonical serialisation for cross-language hashing

`graphVersionHash`, `bundleRef`, `subjectHash` and the audit hash chain all require Java and
Python to produce **byte-identical** canonical JSON. Key ordering, number formatting, Unicode
normalisation and escaping all differ between ecosystems by default.

A mismatch means approvals spuriously void themselves on resume and audit chains fail to verify —
symptoms that would be very hard to attribute to their cause.

*Recommendation:* adopt a published canonicalisation (RFC 8785 JCS) rather than defining one, and
make a cross-language conformance vector part of the schema test suite. **Affects V1. ADR
required.**

### OQ-10 — Mid-loop context retrieval

An agent receives one ContextBundle and can fetch it by reference. There is no way to retrieve
*more* context mid-loop. But the context principles call for progressive disclosure, and an agent
that discovers it needs an unincluded file can currently only fail the node.

The natural resolution is a `READ`-class `context.search` tool, which would route retrieval
through the choke point and keep it audited — but it would also mean bundles are no longer the
complete record of what the agent saw, which weakens INV-41 and the evaluation story.

*Recommendation:* allow it as a `READ` tool, and require that anything it returns is appended to a
superseding bundle so the provenance record stays complete. **Affects V1. ADR required.**

### OQ-11 — Reconciliation procedure per integration

ADR-0008 requires that `INDETERMINATE` be resolvable, and ADR-0005 makes it reachable, but no
document defines *how* to reconcile for GitHub, Jira or Confluence — which query proves a branch,
PR, comment or page version was or was not created.

An enum value with no operational procedure behind it is how `INDETERMINATE` becomes a state that
silently accumulates.

*Recommendation:* one reconciliation procedure per write tool, defined alongside the tool and
covered by the tool's contract tests. **Affects V1. ADR not required if documented per tool.**

---

## 11. Deliberately out of scope for V1

Recorded so that absence reads as a decision rather than an oversight:

- parallel node execution — bounded concurrency of one in-flight attempt
- intra-agent-loop checkpointing
- agent-authored or agent-selected graphs
- nested graphs and sub-runs
- cross-run coordination
- streaming model responses
- multi-user shared state, which is coupled to reopening the identity question
- a hosted control plane
- Kubernetes execution
- automatic merge or deployment authority

---

## 12. Consequences of adopting this specification

**Accepted costs.** The invariant set is large, and much of it is only enforceable by tests that
must be written before the components they constrain. Three entities need contracts that do not
exist yet, and two of the open questions change the data model — so accepting this document
implies accepting a short ADR round before implementation rather than after.

**Gained.** The contracts become independently testable, the Java and Python sides can be built
against the same specification without a shared codebase, and the questions that would otherwise
have been settled silently and differently on each side are now visible and decidable.

**Next.** Resolve OQ-02, OQ-03, OQ-04 and OQ-09 first: they change contracts that everything else
is built on. OQ-05, OQ-06, OQ-07 and OQ-08 can be decided in parallel. OQ-01 costs almost nothing
now and progressively more later.
