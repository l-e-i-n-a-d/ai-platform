# Developer Experience

**Status:** Planned (design agreed, not yet implemented)
**Decision:** [ADR-0018](../decisions/0018-developer-entry-surface-cli.md)

Goal 3 — every developer can run the platform on their own machine — is met or missed almost
entirely by this document.

---

## 1. Entry surface

```text
   developer
       |
      aip  (CLI)          thin client; no business logic
       |
       | REST + SSE
       v
  control plane  ──supervises──►  agent runtime
       |
       └──────────────────────►  local executor (containers)
```

The CLI is the only entry surface in V1. Anything it can do is available over the API, so a
future UI is a peer client rather than a rewrite.

---

## 2. Commands

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

`aip up` starts and supervises both processes and verifies the container runtime — one command,
or local-first is undermined in practice.

`aip run show --grants` answers "what is this run allowed to do" before and during a run.

Output is human-readable by default and `--json` for scripting. Exit codes are stable and
categorised: success, run failed, run rejected, approval required, not found, configuration
error, platform unavailable.

---

## 3. Approvals

`aip run approve` displays the subject and its **content hash** (ADR-0008 §13) and requires
explicit confirmation on an interactive terminal. The hash is shown because it is what makes
the time-of-check/time-of-use protection visible to the person taking responsibility.

`--yes` is supported for scripting and recorded distinctly in the audit trail: an unattended
approval is a different assertion from a human reading a diff.

With no central identity in V1, the CLI is where local operator consent is established.

---

## 4. Prerequisites

- a container runtime (Docker or Podman) — ADR-0006
- a JVM toolchain — control plane
- Python — agent runtime
- credentials for GitHub, Jira, Confluence and at least one model provider, in the OS keychain

**Node is not a V1 prerequisite.** No UI is built until the trigger in ADR-0018 §6 is met.

No database, storage emulator or cloud account is required — ADR-0007 removed them.

---

## 5. Bootstrap acceptance criterion

> **Clone to first successful run in under thirty minutes**, on a machine with a container
> runtime.

This is a Phase 1 acceptance criterion, measured rather than assumed. Supporting it:

- `aip doctor` reports what is missing and how to fix it; startup failures are actionable, never
  a stack trace
- a documented, validated configuration schema, with the offending field named on error
- credentials read from the OS keychain, never from repository files; `doctor` checks presence
  without printing values

---

## 6. Offline smoke workflow

A fixture repository and a graph that exercise **graph → agent → tool → execution interface →
local executor → persistence** end to end with **no external system access**: no Jira, no
GitHub, no model provider.

It serves three purposes at once — onboarding proof, CI acceptance test, and the check that
tells a new contributor whether their machine works before they have obtained a single
credential.

---

## 7. Contained toolchain cost

The Java-plus-Python split is paid for by every contributor. It is contained by keeping the
Python runtime dependency-light, deferring Node entirely, and treating onboarding time as a
measured metric.
