# AI Engineering Platform — Glossary

## Agent

A constrained AI execution unit with an explicit objective, context, tools, policies and output contract.

## Agent Runtime

The runtime responsible for executing agents. V1 uses Python.

## Control Plane

The Quarkus-based coordination layer responsible for APIs, workflow state, policies and integrations.

## Context Engine

The component responsible for discovering, ranking and preparing relevant information for agents.

## Execution Backend

An implementation of the execution abstraction.

V1:

- Local Executor

Future:

- Kubernetes Executor

## Execution Workspace

An environment in which repository operations, builds and tests execute.

## Graph

A versioned workflow definition containing nodes, transitions and execution semantics.

A graph does not imply a graph database.

## Graph Engine

The component responsible for executing workflow graphs.

## Harness

The complete system around a model that makes AI useful for engineering work, including context, tools, workflows, verification and recovery.

## Model Gateway

The provider-neutral interface through which agents access AI models.

## Model Provider

An external AI model service such as Anthropic or OpenAI.

## Local Executor

The V1 execution backend that runs engineering workloads on a developer's machine.

## Kubernetes Executor

A future execution backend that runs workloads in Kubernetes/AKS.

## Run

A concrete execution of a graph.

## Tool

A capability exposed to an agent, such as reading a repository, running tests or creating a pull request.

## Checkpoint

Persisted execution state that allows a workflow to resume after interruption.

## Repair Loop

A controlled cycle in which verification failures are analyzed and the agent attempts a bounded correction.

## Context Provenance

Information describing where context came from and why it was supplied to an agent.

## Observability

Metrics, logs and traces that allow platform behavior to be understood and diagnosed.

## Correlation ID

An identifier used to connect related operations across graphs, agents, tools, models and execution workspaces.

## System of Record

The authoritative external system for a particular type of information.

- Jira → engineering work
- Confluence → product/engineering knowledge
- GitHub → source code and CI
