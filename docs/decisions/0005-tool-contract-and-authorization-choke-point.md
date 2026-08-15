# ADR-0005: Tool Contract, Capability Grants and the Authorization Choke Point

## Status

Accepted — 2026-08-15

Read together with ADR-0004 (boundary and protocol) and ADR-0008 (graph semantics).

---

## Context

The architecture requires that agents act only through explicit tools with contracts, input
validation, authorization, observability and clear side-effect semantics. It does not say
where any of that is enforced, what a grant looks like, or what an agent is allowed to ask for.

Three specific hazards make this the platform's most important security decision.

**Enforcement placed in the wrong process is not enforcement.** If tools are implemented in
the Python runtime, then authorization runs inside the process that is being fed untrusted
repository and issue content. A successful injection does not need to defeat the policy; it
runs on the same side of it.

**The interesting tools are the dangerous ones.** The platform must build code, run tests,
create branches, open pull requests and update Jira. These are exactly the operations that are
consequential, partially irreversible, and externally visible.

**Models will ask for shell access, because shell access solves everything.** The natural
design — a `run_command` tool taking a command string — hands the model arbitrary code
execution on a developer's machine, with that developer's credentials, driven by text that
originated in a Jira ticket. It also destroys any hope of a meaningful audit trail, because
every invocation reads `run_command`.

---

## Decision

### 1. One choke point, in the control plane, with no bypass

All tool invocation passes through a single control-plane component:

```text
   agent runtime  --(tool-invocation callback, ADR-0004)-->  TOOL LAYER
                                                                 |
                                                +----------------+----------------+
                                                |                                 |
                                       integration tools                 workspace tools
                                       Jira / Confluence / GitHub        execution interface
```

The agent runtime holds **descriptors**, never implementations. It cannot invoke a tool by any
other path, because it has neither credentials nor egress (ADR-0004 §3, §4).

The graph engine invokes `tool` nodes through the same component. There is exactly one code
path through which side effects occur, and therefore exactly one place where authorization,
idempotency, audit and telemetry are applied.

### 2. Tool descriptor contract

Every tool declares, as data:

```text
id                    stable, namespaced           e.g. github.pull_request.create
version               semantic; descriptors are immutable per version
title, description    model-facing
inputSchema           JSON Schema, closed (additionalProperties: false)
outputSchema          JSON Schema
sideEffectClass       READ | WORKSPACE_WRITE | EXTERNAL_WRITE | IRREVERSIBLE
scopeRequirements     repository / path / project scopes the grant must contain
idempotency           NATURAL | KEYED | NONE
approvalPolicy        NEVER | ALWAYS | CONDITIONAL(predicate over validated input)
timeout, costHint
```

`inputSchema` is closed. Anything not declared is rejected rather than ignored, so a model
cannot smuggle fields past validation into an integration client.

### 3. Side-effect classes carry obligations

| Class | Examples | Obligations |
|---|---|---|
| `READ` | read file, search repo, read issue | no approval; no write-ahead record; cacheable |
| `WORKSPACE_WRITE` | apply patch, run build | confined to the granted workspace; reversible by workspace rebuild |
| `EXTERNAL_WRITE` | create branch, open PR, comment on issue | idempotency key required; write-ahead intent required; audited |
| `IRREVERSIBLE` | merge PR, publish page, close issue | all of the above, **plus** human approval, always |

Class is declared on the tool and is not negotiable per call. Grants may narrow permitted
classes; nothing may widen them.

### 4. Capability grants are minted per node attempt and cannot escalate

The control plane mints a grant when it dispatches a node attempt:

```text
grantId
subject          (runId, nodeId, attempt)
allowedTools     explicit tool ids and versions — never a wildcard
maxSideEffect    the highest permitted side-effect class
repositoryScope  repository ids
pathScope        allow/deny globs within the workspace
externalScope    Jira project keys, GitHub repos, Confluence spaces
commandProfiles  permitted named profiles (see §5)
budget           invocation count, wall-clock, cost ceiling
notAfter         attempt deadline
```

Properties: grants are derived from the graph node definition intersected with the repository
registry's capability ceiling (ADR-0014), never from anything the model produced; they are
**monotonically non-increasing** — no operation grows a grant mid-attempt; and the runtime
never handles a grant, only the attempt token that resolves to it (ADR-0004 §10).

The retry of a failed node gets a *fresh* grant, so a failed attempt cannot leave residual
authority behind.

### 5. Models select command profiles; they never author commands

There is no tool that accepts a shell string or a free-form argv array from a model.

Instead, each repository declares named **command profiles** in the repository registry:

```text
profileId        maven.test
argv             ["mvn", "-B", "-ntp", "test"]
parameters       declared, typed, schema-validated, substituted positionally
cwdScope         paths within the workspace where it may run
timeout, limits, network policy
sideEffectClass  WORKSPACE_WRITE
```

The tool `workspace.run_profile(profileId, parameters)` is the only route to command
execution. Parameters are substituted as discrete argv elements; string concatenation into a
shell is never performed, and no shell is involved at any layer.

This costs flexibility: an agent cannot invent a command to diagnose an unusual failure, and
each repository must declare what its build and test commands are. That cost is accepted. It
converts "the agent may run anything on this laptop" into an enumerable, reviewable,
per-repository list, and it makes the audit trail say what actually happened.

Adding a profile is a human action — a reviewed change to repository configuration — not
something an agent can do for itself.

### 6. Deny by default; denials are results, not errors

Unknown tool, ungranted tool, schema violation, out-of-scope target, exhausted budget: all
denied. Deny is the default for anything not explicitly granted.

A denial is returned to the agent as a **structured tool result**, not as a transport error,
so the model can adapt rather than the node collapsing. Every denial is simultaneously written
as an audit event.

Repeated denial is itself a signal: a bounded denial budget per attempt trips a circuit
breaker and fails the node with `TOOL_DENIED`. This prevents the pathological loop where a
model spends its entire budget rediscovering that it may not do something, and it surfaces
grants that are wrong rather than letting them fail quietly.

### 7. The invocation pipeline, in order

```text
1. resolve grant from attempt token          -> deny: not authorized
2. resolve tool descriptor (id + version)    -> deny: unknown tool
3. validate input against closed inputSchema -> deny: invalid input
4. check scope: repo / path / external       -> deny: out of scope
5. check budget and denial circuit breaker   -> deny: budget exhausted
6. approval gate (class or approvalPolicy)   -> suspend node (ADR-0008)
7. derive idempotency key; check for prior outcome
      prior success  -> return recorded result, do not re-execute
      prior intent, no outcome -> INDETERMINATE, do not re-execute
8. write-ahead intent record   (EXTERNAL_WRITE and IRREVERSIBLE only)
9. dispatch: integration client | execution interface
10. write outcome record + audit entry; offload large payloads to artifact store
11. return result
```

Steps 8 and 10 straddle the dispatch deliberately. An intent with no outcome is what a crash
mid-side-effect looks like, and it is the only way the platform can later tell "it did not
happen" apart from "it may have happened". Per ADR-0008, that state is never auto-retried.

### 8. Idempotency

`EXTERNAL_WRITE` and `IRREVERSIBLE` tools require an idempotency key derived from
`(runId, nodeId, toolId, canonicalised input)` — deliberately not including `attempt`, so that
a retry of the same logical operation deduplicates instead of double-posting.

Where the external system supports native idempotency or natural keys (a branch name, an
existing PR for a head ref), the integration must prefer detect-and-adopt over blind create.
The platform must be able to run the same node twice and leave one branch, one pull request
and one comment.

### 9. Tool results are data, never instructions

Results are untrusted content. They are inserted into the model context as data, are never
interpreted as platform directives, and can never alter a grant, a budget, an approval or a
graph transition. Results above the size threshold are offloaded to the artifact store and
passed by reference with a truncated inline preview.

### 10. Audit is separate from telemetry

Every invocation writes an audit record: `runId`, `nodeId`, `attempt`, `grantId`, `toolId` and
version, canonicalised input hash, decision (`ALLOWED` / `DENIED` with reason), outcome,
external references produced, actor, timestamps, `traceId`.

Audit records are append-only and durable, and are retained independently of telemetry. Traces
may be sampled and logs may be dropped; audit may not.

---

## Alternatives

**A. Implement tools in the Python runtime.**
Simplest to build and the natural fit for the ecosystem. Rejected: it places enforcement
inside the process handling untrusted input, and gives that process the credentials.

**B. Per-tool ad-hoc authorization.**
Rejected: correctness would depend on every tool author remembering, and the failure mode is
silent. A choke point fails closed by construction.

**C. A general `run_command(command: string)` tool with an allowlist of binaries.**
Rejected. Binary allowlists are defeated by arguments (`git`, `mvn` and `npm` all execute
arbitrary code via configuration or plugins), and the audit trail loses the semantics of what
was attempted.

**D. Let the provider's native tool-use mechanism call tools directly.**
Rejected: it moves dispatch into the provider integration, couples the tool layer to provider
semantics, and bypasses the choke point. The model gateway normalises tool *calls* into
requests; the tool layer decides and executes.

**E. Grant capabilities per run instead of per node attempt.**
Simpler, and materially weaker: a run-scoped grant means the least-trusted node in a graph
holds the authority of the most-privileged one for the run's whole lifetime.

---

## Consequences

**Accepted costs**

- Every repository must declare its command profiles before agents can build or test it. This
  is onboarding work, and it will occasionally block an agent that could otherwise have
  improvised.
- Tools are more expensive to add than a Python function would be: schema, class, scopes,
  idempotency semantics, tests.
- The choke point is on the hot path of every agent iteration; it must be fast and must not
  become a place where business logic accumulates.

**Gained**

- One place to reason about, review and test everything an agent can do.
- Grants are small enough to print, which makes "what could this run have done?" answerable
  before it runs rather than after.
- Idempotency and write-ahead records make crash recovery a defined procedure instead of a
  manual investigation.
- Prompt injection is bounded by the grant rather than by the model's judgement.

---

## Security / Operational Impact

- This ADR, with ADR-0004 §4, is the platform's primary defence against prompt injection.
  Neither is sufficient alone: no egress without a choke point still permits an over-broad
  grant; a choke point without egress control permits a direct call.
- Grants must be logged at mint time, in full. "What was this agent allowed to do" must be
  answerable from durable state, not reconstructed.
- The denial circuit breaker is a security signal as well as a cost control; sustained denials
  deserve an alert once alerting exists.
- Credentials for integrations and workspaces are held by the tool layer and execution
  interface, never passed outward toward the model.
- Approval-gated invocations must bind to the content approved, per ADR-0008 and ADR-0009.

---

## Follow-up

- `docs/architecture/tool-layer.md` — component documentation.
- ADR-0006 — local execution isolation, which enforces command profiles at the executor.
- ADR-0009 — approval semantics for `IRREVERSIBLE` invocations.
- ADR-0012 — GitHub actor identity and per-run token scoping.
- ADR-0014 — repository registry, capability ceilings and command profile declaration.
- Define the initial V1 tool set explicitly, with classes and schemas, before implementation.
