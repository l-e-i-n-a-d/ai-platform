# Model Gateway

**Status:** Planned (contract agreed, not yet implemented)
**Location:** Control plane (Java/Quarkus)
**Decisions:** [ADR-0010](../decisions/0010-model-gateway-interface.md),
[ADR-0011](../decisions/0011-model-credentials-cost-and-egress-redaction.md)

---

## 1. Responsibility

The gateway is the only component that talks to a model provider. It owns translation,
resilience, usage accounting, cost, recording and egress redaction.

It does **not** own the tool-calling loop. The agent runtime iterates; the control plane
authorises and executes tools. A gateway that ran the loop would need to invoke tools, putting
execution authority inside the component that talks to third parties.

```text
agent runtime
     |  canonical ModelRequest
     v
model gateway ---- budget check ---- redaction ---- record
     |
     v
provider adapter (Anthropic | OpenAI)
     |
     v
provider API
```

---

## 2. Canonical model

```text
ModelRequest {
  modelRef            logical name, resolved by configuration
  system[]            platform-authored instructions
  messages[]          USER | ASSISTANT | TOOL_RESULT
  tools[]             name, description, JSON Schema
  toolChoice          AUTO | REQUIRED | NONE | { name }
  outputContract      JSON Schema
  params, budgets
  providerOptions     narrow, labelled escape hatch
  correlation         runId, nodeId, attempt, agentId, traceparent
}

ModelResponse {
  modelInvocationId, content[], toolCalls[], finishReason,
  usage { inputTokens, outputTokens, cachedInputTokens, reasoningTokens },
  providerModelId, latencyMs, cost
}
```

No provider SDK type crosses this boundary.

`modelRef` is **logical** — `default-reasoning`, `fast-summarize` — resolved by gateway
configuration. Agents and graphs never name a provider model id, which is what makes changing a
model configuration rather than code, and what lets an evaluation run the same graph against
both providers.

---

## 3. Errors

```text
RATE_LIMITED · TRANSIENT · TIMEOUT · AUTH · INVALID_REQUEST
CONTEXT_TOO_LARGE · CONTENT_FILTER · INVALID_OUTPUT · PROVIDER_ERROR
```

These map onto ADR-0008 failure categories. Retry policy belongs to the graph engine.

The gateway retries internally **only while it is certain no tool call has been returned to the
caller**. A retried invocation whose earlier attempt already produced a tool call is a
correctness bug, not a latency optimisation.

---

## 4. What is deliberately not exposed

- streaming (V1; graph nodes consume complete results)
- provider-specific caching controls (adapter optimisation; visible only as
  `usage.cachedInputTokens`)
- provider-native server-side execution tools — **forbidden**, since they would bypass the
  execution interface, the capability model and the audit trail at once

`providerOptions` is the explicit escape hatch. Making it visible and greppable is better than
pretending none is needed and getting a covert one.

---

## 5. Credentials

Per developer, held in the **OS keychain** — not `.env` files, not environment variables.

Read by the control plane, used only by provider adapters. Never passed to the agent runtime,
never in a workspace container, never in a command environment, never logged. Code executed on
behalf of a model must not be able to steal the means to call one.

---

## 6. Budgets

```text
per-invocation    maxInputTokens, maxOutputTokens, timeout
per-node-attempt  token/cost ceiling, iteration limit
per-run           total cost ceiling
per-day           per-developer ceiling
```

Each is the minimum of platform default, repository `budgetCeiling` and node definition, clamped
to what remains at the enclosing level (ADR-0026 §3), so a node may receive less than it asks for.
The run-level ceiling is **mandatory**: a loop of bounded nodes is still unbounded spend unless
something computes the total.

Cost is denominated in integer micro-units of the run's currency (ADR-0026 §1) — 1 000 000 units
is 1.00 of the ISO 4217 code on the `GraphRun`. Integers because float accumulation makes a
spending limit approximate, which for a spending limit is the same as unenforced.

Exhausting a ceiling **suspends** the run with `BUDGET_EXCEEDED` rather than failing it, so an
operator can raise the ceiling and resume without discarding checkpointed work. It is never a
warning and never auto-raised: raising a budget is a consequential, audited action. It is never
retryable either — retrying a bound that was hit re-hits it.

Consumption is recorded **durably before the next invocation**. A crashed and resumed run must
not receive a fresh budget, or a crash loop becomes unbounded spend.

---

## 7. Cost

Sole authority. Provider-reported usage plus a **versioned pricing table**; cost is stored with
the pricing version that produced it, so historical figures stay reproducible. Where a provider
report and a local estimate disagree, the provider wins and the discrepancy is recorded.

Nothing else in the platform recomputes cost.

---

## 8. Egress redaction

The gateway is the mandatory egress choke point. Every outbound request passes credential
pattern matching, entropy heuristics and configured deny-lists.

Layered, each layer assumed imperfect:

1. `contextPolicy.excludePaths` keeps credential files out of retrieval
2. command profiles and CI log extraction limit what reaches a bundle
3. gateway redaction catches the rest

A redaction **match** redacts, records and proceeds — failing the run on every match would be
too noisy to survive real repositories, and disabled controls protect nothing. A redaction
**failure** blocks egress: a control that degrades silently is not a control.

Redaction applies identically to persisted invocation records. A cassette containing a live key
is the same disclosure, delayed.

---

## 9. Record and replay

Every invocation is recorded — canonical request and response, usage, latency, provider,
concrete model id — keyed by a deterministic hash of the normalised request. Replay mode serves
from the recording.

This makes tests offline and fast, regression evaluation cheap, and harness evaluation possible
at all by holding model non-determinism constant. Retrofitting it means re-plumbing every call
site, so it exists from Phase 1.

---

## 10. Proving neutrality

The same evaluation suite runs against both providers from the start. An abstraction exercised
by one provider is a hypothesis, not a property.
