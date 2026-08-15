# Observability

**Status:** Planned (contracts agreed, not yet implemented)
**Scope:** Every component, both languages
**Decisions:** [ADR-0015](../decisions/0015-telemetry-contracts-and-collection-model.md)

---

## 1. Instrumentation vs deployment

These are different things and they happen in different phases.

| | Phase |
|---|---|
| OTel API instrumentation, propagation, log schema, identifiers | **1** |
| Collector deployment, Prometheus, Loki, Grafana, Alertmanager, dashboards, alerts | **3** |

Business logic depends on the **OpenTelemetry API only**. Nothing imports a Prometheus, Loki or
Grafana client. Phase 3 is configuration, not code.

The default exporter is console or file. OTLP export is opt-in and a collector is never required
to run the platform.

---

## 2. Collection

```text
components  --OTLP push-->  OpenTelemetry Collector  -->  Prometheus (remote-write)
                                                     -->  Loki
                                                     -->  trace backend
```

Push, not scrape. V1 components are short-lived laptop processes with no stable scrape target,
so a pull-based collector cannot reach them. The collector owns all backend translation.

---

## 3. Correlation

W3C Trace Context crosses every boundary:

| Boundary | Carrier |
|---|---|
| CLI → control plane | `traceparent` header |
| control plane ↔ agent runtime | `traceparent` header |
| tool layer → executor | `TRACEPARENT` env var (on the ADR-0006 allowlist) |
| model gateway → provider | recorded on the client span |

`traceId` and `spanId` **are** the correlation identifiers. There is no second scheme.

**Every persisted document carries `traceId` and `spanId`** — runs, node attempts, tool and
model invocations, approvals, audit entries. State and telemetry are then navigable in both
directions, which is the highest-value debugging property available here and costs two fields.

Canonical identifier names, identical in Java, Python, logs, spans, persistence and the CLI:

```text
runId, nodeId, attempt, graphId, graphVersion,
agentId, toolInvocationId, modelInvocationId,
workspaceId, executionId, workItemKey, repositoryId,
approvalId, contextBundleRef, actor
```

---

## 4. Spans

```text
run                     graphId, graphVersion, mode, workItemKey
+-- node                nodeType, attempt
    +-- context.build   sources, itemCount, tokenBudget, tokensUsed, excludedCount
    +-- agent.execute   agentId, iterations, tokens, cost
    |   +-- model.invoke        GenAI semantic conventions
    |   \-- tool.invoke         tool, sideEffectClass, authzDecision, idempotencyKey
    |       \-- execution.command  argv[0], exitCode, durationMs, limits
    \-- approval.wait   approvalId, waitSeconds, decision
```

Model spans use OTel **GenAI semantic conventions** (`gen_ai.system`, `gen_ai.request.model`,
`gen_ai.usage.*`), not bespoke attributes.

`approval.wait` may legitimately span days.

Spans carry references and counts — never prompt text, completions or file content.

---

## 5. Metrics

```text
platform_runs_total{graph_id, graph_version, mode, outcome}
platform_run_duration_seconds{graph_id, outcome}
platform_nodes_total{graph_id, node_type, outcome}
platform_node_duration_seconds{node_type, outcome}
platform_node_retries_total{node_type, failure_category}
platform_agent_iterations{agent_id}
platform_model_requests_total{provider, model, outcome}
platform_model_tokens_total{provider, model, direction}
platform_model_cost_usd_total{provider, model}
platform_model_latency_seconds{provider, model}
platform_tool_invocations_total{tool, side_effect_class, outcome}
platform_tool_denied_total{tool, reason}
platform_execution_duration_seconds{tool_kind, outcome}
platform_egress_denied_total{destination_class}
platform_approval_wait_seconds{graph_id}
platform_workspace_bytes{repository_id}
```

### Cardinality rule

`runId`, `nodeId`, `workspaceId`, `executionId`, `workItemKey`, `contextBundleRef` and all
invocation identifiers are **forbidden as metric labels**. They belong on spans, logs and
exemplars.

Permitted labels are bounded by design: graph, graph version, mode, node type, tool, side-effect
class, provider, model, outcome, failure category, destination class, repository. A new label
requires an argument that its value space is bounded.

Nothing fails immediately when this rule is broken, which is why it is enforced in review.

### Security signals

`platform_tool_denied_total` and `platform_egress_denied_total` measure policy being tested — by
a bug or by an injection attempt. These are the first alerts worth configuring in Phase 3.

---

## 6. Logs

Structured JSON, one schema, shared configuration in both runtimes.

Mandatory: `timestamp`, `level`, `message`, `service`, `serviceVersion`, `traceId`, `spanId`.
Contextual: `runId`, `nodeId`, `attempt`, `actor`, `repositoryId`, relevant invocation id.

Prompts, completions, tool results and file contents are never logged at default levels — log
the artifact reference. Redaction is shared with model egress and persisted artifacts: one
implementation, three call sites.

---

## 7. Cost accounting

The **model gateway is the sole authority**. It records provider-reported usage on each model
invocation and computes cost from a versioned pricing table. Metrics, evaluations and reports
derive from those records and never recompute independently.

Contradictory cost numbers between a dashboard and an evaluation report would undermine
confidence in the evaluation itself.

---

## 8. Telemetry is not audit

Telemetry may be sampled, dropped, disabled or expired. The audit trail may not. Audit records
are durable, unsampled and retained independently (ADR-0016).

Never satisfy an audit requirement with a log line.
