# Repository Registry

**Status:** Planned (design agreed, not yet implemented)
**Location:** Control plane; configuration under `repositories/`
**Decision:** [ADR-0014](../decisions/0014-repository-registry-and-instruction-precedence.md)

---

## 1. Responsibility

The registry is the platform's record of **which repositories exist, what they are, and how
much authority the platform may exercise in them**.

**Responsible for**

- stable repository identity
- trust classification
- capability ceilings
- command profiles and tool image selection
- network allowlists
- context policy
- required verification checks
- approval routing

**Not responsible for**

- deciding what an individual run may do — that is the capability grant (ADR-0005)
- storing repository content
- cross-repository change coordination (Phase 5)

---

## 2. Source of truth

```text
repositories/*.yaml           version-controlled, reviewed, in this repository
        |
        |  materialise, hash
        v
repositories container        operational store (ADR-0007)
        |
        v
capability grant minting      per node attempt (ADR-0005)
```

Registry records are **never read from the target repository**. Repository content is
attacker-controllable; a pull request must not be able to influence the authority of the agent
that processes it.

A run pins the `configHash` of every repository in its scope, so editing the registry cannot
change what an in-flight run may do.

---

## 3. Record

```text
repositoryId, displayName, remotes[], defaultBranch
trustLevel          INTERNAL | RESTRICTED | EXTERNAL
toolImage           digest-pinned
commandProfiles[]
capabilityCeiling   maxSideEffect, allowedTools[], networkAllowlist[],
                    pathScope, approvalOverrides, budgetCeiling
contextPolicy       includePaths[], excludePaths[], instructionFiles[], maxContextBudget
verification        requiredChecks[]
owners[], status, registeredBy, registeredAt, configHash
```

`repositoryId` is stable and independent of the remote URL. Repositories get renamed, moved
and forked; audit history must survive all three.

---

## 4. Trust levels

| Level | Applies to | Ceiling |
|---|---|---|
| `INTERNAL` | org-owned, reviewed | up to `EXTERNAL_WRITE`; network limited to declared registries |
| `RESTRICTED` | production, infrastructure, security-sensitive | `WORKSPACE_WRITE` default; every `EXTERNAL_WRITE` needs approval; no `IRREVERSIBLE` |
| `EXTERNAL` | forks, vendor, unreviewed | `WORKSPACE_WRITE` max, network `NONE`; no `EXTERNAL_WRITE` |

Trust level is recorded by the platform, never claimed by the repository.

---

## 5. Precedence

```text
platform policy  ⊇  trust-level ceiling  ⊇  registry record  ⊇  graph node definition
                                   |
                                   v
                        effective capability grant
```

Every layer may only **narrow**. The effective grant is the intersection. Nothing in the
platform widens a grant.

Repository-resident instruction files sit outside this chain entirely: they are **context, not
policy**. They are labelled with provenance, treated as untrusted data, and have zero effect on
tools, commands, network, approvals or budgets.

A repository may propose registry changes through a schema-validated file. Narrowing proposals
may be adopted automatically; anything that widens requires a reviewed human change.

---

## 6. Multi-repository runs

Each repository in a run's scope gets its own workspace, ceiling and materialisation. Where a
node spans several, the effective ceiling is the intersection — the most restrictive
repository governs.

Cross-repository coordination (dependent changes, linked pull requests, ordered merges) is
Phase 5. Identity, scoping and ceilings are V1.

---

## 7. Registration

Explicit only. There is no automatic discovery in V1: scanning an organisation and inferring
build systems would amount to granting capabilities by heuristic. If discovery is added later
it must produce proposals, never registrations.
