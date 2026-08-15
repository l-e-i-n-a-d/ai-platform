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

## Repository

This repository is initially an architectural scaffold. Implementation will proceed incrementally.

See:

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PRINCIPLES.md](PRINCIPLES.md)
- [ROADMAP.md](ROADMAP.md)
- [SECURITY.md](SECURITY.md)
- [EVALUATION.md](EVALUATION.md)
- [GLOSSARY.md](GLOSSARY.md)

## Status

Proposed / scaffold stage. Components are not considered implemented unless explicitly marked as such.
