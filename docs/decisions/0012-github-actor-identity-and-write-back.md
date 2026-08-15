# ADR-0012: GitHub Actor Identity and Write-Back Semantics

## Status

Accepted — 2026-08-15

Provides the external identity relied on by ADR-0009 (`EXTERNAL_ATTESTATION`) and the host-side
publishing path in ADR-0006 §6. Uses the repository registry from ADR-0014 for installation
scope.

---

## Context

The platform will create branches, push commits, open pull requests and read CI results. No
decision exists on the identity it does so under, and the three candidates behave very
differently.

A **developer PAT** makes agent actions indistinguishable from the developer's own. Branch
protection, CODEOWNERS and review policy all treat them as human work, the organisation loses
any ability to measure AI contribution, and PATs typically carry far broader scope than the task
requires. It also cannot be scoped per run.

A **machine user account** consumes a seat, is a shared credential in practice, and tends to
accumulate access.

A **GitHub App** issues short-lived installation tokens, scoped per repository and per
permission set.

There is a second question that is usually answered by accident: what the platform may write to
Jira and Confluence unattended. Retries duplicate comments. Unattended status transitions
disrupt a team's real process and erode trust in Jira as the system of record. Unmarked
platform-authored Confluence content is worse still, because that content later becomes agent
context — the platform learns from its own unreviewed output, and the loop reinforces whatever
it got wrong.

---

## Decision

### 1. GitHub actions use a GitHub App

The platform acts as a GitHub App, installed per repository, minting **short-lived installation
tokens per run**, scoped to the repositories that run touches.

This gives clear provenance — an agent-authored PR is visibly not a human one — least privilege,
per-run scoping and clean revocation. It is also what makes per-run credential scoping practical
at all; nothing else on the list can do it.

### 2. The App is explicitly denied merge and deployment rights

The installation must not hold:

- merge or branch-protection-bypass permissions
- environment or deployment approval permissions
- repository administration or settings permissions
- secret management permissions

The platform opens pull requests. Humans merge them. This is a permission boundary, not a policy
the platform enforces on itself, because a boundary the platform could lift is not a boundary.

### 3. The requesting developer is recorded on every action

Commits carry a trailer naming the initiating developer and the run:

```text
Co-authored-by: <developer>
AI-Platform-Run: <runId>
```

Pull request bodies carry the run id, the graph id and version, the work item key and the
context bundle ref.

The App is *who acted*; the developer is *who asked*. Both belong in the record, and after the
fact the second question is the one people actually ask.

### 4. Token scope is per run, and tokens never enter a workspace

Installation tokens are minted for the repositories a run touches, held by the control plane,
and used only by the GitHub integration adapter.

They are never placed in a workspace container, never written to a git config inside a
workspace, and never exposed to executed code (ADR-0006 §4). Publishing is a host-side tool-layer
operation that applies a workspace snapshot — `git push` never runs inside a workspace.

### 5. Retrieval identity is not action identity

The App's identity is used for **actions**. Context retrieval continues to authenticate as the
developer (ADR-0013 §4).

This distinction is essential. Using the App to read would silently restore the permission
amplification ADR-0013 exists to prevent: the App is installed across repositories, so reading
through it would let any developer obtain content from repositories they cannot access.

### 6. Integrations are anti-corruption layers over canonical models

Each integration maps its external system onto canonical internal models — `WorkItem`,
`KnowledgeDocument`, `Repository`, `PullRequest`, `CheckResult` — and nothing else in the
platform sees Jira, Confluence or GitHub shapes.

Jira and Confluence data models are irregular by nature: custom fields, per-project workflows,
storage-format markup. Leaking those into graph and agent logic makes every Jira configuration
change a platform change.

Rate limiting, pagination, retry and error mapping are centralised per integration. Agents
generate bursty access patterns and all three APIs are aggressively rate-limited.

### 7. Polling, not webhooks, in V1

Webhooks require a publicly reachable endpoint. Laptops do not have one, and arranging one would
contradict local-first.

CI feedback correlates by commit SHA plus a run identifier in the branch name, polled with
backoff and an explicit overall timeout. CI logs are retrieved to the artifact store, and
**failure-relevant excerpts are extracted deterministically before any model sees them** —
feeding multi-megabyte raw logs to a model is expensive, ineffective, and a fine way to smuggle
content into a prompt.

A workflow that requires manual approval pauses the run as an approval state, not a failure.

Webhooks become reasonable if the platform is ever centrally hosted; that is a Phase 7 revisit.

### 8. Write-back is read-mostly by default

| Action | V1 |
|---|---|
| Jira comment, clearly marked, idempotent, carrying the run id | unattended |
| Jira status transition | requires approval |
| Confluence publication or edit | requires approval |
| GitHub branch and commit push | unattended, within capability grant |
| GitHub pull request creation | unattended for `INTERNAL`; approval for `RESTRICTED` |
| GitHub merge | never (§2) |

Every unattended write is idempotent, keyed by run and node, so a retry updates rather than
duplicates. Duplicate comments are the classic symptom of a durable system that forgot its
external effects are not transactional (ADR-0008 §12).

### 9. Platform-authored content is machine-readably marked, and treated as lower trust

All platform-authored comments, pages and PR bodies carry provenance markers.

The context engine treats platform-authored content as lower-trust than human-authored content
and never lets it silently become authoritative. Without this, the platform reads its own
unreviewed output back as fact, and confident errors compound quietly across runs. This is the
one integration failure mode that gets worse the longer it goes unnoticed.

---

## Alternatives Considered

**Developer PAT.** Zero setup, works immediately. Rejected: no provenance, broad scope, no
per-run scoping, and agent work becomes indistinguishable from human work — which quietly
defeats review policy and makes AI contribution unmeasurable.

**Machine user account.** Familiar. Rejected: a shared long-lived credential that accumulates
access and consumes a seat, with no per-run scoping.

**GitHub App with merge rights, gated by platform policy.** More autonomy. Rejected: a control
the platform can lift is not a control. Merge authority should be absent, not withheld.

**Webhooks in V1.** Lower latency, less API load. Rejected: incompatible with local-first.

**Free-form write-back with the platform trusted to be sensible.** Rejected: retries duplicate,
status transitions disrupt real processes, and unmarked Confluence content poisons future
context.

---

## Consequences

**Positive**

- Agent-authored changes are visibly distinct, so review policy and contribution measurement
  both work.
- Least privilege and per-run token scoping become practical.
- Revocation is clean — uninstall or rotate, without touching developer credentials.
- Canonical models keep external system irregularities out of graph and agent logic.
- Idempotent write-back means retries do not embarrass the team in front of stakeholders.

**Negative**

- A GitHub App requires organisation-level setup and its private key must be managed; this is
  the heaviest onboarding step in V1.
- Two identities in play — App for actions, developer for retrieval — is a distinction people
  will get wrong, so it needs stating repeatedly.
- Polling costs API quota and adds latency to CI feedback.
- Anti-corruption layers are real work and lag external system features.
- Approval-gated Jira transitions make some workflows feel slower than a fully autonomous
  platform would.

---

## Security Notes

- Installation tokens are short-lived, per-run, per-repository, and never enter a workspace or a
  command environment.
- The App must not hold merge, deployment, administration or secret-management permissions.
- The App identity is never used to widen context retrieval (§5).
- CI logs are untrusted content and are extracted deterministically before reaching a model.
- Platform-authored content is marked and down-weighted so the platform cannot launder its own
  output into authoritative context.
- The App private key is a high-value credential held by the control plane only, and is a strong
  candidate for centralised secret management if the platform is ever hosted.

---

## Follow-up

- Rewrite `docs/integrations/github.md` with App identity, token scoping and write-back rules.
- Update `docs/integrations/jira.md` and `confluence.md` with canonical models, polling and
  write-back defaults.
- Update `SECURITY.md` §4 with the App permission denials.
- Update `README.md` prerequisites with GitHub App installation.
- ADR-0016 — audit and attribution, which consumes the run/developer/App triple.
