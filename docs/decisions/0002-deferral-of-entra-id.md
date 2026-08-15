# ADR-0002: Deferral of Microsoft Entra ID

## Status

Accepted — 2026-08-15

Recorded retrospectively. Follows from ADR-0001. Constrains ADR-0007, ADR-0009, ADR-0012,
ADR-0013 and ADR-0016, each of which had to be designed around the absence of central identity.

---

## Context

The organisation uses Microsoft Azure, and Entra ID is the natural identity provider. Making it
a V1 requirement would have been the default choice, and it was deliberately not taken.

The reason is that Entra ID solves a problem V1 does not have. Central identity exists to
answer "who is this, across a shared system." In V1 there is no shared system: each developer
runs their own platform instance, against their own credentials, on their own machine
(ADR-0001). The only user of a given instance is the person who started it.

Requiring Entra ID anyway would mean app registrations, tenant configuration, redirect URIs,
token acquisition and refresh, and a login flow — all before a developer can run anything, and
all to authenticate a user to their own laptop.

But deferral has a consequence that must be stated rather than discovered: **several controls
in this architecture would be materially stronger with authenticated identity, and they are
weaker without it.** The honest position is not that identity is unnecessary, but that its
absence is affordable at V1 scope and its cost is written down.

---

## Decision

**Microsoft Entra ID is not a V1 requirement, and no substitute identity system is built.**

The platform does not invent local accounts, tokens, roles or a login flow. Building a
home-grown identity system would deliver the complexity of identity with none of the assurance —
the worst available trade.

### Where identity is genuinely needed, it is borrowed

The platform uses identity from systems that already have it, rather than asserting its own:

| Need | Borrowed from |
|---|---|
| Who may read this Jira issue or Confluence page | the developer's own credentials (ADR-0013 §4) |
| Who approved a consequential action | GitHub review or Jira transition (ADR-0009 §2) |
| Who performed a repository action | GitHub App installation (ADR-0012 §1) |
| Externally verifiable evidence | GitHub and Jira audit logs (ADR-0016 §6) |

This is the load-bearing idea of the whole decision. Rather than approximating identity, the
platform delegates to systems whose identity is real, and records which system provided the
assurance.

### Where identity is missing, the limit is stated

Three controls are explicitly weaker, and each says so in its own document:

- **Approvals** — `LOCAL_OPERATOR_CONSENT` proves the terminal operator consented. It is
  operator consent, not segregation of duties (ADR-0009 §5).
- **Audit** — attribution to a local OS username is self-asserted. V1 audit is
  developer-attested, not adversarial-grade (ADR-0016 §4).
- **State and artifacts** — per-developer and local, because a shared store without identity is
  less trustworthy than a local one while appearing more authoritative (ADR-0007, ADR-0017 §6).

Stating limits is a design requirement, not documentation hygiene. A control believed stronger
than it is causes more harm than a control known to be weak.

### The trigger for revisiting

Entra ID becomes necessary when **any** of the following becomes true:

1. the control plane is centrally hosted and serves more than one user
2. state, audit or approvals are shared across developers
3. an approval must be attributable to a specific person for compliance
4. audit must withstand adversarial examination
5. delegated permissions are required for retrieval on behalf of a user

Any one of these is sufficient. They are not independent — they tend to arrive together, as
Phase 7.

---

## Alternatives Considered

**Require Entra ID in V1.** Real identity from the start, and no retrofit later. Rejected: it
authenticates a developer to their own laptop, blocks onboarding behind tenant configuration,
and solves a sharing problem V1 does not have.

**Build a lightweight local identity system.** Local accounts and roles, small and
self-contained. Rejected firmly: identity built by an application, with a credential store on the
same machine as its subject, provides no assurance while adding a login flow, a permission model
and a credential lifecycle. It would also make the weakness *invisible*, which is worse than the
weakness itself.

**Use OS user identity as authoritative.** Free and already present. Rejected as authoritative,
accepted as a recorded fact: it is self-asserted and trivially changed, so it is recorded at
`SELF_ASSERTED` assurance and never treated as proof.

**Use GitHub identity as the platform's identity provider.** Every developer already has one,
and the platform already integrates. Genuinely tempting, and partially adopted — GitHub is used
for external attestation and anchoring. Rejected as a general identity provider because it
would couple platform authentication to a code-hosting integration, and because it does not
cover the Jira, Confluence and local-execution surfaces.

**Defer identity silently, without recording the consequences.** The most common outcome in
practice. Rejected: the gap resurfaces later as an assumption someone has already relied on.

---

## Consequences

**Positive**

- Onboarding requires no tenant configuration or app registration.
- No login flow, token refresh or session handling in V1.
- Authorization for retrieval is inherited from systems that already enforce it correctly.
- No home-grown identity system to maintain, migrate or explain.
- The path to Entra ID is clean, because nothing competes with it.

**Negative**

- Approvals and audit have materially lower assurance, and the caveat must be repeated wherever
  they surface.
- No shared state, shared audit or cross-developer approval queues.
- Every developer manages their own credentials for every integration.
- Some compliance conversations cannot be had until the Phase 7 decision is made.
- Consistently stating assurance limits is ongoing discipline, and it is easy to let slide.

---

## Security Notes

- Deferring Entra ID removes an assurance mechanism, not a security requirement. Least
  privilege, capability grants, approval gating, egress control and audit all still apply.
- The absence of identity is the reason several controls are deliberately conservative:
  credential-free workspaces, developer-scoped retrieval, no shared stores, no standing
  approvals.
- No component may claim identity-backed assurance it does not have. Assurance tiers are
  recorded in the data, not merely described in prose.
- If the platform becomes hosted without revisiting this decision, several controls silently
  become misleading rather than merely weak. That is the failure mode this ADR exists to
  prevent.

---

## Follow-up

- ADR-0009, ADR-0012, ADR-0013, ADR-0016 — the four decisions shaped by this deferral.
- Phase 7 in `ROADMAP.md` — where identity, tenancy, hosted state and adversarial-grade audit
  are decided together.
