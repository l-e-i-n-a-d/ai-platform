# Repository Registry

This directory holds the **repository registry**: the version-controlled record of which
repositories the platform may operate on, and how much authority it has in each.

Decision: [ADR-0014](../docs/decisions/0014-repository-registry-and-instruction-precedence.md)
Component: [docs/architecture/repository-registry.md](../docs/architecture/repository-registry.md)

Registry records are **platform-controlled configuration, reviewed like code**. They are never
read from the target repository — repository content is attacker-controllable, and a pull
request must not be able to influence the authority of the agent that processes it.

One file per repository:

```text
repositoryId, displayName, remotes[], defaultBranch
trustLevel          INTERNAL | RESTRICTED | EXTERNAL
toolImage           digest-pinned
commandProfiles[]   named, typed argv; no shell
capabilityCeiling   maxSideEffect, allowedTools[], networkAllowlist[],
                    pathScope, approvalOverrides, budgetCeiling
contextPolicy       includePaths[], excludePaths[], instructionFiles[], maxContextBudget
verification        requiredChecks[]
owners[], status
```

Changes here are security-relevant. Every layer of the precedence chain may only **narrow**
capabilities; nothing in the platform widens a grant.

This directory replaces the earlier `services/` scaffold, whose purpose — service and
repository metadata for the context engine — is served by the registry record's
`contextPolicy`.
