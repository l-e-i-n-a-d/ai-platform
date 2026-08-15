# GitHub Integration

GitHub is the system of record for source code, repositories, pull requests, code review and CI/CD.

**Decisions:** [ADR-0012](../decisions/0012-github-actor-identity-and-write-back.md),
[ADR-0006 §6](../decisions/0006-local-execution-isolation-and-credentials.md),
[ADR-0013 §4](../decisions/0013-context-bundle-contract.md)

---

## Identity

The platform acts as a **GitHub App**, installed per repository, minting short-lived
installation tokens **per run**, scoped to the repositories that run touches.

Not a developer PAT: that would make agent work indistinguishable from human work, break review
policy and CODEOWNERS assumptions, carry far broader scope than needed, and cannot be scoped per
run. Not a machine user: a shared long-lived credential that accumulates access.

The App is explicitly **denied**:

- merge and branch-protection bypass
- environment and deployment approvals
- repository administration and settings
- secret management

The platform opens pull requests; humans merge them. A control the platform could lift is not a
control.

### Action identity is not retrieval identity

The App acts. **Context retrieval authenticates as the developer** (ADR-0013 §4). Reading
through an App installed across many repositories would let any developer obtain content from
repositories they cannot access — the exact permission amplification the context model exists to
prevent.

### Attribution

```text
Co-authored-by: <developer>
AI-Platform-Run: <runId>
```

Pull request bodies carry the run id, graph id and version, work item key and context bundle
ref. The App is who acted; the developer is who asked. After the fact, the second is the
question people actually ask.

---

## Credential handling

Installation tokens are held by the control plane and used only by this adapter. They never
enter a workspace container, never reach a workspace git config, and are never visible to
executed code.

`git push` never runs inside a workspace. Publishing is a host-side tool-layer operation that
applies a workspace snapshot (ADR-0006 §6).

---

## Canonical models

This adapter maps GitHub onto `Repository`, `PullRequest` and `CheckResult`. GitHub API shapes
do not appear elsewhere in the platform.

Rate limiting, pagination, retry and error mapping are centralised here. Agents produce bursty
access patterns.

---

## CI feedback

Polling, not webhooks — laptops have no publicly reachable endpoint, and arranging one would
contradict local-first.

- correlate by commit SHA plus a run identifier in the branch name
- poll check runs with backoff and an explicit overall timeout
- retrieve logs to the artifact store
- **extract failure-relevant excerpts deterministically before any model sees them** — raw
  multi-megabyte logs are expensive, ineffective, and an easy way to smuggle content into a
  prompt
- a workflow requiring manual approval pauses the run as an approval state, not a failure

---

## Write-back

| Action | V1 |
|---|---|
| branch and commit push | unattended, within capability grant |
| pull request creation | unattended for `INTERNAL`; approval for `RESTRICTED` |
| PR comments and review replies | unattended, marked, idempotent |
| merge | never |

Every unattended write is idempotent, keyed by run and node, so retries update rather than
duplicate.

All platform-authored content carries machine-readable provenance markers, and the context
engine treats it as lower trust than human-authored content.
