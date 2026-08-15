# ADR-0015: Telemetry Contracts, Correlation and Collection Model

## Status

Accepted — 2026-08-15

Applies across every component. Depends on ADR-0004 §5 (the control plane ↔ runtime boundary
where trace context must cross), ADR-0003 §4 (`correlation` on the execution request),
ADR-0006 §4 (the environment allowlist) and ADR-0007 (persisted state that must carry trace
identifiers).

---

## Context

The documentation states two things that cannot both be true. `ARCHITECTURE.md` §7 and
`copilot-instructions.md` §20 require correlation identifiers and telemetry contracts "from the
beginning"; `ROADMAP.md` Phase 3 says "introduce OpenTelemetry". One of these is instrumentation
and the other is deployment, and conflating them has a predictable cost: Phases 1 and 2 get
written without spans or context propagation, and Phase 3 becomes a cross-cutting retrofit of
every service in two languages. The phase hardest to debug — early development of a distributed
agent system — would be the phase with the least telemetry.

There is also an unexamined incompatibility. Prometheus is a pull-based scraper that needs
stable scrape targets. V1 components are short-lived processes on developer laptops behind no
stable address. The stated observability stack is architecturally incompatible with the stated
execution model, and discovering that in Phase 3 means either abandoning Prometheus or
rearchitecting collection.

Finally, `ARCHITECTURE.md` §7 lists nine correlation identifiers with no guidance on where each
belongs. The natural reading — attach them all as metric labels — produces unbounded cardinality
that will destroy any Prometheus deployment, and it is close to impossible to unwind once
dashboards depend on it.

The platform's headline observability claim is an end-to-end trace from Jira issue through graph
run, agent, model, tool, workspace, build, tests, repair and pull request. That trace crosses at
least three processes and two languages. Nothing currently specifies how it stays connected.

---

## Decision

### 1. Instrument in Phase 1; defer only the backends

Business logic depends on the **OpenTelemetry API only**. Instrumentation — spans, metrics,
structured logs, propagation — is written in Phase 1, alongside the code it describes.

What is deferred to Phase 3 is the *stack*: Prometheus, Loki, Grafana, Alertmanager and their
deployment. Phase 3 becomes collector configuration rather than a code change.

The default exporter is console or file, and OTLP export is opt-in. A developer who wants
nothing more than readable local output gets exactly that; a developer debugging a run can point
at a collector by changing one setting.

Instrumentation written with the code is cheap. Instrumentation added afterwards is a
migration.

### 2. Collection is OTLP push to a local collector

All signals — traces, metrics and logs — are exported over OTLP to an OpenTelemetry Collector.
The collector owns every backend translation: Prometheus remote-write, Loki, and whichever trace
backend is chosen.

No component ever exposes a Prometheus scrape endpoint, and no business logic imports a
Prometheus, Loki or Grafana client. This is what makes "do not couple business logic to
Prometheus or Loki" enforceable rather than aspirational, and it resolves the pull/push
incompatibility before it becomes a Phase 3 crisis.

The collector is optional in V1. It is not a prerequisite for running the platform (ADR-0018).

### 3. W3C Trace Context is mandatory at every boundary

| Boundary | Mechanism |
|---|---|
| CLI → control plane | `traceparent` HTTP header |
| control plane → agent runtime | `traceparent` HTTP header |
| agent runtime → control plane callbacks | `traceparent` HTTP header |
| tool layer → executor | `TRACEPARENT` environment variable, explicitly on the ADR-0006 §4 allowlist |
| model gateway → provider | recorded on the client span; not propagated to the provider |

`TRACEPARENT` is one of the very few environment variables permitted into a workspace. It
carries no authority and no secret — it is an identifier — which is precisely why it is safe to
allow where credentials are not.

The platform does not maintain a second, parallel correlation scheme. `traceId` and `spanId`
**are** the correlation identifiers; the domain identifiers below are attributes, not a
substitute.

### 4. Every persisted document carries `traceId` and `spanId`

Every durable record written under ADR-0007 — runs, node attempts, tool invocations, model
invocations, approvals, audit entries — carries the trace and span identifiers active when it
was written.

This makes durable state and telemetry mutually navigable in both directions: from a stuck run
to the trace that produced it, and from a slow span to the state it wrote. It is the single most
useful debugging property this architecture can have, it costs two fields, and it is
unrecoverable retroactively.

### 5. Canonical identifier names, fixed once

Used identically in Java, Python, logs, span attributes, persisted documents and the CLI:

```text
runId, nodeId, attempt, graphId, graphVersion,
agentId, toolInvocationId, modelInvocationId,
workspaceId, executionId, workItemKey, repositoryId,
approvalId, contextBundleRef, actor
```

Cross-language, cross-signal queries only work if the field names match exactly. Renaming later
means rewriting every query and dashboard, so the names are fixed now and belong in
`GLOSSARY.md`.

### 6. Span taxonomy

```text
run                     root; graphId, graphVersion, mode, workItemKey
+-- node                nodeType, attempt
    +-- context.build   sources, itemCount, tokenBudget, tokensUsed, excludedCount
    +-- agent.execute   agentId, iterations, tokens, cost
    |   +-- model.invoke        OTel GenAI semantic conventions
    |   \-- tool.invoke         tool, sideEffectClass, authzDecision, idempotencyKey
    |       \-- execution.command  argv[0], exitCode, durationMs, limits
    \-- approval.wait   approvalId, waitSeconds, decision
```

Model spans use the OTel **GenAI semantic conventions** — `gen_ai.system`,
`gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` — rather than
bespoke attribute names, so backends and vendor tooling work without translation.

`approval.wait` may span days. Long spans are acceptable and informative; the alternative,
ending the trace at the pause, would break exactly the end-to-end trace the platform promises.

### 7. Metric catalogue, and a normative cardinality rule

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

**`runId`, `nodeId`, `workspaceId`, `executionId`, `workItemKey`, `contextBundleRef` and every
invocation identifier are forbidden as metric labels.** They belong on spans, on logs and on
exemplars linking a metric back to a trace.

Metric labels must be low-cardinality and bounded by design: graph, graph version, node type,
tool, provider, model, outcome, failure category. Any new label requires justification that its
value space is bounded.

`platform_tool_denied_total` and `platform_egress_denied_total` are **security signals**, not
performance ones. A rising denial rate means policy is being tested — by a bug or by an
injection — and these are the first alerts worth wiring in Phase 3.

### 8. Structured logs with one schema and enforced redaction

JSON, identical in both runtimes, produced by shared configuration rather than convention.

Mandatory: `timestamp`, `level`, `message`, `service`, `serviceVersion`, `traceId`, `spanId`.
Contextual where applicable: `runId`, `nodeId`, `attempt`, `actor`, `repositoryId`, and the
relevant invocation identifier.

Prompts, completions, tool results and file contents are **never** logged at default levels. The
log references the artifact-store pointer instead. Agent logs naturally contain untrusted,
potentially sensitive and potentially credential-bearing content; a log line is the easiest
place for a secret to escape a system that is otherwise careful with them.

The same redaction pipeline applies to logs, persisted artifacts and model egress. One
implementation, three call sites — not three implementations that drift.

### 9. The model gateway is the sole authority for token and cost accounting

The gateway records provider-reported usage on every model invocation record and computes cost
from a **versioned pricing table** held in configuration. Metrics, evaluations, run summaries
and dashboards all derive from those records.

Nothing recomputes cost independently. Divergent numbers between a dashboard and an evaluation
report do not merely confuse; they destroy trust in the evaluation results, which is the one
thing the platform cannot afford to lose. Versioning the pricing table keeps historical costs
reproducible when prices change.

Details of the pricing table and budget enforcement belong to ADR-0011.

### 10. Phase 1 minimum

- traces with full propagation across CLI, control plane, runtime and executor
- the metric catalogue emitted through the OTel API, exporter optional
- structured logs conforming to the schema, in both languages
- `traceId` and `spanId` on every persisted document
- redaction active

Meeting that minimum is what makes Phase 3 purely additive.

---

## Alternatives Considered

**Defer all instrumentation to Phase 3, as the roadmap originally implied.** Less Phase 1 work.
Rejected: it is not deferral, it is deferred cost with interest. Retrofitting propagation across
two languages and three processes touches every call site, and the debugging benefit is lost
precisely when it is most needed.

**Expose Prometheus scrape endpoints directly.** Fewer moving parts and no collector.
Rejected: incompatible with short-lived laptop processes, and it couples business logic to
Prometheus, which the platform's own principles forbid.

**A bespoke correlation-ID scheme independent of OTel.** Simple and language-neutral.
Rejected: it means maintaining two correlation systems that must be kept consistent, and it
gives up every tool that understands W3C Trace Context for no gain.

**Vendor-specific APM instrumentation.** Richer out of the box. Rejected: it couples business
logic to a vendor and contradicts the provider-neutral posture applied everywhere else.

**Allow high-cardinality metric labels and rely on operational limits.** Convenient for
debugging. Rejected: it fails silently at first and catastrophically later, and dashboards built
on those labels become very hard to unwind.

---

## Consequences

**Positive**

- Phase 3 is a configuration change, not a migration.
- The end-to-end trace the platform promises is actually achievable.
- Durable state and telemetry are mutually navigable from the first commit.
- Security signals — denied tools, denied egress — are first-class metrics rather than
  afterthoughts.
- Cost is computed in one place, so evaluation and operations agree.

**Negative**

- Phase 1 carries instrumentation work that produces no user-visible feature.
- Two languages must maintain one log schema and one identifier vocabulary, which requires
  shared configuration and review discipline.
- The cardinality rule is a constraint developers will occasionally find inconvenient, and it
  needs enforcing in review because nothing fails immediately when it is broken.
- Long-lived `approval.wait` spans are unusual and some tooling handles them poorly.

---

## Security Notes

- `TRACEPARENT` is permitted into workspaces because it conveys no authority. No other
  telemetry configuration crosses that boundary, and no credential ever does (ADR-0006).
- Logs are a leading cause of credential disclosure. Redaction is mandatory, applies at default
  and elevated levels, and is shared with model egress redaction.
- Telemetry is diagnostic and may be sampled, dropped or disabled. The **audit trail is not
  telemetry**: it is durable, unsampled and retained independently (ADR-0016). Never satisfy an
  audit requirement with a log line.
- Trace and span identifiers are not secrets, but spans must not carry prompt or file content —
  only references and counts.

---

## Follow-up

- Create `docs/architecture/observability.md` with the taxonomy, catalogue, label rule and log
  schema.
- Amend `ROADMAP.md`: instrumentation moves to Phase 1; Phase 3 becomes backends and dashboards.
- Update `ARCHITECTURE.md` §7 with the collection model and the cardinality rule.
- Update `copilot-instructions.md` §20 to separate instrumentation from deployment.
- Add the canonical identifier vocabulary to `GLOSSARY.md`.
- ADR-0011 — model credentials, pricing table and budget enforcement.
- ADR-0016 — audit integrity, and the audit-is-not-telemetry boundary.
- ADR-0017 — artifact retention and redaction, shared with §8.
