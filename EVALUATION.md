# AI Engineering Platform Evaluation

## Purpose

Evaluate the platform as an engineering system, not merely as a model wrapper.

Primary question:

> Can the platform reliably complete real engineering work to an acceptable engineering standard?

## Dimensions

- task success
- correctness
- deterministic verification
- context quality
- tool effectiveness
- recovery
- cost
- latency
- security/policy compliance

## Initial Benchmarks

Include:

1. bug fixes
2. unit tests
3. refactoring
4. API changes
5. cross-repository changes
6. Quarkus backend changes
7. Angular frontend changes
8. Helm changes
9. Kubernetes changes
10. CI/CD changes
11. documentation changes
12. architecture-aware changes

A flagship benchmark should test a cross-repository API change:

Jira -> Confluence -> Quarkus service -> API contract -> Angular client -> tests -> CI -> PR.

## Model Evaluation

Compare Claude, GPT and future models under equivalent task, context, tools, graph and verification conditions.

## Harness Evaluation

Also evaluate changes to graphs, context strategy, tools, prompts, policies and repository/service knowledge.

## Regression

Significant platform changes should run against a stable benchmark set.

## Evaluation Metadata

Eventually capture:

- evaluation ID
- task ID
- graph/version
- agent/version
- model/version
- context/version
- tool/version
- success
- verification result
- iterations
- duration
- token usage
- estimated cost
- failure reason
- artifacts
