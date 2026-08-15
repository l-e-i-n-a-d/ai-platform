# Security Model

Security is capability-based and least-privilege.

V1 has **no centralized identity provider**. Microsoft Entra ID, AKS Workload Identity and
Key Vault are future hosted-deployment mechanisms, not V1 controls. Removing centralized
identity does not remove any security requirement — it means the remaining controls must
carry the load, and that the honest limits of attribution must be stated.

## V1 mechanisms

- explicit tool contracts and capability grants
- a single non-bypassable authorization choke point for all tool invocations
- repository and workspace boundaries
- command restrictions in the local executor
- scoped GitHub permissions, with no merge or production-deployment authority
- credentials held by the local developer and never exposed to models
- no shared platform credentials — V1 requires no shared operational store (ADR-0007)
- human approval for consequential actions, bound to the content approved
- an append-only audit trail of consequential actions

## Trust model

The platform runs on a developer's machine, under that developer's OS account, with that
developer's credentials. The local operator is therefore trusted at the level of their own
machine. The platform's job is not to defend against its own operator; it is to ensure that
**the agent cannot exceed what the operator has explicitly granted**, and that everything the
agent did is recorded.

Repository content, Jira issues, Confluence pages and pull-request text are **untrusted
input** and must never be treated as instructions to the platform.

## Attribution limits

Without a central identity provider, actions are attributed to the local developer identity
and to the run, graph, node, agent and tool that produced them. This attribution is
self-asserted and locally forgeable. Actions with external effect (GitHub, Jira) carry
stronger evidence because the external system records its own actor.

This limitation is accepted for V1 and must be revisited if the platform becomes a shared,
hosted, multi-user service.

## Defaults

- read-only capabilities by default
- production access denied by default
- write and destructive capabilities require an explicit grant, and may require approval

Related decisions: ADR-0002 (Entra deferral), ADR-0005 (tool authorization), ADR-0006 (local
execution isolation), ADR-0009 (approvals), ADR-0016 (audit and attribution).
