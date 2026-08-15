# ADR-0017: Artifact Classification, Retention and Redaction

## Status

Accepted — 2026-08-15

Completes ADR-0007 §3 (the artifact store) with content policy. Shares the redaction pipeline
with ADR-0011 §6. Retention of audit records is constrained by ADR-0016 §1.

---

## Context

"Blob Storage is used for large artifacts" was the entire specification. Container layout,
pointer contract, size threshold, retention, encryption and — most importantly — content
sensitivity were all undefined.

What actually accumulates there is not neutral. Model transcripts, prompts and completions, full
diffs and patch series, build and CI logs, context bundles, evaluation outputs. In aggregate this
is a growing, unclassified copy of the organisation's source code and of every AI interaction
about it, sitting on developer laptops with no expiry.

Transcripts and build logs are the hazardous cases. A build log routinely echoes a token. A
context bundle may contain a `.env` that slipped past an exclusion rule. Once written, that
content persists long after the run that produced it, and it is exactly the material a developer
would later copy into an issue to ask for help.

There is also a durability trap. ADR-0008 makes runs resumable and ADR-0003 makes workspaces
reconstructible from `(repoRef, baseSHA, patch series)`. Both depend on artifacts still existing.
A retention policy written without that in mind will silently break resume, and it will break it
for exactly the long-paused runs that most need to resume.

---

## Decision

### 1. Every artifact is classified on write

```text
artifactType     TRANSCRIPT | PROMPT | COMPLETION | CONTEXT_BUNDLE | PATCH
                 BUILD_LOG | CI_LOG | TOOL_OUTPUT | EVALUATION | REPORT | AUDIT_EXPORT
sensitivity      PUBLIC | INTERNAL | SENSITIVE
provenance       PLATFORM_GENERATED | RETRIEVED | EXECUTED_OUTPUT | MODEL_OUTPUT
redacted         whether the redaction pass modified it
retentionTier    §4
```

Classification happens at write time, by the component that produces the artifact. Classifying
later is guesswork, and unclassified data defaults to being kept forever by accident.

`sensitivity` defaults to `INTERNAL` and is raised, never lowered, by any contributing input. A
bundle containing one `SENSITIVE` item is `SENSITIVE`.

### 2. The pointer contract

```text
ArtifactRef {
  uri
  sha256
  sizeBytes
  contentType
  encoding
  classification    §1
  createdAt
  expiresAt
}
```

Operational state holds refs; content lives in the artifact store (ADR-0007). Any payload above
**100 KB** is offloaded. Content addressing gives deduplication and integrity checking for free,
and makes a reference stable regardless of where the store is backed.

Layout is content-addressed with a logical index:

```text
content:  <sha256[0:2]>/<sha256>
index:    <runId>/<nodeId>/<artifactType>/<invocationId> -> sha256
```

Content addressing deduplicates the large repeated payloads — the same repository file appearing
in twenty bundles is stored once. The index makes "everything this run produced" answerable
without scanning.

### 3. Redaction runs before persistence, not after

The ADR-0011 §6 pipeline — credential patterns, entropy heuristics, configured deny-lists —
applies to every artifact **before it is written**, not to what is displayed later.

One implementation, three call sites: model egress, artifact persistence, log emission. Three
implementations would drift, and the one that drifted would be discovered by a leak.

Redaction is fail-closed: if the pipeline errors, the write fails and the action fails with it.
A match redacts, records the event and proceeds, and sets `redacted: true` on the artifact.

The redaction event counts toward `platform_redactions_total`. A rising rate means upstream
controls are leaking, not that redaction is working well.

### 4. Retention tiers

| Tier | Artifacts | Default | Rule |
|---|---|---|---|
| `EPHEMERAL` | tool output, build logs of successful runs | 7 days | freely deleted |
| `RUN_LIFECYCLE` | transcripts, prompts, completions, context bundles, CI logs | 30 days **or until the run reaches a terminal state, whichever is later** | never deleted while a run can still resume |
| `REPRODUCIBILITY` | patch series, evaluation inputs and outputs, replay cassettes | 180 days | needed to reproduce a result |
| `AUDIT` | audit exports, approval renderings, artifacts referenced by audit entries | 400 days, independent | immutable; never deleted by a retention sweep alone |

The `RUN_LIFECYCLE` rule matters more than its dry wording suggests. A run paused awaiting
approval for six weeks must still be resumable, so **retention is bounded by run state, not by
wall-clock age alone**. Deleting an artifact a live run depends on turns a resumable run into an
unrecoverable one — a self-inflicted durability failure that a naive time-based sweep would cause
routinely.

Audit-relevant artifacts are immutable and outlive the runs that produced them, because the
record of what was approved must survive the run being cleaned up.

### 5. Deletion is reference-aware and recorded

Before deleting, the store checks that no live run, no audit entry and no retained evaluation
references the artifact. Content-addressed storage means one artifact may have many referents.

Deletions are recorded: what was deleted, when, under which policy. A store that silently loses
data cannot be debugged, and "it must have been retention" is not an answer.

`aip artifacts prune --dry-run` shows what a sweep would remove before it removes it.

### 6. Artifacts are local and per-developer in V1

Artifacts live under the platform's local directory, inheriting the developer's filesystem
permissions. There is no shared artifact store, for the same reason there is no shared audit
store (ADR-0016 §7): sharing without identity means every developer can read and alter every
other developer's transcripts, and those transcripts contain source code and possibly secrets.

Encryption at rest is delegated to the operating system's full-disk encryption. Adding an
application-layer encryption scheme whose key sits beside the data on the same laptop would add
complexity and no meaningful protection.

If the platform is ever hosted, artifact storage becomes Azure Blob Storage with its own access
control, and the classification and retention tiers defined here carry over unchanged. That is
the point of classifying now.

### 7. Sharing an artifact is an explicit, classified action

Exporting or sharing a transcript requires an explicit command, shows the classification, and is
recorded. `SENSITIVE` artifacts warn before export.

The realistic disclosure path in a local-first platform is not an attacker — it is a developer
pasting a transcript into an issue to ask for help. Making classification visible at the moment
of export is the only control that addresses it.

---

## Alternatives Considered

**Keep everything indefinitely.** Simplest, and nothing needed is ever missing. Rejected: an
unbounded, unclassified store of source code and AI interactions on every laptop is a liability
that grows without anyone deciding to accept it.

**Pure time-based retention.** Trivial to implement. Rejected: it deletes artifacts that live
runs depend on and silently breaks resume, hitting hardest the long-paused runs that most need
it.

**Redact on read instead of on write.** Preserves fidelity for debugging. Rejected: the
sensitive content is then durably stored and only conditionally hidden, which is a filter rather
than a control.

**Application-layer encryption at rest in V1.** Sounds stronger. Rejected: the key lives on the
same machine as the data, so it adds key management and roughly nothing else. OS full-disk
encryption is the honest answer.

**A shared team artifact store.** Better collaboration and one place to look. Rejected: without
identity every developer could read every other developer's transcripts, which contain source
code and possibly secrets.

**No classification, apply one policy to everything.** Less metadata. Rejected: a single policy
is either too aggressive for reproducibility artifacts or too lax for transcripts, and there is
no setting that is right for both.

---

## Consequences

**Positive**

- The store stops growing without bound, and what it holds is known rather than assumed.
- Resume and reproducibility are protected by policy rather than by luck.
- One redaction pipeline covers egress, persistence and logs.
- Classification is recorded at write time, so a future hosted deployment inherits a usable
  policy instead of an archaeology project.
- The realistic disclosure path — a developer sharing a transcript — has a control on it.

**Negative**

- Classification is metadata every producing component must set correctly, and a wrong
  classification is silent.
- Reference-aware deletion is more complex than a timestamp sweep.
- Redaction on write means the original is unrecoverable, which will occasionally frustrate
  debugging.
- Retention windows are guesses and will need adjusting once real usage exists.
- No shared store means no easy team-wide view of past runs.

---

## Security Notes

- Redaction is fail-closed on error and applies before persistence, never only on display.
- Transcripts, prompts, completions and CI logs are `SENSITIVE` by default. Reclassifying
  downward requires a deliberate act.
- Artifacts referenced by audit entries are immutable and cannot be removed by a retention sweep
  (ADR-0016 §1).
- Replay cassettes contain full prompts and completions and are `REPRODUCIBILITY` tier —
  long-lived, and therefore a deliberate retention decision rather than an oversight.
- Encryption at rest is the operating system's responsibility in V1, and this is a stated
  limitation rather than an omission.
- Export of `SENSITIVE` artifacts is warned and recorded.

---

## Follow-up

- Add the classification, pointer contract and retention tiers to
  `docs/architecture/persistence.md`.
- Update `SECURITY.md` with the artifact classification and export rules.
- Add `aip artifacts prune` and `aip artifacts export` to
  `docs/architecture/developer-experience.md`.
- Add `platform_artifact_bytes{tier}` and `platform_artifacts_pruned_total{tier}` to the metric
  catalogue.
