# ADR-0004: Control Plane / Agent Runtime Boundary and Protocol

## Status

Accepted — 2026-08-15

Depends on ADR-0007 (persistence port). Must be read together with ADR-0005 (tool
authorization) and ADR-0008 (graph execution semantics); the three describe one boundary from
three angles and should be accepted or rejected together.

---

## Context

The architecture states that the control plane is Java/Quarkus and the agent runtime is
Python, and that "agent execution should not be embedded in the control plane". That is the
entire specification. Everything that makes the split meaningful is undefined:

- which component owns which loop
- what the Python process is allowed to reach
- how the two communicate
- what happens when either side dies mid-node
- whether the control plane trusts what the runtime reports

A boundary that is only a language boundary decays predictably. The agent runtime acquires a
database client "just for checkpoints", a Jira client "just to read the issue", a provider SDK
"just for streaming", and its own retry loop "just for flakiness". At that point there are two
orchestrators, two sources of truth, two audit paths, and the security controls in the control
plane are advisory because there is a second path around them.

Two further pressures make this decision security-relevant rather than merely tidy:

**The agent runtime processes untrusted input.** Repository files, Jira descriptions,
Confluence pages and pull-request comments all reach the model through this process. Prompt
injection is not a hypothetical: the realistic attack is content that persuades the model to
exfiltrate a credential or reach an attacker-controlled host. The runtime's network reach is
therefore a security boundary, not a deployment detail.

**V1 is local-first.** Both processes run on a developer's laptop, which will be suspended,
run out of battery, and lose network. Durability cannot depend on either process staying
alive.

---

## Decision

### 1. Two loops, strictly nested, with different durability guarantees

```text
OUTER LOOP — graph loop            control plane, durable, ADR-0008
  selects the next node, applies retry/timeout policy,
  writes every state transition, holds the run lease
        |
        |  one node attempt
        v
INNER LOOP — agent loop            agent runtime, ephemeral
  assemble prompt -> model -> tool request -> tool result -> repeat
  until structured output or budget exhaustion
```

The agent runtime executes **exactly one node attempt per request** and then returns. It
never selects the next node, never decides to retry a failed node, never branches, and never
schedules work. All workflow control lives in the graph engine.

Consequently the runtime holds no durable state. Killing it loses at most one node attempt,
which the graph engine already knows how to reschedule.

### 2. The runtime is stateless and freely restartable

No local database, no cache that survives a request, no run-scoped memory between calls. Two
consecutive node attempts may be served by different runtime processes. Any state that must
survive is passed in the request or fetched by reference from the control plane.

### 3. Capability restrictions (a negative list, enforced, not advisory)

The agent runtime **may not**:

- open a connection to the operational store or the artifact store
- call Jira, Confluence or GitHub
- hold or read model provider credentials
- import a model provider SDK
- execute commands, containers or workspace operations
- write outside its own process-scoped temporary directory
- open a network connection to any host other than the control plane

### 4. The control plane is the runtime's only network peer

This is the load-bearing security decision of this ADR. The runtime runs with default-deny
egress; the sole permitted destination is the control plane's loopback listener.

The consequence is that a successful prompt injection cannot exfiltrate directly. To reach the
outside world it must pass through a tool invocation, which means it must pass the
authorization choke point of ADR-0005 and appear in the audit trail. Injection becomes a
containable problem rather than an unbounded one.

### 5. Transport: HTTP/1.1 with JSON over loopback, in both directions

- Control plane → runtime: `POST /v1/agent-executions` — one call, one node attempt.
- Runtime → control plane: callbacks for model invocation, tool invocation and context
  retrieval.

Both directions carry an explicit `protocolVersion`. Incompatible versions fail fast at
startup rather than at the first interesting node.

HTTP/JSON is chosen for observability and debuggability: every interaction can be inspected,
logged, replayed and reproduced with ordinary tooling, and W3C trace context propagates
natively. The same protocol works unchanged if the runtime later moves into a container or
onto another host — nothing in it assumes co-location.

### 6. Process model: a supervised long-running local process

The control plane supervises a single runtime process per platform instance, with bounded
concurrency (default: one in-flight node attempt; configurable). The runtime is restarted on
crash; in-flight attempts are reconciled by the graph engine, not by the supervisor.

A subprocess per node was rejected (see Alternatives) primarily because it makes the common
developer experience — start the platform, run a graph, watch it work — depend on Python
process startup on every node.

### 7. Durable state is authoritative; the HTTP call is not

When the control plane dispatches a node attempt it has already written
`NodeExecution{status=RUNNING, attempt=n}` durably. If the HTTP call then fails, times out, or
the control plane itself restarts, recovery is driven entirely from durable state per ADR-0008.
The response is an optimisation, not the record.

Each attempt carries a deadline. Liveness is inferred from callbacks and the deadline; a
runtime that neither calls back nor returns before the deadline is terminated and the attempt
is failed with `EXECUTION_ERROR`.

### 8. Cancellation is cooperative, with a hard backstop

Every callback response carries a `cancelRequested` flag. The runtime must abandon the agent
loop at the next iteration boundary and return `status=CANCELLED`. If it does not do so before
the deadline, the process is terminated. Cancellation is therefore guaranteed to stop new work
and best-effort for work already in flight — the same guarantee ADR-0008 makes for runs.

### 9. The control plane never trusts the runtime's self-report

The runtime returns *claimed* output. The control plane validates it against the node's
declared output schema before any transition is evaluated. Usage and cost are taken from the
model gateway's own records, not from the runtime's summary. Tool effects are known from the
tool layer's records, not from the runtime's narrative.

This is what makes the boundary a trust boundary rather than a module boundary.

### 10. Authentication: a per-attempt callback token

The control plane mints a token bound to `(runId, nodeId, attempt)`, valid until the attempt
deadline, and passes it in the request. Every callback must present it. The token is the
bearer of the capability grant defined in ADR-0005: the tool layer resolves grant from token,
so the runtime cannot widen its own authority by asking differently.

Tokens are single-attempt. A retry gets a new token and a new grant.

### 11. Protocol messages

```text
POST /v1/agent-executions            (control plane -> runtime)
{
  protocolVersion, runId, nodeId, attempt, traceparent,
  agentId, objective, instructions,
  contextBundleRef,                  // fetched by reference, not inlined
  toolDescriptors[],                 // descriptors only; no implementations
  outputSchema,
  budgets: { maxIterations, maxTokens, maxCostUnits, deadline },
  modelPolicy: { selector | modelId },
  callbackToken
}

-> AgentExecutionResult
{
  protocolVersion, status, claimedOutput,
  iterations, stopReason,
  failure: { category, message, detailsRef }   // when status != COMPLETED
}

Callbacks (runtime -> control plane), all bearing callbackToken:
  POST /v1/runs/{runId}/nodes/{nodeId}/model-invocations   -> model gateway
  POST /v1/runs/{runId}/nodes/{nodeId}/tool-invocations    -> tool layer  (ADR-0005)
  GET  /v1/context-bundles/{ref}                           -> context engine
```

`status` is one of `COMPLETED`, `BUDGET_EXHAUSTED`, `MODEL_ERROR`, `TOOL_ERROR`,
`RUNTIME_ERROR`, `CANCELLED`. It maps to the failure categories in ADR-0008; the runtime does
not invent categories and does not decide retryability.

---

## Alternatives

**A. Implement the agent loop in Java and drop the Python runtime.**
Removes the boundary, the protocol, the second process and a whole class of failure. Rejected
because the AI ecosystem — evaluation harnesses, prompt tooling, model client libraries — is
overwhelmingly Python, and the platform must be able to adopt it. The cost of this ADR is the
price of that access, and it is paid once.

**B. Subprocess per node attempt, communicating over stdio JSON-RPC.**
Attractive: strongest isolation, no listening port, no token, fresh state guaranteed rather
than promised. Rejected for V1 because it pays Python interpreter and import startup on every
node, makes the inner loop materially harder to observe with standard tooling, and does not
survive a move to a remote runtime without being replaced. Worth revisiting if runtime
isolation becomes the dominant concern.

**C. Give the runtime direct database and integration access.**
Rejected. It creates a second writer of durable state, a second audit path and a second set of
credentials on the untrusted side of the prompt-injection boundary. This is the specific
outcome this ADR exists to prevent.

**D. gRPC instead of HTTP/JSON.**
Better typed, better streaming, worse to debug at 22:00 on a laptop. Rejected for V1 on
developer-experience grounds; the message shapes above are transport-agnostic, so this can be
revisited without changing the boundary.

**E. A message broker between the two.**
Rejected: new infrastructure for a single-node local platform, contrary to the local-first
principle and the exclusion of broker infrastructure from V1.

---

## Consequences

**Accepted costs**

- Two processes to start, supervise and version. The developer experience must hide this
  behind a single command, or the local-first goal is undermined in practice.
- The protocol is a compatibility surface. It needs a version, a schema and contract tests.
- Fetching the context bundle by reference costs a round trip per node attempt.
- Bounded concurrency means a V1 graph does not execute nodes in parallel across agents.
  Accepted deliberately: parallelism before durability is proven would be premature.

**Gained**

- Killing either process is safe at any moment, which is the property local-first execution
  most needs.
- Every model call, tool call and context read is observable and attributable at the boundary,
  because there is no other path.
- The runtime is trivially testable: it is a function from request to result with two
  well-defined callbacks, both of which can be faked.
- The same protocol supports a future containerised or remote runtime with no semantic change.

---

## Security / Operational Impact

- The runtime sits on the untrusted side of the prompt-injection boundary and is treated as
  such: no credentials, no data-store access, no egress except to the control plane.
- Callback tokens are short-lived, attempt-scoped and non-escalating.
- The loopback listener must bind to localhost only and must not be exposed on any interface.
- Compromise of the runtime process yields exactly the authority in the current capability
  grant, for the remainder of one node attempt. That is the intended blast radius.
- Untrusted content must never be placed where the protocol expects platform-controlled
  fields; `instructions` are platform-authored, `contextBundleRef` content is data.

---

## Follow-up

- `docs/architecture/agent-runtime.md` — component documentation (this ADR's operational form).
- Update `docs/architecture/control-plane.md` to name the boundary and the invariants.
- ADR-0005 — the tool contract this protocol carries descriptors for.
- ADR-0008 — the graph semantics that make the outer loop durable.
- ADR-0010 — model gateway interface behind the model-invocation callback.
- ADR-0015 — trace propagation across the boundary via `traceparent`.
- Protocol JSON Schemas and a cross-language contract test suite, before implementation.
