# Azure Integration

**Status:** Future (hosted deployment). Not a V1 requirement.

V1 is local-first and runs entirely on a developer's machine. It requires **no Azure
subscription, no Azure resources and no Azure credentials**. Azure is the documented target
for a later hosted deployment, not a dependency of the platform today.

See [ADR-0007](../decisions/0007-operational-persistence-and-local-first-storage.md).

## Not used in V1

| Service | Intended future role | V1 substitute |
|---|---|---|
| Cosmos DB | shared operational state | local embedded store behind the persistence port |
| Blob Storage | large artifacts | local content-addressed artifact store |
| AKS | remote execution backend | local executor behind the execution interface |
| Key Vault | centralized secret management | local OS keychain / developer-held credentials |
| Entra ID / Workload Identity | platform identity | deferred; see the security model |

## Conditions for adoption

Each service is adopted only when a demonstrated requirement exists, and each requires its
own ADR. In particular:

- **Cosmos DB and Blob Storage** become relevant when a shared operational store is required.
  That decision is coupled to centralized identity and must be taken together with it — a
  shared store without identity-bound access reintroduces the credential-sharing problem that
  ADR-0007 removes.
- **AKS** becomes relevant only as an alternative execution backend implementing the existing
  execution interface, and must not change graph or agent semantics.

Avoid introducing additional Azure services without a demonstrated requirement and an ADR.
