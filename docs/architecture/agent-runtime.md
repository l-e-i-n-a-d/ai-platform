# Agent Runtime

**Status:** Planned (design agreed, not yet implemented)
**Language:** Python
**Decision:** [ADR-0004](../decisions/0004-control-plane-agent-runtime-boundary.md)

---

## 1. Responsibility

The agent runtime executes **one node attempt** of one agent, and returns.

```text
control plane                                agent runtime
     |                                            |
     |  POST /v1/agent-executions  ------------>  |
     |                                            |  assemble prompt
     |  <----  model invocation callback  ------  |
     |  ---->  model response                     |
     |                                            |  model requests a tool
     |  <----  tool invocation callback  -------  |
     |  ---->  tool result (or structured denial) |
     |                                            |  ... until output or budget
     |  <----  AgentExecutionResult  ------------ |
```

**Responsible for**

- prompt assembly from the supplied context bundle
- the inner agent loop for a single node attempt
- interpreting model tool-call requests and issuing tool invocation callbacks
- producing claimed structured output
- respecting the supplied iteration, token, cost and deadline budgets
- abandoning the loop when a callback signals `cancelRequested`

**Not responsible for**

- selecting the next node, branching, or retrying a failed node
- writing durable state
- authorizing tools
- talking to model providers, Jira, Confluence, GitHub or any data store
- executing commands or touching workspaces

---

## 2. Constraints

- **Stateless.** Nothing survives between requests. Consecutive attempts may be served by
  different processes.
- **No credentials.** The runtime holds no provider keys and no integration credentials.
- **One network peer.** Egress is default-deny; the control plane's loopback listener is the
  only permitted destination.
- **Descriptors, not implementations.** Tools arrive as schemas; the runtime cannot execute
  them.
- **Untrusted by design.** The control plane validates the runtime's output and takes usage,
  cost and side-effect facts from its own records.

The runtime sits on the untrusted side of the prompt-injection boundary. These constraints are
what make a successful injection containable: to reach anything, it must go through a tool
invocation, which is authorized and audited in the control plane.

---

## 3. Interface

`POST /v1/agent-executions` — request and result shapes are specified in ADR-0004 §11.

Callbacks, each bearing the attempt-scoped `callbackToken`:

| Callback | Serves |
|---|---|
| `POST /v1/runs/{runId}/nodes/{nodeId}/model-invocations` | model gateway |
| `POST /v1/runs/{runId}/nodes/{nodeId}/tool-invocations` | tool layer |
| `GET /v1/context-bundles/{ref}` | context engine |

Every callback response carries `cancelRequested`. The runtime must honour it at the next
iteration boundary.

Result statuses: `COMPLETED`, `BUDGET_EXHAUSTED`, `MODEL_ERROR`, `TOOL_ERROR`,
`RUNTIME_ERROR`, `CANCELLED`. The runtime reports what happened; it does not decide
retryability or failure category policy.

---

## 4. Process model

A single supervised process per platform instance, with bounded concurrency (default: one
in-flight attempt). Restarted on crash. In-flight attempts are reconciled by the graph engine
from durable state, never by the supervisor.

Killing the runtime at any moment is safe and costs at most one node attempt.

---

## 5. Agent definition

An agent is configuration, not code branching:

```text
agentId, version
objective
instructions          platform-authored; never derived from untrusted content
toolIds[]             intersected with the node's capability grant
outputSchema
modelPolicy
budgets               iterations, tokens, cost, deadline
```

Prefer several narrow agents over one broad one. Agents are versioned so evaluation can
compare them.

---

## 6. Testing

The runtime is a function of its request plus model non-determinism, with two fakeable
callbacks. Contract tests cover: schema conformance in both directions, protocol version
negotiation, budget enforcement, cancellation at an iteration boundary, structured denial
handling, and behaviour when the control plane becomes unreachable mid-loop.
