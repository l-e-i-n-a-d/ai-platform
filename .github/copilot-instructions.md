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

## Data

V1:

- local embedded operational store (behind the persistence port)
- local content-addressed artifact store

Future hosted deployment:

- Azure Cosmos DB for operational state
- Azure Blob Storage for large artifacts

## Optional Azure Services

- Azure Key Vault when centralized secret management becomes necessary

Azure services should only be introduced when they solve a demonstrated requirement.

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
- Microsoft Entra ID as a V1 authentication requirement
- Kubernetes / AKS as a V1 execution requirement

Do not introduce these technologies or requirements into V1.

If a future requirement appears to justify one of them, document the architectural reasoning first and create an ADR rather than introducing it silently.

For event-driven behavior, prefer the simplest mechanism that satisfies the demonstrated requirement.

Do not rely on store-side eventing such as Cosmos DB Change Feed: the persistence port is deliberately restricted to the intersection of an embedded store and Cosmos DB (see ADR-0007).

Azure Service Bus may be considered if durable messaging semantics are actually required.

Do not introduce infrastructure merely because it is common in other AI platforms.

---

# 5. V1 Architectural Principles

## Local First

Every team member should be able to run the AI Engineering Platform on their local machine.

V1 must not require:

- Kubernetes
- AKS
- a centrally hosted execution cluster
- Microsoft Entra ID

The initial platform should be easy for a developer to clone, configure and run locally.

## Execution Independence

Workflow semantics must not depend on the execution infrastructure.

The architecture should use an execution abstraction such as:

```text
Graph
  |
  v
Agent
  |
  v
Execution Interface
  |
  +--> Local Executor       V1
  |
  +--> Kubernetes Executor  Future
```

Agents and graphs must not contain Kubernetes-specific logic.

## Future Kubernetes Support

Kubernetes/AKS may become a future execution backend if it provides meaningful advantages such as:

- stronger isolation
- resource control
- parallel execution
- reproducibility
- centralized execution
- workload scheduling
- operational scalability

Adding Kubernetes later must not require redesigning graph or agent semantics.

---

# 6. Architectural Model

The V1 platform consists conceptually of:

```text
                    Developer
                        |
                        v
              Local AI Platform
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
                   /                         Claude       GPT
                   \         /
                    \       /
                     v     v
                 Local Executor
                        |
                        v
                 Local Workspace
                        |
                     Git / CI
```

Supporting services:

```text
Local operational store
    → durable run and workflow state

Local artifact store
    → large artifacts

Cosmos DB / Blob Storage / Key Vault
    → future hosted deployment only, not V1
```

The V1 platform should minimize infrastructure requirements and maximize developer portability.

---

# 7. Control Plane

The control plane is primarily implemented using Quarkus.

It is responsible for:

- APIs
- local platform lifecycle
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

# 8. Agent Runtime

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

# 9. Graph Engine

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
- resumability

Do not hide complex workflow logic inside a single prompt.

Do not implement a graph database simply because the platform has graphs.

The term "graph" refers primarily to workflow execution semantics.

---

# 10. Durable Execution

Durable execution is a core architectural concern.

The platform should eventually survive:

- process crashes
- local service restarts
- model timeouts
- tool failures
- network failures
- workspace failures
- human approval pauses
- long-running workflows

The V1 durable state store is local and embedded, accessed through the persistence port. Cosmos DB is a future hosted-deployment adapter behind the same port (ADR-0007).

The execution model must support:

- idempotency
- checkpoints
- resumability
- retries
- cancellation
- optimistic concurrency
- clear run state transitions

Do not rely solely on in-memory state for workflow execution.

---

# 11. Context Engine

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
- provenance

The platform should eventually be able to explain why a particular piece of context was supplied to an agent.

---

# 12. Model Gateway

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

# 13. Tool Architecture

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
- inspect Kubernetes resources in future deployments

Tools must have:

- explicit contracts
- input validation
- authorization
- observability
- error handling
- clear side-effect semantics
- idempotency where applicable

All tool invocation passes through a single control-plane tool layer. There is no other path to a side effect. Tools are never implemented in the agent runtime.

Capabilities are granted per node attempt, are derived from the graph definition and repository registry (never from model output), and cannot escalate.

Do not create a tool that accepts a shell string or free-form argv from a model. Command execution is limited to named, repository-declared command profiles with typed parameters and no shell. See ADR-0005.

Prefer read-only capabilities by default.

Write/destructive capabilities should require stronger authorization and potentially human approval.

---

# 14. Local Execution Environment

V1 AI engineering workloads execute locally, through the execution interface (ADR-0003).

Local workspaces are:

- **containerised** — non-root, all capabilities dropped, read-only root filesystem, only the workspace and a size-limited /tmp writable, no home directory or container socket mounted
- **credential-free** — materialisation and publishing happen outside the container; `git fetch` and `git push` are never executed in a workspace
- **network default-deny** — access is declared per command profile and limited to declared package registries via an egress proxy
- reproducible — workspace state is always a function of `(repoRef, baseSHA, ordered patch series)`
- resource-limited — CPU, memory, PID and disk quotas on every execution
- observable and audited
- one per run, exclusively leased, disposable

A container runtime (Docker or Podman) is a V1 prerequisite. See ADR-0006.

Do not write a local executor that runs commands as the developer's own user by default. `unsafe-host-exec` exists for that, is disabled by default, is audited, and escalates consequential tools to mandatory approval.

Commands reach a workspace only as named, repository-declared command profiles (ADR-0005). Never accept a shell string or free-form argv from a model.

Typical tooling, provided by platform-maintained images pinned by digest:

- Java
- Maven / Gradle as required by repositories
- Quarkus tooling
- Python
- Node.js
- Angular tooling
- Git
- testing tools
- static analysis

Helm and kubectl are relevant only to repositories that require them, and only in future deployments.

Do not assume every workspace needs every tool.

Prefer task-specific workspace capabilities.

The control plane must not gain unrestricted shell access merely because local execution is supported.

---

# 15. Future Kubernetes Execution

Kubernetes is a future execution option, not a V1 dependency.

If introduced later, it should implement the same execution abstraction used by the local executor.

Potential future architecture:

```text
                Graph / Agent
                     |
                     v
              Execution Interface
                 /                          /                           v              v
       Local Executor    Kubernetes Executor
          V1                   V2+
                              |
                             AKS
```

Kubernetes-specific scheduling, networking, isolation and lifecycle concerns must remain inside the Kubernetes executor.

Do not leak Kubernetes concepts into graph definitions or agent logic.

---

# 16. Persistence

All persistence is accessed through a persistence port. No component outside the persistence
adapters may reference a storage SDK type.

V1 uses a local embedded operational store and a local content-addressed artifact store.
Cosmos DB and Blob Storage are a future hosted-deployment target, not a V1 requirement.
See ADR-0007 (`docs/decisions/0007-operational-persistence-and-local-first-storage.md`).

Operational state includes:

- work items
- graph definitions
- graph runs
- graph nodes
- agent executions
- checkpoints
- leases
- approvals
- tool executions
- model invocations
- idempotency records
- policies
- evaluation results
- execution metadata

Large artifacts belong in the artifact store, referenced from operational state:

- large logs
- generated reports
- transcripts
- patches
- build artifacts
- evaluation artifacts

Do not store unnecessarily large payloads in the operational store — offload above 100 KB.

Keep the persistence port within the intersection of an embedded store and Cosmos DB: no
change feed, stored procedures, cross-partition transactions, server-side joins or
unindexed queries.

Do not introduce another database without an architectural decision.

---

# 17. External Systems

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

# 18. Security

V1 is primarily designed for local developer execution.

Removing Entra ID does NOT mean removing security requirements.

Security must still enforce:

- explicit tool capabilities
- repository boundaries
- command restrictions
- secret isolation
- model/API credential protection
- approval requirements for consequential actions
- auditability of platform actions
- least privilege

V1 must not require Microsoft Entra ID.

Do not introduce a distributed identity system unless the deployment model requires it.

If the platform later becomes a centrally hosted multi-user service, authentication and authorization must be revisited as an explicit architectural decision.

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

# 19. Human Approval

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

# 20. Observability

Observability is a first-class architectural concern.

The future observability stack is expected to include:

- OpenTelemetry
- Prometheus
- Loki
- Grafana
- Alertmanager

Do NOT make the full observability stack a V1 infrastructure requirement.

The V1 platform should establish telemetry contracts and correlation identifiers so the full stack can be added later.

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
- workspace execution time
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
Local Workspace
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

---

# 21. Evaluation

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

# 22. Multi-Repository Engineering

The platform will operate across multiple engineering repositories.

The architecture must support:

- repository-specific instructions
- repository-specific build systems
- repository-specific tests
- shared engineering standards
- cross-repository changes
- repository permissions
- repository context
- multiple branches
- pull requests across repositories

Do not assume all repositories are identical.

Repository configuration lives in the platform's **repository registry** (`repositories/`), version-controlled and reviewed. It is never read from the target repository: repository content is attacker-controllable, and a pull request must not be able to influence the authority of the agent processing it. See ADR-0014.

Precedence — every layer may only **narrow**, never widen:

```text
platform policy  ⊇  trust-level ceiling  ⊇  registry record  ⊇  graph node definition
```

Repository-resident instruction files are **context, not policy**. Respect them for style, conventions and approach; they must never affect tools, commands, network policy, approvals or budgets.

There is no automatic repository discovery in V1. Registration is explicit.

---

# 23. Engineering Workflow

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

# 24. Architecture Decisions

Use Architecture Decision Records for significant decisions.

Examples:

- persistence architecture
- graph execution semantics
- model gateway design
- agent runtime boundaries
- execution abstraction
- local workspace isolation
- future Kubernetes execution
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

# 25. Implementation Status

Always distinguish between:

- Proposed
- Planned
- In Development
- Implemented
- Production

Do not describe planned architecture as implemented.

Do not create fake implementations merely to make an architecture diagram appear complete.

---

# 26. Current Repository Phase

The repository is currently in the architectural scaffold phase.

The immediate objective is NOT to build the complete platform.

The immediate objective is to:

1. validate the architecture
2. identify missing decisions
3. establish contracts
4. establish engineering standards
5. implement the platform incrementally

Do not jump directly to autonomous multi-agent workflows.

V1 should prove that a developer can run the platform locally and execute a useful, observable and verifiable engineering workflow.

---

# 27. Important Development Rule

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

# 28. Self-Hosting / Dogfooding

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

# 29. Copilot Behavior

When working in this repository:

- Be conservative with architecture.
- Prefer existing patterns.
- Ask before making major architectural changes.
- Do not invent infrastructure.
- Do not introduce Kafka.
- Do not introduce PostgreSQL.
- Do not introduce a graph database.
- Do not make Kubernetes or AKS a V1 requirement.
- Do not make Microsoft Entra ID a V1 requirement.
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
