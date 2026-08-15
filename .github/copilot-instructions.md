# GitHub Copilot Instructions

## 1. Purpose

This repository contains the AI Engineering Platform used by the engineering team to build, orchestrate, evaluate and operate AI-assisted software engineering workflows across multiple repositories.

The platform is a shared engineering platform, not a single application-specific AI agent.

The platform must eventually support reliable workflows such as:

Jira issue
→ context discovery
→ planning
→ human approval
→ isolated implementation
→ tests
→ CI
→ repair loops
→ GitHub pull request
→ review
→ documentation
→ Jira update

The platform must prioritize reliability, security, observability, recoverability and verification over maximum autonomy.

---

# 2. Source of Truth

Before making significant changes, read the relevant repository documentation.

At minimum:

- `CLAUDE.md`
- `ARCHITECTURE.md`
- `PRINCIPLES.md`
- `ROADMAP.md`
- `SECURITY.md`
- `EVALUATION.md`
- `GLOSSARY.md`

For architectural work, also read:

- `docs/architecture/`
- `docs/decisions/`

For integrations, read the relevant documents under:

- `docs/integrations/`

Do not assume that code is more authoritative than architecture documentation when the repository is still in the design/scaffold phase.

If implementation and documentation disagree, identify the discrepancy and propose the appropriate change.

---

# 3. Current Technology Stack

The engineering organization uses:

## Backend

- Java
- Quarkus

## AI / Agent Runtime

- Python

## Frontend

- Angular

## Cloud

- Microsoft Azure

## Kubernetes

- Azure Kubernetes Service (AKS)
- Kubernetes
- Helm

## Data

- Azure Cosmos DB
- Azure Blob Storage

## Security

- Microsoft Entra ID
- Azure Workload Identity
- Azure Key Vault
- Azure RBAC

## Source Control / CI

- GitHub
- GitHub Actions

## Work Management

- Jira

## Product / Engineering Documentation

- Confluence

## AI Models

The platform should support multiple model providers.

Initial providers include:

- Anthropic Claude / Claude Sonnet
- OpenAI GPT

The architecture must remain model-provider neutral.

Do not hard-code the architecture around a single model provider.

---

# 4. Explicitly Excluded Technologies

The platform does NOT use:

- PostgreSQL
- Kafka
- a dedicated graph database

Do not introduce these technologies.

If a future requirement appears to justify one of them, document the architectural reasoning first and create an ADR rather than introducing it silently.

For event-driven behavior, prefer the simplest Azure-native mechanism that satisfies the requirement.

Cosmos DB Change Feed may be considered where appropriate.

Azure Service Bus may be considered if durable messaging semantics are actually required.

Do not introduce infrastructure merely because it is common in other AI platforms.

---

# 5. Architectural Model

The target platform consists conceptually of:

```text
                    Developer
                        |
                        v
               Quarkus Control Plane
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
        Jira        Confluence      GitHub
          |             |             |
          +-------------+-------------+
                        |
                        v
                  Context Engine
                        |
                        v
                   Graph Engine
                        |
                        v
                  Agent Runtime
                     Python
                        |
                        v
                  Model Gateway
                   /         \
                Claude       GPT
                   \         /
                    \       /
                     v     v
                  AKS Worker
                 / isolated \
                /  workspace \
               +-------------+
                       |
                    Git / CI