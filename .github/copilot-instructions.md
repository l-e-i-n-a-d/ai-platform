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
```

Supporting infrastructure:

```text
Cosmos DB
    → operational state

Blob Storage
    → large artifacts

Key Vault
    → secrets

Entra ID
    → identity

AKS
    → isolated execution
```

---

# 6. Control Plane

The control plane is primarily implemented using Quarkus.

It is responsible for:

- APIs
- authentication and authorization
- work/run lifecycle
- durable execution state
- graph lifecycle
- policy enforcement
- human approvals
- integration contracts
- execution coordination
- observability metadata

The control plane should coordinate execution.

It should not become an unrestricted command execution environment.

Do not execute arbitrary repository commands directly inside the control plane.

---

# 7. Agent Runtime

The agent runtime is Python-based.

Agents are constrained AI execution units.

An agent should have explicit:

- identity
- objective
- instructions
- context
- tools
- policies
- model configuration
- iteration limits
- timeout
- output contract

Agents must not have unrestricted access to the environment.

Prefer specialized agents over a single giant autonomous agent.

Examples of future specialized agents include:

- repository analyst
- architect
- software engineer
- test engineer
- debugger
- code reviewer
- technical writer

Do not create these agents until their contracts and responsibilities are sufficiently defined.

---

# 8. Graph Engine

Important engineering workflows must be represented as explicit, versioned graphs.

Graphs may eventually support:

- sequential execution
- branching
- loops
- retries
- timeouts
- checkpoints
- human approvals
- failure handling
- recovery
- compensation
- graph versioning

Do not hide complex workflow logic inside a single prompt.

Do not implement a graph database simply because the platform has graphs.

The term "graph" refers primarily to workflow execution semantics.

---

# 9. Context Engine

Context is an engineering concern.

The platform should progressively construct relevant context from sources such as:

- Jira
- Confluence
- GitHub
- repositories
- services
- APIs
- architecture documentation
- CI results
- previous execution state
- evaluation results

Do not indiscriminately send entire repositories or large knowledge bases to models.

Prefer:

- relevance
- ranking
- summarization
- progressive disclosure
- traceability
- context budgets

The platform should eventually be able to explain why a particular piece of context was supplied to an agent.

---

# 10. Model Gateway

Agents must access models through a provider-neutral abstraction.

Initial models/providers include:

- Claude Sonnet
- GPT

The gateway should eventually support:

- model selection
- model configuration
- structured outputs
- retries
- timeouts
- token accounting
- cost metadata
- latency metadata
- request tracing
- provider-specific configuration

Do not spread provider-specific SDK calls throughout the agent code.

Provider-specific implementation belongs behind the model gateway.

---

# 11. Tool Architecture

Agent capabilities must be exposed through explicit tools.

Examples include:

- read repository
- search repository
- modify files
- run tests
- run builds
- inspect CI
- create branch
- create pull request
- read Jira
- update Jira
- search Confluence
- publish documentation
- inspect Kubernetes resources

Tools must have:

- explicit contracts
- input validation
- authorization
- observability
- error handling
- clear side-effect semantics

Prefer read-only capabilities by default.

Write/destructive capabilities should require stronger authorization and potentially human approval.

---

# 12. Execution Environment

AI engineering workloads should execute in isolated AKS environments.

Workspaces should preferably be:

- isolated
- ephemeral
- reproducible
- observable
- resource-limited
- identity-scoped

Typical tooling may include:

- Java
- Maven / Gradle as required by repositories
- Quarkus tooling
- Python
- Node.js
- Angular tooling
- Helm
- kubectl
- Git
- testing tools
- static analysis

Do not assume every workspace needs every tool.

Prefer task-specific workspace capabilities.

---

# 13. Persistence

Use Azure Cosmos DB for platform operational state.

Potential state includes:

- work items
- graph runs
- graph nodes
- agent executions
- checkpoints
- approvals
- tool executions
- model invocations
- policies
- evaluation results
- execution metadata

Use Azure Blob Storage for large artifacts such as:

- large logs
- generated reports
- transcripts
- patches
- build artifacts
- evaluation artifacts

Do not store unnecessarily large payloads directly in Cosmos DB.

Do not introduce another database without an architectural decision.

---

# 14. External Systems

## Jira

Jira is the system of record for engineering work.

Do not recreate Jira's work-management functionality inside the platform.

The platform may read and update:

- issues
- requirements
- acceptance criteria
- status
- comments
- links
- metadata

## Confluence

Confluence is the system of record for product and engineering knowledge.

The platform may:

- search pages
- retrieve relevant content
- use documentation as context
- propose documentation changes
- eventually publish approved documentation

## GitHub

GitHub is the system of record for:

- source code
- repositories
- branches
- pull requests
- reviews
- GitHub Actions / CI

Use scoped permissions.

Agents should not automatically have merge or production-deployment authority.

---

# 15. Security

Security is a core platform capability.

Prefer:

- Microsoft Entra ID
- AKS Workload Identity
- Azure Key Vault
- Azure RBAC
- scoped GitHub permissions
- capability-based tools
- isolated execution
- explicit policies
- human approval

Never:

- commit secrets
- put secrets into prompts
- expose secrets unnecessarily to models
- use long-lived credentials where avoidable
- give agents broad permissions by default
- grant production access by default
- bypass policy controls

Every meaningful consequential action should be attributable to a user, run, agent, graph and tool.

---

# 16. Human Approval

Human approval is a first-class workflow capability.

Examples of actions that may require approval:

- changing production-impacting configuration
- merging a pull request
- publishing important documentation
- modifying security-sensitive configuration
- changing infrastructure
- granting elevated capabilities

Graphs must be able to pause and resume around approval points.

Do not design the system around the assumption that agents should always operate autonomously.

---

# 17. Observability

Observability is a first-class architectural concern.

The future observability stack is expected to include:

- OpenTelemetry
- Prometheus
- Loki
- Grafana
- Alertmanager

The platform should eventually expose:

## Metrics

Examples:

- API request count
- API latency
- error rates
- graph runs
- agent runs
- node execution duration
- retries
- failures
- model latency
- token usage
- estimated model cost
- workspace provisioning time
- CI success/failure
- task success rate

## Logs

Logs should support correlation by identifiers such as:

- request ID
- work item ID
- run ID
- graph ID/version
- node ID
- agent ID
- workspace ID
- model invocation ID
- tool invocation ID

## Traces

The architecture should eventually support end-to-end traces such as:

```text
Jira Issue
   |
Graph Run
   |
Context Retrieval
   |
Agent
   |
Model Invocation
   |
Tool Invocation
   |
AKS Workspace
   |
Build
   |
Tests
   |
Repair
   |
Pull Request
```

Use OpenTelemetry as the preferred instrumentation abstraction.

Do not couple business logic directly to Grafana.

Do not couple business logic directly to Prometheus or Loki when an instrumentation abstraction is appropriate.

The initial platform does not need to deploy the complete observability stack, but components should be designed so observability can be added without architectural redesign.

---

# 18. Evaluation

The platform must evaluate both:

1. models
2. the engineering harness

Do not assume that a better model automatically produces a better engineering system.

Evaluate:

- task success
- correctness
- deterministic verification
- context quality
- tool effectiveness
- graph effectiveness
- recovery
- cost
- latency
- security compliance

Potential benchmark tasks include:

- Java/Quarkus bug fixes
- Java/Quarkus feature changes
- Python changes
- Angular changes
- Helm changes
- Kubernetes changes
- CI/CD changes
- documentation changes
- cross-repository changes

A representative future benchmark is:

```text
Jira
 ↓
Confluence
 ↓
Quarkus service
 ↓
API contract
 ↓
Angular client
 ↓
Tests
 ↓
CI
 ↓
Repair
 ↓
GitHub PR
```

---

# 19. Engineering Workflow

Before implementing a significant change:

1. Read the relevant documentation.
2. Inspect the existing repository.
3. Identify affected components.
4. Check relevant ADRs.
5. Determine whether an architectural decision is required.
6. Propose the smallest coherent implementation.
7. Implement incrementally.
8. Add tests.
9. Verify behavior.
10. Update documentation.
11. Update implementation status.

Do not make large speculative changes.

Do not refactor unrelated code.

Do not introduce infrastructure simply because it may be useful later.

---

# 20. Architecture Decisions

Use Architecture Decision Records for significant decisions.

Examples:

- persistence architecture
- graph execution semantics
- model gateway design
- agent runtime boundaries
- AKS isolation
- authorization model
- context architecture
- observability architecture
- integration boundaries

ADR location:

```text
docs/decisions/
```

Before making a significant architectural change, check existing ADRs.

---

# 21. Implementation Status

Always distinguish between:

- Proposed
- Planned
- In Development
- Implemented
- Production

Do not describe planned architecture as implemented.

Do not create fake implementations merely to make an architecture diagram appear complete.

---

# 22. Current Repository Phase

The repository is currently in the architectural scaffold phase.

The immediate objective is NOT to build the complete platform.

The immediate objective is to:

1. validate the architecture
2. identify missing decisions
3. establish contracts
4. establish engineering standards
5. implement the platform incrementally

Do not jump directly to autonomous multi-agent workflows.

---

# 23. Important Development Rule

When requirements are ambiguous:

Do not silently invent architecture.

Instead:

1. identify the ambiguity
2. explain the relevant trade-offs
3. propose a recommendation
4. ask for a decision if the choice has significant architectural consequences
5. record significant decisions in an ADR

Prefer the simplest architecture that satisfies the demonstrated requirement.

---

# 24. Self-Hosting / Dogfooding

Eventually, the AI Engineering Platform should be capable of helping develop and maintain itself.

This means future agents should be able to:

- understand the architecture
- discover contracts
- inspect code
- run tests
- analyze failures
- make changes
- verify changes
- create pull requests
- update documentation

However, self-modification must be introduced gradually.

Reliability and safety come before autonomy.

---

# 25. Copilot Behavior

When working in this repository:

- Be conservative with architecture.
- Prefer existing patterns.
- Ask before making major architectural changes.
- Do not invent infrastructure.
- Do not introduce Kafka.
- Do not introduce PostgreSQL.
- Do not introduce a graph database.
- Do not create unnecessary microservices.
- Do not implement future phases prematurely.
- Do not bypass security controls.
- Do not silently change system-of-record boundaries.
- Do not claim functionality is implemented when it is only scaffolded.
- Keep changes focused.
- Add tests for implemented behavior.
- Update documentation when architecture or behavior changes.

When a task is large, decompose it into smaller independently verifiable steps.

The goal is not to produce the largest amount of code.

The goal is to produce the smallest correct, maintainable and verifiable change.

