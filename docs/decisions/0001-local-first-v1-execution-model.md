# ADR-0001: Local-First V1 Execution Model

## Status

Accepted — 2026-08-15

Recorded retrospectively. This decision predates the ADR process and is the premise of
ADR-0003, ADR-0006, ADR-0007, ADR-0009, ADR-0011, ADR-0013, ADR-0016, ADR-0017 and ADR-0018.

---

## Context

An AI engineering platform of this shape is normally built as a hosted service: a cluster runs
the control plane, workloads execute in Kubernetes, state lives in a managed database, and
developers interact through a web UI. That is the architecture most reference material assumes,
and it is where this platform will probably end up.

Starting there would have been a mistake, and the reasons are worth recording because the
pressure to skip ahead will recur.

The platform is unproven. Nobody on the team yet knows which graph shapes work, how often
repair loops converge, how much context an agent actually needs, or where the failure modes
concentrate. Building shared infrastructure first means committing to answers before the
questions are understood, and infrastructure is the most expensive thing to be wrong about.

Hosted execution also front-loads the hardest problems for no immediate return: identity,
tenancy, cluster operations, network policy, secret distribution, shared-state concurrency. Each
is real work that produces no engineering capability, and each is easier to solve later against
observed requirements than earlier against imagined ones.

There is a third factor specific to this domain. The platform's purpose is to help engineers,
and the tightest feedback loop available is a developer running it on the machine where they
already work, against repositories they already have, with credentials they already hold.

---

## Decision

**V1 runs entirely on a developer's machine.**

Every team member can clone the repository, configure credentials, and execute a complete
engineering workflow without a cloud account, a cluster, or a shared service.

### What this means concretely

- The control plane and agent runtime are local processes started by a CLI (ADR-0018).
- Durable state is an embedded store on the developer's machine (ADR-0007).
- Artifacts are local files (ADR-0007, ADR-0017).
- Execution happens in local containers (ADR-0006).
- Credentials are the developer's own, held locally (ADR-0011, ADR-0013).
- Audit and approvals are local and developer-attested (ADR-0016, ADR-0009).

### What it does not mean

Local-first is **not** an excuse for weaker architecture. Three rules follow, and they are the
reason this decision is safe rather than merely convenient:

1. **Workflow semantics must not depend on the execution environment.** Graphs and agents are
   written against an execution interface, never against local execution (ADR-0003).
2. **No storage SDK type crosses the persistence port.** The local store is an adapter, not the
   model (ADR-0007).
3. **Security is not relaxed.** Removing central identity removes an *assurance mechanism*, not
   a *requirement*, and each affected control states its honest limits rather than pretending
   the limit does not exist.

Every one of those rules exists so that the hosted future stays reachable without a rewrite.

### The V1 exit condition

A developer runs a real engineering workflow — Jira issue to pull request, with verification and
repair — locally, observably and reproducibly. Until that works, no amount of shared
infrastructure would help.

---

## Alternatives Considered

**Hosted-first on AKS.** The eventual destination, and building there directly avoids a
migration. Rejected: it front-loads identity, tenancy and cluster operations before the platform
has demonstrated it does anything useful, and it makes every experiment slow. It also makes the
team's first hard problems infrastructural rather than architectural, which is precisely
backwards for an unproven system.

**Hybrid — local execution against shared cloud state.** Superficially attractive: developers
run workloads locally, everyone sees the same runs. Rejected after analysis, and this is the
alternative that looked most reasonable until examined. A shared Cosmos DB without Entra ID
offers only account keys, so every laptop would hold a root-equivalent credential over all
runs, approvals and audit records for the whole team. The shared store would *look* more
authoritative while being strictly less trustworthy than a local one (ADR-0007, ADR-0016 §7).

**Local-only with no hosted ambition.** Simpler still, and it would justify skipping the
execution interface, the persistence port and much of the state model. Rejected: the platform is
intended to become a shared capability, and those abstractions are cheap now and expensive to
retrofit.

**Devcontainer or VM as the unit of isolation instead of the developer's machine.** Considered
and partially adopted — workspace containers are the execution boundary (ADR-0006). Rejected as
the *platform* boundary, because requiring developers to work inside a prescribed environment
adds friction to the thing this decision optimises for.

---

## Consequences

**Positive**

- A developer can be productive on day one, with no infrastructure to provision.
- Experiments are cheap, so architecture can be corrected by evidence.
- Retrieval and action inherit the developer's existing entitlements, which solves authorization
  without building any (ADR-0013 §4).
- Blast radius is one machine.
- The hosted migration remains a deployment change, because the abstractions that matter were
  drawn from the start.

**Negative**

- No shared visibility: runs, audit and artifacts are per-developer, and a team-wide view
  requires collecting exports.
- Onboarding requires local prerequisites — container runtime, toolchains, credentials, a GitHub
  App — which is real friction that `aip doctor` must make survivable.
- Behaviour can vary across machines, so "works on mine" is a genuine risk that container-based
  execution only partly mitigates.
- Long-running workflows are bounded by a laptop being awake.
- Some capabilities — adversarial-grade audit, cross-developer approval, shared evaluation
  history — are simply out of reach until the hosted decision is made.

---

## Security Notes

- Local execution is privileged: the platform runs with the developer's own authority, which is
  why command execution is containerised, credential-free and default-deny (ADR-0006).
- Removing central identity weakens *attribution*, and every control that depends on identity
  states its assurance honestly rather than overclaiming (ADR-0009, ADR-0016).
- One developer's compromise exposes one developer's credentials and state, not the
  organisation's.
- The platform holds high-value secrets locally — model keys, a GitHub App token — and their
  handling is correspondingly strict (ADR-0011, ADR-0012).

---

## Follow-up

- ADR-0003 — the execution interface that keeps this reversible.
- ADR-0018 — the CLI as the V1 entry surface.
- Phase 7 in `ROADMAP.md` — the hosted decision, which must be explicit rather than gradual.
