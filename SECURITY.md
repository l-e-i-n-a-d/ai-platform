# Security Model

## Principles

- least privilege
- explicit capability access
- workload identity
- short-lived credentials
- isolated execution
- human approval for consequential actions
- auditable execution

## Identity and Azure

Prefer Entra ID, AKS Workload Identity, Key Vault and scoped Azure RBAC.

## GitHub

Use the narrowest practical repository permissions. Separate read, branch-write, pull-request and merge capabilities.

Agents should not automatically receive merge authority.

## Secrets

Never commit secrets, place secrets in prompts, store plaintext secrets in Cosmos DB, or unnecessarily expose secrets to model context.

## Production

Production access is denied by default. Future production capabilities require an explicit security and architecture decision.

## Audit

Meaningful agent actions should be traceable to user, Jira work item, run, graph/node, agent, tool, repository and resulting change.
