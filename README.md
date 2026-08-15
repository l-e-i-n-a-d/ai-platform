# AI Engineering Platform

A shared internal AI Engineering Platform for reliable, observable and secure AI-assisted software engineering across multiple repositories.

## Initial Architecture

The platform is intended to connect:

- Jira for work management
- Confluence for product and engineering knowledge
- GitHub for source code, pull requests and CI/CD
- local execution and local persistence in V1
- Claude and GPT through a provider-neutral model gateway

Azure services (Cosmos DB, Blob Storage, AKS, Key Vault) are the documented target for a
future hosted deployment. They are not V1 requirements — V1 runs entirely on a developer's
machine. See [ADR-0007](docs/decisions/0007-operational-persistence-and-local-first-storage.md).

## V1 Prerequisites

V1 runs entirely on a developer's machine and needs no cloud account. It does require:

- a container runtime (Docker or Podman) — every repository command runs in a container
- Java and Python toolchains for the control plane and agent runtime
- credentials for GitHub, Jira, Confluence and at least one model provider, held locally
- a GitHub App installed for the repositories the platform will act on — the platform acts as
  the App, never as your personal token (ADR-0012)

Model provider credentials are **per developer** and are read from the OS keychain, not from
`.env` files or environment variables (ADR-0011). Jira, Confluence and GitHub *retrieval* uses
your own credentials, so the platform can never read more than you can.

Node is **not** a V1 prerequisite: the entry surface is a CLI, and the Angular UI is deferred.

See [ADR-0006](docs/decisions/0006-local-execution-isolation-and-credentials.md) and
[ADR-0018](docs/decisions/0018-developer-entry-surface-cli.md).

## Repository

This repository is initially an architectural scaffold. Implementation will proceed incrementally.

See:

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PRINCIPLES.md](PRINCIPLES.md)
- [ROADMAP.md](ROADMAP.md)
- [SECURITY.md](SECURITY.md)
- [EVALUATION.md](EVALUATION.md)
- [GLOSSARY.md](GLOSSARY.md)
- [docs/decisions/](docs/decisions/README.md) — architecture decision records
- [schemas/](schemas/README.md) — machine-readable contract schemas derived from the ADRs
- [CONTRIBUTING.md](CONTRIBUTING.md)

## Status

Proposed / scaffold stage. Components are not considered implemented unless explicitly marked as such.
