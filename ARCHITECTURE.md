# AI Engineering Platform Architecture

## 1. Purpose

The AI Engineering Platform is a centralized control plane for executing reliable AI-assisted software engineering workflows across multiple repositories.

## 2. High-Level Architecture

```text
Developer
   |
   v
Platform API (Quarkus)
   |
   +--> Jira
   +--> Confluence
   +--> GitHub
   |
   v
Context Engine
   |
   v
Graph Engine
   |
   v
Agent Runtime (Python)
   |
   v
Model Gateway
   |
   v
AKS isolated engineering workspace
   |
   +--> GitHub / CI
   +--> tests / tools

Operational state --> Cosmos DB
Large artifacts   --> Blob Storage
Secrets           --> Key Vault
Identity          --> Entra ID / Workload Identity
```

## 3. System-of-Record Boundaries

Jira remains authoritative for work management. Confluence remains authoritative for product and engineering knowledge. GitHub remains authoritative for source code and pull requests.

Cosmos DB stores AI platform operational state. Blob Storage stores large artifacts.

## 4. Control Plane

The Quarkus control plane owns APIs, work/run management, authorization, policy enforcement, graph lifecycle, integration contracts and durable execution metadata.

## 5. Agent Runtime

The Python runtime executes constrained agents. An agent has an identity, objective, instructions, skills, tools, context, model configuration, iteration limits, policies and an output contract.

## 6. Graph Engine

Important engineering workflows are explicit, versioned graphs supporting sequential execution, branching, loops, retries, checkpoints, approvals, timeouts and failure handling.

## 7. Context Engine

The Context Engine progressively constructs task context from Jira, Confluence, GitHub, repository/service relationships, architecture information, CI results and previous run state.

Do not indiscriminately load entire repositories or organizational knowledge into model context.

## 8. Repository / Service Graph

The platform should model relationships between Jira issues, Confluence pages, repositories, services, APIs, Helm charts, Kubernetes workloads, CI pipelines and pull requests.

A dedicated graph database is not required for the initial architecture.

## 9. Execution Plane

Agent execution occurs in isolated AKS workloads where practical. Workspaces should be ephemeral where possible.

The control plane should not directly execute arbitrary repository commands.

## 10. State and Eventing

Cosmos DB is the operational state store. Cosmos DB Change Feed may be used for state-driven processing.

Kafka is not part of this architecture.

Azure Service Bus may be considered only when explicit durable queue semantics are demonstrated as necessary.

## 11. Security

Use least privilege, Entra ID, AKS Workload Identity, Key Vault, scoped GitHub permissions, policy-controlled tools and human approval for consequential operations.

Production access is denied by default.

## 12. Observability

Meaningful executions should record run ID, task ID, graph/version, node, agent, model, tool calls, duration, token/cost metadata, failures, retries, checkpoints and outcome.

Large payloads belong in Blob Storage; metadata belongs in Cosmos DB.

## 13. Model Gateway

Agents use a provider-neutral Model Gateway supporting Claude, GPT and future providers. Provider-specific behavior should be isolated behind the gateway.

## 14. Human Approval

Approval is a first-class graph capability. Workflows must be able to pause and resume around approval gates.

## 15. Status

This document describes the target architecture. It does not imply implementation.
