# ADR-0010: Model Gateway Interface and Provider Neutrality

## Status

Accepted — 2026-08-15

Consumed by the agent runtime through the control plane (ADR-0004 §5). Emits the telemetry
defined in ADR-0015 §6/§9. Credentials, cost control and egress redaction are ADR-0011.

---

## Context

The platform requires a provider-neutral model interface, with Claude Sonnet and GPT as initial
providers. No interface is defined, and the genuinely difficult part is unacknowledged.

Claude and GPT differ materially in tool-calling protocol, message and role structure,
system-prompt handling, streaming semantics, structured-output mechanisms, reasoning-token
behaviour and error taxonomy. These are not cosmetic differences; the tool-calling loop *is*
agent execution, so how tool calls are normalised effectively determines the gateway design.

Provider neutrality fails in one of two directions, and both are common:

- **Lowest common denominator** — the abstraction exposes only what both providers share, and
  the platform forfeits the strengths it is paying for.
- **Leaky** — provider quirks surface in agent code, and the platform ends up with `if
  provider == "anthropic"` branches scattered through the runtime. This is exactly what the
  platform's principles forbid.

There is a third failure that is subtler and worse: an abstraction that *appears* neutral
because it has only ever been used with one provider. Neutrality that has not been exercised is
an assumption, not a property.

---

## Decision

### 1. A canonical request and response model

The gateway defines its own model. Provider adapters translate in both directions. No provider
SDK type crosses the gateway boundary.

```text
ModelRequest {
  modelRef            logical name resolved by the gateway, not a provider model id
  system[]            platform-authored instruction blocks
  messages[]          { role: USER | ASSISTANT | TOOL_RESULT, content[] }
  tools[]             { name, description, inputSchema (JSON Schema) }
  toolChoice          AUTO | REQUIRED | NONE | { name }
  outputContract      JSON Schema, when a structured result is required
  params              { temperature, topP, maxOutputTokens, stopSequences }
  budgets             { maxInputTokens, maxOutputTokens, timeoutMs }
  providerOptions     narrow, explicitly-labelled escape hatch (§4)
  correlation         runId, nodeId, attempt, agentId, traceparent
}

ModelResponse {
  modelInvocationId
  content[]           { type: TEXT | TOOL_CALL, ... }
  toolCalls[]         { toolCallId, name, arguments }
  finishReason        STOP | TOOL_CALLS | MAX_TOKENS | CONTENT_FILTER | ERROR
  usage               { inputTokens, outputTokens, cachedInputTokens, reasoningTokens }
  providerModelId     the concrete model actually served
  latencyMs
  cost                computed by the gateway (ADR-0011 §5)
}
```

`modelRef` is a **logical** name — `default-reasoning`, `fast-summarize` — resolved by gateway
configuration to a concrete provider and model. Agents and graph definitions never name a
provider model id. This is what makes swapping a model an operational change rather than a code
change, and what lets an evaluation run the same graph against both providers.

### 2. Tool calling is normalised; the loop belongs to the caller

The gateway translates tool descriptors to each provider's format and normalises tool-call
requests and results back to the canonical shape. It emphatically **does not** run the
tool-calling loop.

The agent runtime drives iteration; the control plane authorises and executes each tool call
(ADR-0004, ADR-0005). If the gateway ran the loop it would need to invoke tools, which would
put execution authority inside the component that talks to third parties — collapsing the
choke point the whole security model depends on.

Tool schemas are JSON Schema, and the gateway validates arguments against the declared schema
before returning them. A model that emits malformed arguments produces a canonical
`INVALID_OUTPUT` error rather than a provider-shaped surprise at the call site.

### 3. A canonical error taxonomy

```text
RATE_LIMITED        retryable, provider-advised delay where available
TRANSIENT           retryable
TIMEOUT             retryable within the attempt budget
AUTH                not retryable; credential problem
INVALID_REQUEST     not retryable; platform bug
CONTEXT_TOO_LARGE   not retryable; budget or context bug
CONTENT_FILTER      not retryable; recorded, never silently swallowed
INVALID_OUTPUT      model produced output violating the contract or tool schema
PROVIDER_ERROR      unclassified provider failure
```

These map onto the graph failure categories in ADR-0008 §11. Retry policy is decided by the
graph engine, not by the gateway inventing its own durability semantics — but see §6 for the
narrow exception.

### 4. A deliberate, narrow escape hatch

`providerOptions` is a map, explicitly labelled provider-specific, ignored by other adapters,
and recorded on the invocation.

Pretending no escape hatch is needed guarantees one gets built badly — usually as a magic
string smuggled through a general-purpose field. Making it explicit means its use is visible,
greppable, and reviewable. Any option used by more than one provider is a candidate for
promotion into the canonical model.

The gateway also documents what it deliberately does **not** expose. In V1 that includes
streaming, provider-specific caching controls, and provider-native tool implementations such as
server-side code execution — the last of which would bypass the execution interface entirely
and is therefore forbidden, not merely unsupported.

### 5. Non-streaming in V1

Graph-driven execution consumes a complete result; streaming adds partial-state handling,
complicates durability and offers nothing to a workflow node. Interactive surfaces may need it
later, and the response model can be extended then.

### 6. Resilience is centralised

The gateway owns exponential backoff with jitter, provider-aware rate-limit handling,
per-attempt and per-request timeouts, and a bounded retry budget. Every agent otherwise
reinvents this, badly and differently.

One rule constrains it: **the gateway may retry only when it is certain no tool call was
returned to the caller.** A retried invocation whose earlier attempt already produced a tool
call is a correctness failure, not a latency optimisation. Once a response has been handed
back, retry becomes the graph engine's decision under ADR-0008.

Prompt caching is an adapter-level optimisation, invisible to callers except as
`usage.cachedInputTokens`.

### 7. Record and replay, from Phase 1

Every invocation is recorded: canonical request, canonical response, usage, latency, provider,
concrete model id, and a deterministic hash over the normalised request.

A replay mode serves matching invocations from the recording instead of calling the provider.

This is the single most leveraged thing available early. It makes tests offline and fast, makes
regression evaluation cheap, and — decisively — makes it possible to evaluate a *harness*
change by holding model non-determinism constant. Without it, every evaluation conflates the
change under test with model variance. Retrofitting it means re-plumbing every call site, so it
is built into the gateway from the start.

### 8. Neutrality is proved, not asserted

The same evaluation suite runs against both providers from the beginning. An abstraction
exercised by one provider is an untested hypothesis, and the cost of discovering that late is a
rewrite of the agent runtime.

---

## Alternatives Considered

**Use a third-party multi-provider SDK.** Faster to start and someone else maintains the
adapters. Rejected for the gateway boundary itself: it makes the platform's most
security-relevant egress point an external dependency, its abstraction is not ours to shape,
and record/replay plus egress redaction would sit awkwardly around it. An adapter may use a
provider's own SDK internally.

**Expose provider-native request objects with a thin routing layer.** No fidelity loss.
Rejected: it is not an abstraction, and agent code becomes provider-specific immediately.

**Let the gateway run the tool-calling loop.** Common in agent frameworks and less code in the
runtime. Rejected: it puts tool execution inside the component that talks to third parties and
destroys the single authorization choke point.

**Streaming in V1.** Better perceived latency. Rejected as unnecessary complexity for
graph-driven execution; deferred, not precluded.

**No escape hatch.** Purer. Rejected as unrealistic — it produces covert escape hatches rather
than none.

---

## Consequences

**Positive**

- Agent code is provider-agnostic in fact, not merely in intention.
- Swapping or adding a model is configuration.
- Record/replay makes evaluation of the harness tractable and tests offline.
- One place implements retries, rate limits, timeouts, usage accounting and redaction.
- Provider-specific usage is explicit and greppable.

**Negative**

- Adapters are real work, and each new provider costs a translation layer plus a compatibility
  matrix.
- Canonical models always lag provider features by some interval.
- Two providers must be exercised continuously, which costs evaluation time and tokens.
- Normalisation can mask a provider's genuine strength if a capability is left out of the
  canonical model for too long.

---

## Security Notes

- The gateway is the platform's **egress choke point** to third parties. Redaction and secret
  scanning are mandatory there (ADR-0011 §6).
- Provider-native server-side execution tools are forbidden: they would bypass the execution
  interface, the capability model and the audit trail simultaneously.
- Tool arguments returned by a model are untrusted input and are schema-validated before use.
  Validation at the gateway does not replace authorization at the tool layer (ADR-0005).
- Recorded invocations contain prompts and completions and are therefore sensitive artifacts
  subject to ADR-0017 retention and redaction.

---

## Follow-up

- Create `docs/architecture/model-gateway.md`.
- Update `ARCHITECTURE.md` and `copilot-instructions.md` §12 with the canonical model,
  `modelRef` indirection and the no-loop rule.
- ADR-0011 — credentials, cost control and redaction.
- Add gateway record/replay to the Phase 1 scope in `ROADMAP.md`.
