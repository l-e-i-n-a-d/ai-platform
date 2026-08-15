# AI Engineering Platform — Evaluation

## Purpose

The platform must evaluate the engineering harness, not merely individual models.

A stronger model does not necessarily produce a better engineering system.

---

## Evaluation Dimensions

Evaluate:

- correctness
- task completion
- deterministic verification
- context quality
- tool effectiveness
- graph effectiveness
- recovery
- reliability
- cost
- latency
- security

---

## Initial Benchmark Categories

### Java / Quarkus

- bug fixes
- feature changes
- API changes
- tests

### Python

- implementation
- bug fixing
- test repair

### Angular

- UI changes
- API integration
- tests

### Helm / Kubernetes

- chart changes
- configuration changes
- manifests

### CI/CD

- pipeline changes
- failed build repair
- test failure repair

### Documentation

- Jira requirement interpretation
- Confluence updates
- architecture documentation

### Cross Repository

- API + backend + frontend
- shared library changes
- coordinated pull requests

---

## Representative Workflow

```text
Jira
 ↓
Confluence
 ↓
Repository context
 ↓
Plan
 ↓
Human approval
 ↓
Implementation
 ↓
Tests
 ↓
CI
 ↓
Repair loop
 ↓
Verification
 ↓
GitHub PR
```

---

## Evaluation Reproducibility

Evaluations should record:

- model
- model configuration
- prompt/instructions
- graph version
- tool versions
- repository revision
- context sources
- execution environment
- outcome
- cost
- latency

---

## Future Observability Integration

Evaluation data should eventually integrate with the observability platform using OpenTelemetry-compatible correlation identifiers.

Future stack:

- Prometheus
- Loki
- Grafana
- Alertmanager
