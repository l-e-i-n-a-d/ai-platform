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

## Execution Interface

The contract between the tool layer and an execution backend. Workspaces are addressed by opaque ID, commands are argv arrays, and artifacts move as references — the properties that keep executors substitutable.

## Node Attempt

One execution of one graph node. The unit of retry, of capability granting and of agent runtime invocation.

## Capability Grant

The set of tools, scopes, command profiles and budgets available to a single node attempt. Derived from policy, never from model output, and never widened.

## Capability Ceiling

The maximum authority the platform may exercise in a given repository, recorded in the repository registry.

## Side-Effect Class

The consequence category of a tool: `READ`, `WORKSPACE_WRITE`, `EXTERNAL_WRITE` or `IRREVERSIBLE`. Determines idempotency and approval obligations.

## Command Profile

A named, repository-declared command with fixed argv and typed parameters. Models select profiles; they never author commands.

## Repository Registry

The platform's record of which repositories exist, their trust level and their capability ceiling. Version-controlled in the platform, never read from the target repository.

## Trust Level

A repository's classification — `INTERNAL`, `RESTRICTED` or `EXTERNAL` — recorded by the platform, never claimed by the repository.

## Lease

Exclusive, time-bounded ownership of a run. Only the lease holder may transition its state.

## Indeterminate

The state of a node whose side effect may or may not have occurred: a write-ahead intent exists with no recorded outcome. Never auto-retried.

## Idempotency Key

A derived key that makes a repeated side-effecting tool invocation deduplicate rather than repeat.

## Persistence Port

The domain interface through which all durable state is accessed. No storage SDK type appears above it.

## Artifact Store

Content-addressed storage for large payloads — transcripts, diffs, logs, reports — referenced from operational state.

## Approval Kind

The assurance level of an approval: `LOCAL_OPERATOR_CONSENT` (developer-attested) or `EXTERNAL_ATTESTATION` (verified through a system that has identity).

## Rendering Hash

The hash of the exact text a human was shown when approving. Records what was read, as distinct from what the system intended to present.

## Workspace Reconstructibility

The invariant that workspace state is always a function of `(repoRef, baseSHA, ordered patch series)`, which is what makes resume and remote execution possible.
