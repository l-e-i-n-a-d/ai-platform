# Execution Plane

**Status:** Planned (design agreed, not yet implemented)
**Decisions:** [ADR-0003](../decisions/0003-execution-interface-contract.md),
[ADR-0006](../decisions/0006-local-execution-isolation-and-credentials.md)

---

## 1. Structure

```text
              Tool Layer  (control plane)
                     |
                     v
            EXECUTION INTERFACE          contract, ADR-0003
             /                \
            v                  v
    Local Executor        Kubernetes Executor
        V1                    future
```

The execution plane runs repository workloads. In V1 it runs them **locally**, in containers,
on the developer's machine. Kubernetes is a possible future implementation of the same
interface, not a V1 requirement.

The control plane does not execute repository commands directly. Nothing above the execution
interface knows whether execution is local or remote.

---

## 2. Interface

```text
createWorkspace(WorkspaceSpec)                -> WorkspaceId
materialize(WorkspaceId, RepoRef)             -> MaterializationResult
submit(WorkspaceId, ExecutionRequest)         -> ExecutionHandle
await(ExecutionHandle, timeout)               -> ExecutionResult
poll(ExecutionHandle)                         -> ExecutionStatus
cancel(ExecutionHandle)                       -> void
readArtifact(WorkspaceId, path)               -> ArtifactRef
writeArtifact(WorkspaceId, path, ArtifactRef) -> void
snapshot(WorkspaceId)                         -> ArtifactRef
destroy(WorkspaceId)                          -> void
```

Asynchronous by design, even though the local executor completes in milliseconds.

**Contract rules.** Workspaces are addressed by opaque ID — no host path ever crosses the
boundary. Commands are argv arrays, never shell strings. Environment is an explicit allowlist,
never inherited. Artifacts move as references, never paths or handles. No persistent session
exists between executions. Every request declares timeout, resource limits and network policy.

A non-zero exit code is a **result**, not an error. A failing test is the normal case.

---

## 3. Reconstructibility invariant

> Workspace state is always a function of `(repoRef, baseSHA, ordered patch series)`.

This is what makes resume work and what makes a remote executor a drop-in. Workspaces are
disposable, never precious.

---

## 4. Workspace lifecycle

- one workspace per **run**, not per node
- materialised by local clone from a per-developer bare mirror cache; the mirror is never
  exposed to executed commands
- exclusively leased; two runs never share a checkout
- quota with LRU eviction; failed-run workspaces quarantined for a bounded period, then
  collected
- `destroy` is always safe

---

## 5. Local executor isolation (V1)

Every execution runs in a container: non-root with all capabilities dropped, read-only root
filesystem, only the workspace and a size-limited `/tmp` writable, no home directory or
container socket mounted, explicit environment allowlist, CPU/memory/PID/disk limits, and
network **default deny**.

**The workspace container holds no credentials.** Materialisation and publishing both happen
outside it: `git fetch` and `git push` are never executed in a workspace. Publishing a branch
is a tool-layer operation that applies the workspace snapshot host-side using the run's scoped
short-lived token.

Network access is declared per command profile and mediated by an egress proxy limited to the
repository's declared package registries. Denials are recorded and audited.

Images are platform-maintained and pinned by digest. No agent may select, modify or build one.

`unsafe-host-exec` exists for developers without a container runtime: disabled by default,
warned at startup, recorded in the audit trail, and escalating `EXTERNAL_WRITE` and
`IRREVERSIBLE` tools to mandatory approval while active.

A container runtime (Docker or Podman) is a V1 prerequisite.

---

## 6. Typical capabilities

Provided by the platform-maintained tool images, selected per repository:

- Git
- Java / Quarkus tooling (Maven, Gradle)
- Python tooling
- Node / Angular tooling
- tests and static analysis

Not every workspace needs every tool. Helm and kubectl are relevant only to repositories that
require them, and only in future deployments.

---

## 7. Cancellation

`cancel` terminates the execution's process group and returns `CANCELLED`. Guaranteed to stop
new work, best-effort for work in flight. A side-effecting tool invocation is never interrupted
mid-flight; it completes or is recorded as `INDETERMINATE`.

---

## 8. Keeping the abstraction honest

CI runs the local executor in **remote simulation** mode: artifact access by reference only,
path-based access refused, artificial latency injected. Contract violations surface when they
are written rather than at the point a second executor is added.
