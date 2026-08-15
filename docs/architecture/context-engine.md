# Context Engine

**Status:** Planned (contract agreed, not yet implemented)
**Location:** Control plane (Java/Quarkus)
**Decisions:** [ADR-0013](../decisions/0013-context-bundle-contract.md),
[ADR-0014 §4/§6](../decisions/0014-repository-registry-and-instruction-precedence.md),
[ADR-0004 §5](../decisions/0004-control-plane-agent-runtime-boundary.md)

---

## 1. Responsibility

The context engine answers one question, repeatedly and on demand: *what should this node know?*

It is a service **called by** graph nodes and by the tool layer during a run — not a stage that
runs once before the graph. Context is assembled progressively as a run learns more.

It owns retrieval, ranking, budgeting, exclusion, pinning, trust classification and provenance
recording. It does not own prompting, and it never decides what the agent does with what it is
given.

```text
node needs context
        |
        v
context engine  --- retrieves as the developer, from pinned revisions
        |
        v
context bundle  --- immutable, content-addressed, budgeted, provenance-complete
        |
        v
artifact store  --- body; operational state holds the ref
        |
        v
agent runtime   --- GET /v1/context-bundles/{ref}
```

The objective is high-quality relevant context, not maximum context volume.

---

## 2. The bundle

A bundle is an immutable artifact identified by the hash of its canonical serialization. It
carries a budget, a set of pins, an ordered item list and an **exclusion list**.

Each item records: source system, source id, revision, when it was retrieved, **who it was
retrieved as**, the strategy that found it, a relevance score, a token count, an inclusion
reason, a trust class and a pointer to its body.

Each exclusion records what was left out and why — `EVICTED_BUDGET`, `POLICY_EXCLUDED`,
`ACCESS_DENIED` or `STALE`. This list is usually the more diagnostic half.

Refreshing context creates a new bundle that `supersedes` the old one. Bundles are never
mutated.

Full schema: [ADR-0013 §2](../decisions/0013-context-bundle-contract.md).

---

## 3. Budget tiers

The budget is the minimum of the model window, the node configuration and the repository's
`contextPolicy.maxContextBudget`. Eviction proceeds from the lowest tier upward.

| Tier | Content | Evictable |
|---|---|---|
| 0 | task, objective, output contract, platform instructions | never |
| 1 | acceptance criteria, prior failure output, approved plan | last |
| 2 | files, issue and page directly named by the task | by score |
| 3 | supporting material | by score |

If tier 0 does not fit, the node fails `BUDGET_EXCEEDED`. That is a design error in the graph,
not a retryable condition.

Nothing is ever dropped silently. Truncation is allowed only in tiers 2 and 3, at structural
boundaries, and is marked on the item.

---

## 4. Identity: retrieve as the developer

Jira, Confluence and GitHub retrieval authenticates as **the developer running the platform**.
A broadly privileged shared service account is forbidden for retrieval.

Local-first has no central identity, so rather than inventing one the platform borrows
entitlements from systems that already have them. Retrieved context cannot exceed what the
developer could open themselves, and access is logged in the source system under the right
name.

`ACCESS_DENIED` is a recorded outcome, never a trigger to retry with something more privileged.
The platform's own identity (a GitHub App, ADR-0012) is used for *actions*, never to widen
*retrieval*.

Two developers may therefore get different context for the same task. That is correct, and
`retrievedAs` makes it visible.

---

## 5. Trust classes

| Class | Contents |
|---|---|
| `PLATFORM` | platform-authored instructions, task definition, output contract |
| `UNTRUSTED` | every retrieved item, including the repository's own instruction files |

Untrusted content is delimited, provenance-labelled and kept out of the instruction region of
the prompt. Repository instruction files are included because they are useful and classified
untrusted because anyone who can open a pull request can write them (ADR-0014 §6).

The bundle preserves the instruction/data boundary so the prompt can too.

---

## 6. Pinning

Repositories are pinned to a commit SHA at run start; issues and pages record the version seen
at retrieval. Everything in the run reads the pinned revision.

Moving a pin is an explicit refresh that supersedes the bundle, records the delta, and
invalidates any approval whose subject came from the superseded view — an approval given
against one view of the world must not authorize action against another.

This is the context-side half of ADR-0003's reconstructibility invariant: workspace and context
derive from the same `baseSHA`.

---

## 7. Caching

Keyed by `(sourceSystem, sourceId, revision, actingIdentity)`.

Acting identity is part of the key deliberately — without it the cache would serve one
developer's privileged retrieval to another and undo §4. Because revision is in the key,
entries never need invalidating.

---

## 8. V1 retrieval strategies

`DIRECT`, `PATH_MATCH`, `SEARCH`, `LINK_TRAVERSAL`, `GRAPH_STATE`. Relevance is scored from
explainable signals: path proximity, recency, explicit linkage, search rank.

No embeddings, vector store or semantic retrieval in V1. `strategy` is an open enum precisely so
a semantic retriever can be added later without changing the bundle contract, the runtime or
evaluation.

---

## 9. What this enables

Because bundles are immutable and content-addressed, evaluation can hold context constant while
varying the model, and two divergent runs can be compared by first asking whether their inputs
were the same. Provenance makes "why did the agent do that?" a query rather than an
investigation.
