# ADR-0018: Developer Entry Surface — CLI in V1, UI Deferred

## Status

Accepted — 2026-08-15

---

## Context

Phase 1's success criterion is that a developer can run a complete small engineering workflow
locally, and the example workflow explicitly includes a human approval step. Phase 1 lists no
user interface of any kind — no CLI, no API client, no UI. `ARCHITECTURE.md` names Angular as
the frontend technology "where a UI is required" without deciding whether V1 requires one.

As written, there is no way to start a run, observe it, respond to an approval, cancel it, or
inspect a failure. **Phase 1 cannot meet its own success criterion.** Approvals in particular
need an interactive surface by definition — a durable pause with no way to resolve it is just a
stuck run.

This is also the decision that determines whether the local-first goal is real. Seven ADRs now
describe an architecture that is defensible on paper; none of them matter if getting to a first
successful run takes a day. The platform currently requires a JVM, Python and a container
runtime before any target repository's own toolchain is considered.

Two things have made this easier than the review anticipated. ADR-0007 removed the database and
storage emulators from the prerequisite list, and ADR-0006 replaced them with a container
runtime that the Quarkus toolchain already assumes.

---

## Decision

### 1. A CLI is a Phase 1 deliverable and the only entry surface in V1

The CLI is how a developer starts, observes, approves, cancels, resumes and inspects runs. It
suits local-first, it is fast to build, it is scriptable, and it does not commit the platform
to a frontend before the API has stabilised.

### 2. The CLI is a thin client over the control-plane REST API

No business logic in the CLI. It formats requests, renders responses and manages local
configuration. Anything it can do is available over the API.

This is the load-bearing property. It forces the API to be a real, usable contract rather than
an internal detail, and it makes a future UI a *peer client* rather than a rewrite. A CLI that
accumulates logic quietly becomes a second implementation of the platform.

### 3. Command surface

```text
aip up | down | status              start, stop and inspect the local platform
aip doctor                          verify prerequisites, config and credentials

aip run start --graph G --work-item KEY --repo R
aip run list | status <id> | watch <id>
aip run approve <id> | reject <id>
aip run cancel <id> | resume <id>
aip run logs <id> [--node N]
aip run show <id> --grants | --audit | --artifacts

aip repo list | show <id> | validate
aip graph list | show <id> | validate <file>
```

`aip up` supervises both processes (control plane and agent runtime) and verifies the container
runtime. A developer starts the platform with one command or the local-first goal is undermined
in practice.

`aip run show --grants` is deliberate: "what is this run allowed to do" must be answerable
before and during a run, not reconstructed afterwards from an ADR.

### 4. Approval is an interactive, consent-based act

`aip run approve` displays what is being approved, together with its content hash (ADR-0008
§13), and requires explicit confirmation on an interactive terminal.

Non-interactive approval (`--yes`) is supported for scripting, but is recorded distinctly in
the audit trail, because an unattended approval is a materially different assertion from a
human reading a diff.

With no central identity in V1, the CLI is where local operator consent is established. It is
therefore the point at which the approval model of ADR-0009 becomes real, and it is honest
about the limits: consent is asserted by whoever controls the terminal.

### 5. Two output modes and stable exit codes

Human-readable by default; `--json` for scripting and for the platform's own future agents.
Exit codes are stable and categorised — success, run failed, run rejected, approval required,
not found, configuration error, platform unavailable — so the CLI can be used in scripts and,
eventually, by the platform on itself.

### 6. Angular is deferred, with a recorded trigger

A UI becomes genuinely valuable when there are approval queues spanning multiple people,
evaluation dashboards, or a shared hosted deployment. None of those exist in V1.

Building it earlier would commit to a frontend before the API stabilises and would add the
Node toolchain to every contributor's prerequisites for no V1 benefit. **Node is explicitly not
a V1 prerequisite.**

Angular remains the chosen technology when the trigger is met; only the timing is deferred.

### 7. Bootstrap is a measured acceptance criterion

> **Clone to first successful run in under thirty minutes**, on a machine with a container
> runtime, is a Phase 1 acceptance criterion.

Supporting requirements:

- **`aip doctor`** verifies prerequisites, configuration and credentials, and reports what is
  missing and how to fix it. Startup failures must be actionable, never a stack trace.
- **A documented, validated configuration schema.** Configuration errors are reported at
  startup with the offending field named.
- **Credentials come from the OS keychain**, never from files in the repository, and never
  committed. `doctor` checks presence without printing values.
- **A fixture-repository smoke workflow** that exercises graph, agent, tool, executor and
  persistence end to end **with no external system access** — no Jira, no GitHub, no model
  provider. It is the onboarding proof, the CI acceptance test, and the thing that tells a new
  contributor whether their machine is set up before any credential exists.

### 8. Toolchain cost is contained

The Java-plus-Python split has a real cost, paid by every contributor. It is contained by
keeping the Python runtime dependency-light, deferring Node entirely, and treating onboarding
time as a measured metric rather than an assumption.

---

## Alternatives

**A. Build the Angular UI in V1.**
Rejected: it commits to a frontend before the API is stable, adds the Node toolchain to the
prerequisite list, and delivers its main value — shared approval queues and dashboards — only
in a deployment model V1 does not have.

**B. REST API only; use `curl`.**
Rejected. Approvals need an interactive surface with content displayed and confirmed, and
`curl` is not a workflow. It also leaves consent, the one control standing in for identity,
with no defined mechanism.

**C. A terminal UI (TUI).**
Nicer for watching a run; harder to script, harder to test, and premature polish before the
workflow underneath is proven.

**D. An IDE extension as the primary surface.**
Genuinely attractive for this audience and rejected for V1: it multiplies by editor, is harder
to automate, and would still need the API and CLI beneath it. Worth revisiting once the API is
stable.

**E. A CLI containing business logic, talking directly to the store.**
Rejected: it creates a second writer of durable state, violating the first invariant of
ADR-0004, and makes the API a secondary artifact that will drift.

---

## Consequences

**Accepted costs**

- The API must be designed for an external client from day one, including a streaming endpoint
  for `run watch`. That is more work than an internal-only interface.
- No graphical view of a run in V1. Debugging a complex graph will be less pleasant.
- The CLI becomes a compatibility surface with its own versioning concerns.

**Gained**

- Phase 1 can actually meet its success criterion.
- Every capability is scriptable, which makes the platform testable end to end and eventually
  able to operate on itself (`PRINCIPLES.md` self-hosting goal).
- The API is validated by a real consumer before any UI depends on it.
- The prerequisite list stays at JVM, Python and a container runtime.

---

## Security / Operational Impact

- The CLI is the audit actor for developer-initiated actions: every command records the local
  developer identity, and every consequential command is attributable to a run.
- Approval confirmation displays the content hash, which is what makes the TOCTOU protection in
  ADR-0008 §13 visible to the person accepting responsibility for it.
- `--yes` is a genuine weakening of the approval control and is therefore recorded distinctly
  rather than treated as equivalent.
- `aip doctor` must never print credential values.
- The CLI holds no credentials of its own; it talks to the local control plane, which holds
  them.

---

## Follow-up

- `docs/architecture/developer-experience.md` — CLI, bootstrap and smoke workflow.
- Add the CLI to `ROADMAP.md` Phase 1; record the Angular trigger.
- Define the configuration schema and the `doctor` check list.
- Build the fixture repository and its offline smoke graph.
- ADR-0009 — the approval model the CLI surfaces.
- Repository hygiene (CI documentation lint, `CODEOWNERS`, PR templates) remains open; nothing
  currently enforces the documentation consistency this decision set restored.
