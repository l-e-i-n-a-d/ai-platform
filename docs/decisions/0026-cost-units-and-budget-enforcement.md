# ADR-0026: Cost Units, Currency and Run-Level Budget Enforcement

## Status

Accepted — 2026-08-15

Closes OQ-08 from `docs/contracts/v1-domain-contracts.md`. Refines the budget fields of ADR-0005,
ADR-0008 §12, ADR-0011 and ADR-0022, and the telemetry of ADR-0015.

---

## Context

`maxCostUnits` appears on capability grants, node budgets, agent defaults and registry ceilings.
Nothing defines what a cost unit is. `ModelResponse.cost` separately carries `{amount, currency}`,
so the platform currently has two incompatible ways of talking about money and no statement of how
they relate.

That is the smaller half of the problem. The larger half is that **every declared budget is
per-node or per-grant, and there is no run-level ceiling anywhere.** A loop bounded at 20
iterations, each running a node bounded at 50 cost units, is bounded at 1000 — but nothing in the
system computes that number, enforces it, or tells a developer before the fact. A graph with a
repair loop and a mis-specified exit condition is a plausible way to spend real money overnight on
a laptop, and the first signal would be the provider's bill.

`PRINCIPLES.md` requires bounded resource consumption. A bound that is only implied by arithmetic
over other bounds is not enforced.

A third issue is arithmetic. Provider costs are fractional currency amounts. ADR-0020 requires
hashed documents to contain integers only, and floating-point accumulation across thousands of
calls drifts. Budgets compared with `>` against a drifting accumulator produce a limit that is
approximately enforced, which for a spending limit is the same as not enforced.

---

## Decision

### 1. A cost unit is a fixed-point currency amount, not an abstraction

One cost unit is **one micro-unit of the run's currency**: 10⁻⁶ of one unit of `currency`.

```text
1 000 000 cost units == 1.00 USD   when currency == "USD"
```

`currency` is an ISO 4217 code, declared once on the `GraphRun` and immutable for the run's
lifetime. All `maxCostUnits` fields are integers in this denomination.

Micro-units are chosen because provider prices are quoted per million tokens; a per-call cost at
this granularity is an exact integer for every provider currently in scope, so accumulation is
exact addition with no rounding step. Where a provider reports a finer amount, it is rounded **up**
at the point of recording, so the platform never under-reports spend.

`ModelResponse.cost` keeps `{amount, currency}` as the provider-reported figure. The gateway
converts it to integer cost units at record time and both are stored: the provider figure is the
evidence, the integer is what the platform enforces against. Divergence between them is a gateway
bug and is detectable precisely because both are kept.

Cost units are deliberately **not** normalised tokens or provider-neutral credits. Credits require
a conversion table that becomes stale silently, and a developer asking "what did this run cost?"
wants an answer in money.

### 2. Multi-currency runs are rejected, not converted

If a run's model policy could resolve to providers billing in different currencies, the run is
rejected at creation. The platform does not perform currency conversion: a converted budget is
enforced against an exchange rate nobody recorded, and the resulting number is not reproducible
for evaluation.

This is a real constraint on provider mixing, and it is preferable to a budget whose meaning
depends on the day it was evaluated.

### 3. Budgets nest, and each level is enforced where it is declared

```text
GraphRun.budget.maxCostUnits          run ceiling      — graph engine
  └── GraphNode.budget.maxCostUnits   node ceiling     — graph engine, before dispatch
        └── CapabilityGrant.maxCostUnits  grant ceiling — tool layer, before invocation
              └── ModelRequest budget      call ceiling — model gateway
```

Each level is enforced by the component that owns it, at the moment before spend is committed
rather than after it is observed. Enforcement after the fact reports an overrun; it does not
prevent one.

A run budget is **required**. `GraphRun` cannot be created without `budget.maxCostUnits` and
`currency`. A default may come from the graph, the repository registry or platform configuration,
but the resolved value is stored on the run, because a budget that lives in configuration is a
budget that changes underneath a suspended run.

Inner budgets are optional and are clamped, never trusted: an effective ceiling is
`min(declared, remaining at the enclosing level)`. A node declaring 500 units in a run with 40
remaining gets 40. A grant cannot exceed its node, and a node cannot exceed its run. This makes
the nesting a genuine containment rather than four independent numbers that happen to be written
near each other.

### 4. Spend is accumulated on the run, transactionally with the record that caused it

`GraphRun.consumedCostUnits` is a monotonically non-decreasing integer, updated in the same
transactional batch as the `ModelResponse` or `ToolResult` that incurred the cost, under the same
optimistic concurrency as the rest of the run document (ADR-0008 §10).

Batching it with the causing record is what makes the accumulator trustworthy across a crash. A
separate update can be lost, and a lost cost update is spend the platform believes did not happen.

Retries accumulate. An attempt that fails after calling a model spent that money, and a budget
that forgives failed attempts under-counts exactly the runs that are going wrong. This is why
ADR-0021 keeps every attempt's records: retry spend is measurable rather than absorbed.

### 5. Exhaustion suspends, and does not fail

When a run's remaining budget cannot cover the next dispatch, the graph engine suspends the run
with `BUDGET_EXCEEDED` rather than failing it.

Suspension is correct because the condition is externally resolvable: a human can raise the ceiling
and resume, and the completed work is preserved. Failing would discard checkpointed progress over a
condition an operator can fix in one command — the same reasoning as ADR-0025 §4 for approvals.

Raising a run budget is a consequential action: it is audited, attributed, and subject to approval
when it crosses the ceiling set by the repository registry. A budget any agent-adjacent code path
can raise is not a budget.

`BUDGET_EXCEEDED` is never retryable. Retrying a bound that was hit re-hits it.

### 6. Warning before exhaustion

The graph engine emits a warning event when consumption crosses 80% of the run ceiling. A local
developer who learns about the budget only when the run stops has already lost the run's
remaining work to a wait.

The threshold is fixed in V1. Making it configurable is a preference nobody has asked for.

---

## Consequences

Overnight spend is bounded by a number a developer sets and can see, which is the requirement
`PRINCIPLES.md` states.

Integer micro-units make budget arithmetic exact and satisfy ADR-0020's integers-only rule for
hashed documents. The cost of this is a conversion at the gateway boundary and a rounding rule that
must round up; rounding down would let a long run drift under its true spend.

`GraphRun` gains `budget`, `currency` and `consumedCostUnits`. `maxCostUnits` becomes integer
micro-units everywhere it already appears — a semantic change to existing fields, not a new
mechanism.

The clamping rule in §3 means a declared node budget is an upper bound rather than an allocation. A
node may receive less than it asks for, and its failure message must say so, otherwise the
developer debugs the wrong thing.

Multi-currency provider mixes are unavailable. Acceptable while providers are Anthropic and OpenAI;
worth revisiting if a provider bills in another currency, which would need a new decision rather
than a silent conversion.

---

## Alternatives considered

**Provider-neutral credits.** Rejected. A credit is a currency amount with a conversion table
attached, and the table goes stale without anyone noticing. Money is already provider-neutral.

**Decimal or floating-point currency.** Rejected. ADR-0020 bans non-integers from hashed documents
because of cross-language number formatting, and float accumulation makes a spending limit
approximate.

**Per-node budgets only (status quo).** Rejected in §3. Bounded parts do not compose into a bounded
whole unless something computes the whole.

**Fail rather than suspend on exhaustion.** Rejected in §5. Discards recoverable progress over an
operator-fixable condition.

**Enforce after observing spend.** Rejected. Detecting an overrun is not preventing one, and the
gap is exactly one unbounded call wide.
