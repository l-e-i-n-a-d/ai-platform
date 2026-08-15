# ADR-0014: Repository Registry, Instruction Precedence and Capability Ceilings

## Status

Accepted — 2026-08-15

Referenced by ADR-0005 (capability grants, command profiles) and ADR-0006 (tool images,
network allowlists), both of which depend on it.

---

## Context

Multi-repository support is a stated platform goal, and the roadmap defers it to Phase 5. That
sequencing does not survive contact with the rest of the architecture: Phase 1 already
requires GitHub integration and repository operations, and `repositoryId` is already
referenced by workspaces (ADR-0003), capability grants (ADR-0005), tool images and network
policy (ADR-0006), context scoping and every audit record. Deferring the registry while
building everything that depends on it means retrofitting a core identifier.

Two accepted ADRs already assume this document exists. ADR-0005 §4 derives grants from "the
repository registry's capability ceiling"; ADR-0006 §5 has the registry declaring which tool
image a repository uses. Neither is implementable until the registry is specified.

The harder question is where repository configuration *comes from*. The obvious design — the
one CI systems use — is to read it from a file in the target repository. That design is
unsafe here in a way it is not for CI. The platform's job is to act autonomously on content
supplied by Jira tickets and pull requests, and repository files are attacker-controllable: a
pull request could add a file that grants its own branch a wider tool set, a permissive network
allowlist, or a command profile that exfiltrates. "Respect repository-specific instructions"
must never be allowed to mean "let a repository widen its own permissions."

Separately, not all repositories deserve the same authority. A sandbox service and the
repository holding production Terraform should not be reachable with the same capabilities,
and the platform currently has no way to express the difference.

---

## Decision

### 1. The repository registry exists in V1, not Phase 5

A minimal registry ships in Phase 1. Phase 5 retains only the genuinely hard multi-repository
work: coordinated cross-repository changes, linked pull requests and cross-repository context.

### 2. Registry records are platform-controlled configuration

The source of truth is version-controlled configuration in **this** repository, under
`repositories/`, reviewed like code. It is materialised into the `repositories` container of
the operational store (ADR-0007) with a `configHash`.

It is never read from the target repository. This is the central decision of this ADR.

### 3. Record shape

```text
repositoryId        stable, platform-assigned; never derived from the remote URL
displayName
remotes[]           canonical remote
defaultBranch
trustLevel          INTERNAL | RESTRICTED | EXTERNAL
toolImage           digest-pinned (ADR-0006 §5)
commandProfiles[]   named, typed, argv-fixed (ADR-0005 §5)

capabilityCeiling {
  maxSideEffect       READ | WORKSPACE_WRITE | EXTERNAL_WRITE | IRREVERSIBLE
  allowedTools[]      explicit ids
  networkAllowlist[]  package registry hosts
  pathScope           allow / deny globs
  approvalOverrides   classes that always require approval here
  budgetCeiling
}

contextPolicy {
  includePaths[], excludePaths[]     never index secrets or vendored trees
  instructionFiles[]                 repository files surfaced as context
  maxContextBudget
}

verification {
  requiredChecks[]    profiles that must pass before any EXTERNAL_WRITE
}

owners[]              approval routing
status                ACTIVE | SUSPENDED
registeredBy, registeredAt, configHash
```

`repositoryId` is stable and independent of the remote URL, because repositories get renamed,
moved between organisations and forked, and audit history must survive all three.

`verification.requiredChecks` is the deterministic-verification principle expressed per
repository: a repository can require that its tests pass before the platform is permitted to
open a pull request.

### 4. Trust levels carry ceilings

| Trust level | Applies to | Ceiling |
|---|---|---|
| `INTERNAL` | org-owned, reviewed repositories | up to `EXTERNAL_WRITE`; network limited to declared registries |
| `RESTRICTED` | production, infrastructure, security-sensitive | `WORKSPACE_WRITE` by default; every `EXTERNAL_WRITE` requires approval; `IRREVERSIBLE` forbidden; narrowed context policy |
| `EXTERNAL` | forks, vendor code, anything unreviewed | `WORKSPACE_WRITE` maximum, network `NONE`; no `EXTERNAL_WRITE` at all; content always treated as hostile |

Trust level is a property of the repository as recorded by the platform, never a claim the
repository makes about itself.

### 5. Precedence: every layer may only narrow

```text
1. platform policy            hard ceiling; nothing exceeds it
2. trust-level ceiling
3. registry record            per repository
4. graph node definition      per node
5. repository-resident files  CONTEXT ONLY — zero capability effect
        |
        v
   effective capability grant = intersection of 1-4
```

The effective grant is the **intersection**. There is no operation, anywhere in the platform,
that widens a grant. This is the same monotonicity rule ADR-0005 §4 applies within a node
attempt, extended across configuration layers.

### 6. Repository-resident instruction files are context, never policy

Files such as a repository's own contribution guide or agent instructions are read, labelled
with their provenance, and passed to the model as **untrusted data**. They may influence style,
conventions and approach. They can never change which tools are available, which commands may
run, what the network policy is, whether approval is required, or what the budget is.

A repository may *propose* registry changes through a schema-validated file. Proposals that
narrow capabilities may be adopted automatically — the worst case is self-inflicted denial of
service. Proposals that widen anything require a reviewed change to the registry by a human.

This gives repository teams agency over how the platform works in their repository, without
giving them authority over what it is permitted to do.

### 7. No automatic discovery in V1

Repositories are registered explicitly. Automatic discovery — scanning an organisation and
inferring build systems — is convenient and amounts to granting capabilities by heuristic. It
is deferred, and if it is ever added it must produce *proposals*, not registrations.

### 8. Runs pin the registry revision

A run records the `configHash` of every repository in its scope and executes against it for its
whole life, exactly as it pins its graph definition (ADR-0008 §2).

Without this, editing the registry mid-run would silently change what an in-flight run may do,
and the audit trail could not answer "what was this run permitted to do?" after the fact.

### 9. Multi-repository runs in V1

A run may reference several repositories. Each gets its own workspace, its own ceiling and its
own materialisation. Where a node is scoped to more than one, the effective ceiling is the
intersection across all of them — the most restrictive repository governs.

Cross-repository *coordination* — dependent changes, linked pull requests, ordered merges —
remains Phase 5. Only identity, scoping and ceilings are V1.

---

## Alternatives

**A. Read configuration from a file in the target repository, as CI does.**
The expected design, and unsafe here. CI runs configuration that was merged after review; this
platform acts on unmerged, attacker-influenced content by design. A pull request that can
configure the agent reviewing it is a privilege-escalation primitive.

**B. Infer configuration from repository contents.**
Detecting a `pom.xml` and concluding "Maven" is convenient and makes capability decisions by
heuristic on untrusted input. Rejected for the same reason as A.

**C. Defer the registry to Phase 5, as currently roadmapped.**
Rejected: `repositoryId` is a day-one identifier for workspaces, grants, context and audit.
Deferring it means inventing an implicit one and migrating later.

**D. One global capability set for all repositories.**
Simplest, and it forces a single ceiling for a sandbox service and production infrastructure
alike. The ceiling then ends up set by the most dangerous repository, or the most useless one.

**E. Let repository files narrow capabilities directly.**
Superficially safe, since narrowing cannot escalate. Rejected because it makes every
repository file a parsed policy input, which is a validation and confused-deputy surface for
no real benefit — the proposal path of §6 achieves the same outcome with a review step.

---

## Consequences

**Accepted costs**

- Onboarding a repository is a reviewed change to this repository: command profiles, image,
  trust level and ceiling. Nothing works until it is registered. This is the same friction
  ADR-0005 §5 introduced, and it is the friction that makes the capability model real.
- Repository teams cannot self-serve capability changes.
- The registry becomes a security-critical artifact and needs the review discipline to match.
  It should be covered by CODEOWNERS once that exists.

**Gained**

- Capability decisions are enumerable, reviewable and diffable before a run, not reconstructed
  after one.
- A pull request cannot influence the authority of the agent that processes it.
- `RESTRICTED` gives a principled way to point the platform at production and infrastructure
  repositories without granting it production authority.
- Multi-repository work stops being a Phase 5 cliff; only coordination remains there.

---

## Security / Operational Impact

- This ADR closes the escalation path that ADR-0005 and ADR-0006 would otherwise leave open:
  strong grants and strong containment are worth little if the target repository can rewrite
  the configuration that produces them.
- Trust levels are the platform's mechanism for expressing that some repositories warrant less
  autonomy. `EXTERNAL` in particular is what makes it safe to point the platform at a fork.
- `contextPolicy.excludePaths` is a secret-exposure control as much as a relevance one; the
  context engine must never index paths a repository has excluded.
- Registry changes are consequential actions and should themselves be auditable — reviewed
  commits in this repository, materialised with a recorded `configHash`.

---

## Follow-up

- `docs/architecture/repository-registry.md` — component documentation.
- `repositories/` — registry location and record schema (replaces the `services/` scaffold).
- Move the registry and instruction precedence from Phase 5 to Phase 1 in `ROADMAP.md`.
- Update `.github/copilot-instructions.md` §22 with the precedence rule.
- Define the registry record JSON Schema and the proposal file schema.
- ADR-0012 — per-repository GitHub token scoping, which consumes `remotes` and `trustLevel`.
- ADR-0013 — context bundles, which consume `contextPolicy`.
