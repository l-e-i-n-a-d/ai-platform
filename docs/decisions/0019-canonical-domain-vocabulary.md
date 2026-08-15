# ADR-0019: Canonical Domain Vocabulary

## Status

Accepted — 2026-08-15

Closes OQ-01 from `docs/contracts/v1-domain-contracts.md`. Renames schema titles established by
ADR-0008 and referenced by ADR-0004, ADR-0005 and ADR-0013. Prerequisite for the code generation
decided in ADR-0024, because generated type names come directly from schema titles.

---

## Context

The repository currently carries two vocabularies for the same three concepts.

| Concept | Schema title | Architecture prose | Contract specification |
|---|---|---|---|
| the workflow | `GraphDefinition` | "graph", "graph definition" | `Graph` |
| one execution of it | `Run` | "run", "graph run" | `GraphRun` |
| one node attempt record | `NodeExecution` | "node execution" | `NodeRun` |

This is not a cosmetic problem. Three consequences make it worth a decision rather than a
cleanup commit.

**Generated code inherits the ambiguity permanently.** ADR-0024 generates Java and Python types
from schema titles. `Run` is a catastrophic class name in Java — it collides conceptually with
`Runnable`, reads as a verb, and gives no hint of which of the platform's several run-like things
it denotes. Once `contracts.graph.Run` exists in two languages and is imported across a control
plane and an agent runtime, renaming it stops being free.

**`Run` and `NodeExecution` are ambiguous in a system with several execution concepts.** The
platform also has agent executions, tool executions, model invocations and workspace executions.
`NodeExecution` sits in the middle of that list and is distinguished from `AgentExecutionRequest`
only by convention. A reader cannot tell from the name whether `NodeExecution` is a record, a
request or an act.

**Divergent vocabulary defeats search.** A contributor who reads `docs/contracts/` and then greps
for `GraphRun` finds nothing in `schemas/`. The documentation checks cannot catch this, because
both spellings are internally consistent within their own file.

The cost of fixing it is at its historical minimum: no code exists, no data has been persisted,
and no external consumer depends on a name.

---

## Decision

### 1. Sixteen canonical entity names

These names are binding across ADRs, architecture documents, schemas, generated code, CLI output
and log fields.

```text
Graph              a workflow definition: declarative, immutable, content-addressed
GraphRun           one execution of a pinned Graph
GraphNode          one node within a Graph definition
NodeRun            the durable record of one node attempt
Agent              a versioned, pinned agent definition (ADR-0022)
Tool               a versioned tool descriptor
ToolRequest        a request to invoke a Tool, before authorization
ToolResult         the outcome of an authorized Tool invocation
ContextBundle      an immutable, content-addressed context artifact
ModelRequest       a provider-neutral model call
ModelResponse      a provider-neutral model result
ExecutionRequest   a request to the execution interface
ExecutionResult    the outcome of an execution request
Checkpoint         a durable resumption point at a node boundary
Approval           a human decision record
Workspace          an isolated, reconstructible materialisation of repositories
```

### 2. Five renames

| From | To | Schema file |
|---|---|---|
| `GraphDefinition` | `Graph` | `graph-definition.schema.json` → `graph.schema.json` |
| `Run` | `GraphRun` | `run.schema.json` → `graph-run.schema.json` |
| `NodeExecution` | `NodeRun` | `node-execution.schema.json` → `node-run.schema.json` |
| `ToolDescriptor` | `Tool` | `tool-descriptor.schema.json` → `tool.schema.json` |
| `ApprovalRecord` | `Approval` | `approval-record.schema.json` → `approval.schema.json` |

`$id` values change with the filenames. `$id` is an identifier, not a location, but keeping it
aligned with the path is what lets the schema tooling resolve relative `$ref`s without a lookup
table.

The word "definition" is dropped rather than preserved as `GraphDefinition` because immutability
is already carried by ADR-0008 §1: every `Graph` is a definition, so the qualifier distinguishes
nothing. `Descriptor` and `Record` are dropped for the same reason: every `Tool` is a declared
contract and every `Approval` is a record, so the suffix adds a syllable and no meaning. The
field `AgentExecutionRequest.toolDescriptors` becomes `tools` to match.

### 3. Protocol messages are deliberately not domain entities

`AgentExecutionRequest` and `AgentExecutionResult` keep their names. They are the HTTP protocol
between the control plane and the agent runtime (ADR-0004 §11), not durable domain entities. The
`Request`/`Result` suffix pair marks that distinction, and the same pattern applies to
`ExecutionRequest`/`ExecutionResult` and `ToolRequest`/`ToolResult`.

This is the "documented external reason" exception: a name may deviate from the canonical entity
list when it denotes a wire message rather than a stored entity, and the deviation must be stated
where the schema is defined.

### 4. Naming conventions

| Element | Convention | Example |
|---|---|---|
| Entity / schema title | `PascalCase` | `GraphRun` |
| Schema filename | `kebab-case.schema.json` | `graph-run.schema.json` |
| Field name | `camelCase` | `graphVersionHash` |
| Enum value | `UPPER_SNAKE_CASE` | `AWAITING_APPROVAL` |
| Identifier prefix | `<kind>_` | `run_`, `repo_` |

**One documented exception.** The `GraphNode.type` discriminator uses lowercase values —
`context`, `agent`, `tool`, `approval`, `decision`, `loop`, `terminal` — because ADR-0008 §3
fixes the node taxonomy in that form and it is quoted that way throughout the architecture
documents. Changing it would edit an accepted decision for consistency alone. Code generation
handles it by carrying the wire value explicitly rather than deriving it from the constant name,
so the exception costs nothing beyond this paragraph.

### 5. Names that must not reappear

`GraphDefinition`, `Run` (standalone, as an entity), `NodeExecution`, `GraphExecution`,
`RunNode`, `AgentRun`, `WorkflowRun`, `ToolDescriptor` and `ApprovalRecord` are retired.
`doclint` enforces this: a retired name appearing in a Markdown document or schema fails the
build.

Enforcement is the point of this section. A vocabulary decision that is not mechanically checked
degrades within weeks, because every contributor reintroduces the name they personally find
natural.

---

## Alternatives Considered

**Keep the schema names and change the contract specification instead.** Cheaper by line count,
and rejected because it optimises the wrong direction. `Run` remains a poor generated type name
in both target languages regardless of which document is edited to match it, and the specification
names were chosen deliberately against the entity model.

**Allow both, with an alias table.** Rejected. An alias table is a permanent tax on every reader
and every search, and it does not survive contact with generated code: the generator must still
pick one name per type.

**Defer until implementation.** Rejected on cost asymmetry. The rename is nearly free today and
becomes progressively more expensive with every generated artifact, persisted document and log
field that embeds the old name. Deferring a rename is choosing to pay more for it later.

**Also normalise the `GraphNode.type` values to `UPPER_SNAKE_CASE`.** Rejected. It would
contradict ADR-0008 §3 purely for aesthetic uniformity, and code generation already handles
arbitrary wire values.

---

## Consequences

- Schema titles, filenames and `$id`s change for three schemas; all `$ref`s that point at them
  are updated in the same change.
- `docs/contracts/v1-domain-contracts.md` §2 no longer needs its reconciliation table, because
  the two vocabularies it reconciled have become one.
- Generated Java and Python type names follow directly from the titles, so ADR-0024 needs no
  name-mapping configuration — which is itself a source of drift avoided.
- `doclint` gains a retired-vocabulary check. Historical documents that must quote an old name
  can do so inside a fenced code block, which the check skips.
- Any future entity introduced by a later ADR must state its canonical name in that ADR.

---

## Security / Operational Impact

Indirect but real. Audit records, log fields and CLI output all name entities. When an incident
requires correlating a log line with a stored record, two vocabularies for the same concept cost
time at exactly the moment it is least available. ADR-0016's attribution chain is only usable if
the reader can tell that `runId` on a log line and `GraphRun.runId` in the store are the same
thing.

No change to permissions, isolation, credentials or the authorization model.

---

## Follow-up

- Rename the three schemas and update every `$ref`, example and document reference.
- Add the retired-name check to `.github/scripts/doclint.py`.
- Remove the naming-reconciliation table from `docs/contracts/v1-domain-contracts.md` §2.
- ADR-0024 — code generation, which consumes these titles as type names.
- ADR-0022 — `Agent`, whose canonical name is fixed here.
