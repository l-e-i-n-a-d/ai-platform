# ADR-0016: Audit Model and Attribution Limits Without Central Identity

## Status

Accepted — 2026-08-15

Separates audit from the telemetry defined in ADR-0015 §10. Consumes the identity triple from
ADR-0009 (approvals), ADR-0012 (GitHub App) and ADR-0013 §4 (retrieval identity). Retention is
ADR-0017.

---

## Context

The platform requires that "every meaningful consequential action should be attributable to a
user, run, agent, graph and tool."

Four of those five are solved. `runId`, `agentId`, `graphId` and tool identity are all generated
and controlled by the platform. **"User" is not.** Without central identity, the acting user is a
local OS username on the machine that ran the platform — self-asserted, trivially changed, and
recorded by software running with that user's privileges into a store that user can write
directly.

An audit trail whose subjects can forge it is not an audit trail. That matters precisely in the
situations audit exists for: investigating an incident, or establishing what an agent did before
a bad merge landed.

The tempting responses are both wrong. Declaring the audit trail authoritative anyway produces a
control that looks real and fails under examination — worse than no control, because people rely
on it. Abandoning audit entirely discards genuinely valuable capability: the overwhelming
majority of audit use is reconstructing what happened, not resisting an adversary.

There is also a quieter risk. ADR-0015 defines rich telemetry, and telemetry is easy to mistake
for audit. Telemetry is sampled, dropped when a collector is down, and expired by retention
policy. If audit requirements are satisfied by log lines, the record will be missing exactly
when it is needed.

---

## Decision

### 1. Audit is a separate, durable, append-only record — never telemetry

| | Audit | Telemetry |
|---|---|---|
| Completeness | complete; a write failure fails the action | best-effort |
| Sampling | never | permitted |
| Mutability | append-only, never updated or deleted in place | freely expired |
| Retention | independent, long | short |
| Availability | required to proceed | optional |

If the audit record cannot be written, the action does not happen. This is the ordinary
write-ahead intent rule from ADR-0005 §7 and ADR-0008 §12 stated from the audit side: intent is
recorded before the effect, outcome after, and an unmatched intent is `INDETERMINATE`.

Never satisfy an audit requirement with a log line.

### 2. What is audited

Consequential actions only. Audit is not a second event stream.

- every tool invocation with side-effect class `EXTERNAL_WRITE` or `IRREVERSIBLE`
- every capability grant minted, and every authorization **denial**
- every approval requested, granted, rejected, expired or revoked
- every state transition of a run, and every cancellation
- every external write to GitHub, Jira or Confluence
- every registry change, trust-level change and pinning change
- every use of an escape hatch — `unsafe-host-exec`, budget override, approval override
- every redaction failure

`READ` and `WORKSPACE_WRITE` invocations are telemetry, not audit. Auditing them would bury the
consequential records in noise, which is its own form of losing them.

Denials are audited as carefully as successes. A denied action is often the more interesting
record.

### 3. The audit record

```text
auditId
timestamp                monotonic sequence within the run
runId, nodeId, attempt
graphId, graphVersionHash
agentId
action                   what was attempted
subjectRef, subjectHash  what it was attempted against
sideEffectClass
capabilityGrantId
decision                 ALLOWED | DENIED | INDETERMINATE
reason
actor {
  localUser              self-asserted (§4)
  platformInstanceId
  externalIdentity       GitHub App installation, Jira account — where one applies
  initiatedBy            the developer who started the run
}
externalRef              PR number, commit SHA, issue key, page version
traceId, spanId
prevHash, entryHash      hash chain (§5)
```

`initiatedBy` and `actor.localUser` are distinct on purpose. The question asked after the fact
is almost never "which process wrote this" but "who asked for this."

### 4. Attribution is honestly labelled by assurance

Three tiers, recorded explicitly on each entry, never presented as equivalent:

| Tier | Source | Assurance |
|---|---|---|
| `SELF_ASSERTED` | local OS user, platform instance id | none against a motivated insider |
| `PLATFORM_ATTESTED` | run, node, grant, graph version, hashes | strong for reconstruction, forgeable by whoever controls the machine |
| `EXTERNALLY_VERIFIABLE` | GitHub App action, commit, PR, Jira transition | verifiable independently of the platform |

**V1 audit is developer-attested.** It is suitable for debugging, reconstruction, personal
accountability and process improvement. It is **not** adversarial-grade, and no document, report
or dashboard may imply otherwise.

Saying this plainly is the whole point. A team that knows the limit can decide when it matters;
a team that believes a forgeable log is authoritative will discover otherwise at the worst
possible moment.

### 5. Tamper-evidence, not tamper-proofing

Audit entries form a hash chain: each entry includes the hash of its predecessor within the run,
and the chain head is recorded on the run.

This does not prevent tampering — anyone with write access to the store can rewrite the chain.
It makes *silent selective* tampering impractical: removing or altering one entry invalidates
everything after it, so the cheap attack (deleting one embarrassing line) stops working.

An integrity check verifies chains and reports breaks. Cost is one hash per entry; the honest
description is "tamper-evident within a chain," and it must be described that way rather than as
integrity protection.

### 6. High-consequence actions are anchored in systems that have identity

Where an action touches an external system, the platform writes corroborating evidence there:

- commits carry `AI-Platform-Run: <runId>` and the developer trailer (ADR-0012 §3)
- pull request bodies carry run, graph version, work item and context bundle ref
- Jira comments carry the run id

GitHub and Jira have authenticated identity, their own audit logs, and are outside the
developer's control. The platform's own record becomes checkable against a record its subject
cannot rewrite.

This is the same move as `EXTERNAL_ATTESTATION` in ADR-0009: the platform does not build identity
it does not have, it borrows identity from systems that do.

### 7. Audit is local and per-developer in V1

Audit records live in the developer's own store. There is no shared audit database, because a
shared store without identity is worse than a local one: every developer could write and alter
every other developer's records, and the shared store would *look* authoritative while being
less trustworthy than the local one it replaced.

Audit export produces a signed-by-nobody but self-consistent bundle — entries plus chain heads
plus referenced artifact hashes — sufficient for a developer to hand over what happened. Its
assurance tier is stated in the export.

### 8. Adversarial-grade audit requires the Phase 7 identity decision

Central identity, a hosted control plane and a tamper-resistant store are the same decision, and
it is deliberately deferred. This ADR records what is missing so it is chosen rather than
assumed:

- authenticated user identity
- an audit store the subject cannot write directly
- signing or an append-only service with independent retention

---

## Alternatives Considered

**Treat the existing structured logs as the audit trail.** Nothing extra to build. Rejected:
telemetry is sampled, lossy and expired, and will be missing exactly when needed.

**Declare V1 audit authoritative.** Simpler messaging, no caveats to explain. Rejected: it is
untrue, and a control believed to be strong is more dangerous than one known to be weak.

**Skip audit until identity exists.** Consistent with the honest assessment of assurance.
Rejected: it throws away the majority use case — reconstructing what happened — and retrofitting
audit means revisiting every side-effecting call site.

**Cryptographic signing with a local key.** Superficially stronger. Rejected: the key sits on the
same machine as the subject, so it proves possession of a file, not identity. It would buy the
appearance of assurance without the substance, which is the failure mode this ADR is built to
avoid.

**Shared audit database.** Team-wide visibility. Rejected: without identity every developer can
alter every record, and centralisation makes the weakness less visible.

**Audit everything, including reads.** Nothing missed. Rejected: consequential records drown in
volume, and audit that is too noisy to read has failed in a different way.

---

## Consequences

**Positive**

- Reconstruction — the dominant real use of audit — works well and immediately.
- Denials and escape-hatch use are first-class records, which is where security value lives.
- Hash chaining removes the cheapest form of tampering for one hash per entry.
- External anchoring gives genuinely verifiable evidence for the actions that matter most.
- The Phase 7 identity decision has an explicit, written trigger.

**Negative**

- V1 audit cannot support adversarial investigation, and the caveat must be repeated wherever
  audit is surfaced.
- Audit records are per-developer, so a team-wide view requires collecting exports.
- Audit writes are on the critical path, adding latency to every consequential action.
- Maintaining the audit/telemetry distinction requires discipline; the temptation to log and
  call it audited is constant.

---

## Security Notes

- Audit write failure blocks the action. Fail-closed, without exception.
- Audit entries are subject to the same redaction pipeline as artifacts and model egress; an
  audit record containing a leaked credential is still a disclosure (ADR-0011, ADR-0017).
- Audit retention is independent of telemetry retention and longer (ADR-0017).
- The assurance tier is part of the record, not a footnote in documentation. Tooling that
  displays audit must display the tier.
- `unsafe-host-exec`, budget overrides and approval overrides are audited unconditionally. Escape
  hatches that are not recorded are simply holes.

---

## Follow-up

- Create `docs/architecture/audit.md`.
- Update `SECURITY.md` §7 with the audit/telemetry split and the assurance tiers.
- Update `copilot-instructions.md` §18 to replace the unqualified attributability claim with the
  tiered model.
- Add `platform_audit_write_failures_total` to the metric catalogue.
- ADR-0017 — retention, which must treat audit records as a distinct tier.
