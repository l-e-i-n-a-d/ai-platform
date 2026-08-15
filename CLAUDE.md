# CLAUDE.md

## Project

This repository is the source repository for the team's shared AI Engineering Platform.

The platform is a centralized internal engineering platform for AI-assisted software development across multiple repositories.

## Engineering Environment

- Java
- Quarkus
- Python
- Angular
- Kubernetes
- Helm
- CI/CD
- Azure
- Azure Kubernetes Service (AKS)
- Azure Cosmos DB
- Azure Storage / Blob Storage
- Azure Key Vault
- Microsoft Entra ID / Workload Identity
- GitHub / GitHub Actions
- Jira
- Confluence

AI models include Anthropic Claude / Claude Sonnet and OpenAI GPT, with future providers possible.

Kafka is explicitly not part of the architecture.

## System-of-Record Boundaries

| System | Responsibility |
|---|---|
| Jira | Work items, requirements, acceptance criteria, workflow |
| Confluence | Product and engineering documentation, architecture, ADRs, knowledge |
| GitHub | Source code, repositories, pull requests, code review, CI/CD |
| AKS | Isolated AI engineering execution |
| Cosmos DB | Platform operational state, runs, checkpoints, events, metadata |
| Blob Storage | Large artifacts, transcripts, reports, logs, generated files |
| Key Vault | Secrets |
| Entra ID | Identity and authorization |
| AI Platform | Orchestration, context, agents, graphs, policies, evaluations |

## Architectural Goal

Build a reliable AI Engineering Control Plane supporting workflows such as:

Jira Story -> context discovery -> planning -> human approval -> isolated implementation -> tests -> CI -> repair -> GitHub PR -> review -> documentation -> Jira update.

The platform must support interruption, failure, retry, checkpointing and recovery.

## Core Concepts

- Work Item
- Work Context
- Agent
- Skill
- Tool
- Graph
- Graph Run
- Checkpoint
- Policy
- Approval
- Evaluation
- Repository
- Service
- Knowledge Source
- Model Invocation

## Intended Components

- Quarkus Platform API / Control Plane
- Python Agent Runtime
- Graph Engine
- Context Engine
- Model Gateway
- Policy Engine
- Evaluation Framework
- Repository / Service Graph
- Jira, Confluence and GitHub connectors
- AKS execution/workspace management

## Design Principles

Prefer reliability, security, recoverability, deterministic verification, context quality, observability, evaluation, provider neutrality and human approval over maximum autonomy.

Avoid uncontrolled agent loops, giant agents, unnecessary infrastructure, unnecessary databases, Kafka, and autonomous production changes in v1.

## Implementation Status

The initial repository is an architectural scaffold. Do not describe planned or proposed functionality as implemented.

Before significant changes, read the architecture documents and relevant ADRs. For major architectural decisions, create or update an ADR.
