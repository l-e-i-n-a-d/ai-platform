# Platform Contract Schemas

Machine-readable JSON Schemas for the contracts defined by the Architecture Decision Records
in [`docs/decisions/`](../docs/decisions/README.md).

## Why these exist

The platform is deliberately split across two languages: a Java/Quarkus control plane and a
Python agent runtime. Every contract between them was, until now, prose in an ADR. Two teams
implementing the same paragraph in two languages will diverge — not dramatically, but in the
details that matter, like whether `additionalProperties` is closed or whether `INDETERMINATE`
is retryable.

These schemas are the shared, executable form of those decisions. Where a schema and an ADR
disagree, that is a bug in one of them and should be raised, not worked around.

## Status

**Contracts, not implementations.** The repository is still in the architectural scaffold
phase; no component consumes these yet. They are published now because the data model is the
expensive thing to change once runs exist.

## Layout

| Directory | Contracts | Source |
|---|---|---|
| `common/` | shared primitives: identifiers, correlation, network policy, resource limits | — |
| `execution/` | `ExecutionRequest`, `ExecutionResult`, `WorkspaceSpec` | ADR-0003, ADR-0006 |
| `tools/` | `Tool`, `CapabilityGrant`, `CommandProfile` | ADR-0005 |
| `agent/` | `AgentExecutionRequest`, `AgentExecutionResult` | ADR-0004 |
| `graph/` | `GraphDefinition`, `Condition`, `Run`, `NodeExecution`, `Checkpoint` | ADR-0008 |
| `approval/` | `Approval` | ADR-0009 |
| `model/` | `ModelRequest`, `ModelResponse` | ADR-0010, ADR-0011 |
| `context/` | `ContextBundle` | ADR-0013 |
| `registry/` | `RepositoryRecord` | ADR-0014 |
| `audit/` | `AuditEntry` | ADR-0016 |
| `artifacts/` | `ArtifactRef` | ADR-0017 |
| `examples/` | documents that must validate | — |
| `examples/invalid/` | documents that must be **rejected** | — |

## Conventions

- JSON Schema **draft 2020-12**.
- `$id` is `https://ai-platform.internal/schemas/v1/<path>` and must match the file's location.
  The host does not resolve and is not meant to; it is a namespace.
- Cross-schema `$ref`s are **relative paths**, so the directory can be vendored into either
  language's build without a network fetch or a resolver configuration.
- Object schemas are **closed** (`additionalProperties: false`). This follows ADR-0005 §2:
  anything not declared is rejected rather than ignored. The one deliberate exception is a
  field holding an *embedded* schema document, which is open by necessity and marked
  explicitly.
- Descriptions carry the *reason*, not just the shape. A field that exists because of a
  specific failure mode says so, with the ADR section that decided it.

## The invalid examples are the interesting ones

`examples/invalid/` contains documents that must fail validation. Each declares:

- `$expect` — the rule it violates, in prose, with its ADR reference
- `$expectKeyword` — the JSON Schema keyword expected to reject it

The check asserts both that the document is rejected *and* that it is rejected by the declared
keyword. Without the second assertion, a schema could quietly stop enforcing its rule while the
example still appeared to pass, because some unrelated constraint happened to fail instead.

These files are the executable form of the platform's security-relevant invariants. Deleting
the rule that "IRREVERSIBLE tools always require approval" from a schema causes a named,
specific CI failure quoting ADR-0005 §3, rather than a silent loss of a control.

## Checks

```bash
python3 .github/scripts/schemalint.py
```

Structural checks run with the standard library alone: JSON validity, `$id`/path agreement,
`$ref` resolution, closed objects, well-formed enums.

Metaschema validation and example validation additionally require `jsonschema >= 4.18`. When it
is absent the script says so and skips those checks rather than passing silently. CI installs
it, so both always run there.

## Changing a contract

1. Change the ADR first. The schema follows the decision, never the reverse.
2. Update the schema and its description text.
3. Add or update an example — and, for anything security-relevant, an invalid example.
4. Run the checks.

Schemas are versioned by the `v1` path segment. A breaking change to a contract that already
has implementations needs a new version and an ADR, not an edit.
