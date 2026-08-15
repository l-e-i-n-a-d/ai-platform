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

No UI is built in V1. The V1 entry surface is a CLI, and Node is not a V1 prerequisite. Angular remains the chosen technology when a UI is required — see ADR-0018 for the trigger.

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
                             CLI
                              |
                              v
            +---------------------------------------+
            |          Control Plane (Java)         |
            |                                       |
            |   Graph Engine                        |
            |       |                               |
            |       v                               |
            |   Agent Runtime  (Python, stateless)  |
            |       |          |                    |
            |       |          +---> Model Gateway ---> Claude
            |       |          |                    |    GPT
            |       v          v                    |
            |   Tool Layer  <---- Context Engine <------ Jira
            |       |    |                          |    Confluence
            |       |    +---> Integrations ----------->  GitHub
            |       v                               |
            |   Execution Interface                 |
            +---------------------------------------+
                              |
                    +---------+---------+
                    |                   |
                    v                   v
            Local Executor      Kubernetes Executor
                 (V1)                 (future)
                    |
                    v
             Local Workspace
                    |
                    v
                 Git / CI
```

Dependency direction matters. The graph engine drives the agent runtime; the runtime reaches the model gateway directly and the tool layer through callbacks. The tool layer is the only path to integrations and to the execution interface. The context engine is a service called throughout a run, not a stage above the graph. The model gateway is a leaf and never invokes execution.

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

Context is delivered as a **context bundle** (ADR-0013): an immutable, content-addressed artifact with a token budget, revision pins, an ordered item list and an explicit exclusion list. Every item records source system, source id, revision, acting identity, retrieval strategy, relevance score, token count, inclusion reason and trust class. Nothing is dropped or truncated silently.

Rules that must not be weakened:

- Context assembly belongs to the control plane. The agent runtime receives `contextBundleRef` and never queries Jira, Confluence or GitHub itself.
- Retrieval authenticates as **the developer running the platform**. Never use a broadly privileged shared service account for context retrieval — it would let any developer obtain, through an agent, content they cannot open themselves.
- Every item carries a trust class: `PLATFORM` or `UNTRUSTED`. All retrieved content, including a repository's own instruction files, is `UNTRUSTED` and must be delimited and provenance-labelled rather than concatenated into the instruction region.
- Repositories are pinned to a commit SHA for the life of a run; issues and pages record their version. Refreshing supersedes the bundle and invalidates approvals derived from the old one.
- Budget eviction is tiered and deterministic. Tier 0 (task, objective, output contract) is never evictable.
- No embedding index or vector store in V1. `strategy` is an open enum so semantic retrieval can be added later without changing the contract.

---

# 12. Model Gateway

Agents must access models through a provider-neutral abstraction (ADR-0010).

Initial models/providers include:

- Claude Sonnet
- GPT

Do not spread provider-specific SDK calls throughout the agent code. **No provider SDK type crosses the gateway boundary.**

## Canonical model

The gateway defines its own request/response model — messages, tool descriptors as JSON Schema, tool-call requests and results, usage, finish reason, cost — and provider adapters translate in both directions.

Graphs and agents reference a **logical `modelRef`** (`default-reasoning`, `fast-summarize`), never a provider model id. Changing a model must be configuration, not code.

`providerOptions` is a narrow, explicitly-labelled escape hatch. Pretending none is needed produces a covert one.

## The gateway does not run the tool-calling loop

The agent runtime iterates; the control plane authorises and executes tools. Putting the loop in the gateway would give tool-execution authority to the component that talks to third parties, collapsing the authorization choke point.

Provider-native server-side execution tools are **forbidden** — they bypass the execution interface, the capability model and the audit trail at once.

## What the gateway owns

- a canonical error taxonomy mapping onto ADR-0008 failure categories
- retries with backoff, rate-limit handling, timeouts, bounded retry budget
- **record/replay from Phase 1** — without it, every evaluation conflates a harness change with model variance
- token and cost accounting: the gateway is the sole authority, using a versioned pricing table. Never recompute cost anywhere else.
- **egress redaction** (see §18)

The gateway may retry internally only while certain no tool call was returned to the caller. After that, retry is the graph engine's decision.

No streaming in V1. Graph nodes consume complete results.

## Credentials

Per-developer, in the **OS keychain** — not `.env` files, not environment variables. Read by the control plane, used only by provider adapters, never passed to the agent runtime or into a workspace.

## Budgets

Per-invocation, per-node-attempt, per-run and per-day ceilings; each the minimum of platform default, repository `budgetCeiling` and node definition. Exceeding one fails the node with `BUDGET_EXCEEDED` — never a warning, never auto-raised. Consumption is recorded durably before the next invocation, so a crash loop cannot get a fresh budget.

## Proving neutrality

Run the same evaluation suite against both providers from the start. An abstraction exercised by one provider is a hypothesis, not a property.

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

The platform acts as a **GitHub App** with short-lived, per-run, per-repository installation tokens (ADR-0012). Never a developer PAT: it would make agent work indistinguishable from human work, break review policy, and carry far broader scope than needed.

The App must not hold merge, branch-protection-bypass, deployment-approval, repository-administration or secret-management permissions. The platform opens pull requests; humans merge them. A control the platform could lift is not a control.

**Action identity is not retrieval identity.** The App acts; context retrieval authenticates as the developer. Reading through the App would let any developer reach repositories they cannot access.

Tokens never enter a workspace, and `git push` never runs inside one.

## Write-back semantics

Default to **read-mostly**. Unattended writes are limited to clearly-marked, idempotent, additive content carrying the run id.

| Action | V1 |
|---|---|
| Jira comment | unattended, marked, idempotent |
| Jira status transition | requires approval |
| Confluence publication or edit | requires approval |
| GitHub branch/commit push | unattended, within capability grant |
| GitHub pull request creation | unattended for `INTERNAL`; approval for `RESTRICTED` |
| GitHub merge | never |

Idempotency is keyed by run and node, so a retry updates rather than duplicates. Duplicate comments are the classic symptom of a durable system that forgot its external effects are not transactional.

All platform-authored content carries machine-readable provenance markers, and the context engine treats it as **lower trust** than human-authored content. Without this the platform reads its own unreviewed output back as authoritative and confident errors compound quietly — the integration failure mode that gets worse the longer it goes unnoticed.

## Integration contracts

Each integration is an anti-corruption layer over canonical internal models — `WorkItem`, `KnowledgeDocument`, `Repository`, `PullRequest`, `CheckResult`. External system shapes must not reach graph or agent logic, or every Jira configuration change becomes a platform change.

Polling only in V1; webhooks need a reachable endpoint that laptops do not have. CI logs are retrieved to the artifact store and failure-relevant excerpts extracted **deterministically before any model sees them**.

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

**Attribution has honest limits, and they must be stated rather than glossed over (ADR-0016).** Without central identity, the acting "user" is a self-asserted local OS username. Four of the five identifiers are platform-controlled and reliable; the fifth is not.

Audit is therefore tiered, and the tier is recorded on every entry:

- `SELF_ASSERTED` — local OS user; no assurance against a motivated insider
- `PLATFORM_ATTESTED` — run, node, grant, graph version, hashes; strong for reconstruction, forgeable by whoever controls the machine
- `EXTERNALLY_VERIFIABLE` — GitHub App action, commit, PR, Jira transition; verifiable independently of the platform

**V1 audit is developer-attested.** It supports debugging, reconstruction and personal accountability. It is NOT adversarial-grade. Never write a document, report or dashboard that implies otherwise — a control believed to be strong is more dangerous than one known to be weak.

Audit is separate from telemetry. Telemetry may be sampled, dropped or expired; audit is complete, append-only, and written on the critical path — if it cannot be written, the action does not happen. Never satisfy an audit requirement with a log line.

Audit what is consequential: `EXTERNAL_WRITE` and `IRREVERSIBLE` invocations, capability grants and every **denial**, approval decisions, run transitions, external writes, registry changes, escape-hatch use, redaction failures. Do not audit reads — burying the consequential records is its own way of losing them.

Anchor high-consequence actions in systems that have real identity: run ids in commits, PR bodies and Jira comments. The platform does not build identity it does not have; it borrows identity from systems that do.

Artifacts — transcripts, prompts, completions, diffs, context bundles, CI logs — are classified at write time, default to `SENSITIVE`, are redacted **before** persistence, and are retained by tier bounded by run state rather than wall-clock age alone (ADR-0017). Never delete an artifact a resumable run depends on.

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

V1 has two approval kinds with different assurance, and they must never be presented as equivalent (ADR-0009):

- `LOCAL_OPERATOR_CONSENT` — interactive CLI confirmation; developer-attested, not segregation of duties
- `EXTERNAL_ATTESTATION` — a GitHub PR review or Jira transition, verified via the API; required for `IRREVERSIBLE` actions and for `EXTERNAL_WRITE` in `RESTRICTED` repositories

Approvals bind to both the subject's content hash and the rendering hash of what the human was shown. One approval covers one subject: never implement standing, blanket or run-wide approvals. Every approval expires and fails closed.

No agent may request, waive, downgrade or record an approval. Approval renderings are generated by the platform, and untrusted content within them must never be able to impersonate platform text.

Do not design the system around the assumption that agents should always operate autonomously.

---

# 20. Observability

Observability is a first-class architectural concern.

**Instrumentation and deployment are different things and happen in different phases (ADR-0015).**

Instrument in Phase 1. Business logic depends on the **OpenTelemetry API only** — spans, metrics, structured logs and W3C trace context propagation are written alongside the code they describe. Retrofitting them later is a cross-cutting migration across two languages and three processes.

Deploy the backends in Phase 3: Prometheus, Loki, Grafana, Alertmanager. Do NOT make the full observability stack a V1 infrastructure requirement.

All signals are pushed over **OTLP to an OpenTelemetry Collector**, which owns backend translation. Do not expose Prometheus scrape endpoints: V1 components are short-lived laptop processes with no stable scrape target. Do not import a Prometheus, Loki or Grafana client into business logic.

## Correlation

W3C Trace Context is mandatory at every boundary: CLI to control plane, control plane to agent runtime and back, and tool layer to executor via `TRACEPARENT` (one of the few allowlisted environment variables — it carries no authority, which is why it is safe where credentials are not).

`traceId` and `spanId` **are** the correlation identifiers. Do not invent a second correlation scheme.

**Every persisted document carries `traceId` and `spanId`**, so durable state and telemetry are navigable in both directions.

Canonical identifier names, used identically in Java, Python, logs, spans, persistence and the CLI:

```text
runId, nodeId, attempt, graphId, graphVersion,
agentId, toolInvocationId, modelInvocationId,
workspaceId, executionId, workItemKey, repositoryId,
approvalId, contextBundleRef, actor
```

## Metrics

The catalogue and permitted labels are in `docs/architecture/observability.md`.

**Cardinality rule:** `runId`, `nodeId`, `workspaceId`, `executionId`, `workItemKey`, `contextBundleRef` and all invocation identifiers are **forbidden as metric labels**. They belong on spans, logs and exemplars. Metric labels must be low-cardinality and bounded by design: graph, graph version, node type, tool, provider, model, outcome, failure category.

`platform_tool_denied_total` and `platform_egress_denied_total` are security signals, not performance metrics.

Token usage and cost come from the model gateway's records only. Never recompute cost independently.

## Logs

Structured JSON, one schema across both runtimes. Mandatory fields: `timestamp`, `level`, `message`, `service`, `serviceVersion`, `traceId`, `spanId`. Contextual: `runId`, `nodeId`, `attempt`, `actor`, `repositoryId`, relevant invocation id.

Never log prompts, completions, tool results or file contents at default levels — log the artifact reference instead. Redaction is shared with model egress.

## Traces

The architecture should support end-to-end traces such as:

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

Model spans use OpenTelemetry **GenAI semantic conventions** (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.*`), not bespoke attribute names.

## Telemetry is not audit

Telemetry may be sampled, dropped or disabled. The audit trail may not — it is durable, unsampled and retained independently. Never satisfy an audit requirement with a log line.

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

The contracts those decisions define exist in machine-readable form under `schemas/`, with
valid and deliberately-invalid example documents. When implementing a component that produces
or consumes a contract, use the schema as the source of truth for its shape; the ADR remains
the source of truth for the reasoning. If the two disagree, that is a defect in one of them —
raise it rather than choosing one.

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
