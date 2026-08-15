# Tool Layer

**Status:** Planned (design agreed, not yet implemented)
**Location:** Control plane (Java / Quarkus)
**Decision:** [ADR-0005](../decisions/0005-tool-contract-and-authorization-choke-point.md)

---

## 1. Responsibility

The tool layer is the **single path through which any side effect occurs**. It is the
platform's authorization choke point.

```text
  agent runtime (tool callback)  ─┐
                                  ├──►  TOOL LAYER  ──┬──►  integrations (Jira/Confluence/GitHub)
  graph engine (tool node)       ─┘                   └──►  execution interface (workspaces)
```

**Responsible for**

- the tool registry and descriptor contract
- authorization against the node's capability grant
- input validation against closed JSON Schemas
- scope enforcement (repository, path, external project)
- budget and denial circuit breaking
- approval gating
- idempotency and write-ahead intent records
- dispatch to integrations or the execution interface
- audit records for every decision

**Not responsible for**

- deciding *which* tool to call — that is the agent or the graph
- retry policy — that is the graph engine
- knowing whether execution is local or remote — that is the execution interface

---

## 2. Descriptor contract

```text
id                  namespaced, stable          github.pull_request.create
version             immutable per version
inputSchema         JSON Schema, additionalProperties: false
outputSchema        JSON Schema
sideEffectClass     READ | WORKSPACE_WRITE | EXTERNAL_WRITE | IRREVERSIBLE
scopeRequirements   scopes the grant must contain
idempotency         NATURAL | KEYED | NONE
approvalPolicy      NEVER | ALWAYS | CONDITIONAL(predicate)
timeout, costHint
```

| Class | Obligations |
|---|---|
| `READ` | no approval, no intent record |
| `WORKSPACE_WRITE` | confined to the granted workspace; reversible by rebuild |
| `EXTERNAL_WRITE` | idempotency key + write-ahead intent + audit |
| `IRREVERSIBLE` | as above, **plus** mandatory human approval |

---

## 3. Capability grants

Minted per `(runId, nodeId, attempt)` from the graph node definition intersected with the
repository registry's ceiling. Never derived from model output. Monotonically non-increasing —
nothing widens a grant mid-attempt. Resolved from the attempt token, so the runtime cannot ask
for more by asking differently. A retry gets a fresh grant.

Contents: `allowedTools` (explicit ids and versions, never wildcards), `maxSideEffect`,
`repositoryScope`, `pathScope`, `externalScope`, `commandProfiles`, `budget`, `notAfter`.

`pathScope` is a **map keyed by `repositoryId`**, not a flat list of globs (ADR-0023 §3). With
several repositories in one workspace, `src/**` names two directories, and a grant meant for one
repository would silently permit writes in the other. Keying by repository makes that
unrepresentable rather than merely discouraged; every key must name a repository the run actually
has, which is checked when the grant is minted.

---

## 4. Command profiles

**Models never author commands.** There is no tool accepting a shell string or free-form argv.

Repositories declare named profiles (`maven.test`, `npm.build`, …) with fixed argv, typed
parameters, cwd scope, timeout, limits and network policy. The tool
`workspace.run_profile(profileId, parameters)` is the only route to command execution.
Parameters are substituted as discrete argv elements; no shell is involved at any layer.

Adding a profile is a reviewed human change to repository configuration.

---

## 5. Invocation pipeline

```text
1  resolve grant from attempt token
2  resolve tool descriptor (id + version)
3  validate input against closed schema
4  enforce scope
5  enforce budget and denial circuit breaker
6  approval gate
7  idempotency check
      prior success           -> return recorded result
      intent without outcome  -> INDETERMINATE
8  write-ahead intent            (EXTERNAL_WRITE, IRREVERSIBLE)
9  dispatch
10 write outcome + audit; offload large payloads to the artifact store
11 return
```

Steps 8 and 10 straddle dispatch so that a crash mid-side-effect is detectable. Per ADR-0008,
`INDETERMINATE` is never auto-retried.

---

## 6. Denials

Deny by default. Denials are returned as **structured tool results**, not transport errors, so
the model can adapt — and are written as audit events. A bounded denial budget per attempt
trips a circuit breaker and fails the node with `TOOL_DENIED`, preventing budget-burning
thrash and surfacing incorrect grants.

---

## 7. Trust and audit

Tool results are untrusted data. They never carry platform directives and can never alter a
grant, budget, approval or transition. Oversized results are offloaded to the artifact store
and passed by reference.

Every invocation writes an append-only audit record: run, node, attempt, grant, tool and
version, canonical input hash, decision and reason, outcome, external references, actor,
timestamps, trace id. Audit is durable and retained independently of telemetry — traces may be
sampled, audit may not.
