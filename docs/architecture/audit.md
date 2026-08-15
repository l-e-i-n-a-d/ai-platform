# Audit

**Status:** Planned (model agreed, not yet implemented)
**Location:** Control plane; written on the critical path of consequential actions
**Decisions:** [ADR-0016](../decisions/0016-audit-model-and-attribution-limits.md),
[ADR-0009](../decisions/0009-human-approval-model.md),
[ADR-0012](../decisions/0012-github-actor-identity-and-write-back.md)

---

## 1. Audit is not telemetry

| | Audit | Telemetry |
|---|---|---|
| Completeness | complete; write failure fails the action | best-effort |
| Sampling | never | permitted |
| Mutability | append-only | freely expired |
| Retention | independent, 400 days | short |
| Availability | required to proceed | optional |

Telemetry may be sampled, dropped when a collector is down, or expired. If an audit requirement
is satisfied by a log line, the record will be missing exactly when it is needed.

**Never satisfy an audit requirement with a log line.**

---

## 2. What is audited

Consequential actions only — audit is not a second event stream.

- tool invocations with side-effect class `EXTERNAL_WRITE` or `IRREVERSIBLE`
- capability grants minted, and every authorization **denial**
- approvals requested, granted, rejected, expired, revoked
- run state transitions and cancellations
- external writes to GitHub, Jira, Confluence
- registry, trust-level and pin changes
- every escape hatch: `unsafe-host-exec`, budget override, approval override
- redaction failures

`READ` and `WORKSPACE_WRITE` are telemetry. Auditing them buries the consequential records,
which is its own way of losing them.

Denials are audited as carefully as successes — often they are the more interesting record.

---

## 3. Record

```text
auditId, timestamp, runId, nodeId, attempt
graphId, graphVersionHash, agentId
action, subjectRef, subjectHash, sideEffectClass
capabilityGrantId
decision        ALLOWED | DENIED | INDETERMINATE
reason
actor {
  localUser, platformInstanceId, externalIdentity, initiatedBy
}
externalRef, traceId, spanId
prevHash, entryHash
```

`initiatedBy` is separate from `actor.localUser` deliberately. The question asked afterwards is
almost never "which process wrote this" but "who asked for this."

---

## 4. Assurance tiers

Recorded on every entry. Never presented as equivalent.

| Tier | Source | Assurance |
|---|---|---|
| `SELF_ASSERTED` | local OS user, instance id | none against a motivated insider |
| `PLATFORM_ATTESTED` | run, node, grant, graph version, hashes | strong for reconstruction; forgeable by whoever controls the machine |
| `EXTERNALLY_VERIFIABLE` | GitHub App action, commit, PR, Jira transition | verifiable independently of the platform |

**V1 audit is developer-attested.** Good for debugging, reconstruction, personal accountability
and process improvement. **Not** adversarial-grade.

No report, dashboard or document may imply otherwise. Tooling that displays audit must display
the tier.

---

## 5. Tamper-evidence

Entries form a hash chain within a run; the chain head is recorded on the run.

This does not prevent tampering — anyone with write access can rewrite the chain. It makes
*silent selective* tampering impractical: altering one entry invalidates every entry after it,
so deleting a single embarrassing line stops being cheap.

Describe it as "tamper-evident within a chain", never as integrity protection.

---

## 6. External anchoring

High-consequence actions leave corroborating evidence in systems that have real identity:

- commits carry `AI-Platform-Run: <runId>` and the developer trailer
- PR bodies carry run, graph version, work item, context bundle ref
- Jira comments carry the run id

GitHub and Jira are outside the developer's control and keep their own audit logs, so the
platform's record becomes checkable against one its subject cannot rewrite. Same move as
`EXTERNAL_ATTESTATION` for approvals: borrow identity rather than invent it.

---

## 7. Local, per developer

No shared audit database in V1. A shared store without identity is worse than a local one —
everyone could alter everyone's records, while looking more authoritative.

`aip audit export` produces a self-consistent bundle: entries, chain heads, referenced artifact
hashes, and the assurance tier stated plainly.

---

## 8. What Phase 7 must add

Adversarial-grade audit requires the identity decision, and needs all three:

- authenticated user identity
- an audit store the subject cannot write directly
- signing, or an append-only service with independent retention
