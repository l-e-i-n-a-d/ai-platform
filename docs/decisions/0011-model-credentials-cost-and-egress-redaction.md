# ADR-0011: Model Credentials, Cost Control and Egress Redaction

## Status

Accepted — 2026-08-15

Extends ADR-0010 with the operational and security concerns of talking to third-party model
providers. Depends on ADR-0006 §4 (no credentials in workspaces), ADR-0013 §5 (context trust
classes) and ADR-0015 §9 (cost accounting authority).

---

## Context

V1 is local-first with no Key Vault, so model API keys live on developer machines. Three
questions follow, and none of them are currently answered.

**Whose keys?** Shared organisational keys distributed to many laptops cannot be rotated
cleanly, cannot attribute spend, and are readable by any process running as that user —
including build scripts executed by an agent. Per-developer keys attribute cost naturally but
multiply procurement and can produce inconsistent model access across the team.

**What stops runaway spend?** A repair loop is, structurally, a loop that calls a model until
something passes. Without an enforced ceiling, a graph bug or a stubborn failure is a financial
incident, and on a laptop there is nothing else to stop it.

**What stops secrets reaching the provider?** `SECURITY.md` forbids putting secrets into
prompts, but context is *machine-assembled* from repositories, CI logs, Jira and Confluence —
all of which routinely contain credentials. "Do not put secrets in prompts" is not achievable
by intent when no human writes the prompt. A `.env` swept up by repository search, or an API key
echoed into a build log and fed into a repair loop, is a third-party data disclosure with no
attacker involved.

---

## Decision

### 1. Per-developer credentials, held in the OS keychain

Each developer holds their own provider credentials. The platform reads them from the operating
system keychain — macOS Keychain, Windows Credential Manager, or the Secret Service API on
Linux.

Not `.env` files, which get committed. Not environment variables, which are inherited by child
processes and appear in process listings and crash dumps.

Consequences accepted deliberately: per-developer keys make spend attributable without building
any attribution machinery, they are revocable individually, and a compromised laptop exposes one
developer's key rather than the organisation's. Procurement is more work; that is the price.

Where an organisation must use a shared gateway or proxy credential, that is a deployment
decision recorded separately — but it must not be the V1 default, because it silently gives up
attribution and clean rotation.

### 2. Credentials never leave the control plane process

Model credentials are read by the control plane and used only by the gateway's provider
adapters.

They are never passed to the agent runtime, never placed in a workspace container, never in a
command profile's environment, and never in a container image. The runtime asks the control
plane to invoke a model; it does not hold the means to do so itself.

This is the same rule as ADR-0006 §4 for repository credentials, applied to the other class of
secret the platform holds, and for the same reason: code executed on behalf of a model must not
be able to steal the means to call one.

### 3. Budgets are enforced at three levels, and the minimum wins

```text
per-invocation    maxInputTokens, maxOutputTokens, timeout
per-node-attempt  token and cost ceiling, iteration limit
per-run           total cost ceiling
per-day           per-developer cost ceiling
```

Each is the minimum of the platform default, the repository registry's `budgetCeiling`
(ADR-0014) and the graph node definition — the same monotonic narrowing rule used for
capabilities.

Exceeding a ceiling fails the node with `BUDGET_EXCEEDED` (ADR-0008 §11). It is never a warning
and never auto-raised. A run may be resumed with a raised ceiling only through an explicit human
action, which is the correct place for that judgement.

The daily ceiling is a backstop against the failure mode ceilings usually miss: many small runs,
each individually reasonable.

### 4. Budget accounting is durable

Consumption is recorded on the run before the next invocation proceeds, not accumulated in
memory. A crashed and resumed run must not get a fresh budget — otherwise the ceiling is
enforced against process lifetime rather than against the run, and a crash loop becomes an
unbounded spend.

### 5. The gateway is the sole authority for usage and cost

Every invocation records provider-reported usage and a cost computed from a **versioned pricing
table** in configuration. Metrics, evaluation reports and run summaries derive from those
records and never recompute.

Versioning the table keeps historical costs reproducible when prices change — a cost recorded in
March must still mean what it meant in March. Cost is recorded with the pricing-table version
that produced it.

Where a provider reports usage that disagrees with local estimates, the **provider's report
wins** and the discrepancy is recorded. Estimation is only used where a provider reports
nothing, and is marked as estimated.

### 6. The gateway is the mandatory egress choke point, with redaction

Every outbound request passes a redaction pass before it leaves the process:

- known credential patterns — provider keys, tokens, private key blocks, connection strings
- high-entropy string heuristics in contexts where a secret is plausible
- explicit deny-lists from configuration

Redaction is **not** best-effort logging hygiene; it is the last control before data leaves the
organisation. Every redaction event is recorded as security telemetry, because a rising
redaction rate means secrets are reaching the assembly stage and the context-side exclusions
need fixing.

Defence is layered, and each layer is expected to be imperfect:

1. `contextPolicy.excludePaths` keeps credential files out of retrieval entirely (ADR-0013).
2. Command profiles and CI log extraction limit what reaches a bundle.
3. Gateway redaction catches what the first two missed.

Redaction applies identically to persisted invocation records. A recorded cassette that contains
a live key is the same disclosure with a delay.

### 7. Redaction is fail-closed on error, not on match

If the redaction pass itself fails — a malformed pattern, an unavailable configuration — the
invocation fails. It does not proceed unredacted. A control that silently degrades under error
is not a control.

A *match* is not a failure: content is redacted, the event is recorded, and the request
proceeds. Failing the run on every match would make the platform unusable in real repositories,
and would push developers toward disabling the control.

---

## Alternatives Considered

**Shared organisational key.** Simplest procurement, uniform model access. Rejected as the V1
default: unrotatable in practice once distributed, unattributable spend, and readable by any
process on the machine.

**Keys in `.env` files or environment variables.** What most tools do. Rejected: `.env` files
get committed, and environment variables are inherited by exactly the child processes this
architecture is trying to keep credential-free.

**A self-hosted proxy holding the only key.** Genuinely good — central rotation, central
budgets, one egress point. Rejected for V1 because it is a shared service, and V1 is
local-first with no centrally hosted component. Worth revisiting in Phase 7, where it becomes
the natural design.

**Budgets as warnings.** Less disruptive. Rejected: a warning in an autonomous loop is a
message nobody reads until the invoice arrives.

**No egress redaction, rely on context exclusions.** Fewer moving parts. Rejected: exclusion
lists are incomplete by construction, and CI logs and issue comments are not path-filterable.

**Fail the run on any redaction match.** Maximally safe. Rejected: too noisy to survive contact
with real repositories, and controls that get disabled protect nothing.

---

## Consequences

**Positive**

- Spend is attributable per developer without building attribution machinery.
- Credentials are revocable individually and are not readable by executed code.
- Runaway loops are bounded by an enforced, durable ceiling.
- One authority for cost, so evaluation and operations cannot disagree.
- A real, recorded control against secret disclosure to third parties.

**Negative**

- Every developer needs their own provider credentials — real onboarding friction, and `aip
  doctor` must make it obvious (ADR-0018).
- Model access may vary across the team depending on individual provider accounts.
- Keychain access differs across operating systems and needs three implementations.
- The pricing table needs maintenance and will occasionally be wrong.
- Redaction adds latency to every request and will sometimes redact something harmless.

---

## Security Notes

- Credentials are held by one process, in the OS keychain, and never cross into the runtime, a
  container, a command environment or a log.
- Redaction failure blocks egress. Redaction matches are recorded, not fatal.
- Recorded invocations and replay cassettes contain prompts and completions and inherit
  artifact-store controls and ADR-0017 retention rules.
- A rising `platform_redactions_total` is a security signal that upstream context controls are
  leaking, not a sign the redactor is working well.
- Budget ceilings are also a security control: they bound the damage an injected instruction can
  do by looping.

---

## Follow-up

- Include credentials, budgets and redaction in `docs/architecture/model-gateway.md`.
- Update `SECURITY.md` §3/§4 with the keychain rule and the egress choke point.
- Add `platform_redactions_total{source_class}` to the metric catalogue in
  `docs/architecture/observability.md`.
- Update `README.md` prerequisites: per-developer provider credentials.
- ADR-0017 — retention and redaction of recorded invocations.
