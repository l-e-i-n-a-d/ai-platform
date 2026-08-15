# ADR-0020: Canonical Serialisation and Content Hashing

## Status

Accepted — 2026-08-15

Closes OQ-09 from `docs/contracts/v1-domain-contracts.md`. Supplies the definition of "canonical
serialization" already assumed by ADR-0008 §1 (`graphVersionHash`), ADR-0013 §1
(`contextBundleRef`), ADR-0005 §7 (idempotency key input) and ADR-0009 (approval `subjectHash`).
Prerequisite for ADR-0022, which content-addresses `Agent`.

---

## Context

Four accepted decisions already depend on content hashing:

```text
ADR-0008 §1   graphVersionHash  = hash of the Graph's canonical form
ADR-0013 §1   contextBundleRef  = sha256(canonical serialization of the bundle)
ADR-0005 §7   idempotency key   over (runId, nodeId, toolId, canonicalised input)
ADR-0009      subjectHash       binds an approval to what was approved
```

None of them says what "canonical" means. That gap is more dangerous than an ordinary
under-specification, because the failure it produces is silent and delayed.

The control plane is Java and the agent runtime is Python (ADR-0004). Both will compute hashes
over the same logical documents. If their canonical forms differ by so much as a key ordering
rule or a space, then:

- a pinned `Graph` fails to resolve after the component computing the hash changes;
- an idempotency key computed on retry differs from the one written ahead, and the platform
  performs an external write twice — precisely the duplicate pull request ADR-0008 §7 exists to
  prevent;
- an approval's `subjectHash` fails re-verification on resume and a legitimately approved action
  is refused, or worse, a subtly different one is accepted;
- evaluation cannot compare two runs, because identical inputs produce different refs.

None of these surface in a single-language test. They surface the first time the two languages
have to agree, which is deep into M4 or M5.

The naive approach — `json.dumps(obj, sort_keys=True)` in Python and Jackson's default writer in
Java — differs in at least key ordering rules, whitespace, non-ASCII escaping and number
formatting. It is a trap that looks like it works.

---

## Decision

### 1. RFC 8785 JSON Canonicalization Scheme, SHA-256, lowercase hex

```text
canonical bytes = JCS(document)          RFC 8785, UTF-8 encoded
digest          = SHA-256(canonical bytes)
representation  = lowercase hex, 64 characters
```

RFC 8785 is chosen because it is a published specification with a conformance test suite and
existing implementations in both target languages, rather than a convention this platform would
have to define, document and defend on its own.

Concretely, JCS requires:

| Aspect | Rule |
|---|---|
| Whitespace | none, anywhere |
| Object keys | sorted by **UTF-16 code unit** sequence, not by Unicode code point |
| Duplicate keys | not permitted; a document containing them is invalid input |
| Strings | minimal JSON escaping; `"` `\` and control characters below `0x20` only |
| Non-ASCII | emitted as literal UTF-8, never as `\uXXXX` |
| Encoding | UTF-8, no byte order mark |
| Arrays | order preserved; arrays are ordered data |

The UTF-16 ordering rule is the detail most likely to be implemented wrongly. Python sorts
strings by code point, which differs from UTF-16 order once supplementary-plane characters are
involved. Every implementation must sort on the UTF-16 encoding of the key, and the test vectors
in §6 include a case that fails if it does not.

### 2. Hashed documents contain integers only

Any document subject to content hashing must contain no non-integer number, and every integer it
contains must lie within ±(2^53 − 1).

This restriction exists because RFC 8785 delegates number formatting to ECMAScript
`Number::toString`, a shortest-round-trip algorithm whose Java and Python equivalents disagree in
several ranges: Python renders `1e16` as `1e+16` where ECMAScript renders `10000000000000000`.
Implementing that algorithm correctly in two languages is possible but is a genuine source of
rare, data-dependent divergence — the worst kind to debug.

Excluding floating point removes the entire class of defect for no functional loss, because no
hashed document has a demonstrated need for one. The restriction is mechanically enforced:
`schemalint` fails if a schema in the hashed set permits `"type": "number"` or `"type": "null"`.

Two existing fields change representation as a direct consequence:

| Field | Was | Becomes |
|---|---|---|
| `Graph` agent node `budgets.maxCostUnits` | `number` | `integer` |
| `ContextBundle` `items[].relevanceScore` | `number` | `integer` |

`maxCostUnits` is made integral in every schema that carries it, so that the generated types do
not differ between a hashed and an unhashed occurrence of the same concept. This decides the
*representation* of a cost unit only. What a cost unit measures, and how budgets aggregate across
a run, remains OQ-08.

Non-hashed documents are unaffected: `ModelRequest.params.temperature` and
`ModelResponse.cost.amount` stay as they are.

### 3. Absent means absent; null is not a value

An optional field with no value is **omitted**. It is never serialised as `null`.

`null` is therefore not a member of any hashed document, and `{"a":1}` and `{"a":1,"b":null}`
never both occur as representations of the same logical object. Without this rule the two
languages would have to agree on whether a `None`/`null` field round-trips, which they do not do
naturally: Python dataclasses default absent fields to `None`, Jackson omits them only when told
to.

Generated code in both languages must omit absent optional fields on serialisation.

### 4. Self-referencing fields are excluded from their own hash

A document that stores its own hash cannot include that field while computing it. Rather than
special-casing this per schema in two languages, the schema declares it:

```json
"bundleRef": { "$ref": "...#/$defs/sha256", "x-hashExclude": true }
```

Canonicalisation removes every property annotated `x-hashExclude: true` before serialising.
`schemalint` verifies that the annotation appears only on fields of a hashed schema, so the
mechanism cannot be used to quietly drop meaningful content from a hash.

### 5. The hashed set is explicit

Exactly four document kinds are content-addressed in V1:

| Document | Field | Decided by |
|---|---|---|
| `Graph` | `graphVersionHash` | ADR-0008 §1 |
| `Agent` | `agentVersionHash` | ADR-0022 |
| `ContextBundle` | `bundleRef` | ADR-0013 §1 |
| tool input | idempotency key component | ADR-0005 §7 |

Approval `subjectHash` (ADR-0009) is the hash of whichever of these documents is the approval's
subject, computed by the same rule; it introduces no fifth mechanism.

Content hashing is distinct from **artifact** hashing. An `ArtifactRef` digests raw bytes — a
patch, a log, a transcript — with SHA-256 directly. No canonicalisation is involved because there
is no JSON structure to canonicalise. The two must not be conflated: canonicalising an artifact
would corrupt it.

Adding a document to the hashed set requires an ADR, because pinning something new changes what
"the same run" means.

### 6. Language-independent test vectors

`schemas/hashing/vectors.json` holds the conformance suite. Each vector carries the input
document, the exact canonical bytes as a JSON string, and the expected digest:

```text
{
  "id": "key-ordering-utf16",
  "why": "sorting by code point instead of UTF-16 code unit produces a different order",
  "input": { ... },
  "canonical": "{...}",
  "sha256": "..."
}
```

Every implementation — Python today, Java today, any future language — must reproduce both the
canonical string and the digest for every vector. The vectors are part of CI, not documentation.

The suite deliberately includes the cases that distinguish a correct implementation from a
plausible one: UTF-16 versus code-point key ordering, control-character escaping, non-ASCII
literals, empty containers, nested key ordering, integer boundaries at ±(2^53 − 1), and
`x-hashExclude` removal.

---

## Alternatives Considered

**`json.dumps(sort_keys=True)` and Jackson defaults.** Rejected: they differ. Whitespace,
non-ASCII escaping and key ordering all diverge, and the divergence is invisible until the two
languages compare a hash.

**Define a bespoke canonical form.** Rejected. It would need a specification, a test suite and an
implementation in every language the platform ever adds — all of which RFC 8785 already has. The
only reason to prefer a bespoke form would be to permit floating point, which §2 declines to do
anyway.

**Full RFC 8785 including ECMAScript number formatting.** The complete standard, and rejected for
V1 as unfavourable risk for no gain. It is the single hardest part to implement identically in
two languages, and nothing in the hashed set needs it. §2 is a strict subset of RFC 8785: a
document valid under this decision hashes identically under a full implementation, so adopting
the remainder later is a widening, not a breaking change.

**CBOR or Protocol Buffers canonical encoding.** Rejected. Both would make the contracts
unreadable in a text editor and unusable with the JSON Schema tooling the repository already runs,
to solve a problem JCS solves.

**SHA-512 or BLAKE3.** Rejected. SHA-256 is already the digest used by `ArtifactRef`, Git object
identity and container image pinning throughout the architecture. One digest algorithm is one
fewer thing to get wrong, and 256 bits is not the weak link.

---

## Consequences

- Content hashing is implementable identically in Java and Python, and the claim is tested rather
  than asserted.
- Two schema fields change from `number` to `integer`; both are new enough that nothing depends on
  the previous representation.
- Generated code in both languages must omit absent optional fields, which constrains the
  generator in ADR-0024.
- `schemalint` gains three checks: no `number`/`null` in hashed schemas, `x-hashExclude` used only
  where meaningful, and the vector suite reproduced exactly.
- Reintroducing floating point into a hashed document is a breaking change requiring an ADR.
- Any future non-JVM, non-Python component inherits a specification with a conformance suite
  rather than a convention it must reverse-engineer.

---

## Security / Operational Impact

Content hashing is a security control, not only a correctness one.

- **Idempotency.** ADR-0005 §7 derives the idempotency key from canonicalised tool input. A
  divergence between the language that wrote the intent and the language that retries it produces
  duplicate `EXTERNAL_WRITE` side effects — a second pull request, a second Jira transition.
- **Approval binding.** ADR-0009 re-verifies `subjectHash` on resume so that an approval of one
  thing cannot authorise another. A canonicalisation ambiguity is an approval-bypass primitive: if
  two distinct documents can produce one digest through inconsistent handling, the binding is
  decorative.
- **Pinning.** `graphVersionHash` and `agentVersionHash` are what make a run reproducible and what
  prevent an in-flight run from silently changing behaviour.

Rejecting duplicate object keys matters here too: a parser that keeps the last duplicate and a
canonicaliser that keeps the first would let one document present two different digests.

SHA-256 is a collision-resistant digest used as an identifier, not as a message authentication
code. Nothing in this decision treats possession of a hash as authorisation.

---

## Follow-up

- Add `schemas/hashing/vectors.json` and the canonicalisation checks to `schemalint`.
- Change `maxCostUnits` and `relevanceScore` to `integer`.
- Annotate `ContextBundle.bundleRef` with `x-hashExclude`.
- ADR-0022 — `Agent` content addressing, which depends on this.
- ADR-0024 — generated code must omit absent optional fields.
- OQ-08 — cost units and budget aggregation, unaffected by the representation change here.
