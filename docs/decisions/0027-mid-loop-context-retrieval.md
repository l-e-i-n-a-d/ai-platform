# ADR-0027: Mid-Loop Context Retrieval and Bundle Supersession

## Status

Accepted — 2026-08-15

Closes OQ-10 from `docs/contracts/v1-domain-contracts.md`. Refines the context bundle contract of
ADR-0013 and the tool authorization choke point of ADR-0005.

---

## Context

An agent receives one `ContextBundle` at the start of a node and can fetch it by reference. It has
no way to obtain context that was not included.

This is a real dead end. The context engine assembles a bundle under a token budget, ranking and
dropping candidates. When the agent then discovers that the answer lies in a file the ranker
scored just below the cut, it has three options: fail the node, hallucinate, or produce a
low-confidence answer. All three are worse than fetching the file.

`PRINCIPLES.md` calls for progressive disclosure, which a single up-front bundle is the opposite
of. But the naive fix — let the agent read whatever it wants — breaks something the bundle exists
to provide. `docs/architecture/evaluation.md` §4.5 depends on the bundle being *the complete record
of what the agent saw*, both to assess context quality and to make a run explicable. An agent that
retrieves outside the bundle makes that record a partial one, and nothing in the system would
indicate that it had become partial.

The two requirements are not actually in conflict. They conflict only if retrieval happens outside
the provenance record.

---

## Decision

### 1. Mid-loop retrieval is an ordinary tool

Context retrieval during an agent loop is exposed as `context.search`, a `READ`-class tool subject
to every rule in ADR-0005: it requires a capability grant, it passes through the authorization
choke point, it is scoped by `pathScope` per ADR-0023, it is bounded by budget, and it is recorded
as a tool invocation.

No new mechanism is introduced. The agent runtime gains no retrieval channel of its own — it
already has one channel to the outside world, and this goes through it. A dedicated retrieval path
would be a second, differently-audited way to read the repository, which is how choke points stop
being choke points.

`pathScope` scoping matters here specifically: retrieval is the most plausible route to reading a
repository the run was never granted. A `context.search` that ignores path scope hands the agent
the whole workspace.

### 2. Every retrieval produces a superseding bundle

`context.search` does not return content directly to the agent as an opaque result. It returns a
**new `ContextBundle`** that supersedes the previous one, containing every item of its predecessor
plus the retrieved items, each with the same provenance fields as any other item: source,
retrieval method, relevance score, and what was dropped under the budget.

The bundle chain is explicit:

- `ContextBundle.supersedes` holds the `bundleRef` of the predecessor
- `bundleRef` remains the content hash of the bundle (ADR-0020), so each version is distinctly
  addressable
- the chain is append-only; a superseding bundle never removes an item its predecessor contained,
  because an agent cannot un-see something

`NodeRun.contextBundleRef` is updated to the latest bundle in the same transactional batch as the
`ToolResult` that produced it. After the fact, the final bundle is the complete record of what the
agent saw, and the chain shows the order in which it saw it — which is strictly more information
than the single-bundle model provided.

This is what preserves the evaluation story rather than weakening it. INV-41 ("the bundle is the
complete record of what the agent saw") holds unchanged; what changes is that the bundle is now
versioned within a node attempt.

### 3. Retrieval is bounded, and the bound is per attempt

Unbounded mid-loop retrieval is a way to spend a context budget one file at a time until the model
call no longer fits.

- `maxRetrievals` bounds the number of `context.search` calls per node attempt. Default 5.
- The superseding bundle is subject to the same token budget as the original. When adding retrieved
  items would exceed it, the context engine drops lower-ranked items to make room and records the
  eviction in the bundle's provenance, exactly as it does during initial assembly.
- Exhausting `maxRetrievals` does not fail the node. The tool returns a result stating the bound was
  reached, and the agent proceeds with what it has. Failing here would convert a bounded resource
  into a run failure over a condition the agent can reasonably work around.

Eviction under supersession is the subtle case: an item present in bundle *n* may be absent from
the model's prompt at bundle *n+1* while remaining in the bundle record. The bundle records what
was *available* to the agent; the model request records what was *sent*. Both are needed, and
conflating them would make context quality unmeasurable.

### 4. Retrieval is scoped to the run's repositories, and is not an escape hatch

`context.search` retrieves from sources the run already has access to: the repositories in its
workspace, the work item, and the Confluence and GitHub scopes granted to the run.

It is not a route to arbitrary URLs, to repositories outside `GraphRun.repositories`, or to
credentials. A retrieval tool that can reach anything the platform can reach is a general-purpose
egress channel wearing a context-shaped label.

Retrieved content carries the same trust level as any other context: repository, Jira, Confluence
and pull-request content is untrusted input (`SECURITY.md`), and supersession does not launder it
into instructions.

---

## Consequences

Progressive disclosure becomes possible without losing the provenance record, which was the whole
tension in OQ-10.

`ContextBundle` gains `supersedes`. The context engine gains a supersession path that must be
transactional with the tool result — a supersession recorded without its bundle, or a bundle
without the supersession link, produces a chain with a hole in it, and the hole is invisible until
someone tries to explain a run.

Bundles are now mutable *within* a node attempt in the sense that the current bundle changes,
though each version remains immutable and content-addressed. Code that assumed one bundle per node
attempt must read the chain instead. This is the most likely place for an implementation to quietly
regress to the old model.

Evaluation gains a genuinely better signal: the ratio of runs needing mid-loop retrieval is a
direct measure of initial context quality, which the single-bundle model could not produce.

Retrieval costs tokens and time inside the loop, so a poorly-ranked initial bundle now shows up as
slower and more expensive runs rather than as failed ones. That is the right trade, and it must be
visible in telemetry or it becomes an invisible tax.

---

## Alternatives considered

**Leave it unavailable (status quo).** Rejected. The agent's only recourses are failure or
guessing, and one of those is worse than it looks.

**A dedicated retrieval channel in the agent protocol.** Rejected in §1. A second path to the
repository, differently authorized and differently audited, defeats the choke point.

**Return retrieved content directly without superseding the bundle.** Rejected in §2. Simpler, and
it silently converts the provenance record into a partial one — with no marker to say it had
become partial. This is the option that looks fine until the first time someone needs to explain a
result.

**Re-assemble the bundle from scratch on each retrieval.** Rejected. A re-ranked bundle can drop
items the agent has already reasoned about, producing a record that contradicts the transcript.
Append-only supersession avoids this by construction.

**Let the agent read files through the ordinary workspace read tool.** Partially available already,
and insufficient: it produces no ranking, no provenance and no bundle entry, so the same
completeness problem appears one level down. Where an agent reads a file directly, that read is a
tool invocation and is recorded as one — but it is not *context*, and the distinction is worth
keeping.
