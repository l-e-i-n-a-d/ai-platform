# ADR-0003: Execution Interface Contract and Executor Substitutability

## Status

Accepted — 2026-08-15

Read together with ADR-0006 (local execution isolation). ADR-0005 depends on this contract:
command profiles are only meaningful if the executor enforces them.

---

## Context

The execution interface is the abstraction that keeps graph and agent logic free of execution
mechanics, and it is the mechanism by which a Kubernetes executor could later be added without
redesigning workflow semantics. It is named in `ARCHITECTURE.md` and in `PRINCIPLES.md`, and
it has no contract: no operations, no request or result types, no workspace lifecycle, no
error taxonomy.

Unspecified abstractions leak toward their only implementation. Written without a contract,
the first local executor will almost certainly expose host filesystem paths, accept shell
strings, assume the caller shares its filesystem, and return open file handles. Every one of
those breaks under a remote executor. The team would then discover at Phase 6 that "add an
executor" actually means "rewrite the tool layer" — the precise outcome the abstraction exists
to prevent.

The differences are larger than they appear. A remote executor has no shared filesystem with
the control plane, needs volumes for workspace persistence, needs images built and
distributed, schedules pods in seconds rather than milliseconds, and retrieves logs and
artifacts over a network. A contract that quietly assumes the opposite of each is not portable.

`docs/architecture/execution-plane.md` currently states that workloads run on AKS, which
contradicts the local-first decision and must be corrected as part of this ADR.

---

## Decision

### 1. Operations

```text
createWorkspace(WorkspaceSpec)               -> WorkspaceId
materialize(WorkspaceId, RepoRef)            -> MaterializationResult
submit(WorkspaceId, ExecutionRequest)        -> ExecutionHandle
await(ExecutionHandle, timeout)              -> ExecutionResult
poll(ExecutionHandle)                        -> ExecutionStatus
cancel(ExecutionHandle)                      -> void
readArtifact(WorkspaceId, path)              -> ArtifactRef
writeArtifact(WorkspaceId, path, ArtifactRef)-> void
snapshot(WorkspaceId)                        -> ArtifactRef      // ordered patch series
destroy(WorkspaceId)                         -> void
```

### 2. Asynchronous from day one

`submit` returns a handle; results are obtained by `await` or `poll`. The local executor
completes in milliseconds and could have been synchronous — it is not, deliberately. A
synchronous signature would let callers assume low latency, and every caller written against
that assumption breaks when scheduling takes seconds.

### 3. Contract rules

These six rules are the substitutability guarantee. Each maps to a specific way a remote
executor would otherwise break:

| Rule | Prevents |
|---|---|
| Workspaces are addressed by **opaque ID**; no host path ever crosses the boundary | callers building paths and reading them directly |
| Commands are **argv arrays**; never shell strings | shell semantics that no remote runtime reproduces |
| Environment is an **explicit allowlist**; never inherited | dependence on the developer's ambient environment |
| Artifacts move as **references**; never local paths or open handles | shared-filesystem assumptions |
| No persistent interactive session between calls; each execution is independent | statefulness that cannot survive rescheduling |
| Every request declares timeout, resource limits and network policy | unbounded work and implicit connectivity |

A workspace ID is an opaque token. Anything that parses one is a defect.

### 4. Request and result shapes

```text
ExecutionRequest {
  argv[]                    // resolved from a command profile (ADR-0005 §5)
  cwd                       // workspace-relative, validated against pathScope
  envAllowlist{}            // explicit key/value; nothing inherited
  timeout
  resourceLimits            // cpu, memory, pids, disk
  networkPolicy             // NONE | ALLOWLIST(hosts)
  stdinRef?                 // artifact reference
  correlation               // runId, nodeId, attempt, traceparent — telemetry only
}

ExecutionResult {
  status                    // COMPLETED | TIMED_OUT | CANCELLED | RESOURCE_EXCEEDED | EXECUTOR_ERROR
  exitCode                  // present when COMPLETED
  stdoutRef, stderrRef      // artifact references, always; never inline beyond a preview
  durationMs, resourceUsage
  networkDenials[]          // observability and security signal
}
```

**A non-zero exit code is a result, not an error.** A failing test is the normal case in a
repair loop. Interface errors are reserved for the executor failing to run the command at all.

The `correlation` block is carried for telemetry and never interpreted. The executor knows
nothing of graphs, agents, runs or tools.

### 5. Error taxonomy

`WORKSPACE_NOT_FOUND`, `MATERIALIZATION_FAILED`, `INVALID_REQUEST`, `RESOURCE_EXCEEDED`,
`TIMED_OUT`, `CANCELLED`, `EXECUTOR_UNAVAILABLE`, `EXECUTOR_ERROR`.

These map onto the failure categories of ADR-0008; the executor does not decide retryability.

### 6. Workspace reconstructibility (the load-bearing invariant)

> Workspace state must at all times be a function of `(repoRef, baseSHA, ordered patch series)`,
> all of which live in durable state.

If this holds, a workspace can be destroyed and rebuilt anywhere, which is simultaneously what
makes resume work (ADR-0008 §15) and what makes a remote executor a drop-in. If it does not
hold, workspaces become precious mutable state on one laptop and both properties are lost.

Consequences: no execution may depend on state left by an earlier execution other than through
the tracked working tree; `snapshot` must be sufficient to reproduce the workspace; anything
outside the working tree is scratch and may vanish.

### 7. Workspace lifecycle

- **One workspace per run**, not per node. Per-node materialisation of a large repository makes
  the platform feel unusable; per-run reuse keeps the common case fast.
- **Materialisation** from a per-developer cache of bare mirrors, cloned locally into the
  workspace so it owns its own `.git`. The mirror itself is never exposed to executed commands.
- **Exclusive lease** per workspace. Two runs never share a checkout.
- **Quota with LRU eviction**; workspaces of failed runs are quarantined for a bounded period
  for debugging, then collected. Without this, laptops fill silently.
- `destroy` is always safe, because of §6.

### 8. Cancellation

`cancel` terminates the execution's **process group** (or the remote equivalent) and returns
`CANCELLED`. It is best-effort for work in flight and guaranteed to stop new work, matching
ADR-0008 §14. Cancellation never interrupts a side-effecting tool invocation mid-flight; that
is a tool-layer concern and resolves to `INDETERMINATE`.

### 9. Keeping the abstraction honest

A CI mode runs the local executor in **remote simulation**: artifact access by reference only,
path-based access refused, and artificial latency injected into `submit`. Violations then
surface on the day they are written rather than in Phase 6.

This is cheap and it is the only mechanism in this ADR that is self-enforcing. The contract
rules in §3 otherwise depend on code review.

### 10. A future Kubernetes executor changes only the executor

| Concern | Local (V1) | Kubernetes (future) | Layer affected |
|---|---|---|---|
| Workspace | container + local volume | PVC or ephemeral volume | executor only |
| Materialisation | local mirror clone | init container clone | executor only |
| Command | container exec, argv | Job/Pod spec, argv | executor only |
| Latency | milliseconds | seconds | absorbed by async `submit`/`await` |
| Artifacts | path → artifact store | artifact store only | none — already references |
| Credentials | injected short-lived | mounted secret / workload identity | executor only |
| Graph engine, agent runtime, tool layer | — | — | **none** |

---

## Alternatives

**A. No abstraction in V1; add one when Kubernetes arrives.**
Cheaper now, and it is the standard way this goes wrong. By then the tool layer is written
against local assumptions and the abstraction has to be retrofitted through every caller.

**B. A synchronous interface, made asynchronous later.**
Rejected: the signature change is trivial; the assumptions callers build on it are not.

**C. Expose workspace paths for convenience.**
Rejected. It is the single most tempting violation and the one that ends portability, because
every subsequent shortcut builds on it.

**D. Model the interface on the Kubernetes API now.**
Rejected as the opposite error — leaking future execution concepts into V1, which
`PRINCIPLES.md` forbids as directly as it forbids the reverse.

---

## Consequences

**Accepted costs**

- Artifact indirection is slower and more verbose than reading a file, on a laptop where the
  file is right there.
- Async handles add bookkeeping the local executor does not need.
- Remote-simulation CI mode is extra machinery whose only purpose is to make the design fail
  loudly.

**Gained**

- Phase 6 becomes a contained piece of work with a defined blast radius.
- Resume and evaluation both fall out of workspace reconstructibility.
- The tool layer can be tested against a fake executor, and the executor against a fake tool
  layer.

---

## Security / Operational Impact

- Argv-only and env-allowlist are security controls as much as portability ones: they remove
  shell injection as a category and stop ambient credentials reaching executed commands.
- `networkPolicy` is mandatory on every request, so connectivity is a decision rather than a
  default.
- `networkDenials` in results is an injection and supply-chain signal worth alerting on.
- The executor holds workspace and command authority only; it makes no policy decisions and
  never sees a capability grant.

---

## Follow-up

- Rewrite `docs/architecture/execution-plane.md` to this contract (currently says AKS).
- Correct `docs/architecture/system-context.md` and `docs/integrations/kubernetes.md`.
- ADR-0006 — how the local executor enforces this contract.
- Executor contract test suite, runnable against any implementation.
- Workspace quota, retention and GC defaults.
