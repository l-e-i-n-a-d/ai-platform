# ADR-0006: Local Execution Isolation and Credential Handling

## Status

Accepted — 2026-08-15

Implements ADR-0003 for V1. Read together with ADR-0005 (command profiles) and ADR-0012
(GitHub actor identity).

---

## Context

`.github/copilot-instructions.md` §14 asks for local workspaces "isolated as reasonably
practical". That is unfalsifiable, and its default reading — a subprocess in a working
directory, under the developer's own account — is the most dangerous configuration the
platform could ship.

An agent running as the developer inherits everything the developer has: `~/.ssh`,
`~/.aws`, `~/.azure`, `~/.config/gh`, git credential helpers, browser session stores, kube
contexts, mounted network shares, VPN reachability into the corporate network — and the
platform's own model API keys. It can also modify repositories outside its assigned workspace.

This is not primarily a model-misbehaviour concern. **Builds and tests execute untrusted
third-party code by design.** `npm install` runs lifecycle scripts; Maven and Gradle run
plugins; pytest imports whatever is on the path. The platform's core workflow is therefore
"fetch code referenced by a ticket and execute it", which is the standard supply-chain threat
with an autonomous actor attached, on a machine holding production credentials.

V1 has no centralized identity to fall back on. Isolation is the control.

---

## Decision

### 1. Container isolation is the default and only supported local execution mode

The local executor runs every execution in a container:

| Control | Setting |
|---|---|
| User | non-root, fixed UID/GID, no privilege escalation (`no-new-privileges`) |
| Capabilities | drop `ALL` |
| Root filesystem | read-only |
| Writable | the workspace mount, and `/tmp` as a size-limited tmpfs |
| Host mounts | the workspace only — never the home directory, never the container socket |
| Environment | explicit allowlist; the parent environment is never inherited |
| Limits | CPU, memory, PID and disk quotas on every execution |
| Network | default deny (see §4) |
| Image | platform-maintained, pinned by digest (see §5) |
| Seccomp / AppArmor | runtime defaults, not disabled |

A container runtime (Docker or Podman) therefore becomes a V1 prerequisite on the developer
machine. This is acceptable: the Quarkus toolchain the organisation already uses assumes one
for Dev Services and Testcontainers. It is stated plainly in the prerequisites rather than
discovered.

Containerising locally also *reduces* Phase 6 risk, because the local and Kubernetes executors
then share one mental model — image, argv, limits, network policy — rather than two.

### 2. `unsafe-host-exec` is the escape hatch, and it is loud

Some developers will not have a container runtime, and some diagnostics genuinely need the host.
A host execution mode exists with these conditions:

- disabled by default; enabling requires an explicit configuration change, not a flag on a run
- a warning at platform startup and on every run that uses it
- recorded on the run and in every audit record produced under it
- `EXTERNAL_WRITE` and `IRREVERSIBLE` tool classes require human approval regardless of the
  graph definition while it is active
- evaluation results produced under it are marked and excluded from comparisons

The mode is supported, not pretended away. It is simply never the quiet default.

### 3. The workspace container holds no credentials

This is the sharpest decision here, and it removes an entire class of exposure.

- **Materialisation happens outside the container.** The executor clones from a per-developer
  bare mirror cache into the workspace. The clone is local; no network, no token. The mirror
  is never mounted into the container.
- **Publishing happens outside the container.** `git fetch` and `git push` are never executed
  inside a workspace. Publishing a branch is a tool-layer operation: it takes the workspace's
  snapshot (an ordered patch series, ADR-0003 §6), applies it host-side, and pushes using the
  run's scoped short-lived token.
- **The container therefore never receives a GitHub, Jira, Confluence or model credential**,
  and there is no git credential helper reachable from inside it.

Untrusted code executing in the workspace has nothing to steal and nowhere to push. The cost
is that agents cannot perform arbitrary git remote operations; they produce changes, and the
platform publishes them.

### 4. Network policy is declared per command profile, default deny

Every execution declares `networkPolicy` (ADR-0003 §4). The default is `NONE`.

Profiles that genuinely need dependency resolution declare `ALLOWLIST(hosts)`, restricted to
package registries named in the repository registry, and mediated by a local egress proxy so
that the allowlist is enforced rather than advertised. Denied attempts are recorded in
`networkDenials` and audited.

Dependency resolution is where supply-chain compromise and injection-driven exfiltration would
both surface, so it is exactly where the platform should be able to say what was contacted.

### 5. Images are platform-maintained and pinned

A small set of tool images — JVM/Maven, Python, Node/Angular — maintained in this repository,
pinned by digest, with a declared update process. The repository registry declares which image
a repository uses.

No agent may select, modify or build an image, and no image is pulled by tag at execution time.
Image selection is a capability decision, so it belongs with the reviewed configuration and not
with the model.

### 6. Platform secrets never enter the execution path

Model provider keys and integration credentials are held by the control plane, sourced from the
OS keychain or a file readable only by the platform user. They are never placed in the
executor's environment, never in a container, never in a command profile, and never in a
workspace file.

The agent runtime holds none of them either (ADR-0004 §3), so no process handling untrusted
content ever has one in memory.

### 7. Workspace boundaries

Executions run with `cwd` inside the workspace, validated against the grant's `pathScope`.
Symlinks that escape the workspace are refused at materialisation and rejected at write time.
One workspace per run, exclusively leased (ADR-0003 §7). A run cannot reach another run's
workspace, and no run can reach the developer's own repositories.

### 8. Everything produced is untrusted output

Files, stdout, stderr and artifacts produced by an execution are data. They are scanned for
secrets before being persisted, truncated or offloaded above the size threshold, and never
interpreted as platform instructions when placed into model context (ADR-0005 §9).

### 9. Audit

Every execution records: workspace id, image digest, command profile id and resolved argv,
`cwd`, environment key names (values redacted), resource limits and actual usage, network
policy, network denials, exit code, duration, execution mode (`container` / `unsafe-host-exec`),
and the correlation identifiers.

"What did this agent actually run on my machine?" must be answerable exactly, from durable
state.

---

## Alternatives

**A. Subprocess under the developer's account, with a curated `PATH`.**
Simplest, zero prerequisites, and it provides no isolation whatsoever: the process has the
developer's whole identity. Rejected as the default; retained explicitly as
`unsafe-host-exec` so that developers who choose it do so knowingly.

**B. A dedicated local OS user for platform execution.**
Meaningfully better than A and considerably worse than containers: no filesystem, network,
resource or process isolation to speak of, and awkward to set up per platform. Rejected as
adding operational friction without proportionate benefit.

**C. Virtual machines or microVMs.**
Stronger isolation, notably against kernel-level escape. Rejected for V1 on developer
experience and startup cost. Worth revisiting if the platform ever executes code from
repositories outside the organisation.

**D. Give the container credentials so agents can push directly.**
Rejected. It places long-lived-enough credentials inside the one process that executes
untrusted third-party code, to save an indirection the platform needs anyway for idempotency
and audit.

**E. Allow network by default and block known-bad destinations.**
Rejected: denylists do not work for exfiltration, where any reachable host is sufficient.

---

## Consequences

**Accepted costs**

- A container runtime becomes a prerequisite, and container startup is added to execution
  latency. Image caching and per-run workspaces keep this tolerable.
- `NONE` as the default network policy will break naive builds until profiles declare their
  registries. This is intended: it makes each repository's real dependency surface explicit.
- Agents cannot run arbitrary git remote commands. Some workflows must be expressed as tools
  instead of as commands.
- Platform-maintained images are ongoing maintenance, including patching.

**Gained**

- Executing untrusted third-party build code stops being an unbounded risk on a developer's
  primary machine.
- The blast radius of a successful prompt injection is a credential-free, network-denied
  container holding one repository's working tree.
- The local and future Kubernetes executors share one enforcement model.
- The audit trail can state precisely what ran, from which image, with what reachability.

---

## Security / Operational Impact

- This ADR, ADR-0004 §4 and ADR-0005 are the three layers of the platform's injection defence:
  containment of what the model can request, of what the runtime can reach, and of what the
  executed code can touch. Each assumes the others.
- `unsafe-host-exec` is a documented, audited, approval-escalating downgrade — never silent.
- Container escape remains the residual risk and is accepted for V1, with microVMs recorded as
  the mitigation should the threat model change.
- Secret scanning of execution output is required before persistence, because build logs are a
  routine source of leaked credentials.

---

## Follow-up

- Rewrite `docs/architecture/execution-plane.md` (currently states workloads run on AKS).
- Update `SECURITY.md` §2 with the concrete local execution model.
- Update `.github/copilot-instructions.md` §14.
- Define the initial tool images and their update process.
- Define the egress proxy and per-repository registry allowlist format (ADR-0014).
- ADR-0012 — scoping and lifetime of the run's GitHub token used for host-side publishing.
