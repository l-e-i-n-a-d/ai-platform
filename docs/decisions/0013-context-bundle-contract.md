# ADR-0013: Context Bundle Contract, Budgets and Provenance

## Status

Accepted — 2026-08-15

Consumes `contextPolicy` and instruction-file semantics from ADR-0014 §4/§6. Delivered to the
agent runtime by reference under ADR-0004 §5. Persisted under ADR-0007 (pointer in operational
state, content in the artifact store). Enables the evaluation capability described in
`EVALUATION.md`.

---

## Context

Context quality is the dominant determinant of whether an agent succeeds. It is also the part
of the system the platform most needs to *measure*, because when a run goes wrong the first
question is always "what did the model actually know?"

The existing documentation states that context should be "relevance-driven and traceable" and
that the platform "should eventually be able to explain why a particular piece of context was
supplied to an agent." Nothing defines what a context bundle *is*, how it is bounded, or what
is recorded about it. Aspiration without a representation produces the usual outcome: context
assembled ad hoc inside prompt-building code, invisible, unmeasurable and unreproducible.

Three specific problems must be resolved before implementation.

**Provenance and budget.** Without a bundle representation, "why did the agent do that?" is
unanswerable. Token budgets end up enforced implicitly by whatever truncates first, which is
the worst possible eviction policy because it silently discards the tail — often the task
description.

**Permission amplification.** Removing central identity has a consequence that is easy to
overlook. If the platform retrieves Jira, Confluence and GitHub content using one broadly
privileged service account, then any developer can obtain, through an agent, content they
cannot open themselves: restricted Confluence spaces, private repositories, restricted Jira
projects. The platform becomes a permission-laundering channel, and the audit trail in the
source system shows the service account rather than the person who asked. This is a compliance
problem, not only a technical one.

**Pinning.** A run may pause overnight for approval. If its context was gathered when `main`
was at commit X and `main` has since advanced, the agent resumes acting on an understanding
that no longer holds — while everything about the run looks consistent. Unpinned context also
makes evaluation irreproducible, since two runs of the same task are not comparable if their
inputs differed.

---

## Decision

### 1. The context bundle is a first-class, immutable, content-addressed artifact

Context is not a string assembled inside a prompt builder. It is a named artifact with a
schema, produced by the context engine in the control plane, stored in the artifact store, and
referenced by hash.

```text
contextBundleRef = sha256(canonical serialization of the bundle)
```

A bundle is immutable once created. Refreshing context produces a **new** bundle with a new
ref and a `supersedes` link; it never mutates an existing one. Every agent execution record
names the exact bundle ref it was given.

Immutability and content addressing are what make the bundle useful beyond the run: evaluation
can hold context constant while varying the model, and two runs that produced different
outcomes can be compared by first checking whether their inputs were even the same.

### 2. Bundle structure

```text
bundleRef            content hash
runId, nodeId        what it was assembled for
createdAt
supersedes           previous bundleRef, if this is a refresh

budget {
  limit              token budget for this bundle
  used
  policyId           which budget policy produced it
}

pins {
  repositories[]     { repositoryId, ref, commitSha }
  issues[]           { key, versionOrUpdatedAt }
  pages[]            { pageId, version }
}

items[] {
  itemId
  sourceSystem       REPOSITORY | JIRA | CONFLUENCE | GITHUB | PLATFORM | RUN_STATE
  sourceId           path, issue key, page id, PR number, prior node id
  revision           commit SHA, page version, issue updated-at
  retrievedAt
  retrievedAs        acting identity (§4)
  strategy           how it was found: DIRECT | PATH_MATCH | SEARCH | LINK_TRAVERSAL | GRAPH_STATE
  relevanceScore     comparable within a bundle only
  tokenCount
  inclusionReason    short, human-readable, machine-recorded
  trustClass         PLATFORM | UNTRUSTED  (§5)
  contentRef         artifact-store pointer for the item body
}

excluded[] {
  sourceId, reason   EVICTED_BUDGET | POLICY_EXCLUDED | ACCESS_DENIED | STALE
  tokenCount
}
```

The `excluded` list is not bookkeeping. Knowing what was *nearly* included, and why it was not,
is usually more diagnostic than the included list — it is how you discover that the file the
agent needed was dropped by a budget policy or an `excludePaths` rule.

### 3. Budgets are explicit and eviction is deterministic

Every bundle has a token budget derived from the model's context window, the node's
configuration and `contextPolicy.maxContextBudget` from the repository registry. As with
capabilities, the **minimum** of the applicable limits wins.

Items are assigned tiers, and eviction proceeds strictly from the lowest tier upward:

| Tier | Content | Evictable |
|---|---|---|
| 0 | task definition, objective, output contract, platform instructions | never — if tier 0 does not fit, the node fails `BUDGET_EXCEEDED` |
| 1 | acceptance criteria, prior failure output in a repair loop, approved plan | only after tiers 2–3 are exhausted, and the eviction is recorded |
| 2 | primary subject matter: the files, issue and page directly named by the task | by relevance score, ascending |
| 3 | supporting material: neighbouring code, linked issues, related pages | by relevance score, ascending |

Truncating an individual item is permitted only for tier 2 and 3 items, must be marked in the
item, and must cut at a structural boundary rather than mid-token-stream. Silent truncation is
forbidden: an evicted or truncated item always appears in the bundle record.

`BUDGET_EXCEEDED` at tier 0 is a design failure, not a runtime condition to retry. It means a
node was defined that cannot fit its own task.

### 4. Retrieval uses the developer's own credentials

Context retrieval from Jira, Confluence and GitHub authenticates as **the developer running
the platform**, using their personal token or OAuth grant. A broadly privileged shared service
account is forbidden for context retrieval.

This turns a limitation of local-first into a genuine control: retrieved context is bounded by
entitlements the organisation already manages, in systems that already have identity, and
access appears in those systems' own audit logs under the right name. The platform inherits
correct authorization without building any.

Consequences that follow, and are accepted:

- Two developers running the same graph against the same task may receive different context.
  This is correct behaviour, and it is recorded: `retrievedAs` on every item makes the
  difference visible rather than mysterious.
- `ACCESS_DENIED` is a normal, recorded outcome. It is never escalated by retrying with a more
  privileged credential.
- Where the platform must act with its own identity — opening a pull request under a GitHub App
  (ADR-0012) — that identity is used for the *action*, never to widen *retrieval*.

Delegated permissions become a first-class requirement if the platform is ever centrally
hosted, and that is a Phase 7 decision, not something to approximate now.

### 5. Every item carries a trust class, and untrusted content is structurally delimited

Two classes only:

- `PLATFORM` — platform-authored instructions, the task definition, the output contract.
- `UNTRUSTED` — everything retrieved: repository files, issue and PR bodies, comments,
  Confluence pages, CI output, and repository-resident instruction files (ADR-0014 §6).

Untrusted content is rendered into the prompt inside explicit delimiters, labelled with its
source and revision, and is never concatenated into the instruction region. The distinction
between instructions and data is maintained in the bundle so that it can be maintained in the
prompt — a bundle that has already flattened everything into one string makes prompt-level
separation impossible.

Repository instruction files are a deliberate and important case: they are included because
they are useful, and they are `UNTRUSTED` because they are writable by anyone who can open a
pull request.

### 6. Context is pinned for the life of the run

At run start, each repository in scope is pinned to a concrete commit SHA, and that SHA is
recorded on the run. Every subsequent retrieval within that run reads the pinned revision.
Jira issues and Confluence pages record the version identifier observed at retrieval.

Moving a pin requires an explicit refresh operation, which:

- produces a new bundle that `supersedes` the previous one
- records the revision delta
- invalidates any approval whose subject was derived from the superseded context, because an
  approval that was given against one view of the world must not authorize action against
  another (ADR-0009 §4)

Pinning is also what makes the reconstructibility invariant in ADR-0003 hold end to end: the
workspace is a function of `(repoRef, baseSHA, patches)` and the context is a function of the
same `baseSHA`.

### 7. Retrieval results are cached by `(sourceSystem, sourceId, revision, actingIdentity)`

Including the acting identity in the cache key is not optional. A cache keyed only by source
and revision would serve one developer's privileged retrieval to another, reintroducing exactly
the permission amplification §4 exists to prevent.

Because revision is part of the key, entries never need invalidating — a new revision is simply
a different key.

### 8. The context engine lives in the control plane

Retrieval, ranking, budgeting, redaction, pinning and provenance recording are control-plane
responsibilities. The agent runtime receives `contextBundleRef` and fetches the assembled
bundle; it never queries Jira, Confluence or GitHub itself.

This follows directly from ADR-0004 §4 — the runtime's only network peer is the control plane —
and it keeps one integration layer, one redaction point and one place where provenance is
recorded.

### 9. V1 retrieval is deliberately unsophisticated

V1 uses lexical and structural retrieval: path and glob matching from `contextPolicy`,
repository search, symbol and reference lookup, direct fetch of named issues and pages, and
link traversal from the task. Relevance scores are computed from explainable signals — path
proximity, recency, explicit linkage, search rank.

No embedding index, vector store or semantic retrieval in V1. The bundle contract is
deliberately agnostic to *how* an item was found, so a semantic retriever can be added later as
another `strategy` value without changing anything downstream. Building a retrieval index
before there are runs to measure it against optimises a system nobody has observed failing.

---

## Alternatives Considered

**Assemble context inside the agent runtime.** Simplest to write, and it is what most agent
frameworks do. Rejected: it puts integration credentials in the runtime, contradicts ADR-0004,
duplicates the redaction point, and makes provenance a matter of runtime logging rather than a
durable record.

**Shared service account for retrieval.** Operationally simpler, uniform behaviour across
developers, no per-developer credential setup. Rejected: it silently creates a permission
amplification channel and misattributes access in the source systems' audit logs. The
convenience is real; the risk is unacceptable and it is precisely the kind of thing that is
never revisited once shipped.

**Inline the bundle in the agent request.** Avoids a round trip. Rejected: bundles are large,
request payloads become unloggable, and content addressing — the property evaluation depends
on — is lost.

**Vector store / embedding index in V1.** Fashionable and genuinely useful at scale. Rejected
for V1 as speculative infrastructure: it adds a component, an index lifecycle and an
embedding-model dependency before the platform can demonstrate that lexical retrieval is the
binding constraint. The contract keeps the door open.

**Re-retrieve context per node without pinning.** Always current. Rejected: irreproducible,
expensive, and it lets the world shift underneath a paused run.

---

## Consequences

**Positive**

- "Why did the agent do that?" is answerable from durable records, not from log archaeology.
- Context becomes measurable, so context strategy becomes improvable — the precondition for
  evaluating a harness rather than a model.
- Retrieval authorization is inherited from systems that already have identity, at no cost.
- Bundles are replayable, so evaluation can vary one factor at a time.
- Budget failures are explicit and attributable rather than emerging as mysterious truncation.

**Negative**

- Every developer must configure personal credentials for Jira, Confluence and GitHub. This is
  real developer-experience friction and is accepted deliberately (ADR-0018 covers `aip doctor`
  surfacing it clearly).
- Context differs between developers, which complicates reproducing a colleague's run. The
  bundle record makes the difference diagnosable, not absent.
- Bundle assembly is more work than string concatenation, and the artifact store grows.
- Retention and redaction of bundles containing sensitive retrieved content is an open
  obligation, deferred to ADR-0017.

---

## Security Notes

- §4 is the control against permission amplification. Any future proposal for a shared
  retrieval service account must be treated as a security change requiring an ADR.
- §5 maintains the instruction/data separation that ADR-0005 and ADR-0014 depend on. A bundle
  that loses trust classes silently disarms both.
- `contextPolicy.excludePaths` is a secret-exposure control as much as a relevance control
  (ADR-0014 §11): it is what keeps `.env` files, key material and vendored trees out of
  prompts. Exclusions are enforced during retrieval, not during rendering.
- Bundles are durable copies of potentially sensitive content and inherit the artifact store's
  access controls. They must never be shared between developers in V1.
- Recording `retrievedAs` per item is what makes an after-the-fact access review possible.

---

## Follow-up

- Rewrite `docs/architecture/context-engine.md` with the bundle contract, tiers and pinning.
- Add the context bundle schema to the Phase 1 contract set in `ROADMAP.md`.
- Update `.github/copilot-instructions.md` §11 with the bundle, trust classes and the
  developer-credential rule.
- Update `SECURITY.md` §5 to state the retrieval-credential rule explicitly.
- Update `EVALUATION.md` to reference bundle refs as the mechanism for holding context constant.
- ADR-0012 — GitHub App identity, which must not be used to widen retrieval.
- ADR-0017 — retention and redaction of context bundles.
