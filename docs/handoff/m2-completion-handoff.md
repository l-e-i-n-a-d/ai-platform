# M2 Completion — Session Handoff

**Written:** end of the previous session, at the user's request.
**Repository:** `/home/daniel/code/ai-platform`
**Branch head at handoff:** `cac7429`

Paste the block in [PROMPT FOR NEW SESSION](#prompt-for-new-session) into a fresh Copilot CLI
session. Everything above it is context for that prompt.

---

## 1. Where things stand

M2 (Contracts) is **substantially complete but not finished**. Four checks pass from a clean
checkout:

```bash
python3 .github/scripts/doclint.py         # 69 md files, 27 ADRs, 55 schemas scanned
python3 .github/scripts/schemalint.py      # 25 schemas, 29 examples  (needs jsonschema>=4.18)
python3 .github/scripts/codegen.py --check # 164 generated files, 104 records, 54 enums
python3 .github/scripts/contract_test.py   # 158 types, 16 examples, 12 hash vectors
```

`schemalint` needs `jsonschema`; there is no system `pip`. Create a venv:

```bash
python3 -m venv /tmp/svenv && /tmp/svenv/bin/pip install 'jsonschema>=4.18' pyyaml
/tmp/svenv/bin/python .github/scripts/schemalint.py
```

The other three are standard-library only. `contract_test.py` compiles the Java harness itself
(JDK 17 is present).

### Commits made across the M2 push

| Commit | What |
|---|---|
| `a64a2b2` | DEF-01 fix — `ModelRequest` can express the assistant's tool-call turn |
| `8d4e7b2` | ADR-0019..0024; schema edits; four new schemas; version fields |
| `109d5fb` | Java + Python model generation; cross-language conformance harness |
| `6d83b71` | ADR-0025/0026/0027; `evaluation.md`; 11 contract examples; lint enforcement |
| `cac7429` | Contract spec frozen (Proposed → Accepted); CI extended to 4 jobs |

### Uncommitted working-tree changes (intentional, complete, verified)

```text
M docs/architecture/approvals.md      re-request semantics per ADR-0025 §2
M docs/architecture/model-gateway.md  cost units + suspend-on-exhaustion per ADR-0026
M docs/architecture/tool-layer.md     pathScope is a repository-keyed map per ADR-0023 §3
```

These three fix genuine contradictions introduced by ADR-0023/0025/0026. They pass `doclint`.
**They only need committing.**

---

## 2. The one unfinished piece of work

### `CONTEXT_BUDGET_EXCEEDED` — agreed, not yet applied

`docs/architecture/context-engine.md` (around line 73) says a node whose tier-0 context does not
fit fails `BUDGET_EXCEEDED`. ADR-0026 §5 redefined `BUDGET_EXCEEDED` to **suspend** the run so an
operator can raise the ceiling and resume.

These are different failures sharing one enum value. Context overflow is a graph design error that
no retry and no larger allowance fixes; cost exhaustion is operator-resolvable. Under the current
enum, an unfixable design error would suspend a run and wait for a human who has nothing to raise.

The resolution was agreed and the edit was interrupted mid-flight. **Four changes, all prepared:**

1. **`schemas/common/common.schema.json`** — add `"CONTEXT_BUDGET_EXCEEDED",` immediately after
   `"BUDGET_EXCEEDED",` in the `failureCategory` enum. Do **not** add it to `graph.schema.json`'s
   `retryableCategories` — it is never retryable.

2. **`docs/decisions/0026-cost-units-and-budget-enforcement.md`** — append to §5, after the line
   `` `BUDGET_EXCEEDED` is never retryable. Retrying a bound that was hit re-hits it. ``:

   > **`BUDGET_EXCEEDED` means cost exhaustion and nothing else.** The context engine previously
   > used the same category when tier-0 content did not fit the token budget, and this decision
   > makes that reuse wrong: one is an operator-resolvable condition that suspends, the other is a
   > graph that cannot work and must fail. A single category covering both would mean an
   > unfixable design error suspends a run and waits for a human who has nothing to raise.
   >
   > Context overflow therefore becomes `CONTEXT_BUDGET_EXCEEDED`, terminal and never retryable.
   > The two conditions are told apart by category rather than by reading the message, which
   > ADR-0008 §11 requires anyway.

3. **`docs/architecture/context-engine.md`** — replace the two-line `BUDGET_EXCEEDED` paragraph
   with the `CONTEXT_BUDGET_EXCEEDED` version, explaining that the distinction exists precisely
   because `BUDGET_EXCEEDED` suspends and this must not.

4. **`docs/contracts/v1-domain-contracts.md`** — add a row to the retry table in §6.9, above the
   `BUDGET_EXCEEDED` row:

   ```text
   | `CONTEXT_BUDGET_EXCEEDED` | **never** | tier-0 content exceeds the model context: a graph design error, which no retry and no larger allowance fixes |
   ```

Then regenerate (`codegen.py`) and re-run all four checks.

**This is an amendment to ADR-0026, not a new ADR.** The conflict is a direct consequence of
ADR-0026 and belongs inside it. Do not create ADR-0028 for it.

---

## 3. What was completed — do not redo any of it

### Nine ADRs written, all `Accepted — 2026-08-15`

| ADR | Closes | Binding decision |
|---|---|---|
| 0019 | OQ-01 | 16 canonical names; 9 retired; `doclint`-enforced |
| 0020 | OQ-09 | RFC 8785 JCS + SHA-256 + lowercase hex; **integers only** in hashed documents |
| 0021 | OQ-04 | `(runId, nodeId, iteration, attempt)`, both 1-based; idempotency key includes `iteration`, excludes `attempt` |
| 0022 | OQ-02 | `Agent` immutable and content-addressed; `GraphRun.agentPins` resolved once at creation |
| 0023 | OQ-07, DEF-02 | `<workspace>/<repositoryId>/`; `pathScope` is a **map keyed by repositoryId**; paths rejected, never normalised |
| 0024 | — | Schemas are the single source of truth; one generator; **Option A** (generated code committed, CI diffs it) |
| 0025 | OQ-06 | Approval expiry is a non-decision; retry means **re-request the same subject**, never re-execute |
| 0026 | OQ-08 | Cost unit = integer micro-unit of an ISO 4217 currency; mandatory run ceiling; exhaustion **suspends** |
| 0027 | OQ-10 | Mid-loop retrieval is a `READ` tool that **supersedes the bundle**, so provenance stays complete |

OQ-03 and OQ-05 were closed by creating the missing schemas; no ADR was needed.

**OQ-11 (per-integration reconciliation) is the only question still open.** It needs one procedure
per external-write tool, no such tool exists, and it is due at M5. It blocks nothing in M3.

### Artifacts created

- **4 new schemas:** `agent/agent`, `tools/tool-request`, `tools/tool-result`, `execution/workspace`
- **5 renames** via `git mv`: `graph-definition`→`graph`, `run`→`graph-run`,
  `node-execution`→`node-run`, `tool-descriptor`→`tool`, `approval-record`→`approval`
- **`schemas/hashing/vectors.json`** — 12 language-independent vectors
- **`.github/scripts/canonical.py`** — reference JCS implementation
- **`.github/scripts/codegen.py`** — one generator, both languages, standard library only
- **`.github/scripts/contract_test.py`** — three-way conformance driver
- **`contracts/java/`** — pom + 163 generated files + 3 hand-written harness files
- **`contracts/python/`** — pyproject + generated `models.py`
- **`contracts/README.md`**
- **`docs/architecture/evaluation.md`** — V1 evaluation architecture, documentation only
- **11 contract examples** covering all ten cases the M2 prompt §16 required

### Enforcement added, and mutation-tested

Each was verified to fail on a deliberate regression rather than merely to pass:

| Mutation | Detected by |
|---|---|
| Reintroduce `NodeExecution` in a document | `doclint` |
| `"type": "number"` inside a hashed document | `schemalint`, over the transitive `$ref` closure |
| `x-hashExclude` in a non-hashed schema | `schemalint` |
| Rename a schema field without regenerating | `codegen --check` |
| Corrupt a hash vector | `contract_test` — **both** Java and Python, independently |

`schemalint`'s hashed-document check found real drift the moment it was written: `Condition`
permitted float and null literals and is embedded in `Graph`, so a float in an edge condition
would have made `graphVersionHash` depend on which language published the graph. Fixed to
`["string", "integer", "boolean"]`.

### CI

`.github/workflows/docs.yml` now has four jobs: `doclint`, `schemas`, `codegen`, `contracts`.
All run offline — no Azure, Cosmos DB, Entra ID, or provider credentials.

---

## 4. Traps that already cost time — do not rediscover them

- **Never bulk-`sed` across `docs/decisions/`.** ADRs quote retired names as documentation of the
  rename itself. `doclint` allowlists ADR-0019 and ADR-0021 for exactly this reason.
- **Never JSON round-trip a schema file.** It destroys the repository's compact formatting. Use
  targeted text replacement with an assertion on the occurrence count.
- **The `create` tool cannot overwrite.** Use a Python heredoc, or write `<file>.new` and `mv`.
- **Invariant numbers collide silently.** INV-26/27 already belong to the tool layer; two new
  Agent invariants had to be renumbered to INV-90/91. The specification now has **92** invariants,
  all defined, no gaps — re-run the regex audit before adding more.
- **Python's default dict sort is wrong for JCS.** It sorts by code point; RFC 8785 needs UTF-16
  code units. Sort on `key.encode("utf-16-be")`. Java's `String.compareTo` is natively correct.
- **`git checkout --` after every mutation test**, and assert the mutation actually applied. One
  test appeared to pass only because the replacement string silently did not match.

---

## PROMPT FOR NEW SESSION

```text
Continue completing milestone M2 (Contracts) in /home/daniel/code/ai-platform.

Read docs/handoff/m2-completion-handoff.md first. It records exactly what is done, what is
uncommitted, and the one unfinished change. Treat it as accurate; verify rather than redo.

Do NOT start M3. No GraphRun execution, no persistence, no graph engine, no agent runtime, no
model gateway, no tools, no integrations, no Kubernetes, no observability stack. M2 is
documentation, contracts and tooling only.

Set up first:
  python3 -m venv /tmp/svenv && /tmp/svenv/bin/pip install 'jsonschema>=4.18' pyyaml

Then, in order:

1. Apply the CONTEXT_BUDGET_EXCEEDED change described in section 2 of the handoff. It is an
   amendment to ADR-0026 §5, not a new ADR. Four files: the common schema enum, ADR-0026,
   docs/architecture/context-engine.md, and the retry table in
   docs/contracts/v1-domain-contracts.md. Then run codegen.py and confirm all four checks pass.

2. Review the remaining architecture documents for drift against ADR-0019 through ADR-0027. The
   three already fixed in the working tree are approvals.md, model-gateway.md and tool-layer.md.
   Not yet reviewed against the new decisions: graph-engine.md, agent-runtime.md,
   execution-plane.md, persistence.md, security-model.md, audit.md, observability.md,
   repository-registry.md, control-plane.md, developer-experience.md, system-context.md.
   Look specifically for: the four-part NodeRun key, agent pinning, integer cost units and the
   run-level budget, suspend-versus-fail on budget exhaustion, repository-keyed pathScope,
   bundle supersession, and the five renamed types.

3. Review §5 of docs/contracts/v1-domain-contracts.md field-by-field against the canonical
   schemas. The prose field lists in §5.5 (Agent), §5.7 (ToolRequest), §5.8 (ToolResult) and
   §5.16 (Workspace) were written before those schemas existed and may not match them. Where
   they disagree the schema wins (ADR-0024 §1), and the document is the bug.

4. Review all 92 invariants after the above. For each affected one, confirm it is still correct,
   still testable, and that the enforcing component named in §8 is right. Do not weaken an
   invariant to make implementation easier, and do not delete one without recording why.

5. Repository-wide consistency sweep: stale terminology, unresolved OQ references, stale schema,
   example or ADR references, broken links, CI referencing files that do not exist.

6. Commit the working-tree changes together with your own, then produce exactly this table:

| M2 Exit Criterion | Status | Evidence |
|---|---|---|
| Contracts reviewed and agreed | | |
| Critical findings have recorded decisions | | |
| Canonical schemas established | | |
| Java models generated from schemas | | |
| Python models generated from schemas | | |
| Cross-language contract validation | | |
| Evaluation architecture complete | | |
| CI validation passes | | |
| No known contract/schema drift | | |

Then: Decisions closed / Files changed / Generated artifacts / Tests run with results /
Remaining issues. Finish with a verdict of exactly one of:

  M2 COMPLETE — READY FOR M3
  M2 INCOMPLETE

No hedging and no percentages. If incomplete, say precisely what prevents completion.

Justify the "no unresolved contract decisions" criterion explicitly: OQ-11 is the only open
question, it needs one reconciliation procedure per external-write tool, no such tool exists,
and it is due at M5 — so it gates M5, not M3.
```
