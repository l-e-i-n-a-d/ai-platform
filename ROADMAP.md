# AI Engineering Platform Roadmap

## Phase 0 — Architectural Scaffold
Status: Current

- repository structure
- architecture
- principles
- terminology
- system boundaries
- initial ADRs
- open architectural questions

## Phase 1 — Platform Foundation

- Quarkus control-plane skeleton
- Cosmos DB run/task state
- Blob Storage artifacts
- authentication/authorization
- Key Vault integration
- AKS workspace provisioning
- GitHub integration
- initial observability

Target:
Create Run -> Create Workspace -> Execute Controlled Tool -> Persist Result -> Destroy Workspace

## Phase 2 — Agent Runtime

- Python runtime
- Model Gateway
- Claude integration
- GPT integration
- tool contracts
- structured outputs
- iteration limits
- retries
- checkpointing

## Phase 3 — Graph Engine

- declarative graph format
- versioning
- branching
- loops
- retries
- checkpoints
- human approval
- failure handling

## Phase 4 — Engineering Context

- Jira
- Confluence
- GitHub repository discovery
- service catalog
- repository/service graph
- context ranking
- progressive context construction

## Phase 5 — Engineering Automation

- implementation agent
- testing agent
- debugger
- reviewer
- technical writer
- CI feedback loop
- GitHub PR automation
- Jira updates
- documentation proposals

## Phase 6 — Evaluation and Optimization

- benchmark datasets
- model comparison
- context evaluation
- trajectory evaluation
- cost and latency tracking
- regression testing

## Phase 7 — Dogfooding

Use the platform on selected platform-repository tasks, starting with low-risk work.

## v1 Non-Goals

- autonomous production deployments
- Kafka
- dedicated graph database
- unrestricted autonomous agents
- uncontrolled multi-agent swarms
- replacing Jira, Confluence or GitHub
