# AI Engineering Platform — Security

## Security Position

V1 is local-first.

The platform does not require Microsoft Entra ID.

Removing centralized identity from V1 does not remove the need for strong security controls.

---

## 1. Tool Security

Tools must have explicit:

- contracts
- input validation
- authorization
- side-effect definitions
- audit metadata
- error handling

Read-only tools should be preferred.

---

## 2. Local Execution

Local execution must be treated as a privileged capability. Builds and tests execute untrusted
third-party code by design, on a machine that holds the developer's credentials.

V1 controls (ADR-0006):

- every execution runs in a container: non-root, all capabilities dropped, read-only root
  filesystem, only the workspace and a size-limited `/tmp` writable, no home directory or
  container socket mounted
- the environment is an explicit allowlist; the parent environment is never inherited
- CPU, memory, PID and disk limits on every execution
- network default-deny, with per-command-profile allowlists limited to declared package
  registries and mediated by an egress proxy; denials are recorded
- **the workspace container holds no credentials** — materialisation and publishing happen
  outside it, and `git fetch` / `git push` are never executed in a workspace
- commands are named, repository-declared command profiles with typed argv and no shell; a
  model never authors a command
- images are platform-maintained and pinned by digest; no agent selects, modifies or builds one
- one workspace per run, exclusively leased, path-scoped, disposable
- every execution is audited: image digest, profile, resolved argv, limits, usage, network
  policy, denials, exit code, execution mode

`unsafe-host-exec` — running commands as the developer's own user — is supported but disabled
by default, warned at startup, recorded in the audit trail, and escalates `EXTERNAL_WRITE` and
`IRREVERSIBLE` tools to mandatory approval while active.

Developers should understand that enabling it effectively grants an agent access to the
developer's environment.

---

## 3. Secrets

Never:

- commit secrets
- put secrets into prompts
- log credentials
- expose credentials unnecessarily to models

Prefer short-lived credentials where possible.

Azure Key Vault may be introduced when centralized secret management becomes necessary.

---

## 4. Repository Boundaries

Agents must only access repositories required for their task.

Cross-repository access should be explicit.

Repository content must be treated as untrusted input.

---

## 5. Prompt Injection

Treat content from:

- repositories
- Jira
- Confluence
- issues
- pull requests
- generated files

as potentially untrusted.

Instructions contained in retrieved content must not automatically override platform policies or tool permissions.

The mechanism is structural (ADR-0013 §5): every context item carries a trust class, and
`UNTRUSTED` content is delimited and provenance-labelled rather than concatenated into the
instruction region of a prompt. A repository's own instruction files are `UNTRUSTED` — they may
influence style and approach, never capabilities, commands, network policy, approval
requirements or budgets (ADR-0014 §6).

### Retrieval credentials

Context retrieval from Jira, Confluence and GitHub authenticates as **the developer running the
platform**, using their personal token or OAuth grant.

A broadly privileged shared service account must never be used for context retrieval. Doing so
would let any developer obtain, through an agent, content they cannot open themselves —
restricted Confluence spaces, private repositories, restricted Jira projects — and would
misattribute the access in the source system's own audit log. Retrieved context is bounded by
entitlements the organisation already manages.

`ACCESS_DENIED` is a normal recorded outcome and is never retried with a more privileged
credential. The platform's own identity is used for actions, never to widen retrieval.

`contextPolicy.excludePaths` is a secret-exposure control as much as a relevance control, and is
enforced during retrieval rather than during rendering.

---

## 6. Human Approval

Human approval is required for consequential actions such as:

- merge
- production-impacting changes
- security-sensitive changes
- infrastructure changes
- elevated permissions

V1 has two approval kinds with **different assurance**, and they must never be presented as
equivalent (ADR-0009):

- `LOCAL_OPERATOR_CONSENT` — interactive confirmation in the CLI. Proves that whoever
  controlled the terminal accepted responsibility. It is **developer-attested**: operator
  consent, not segregation of duties, and not evidence for adversarial investigation.
- `EXTERNAL_ATTESTATION` — a GitHub pull request review or Jira transition, verified through
  the integration API. Proves that a named, authenticated user approved.

The required kind is the strictest of the tool's side-effect class, the repository's trust
level and the graph node definition. `IRREVERSIBLE` actions, and `EXTERNAL_WRITE` in a
`RESTRICTED` repository, require external attestation.

Rules:

- an approval binds to both the **content hash** of the subject and the **rendering hash** of
  what the human was shown; both are re-verified on resume
- one approval covers one subject — no standing, blanket or run-wide approvals
- every approval expires; expired and revoked approvals fail closed
- no agent may request, waive, downgrade or record an approval
- approval renderings are generated by the platform; untrusted content within them is
  delimited and can never impersonate platform text
- no cross-developer approval queues until identity exists

The platform does not build identity it does not have. Where stronger assurance is needed, it
borrows identity from a system that has it.

---

## 7. Future Hosted Deployment

If the platform becomes a centrally hosted multi-user service, revisit:

- authentication
- authorization
- tenancy
- identity
- secret management

This must be an explicit architectural decision.

Microsoft Entra ID is not a V1 requirement.
