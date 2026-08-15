# Generated Contract Models

**Everything under `java/src/main/` and `python/aiplatform_contracts/models.py` is generated. Do
not edit it.**

Java and Python models are generated from the JSON Schemas in [`schemas/`](../schemas/README.md),
which are the single source of truth (ADR-0024 §1). A change to a contract is a change to a
schema, followed by regeneration.

```bash
python3 .github/scripts/codegen.py           # regenerate both languages
python3 .github/scripts/codegen.py --check   # fail if the committed output is stale
python3 .github/scripts/contract_test.py     # verify the two languages agree
```

## Why the output is committed

ADR-0024 §3 chose to commit generated code and have CI prove it regenerates identically, rather
than generating at build time.

The reason is review. A contract change and its effect on both languages appear in the same diff,
so a reviewer can see that adding a required field broke a Python constructor without checking out
the branch and running a build. The cost is a larger diff and a check that fails when someone edits
generated code by hand — which is exactly the thing that needs to fail.

## Layout

| Path | Contents |
|---|---|
| `java/src/main/java/io/aiplatform/contracts/` | generated Java 17 records and enums |
| `java/src/test/java/io/aiplatform/contracts/` | the only hand-written Java: the conformance harness |
| `python/aiplatform_contracts/models.py` | generated frozen dataclasses and string enums |

Generated types carry no behaviour (ADR-0024 §4). They serialise, deserialise and nothing else.
Validation is the schema's job, and business rules belong to the components that own them; a model
that validates itself becomes a second, divergent copy of the rules.

## What the conformance check actually checks

`contract_test.py` compares three independent readings of the same contracts:

1. the schemas, read directly
2. the Java types, by reflection
3. the Python types, by introspection

Three-way rather than two-way, because comparing the generated Java to the generated Python would
only prove that the generator agrees with itself. It verifies type names, field names, required
versus optional, enum values and schema versions, and round-trips the example documents in both
languages.

It also verifies that both languages reproduce the canonical hashing vectors in
`schemas/hashing/vectors.json`. Java and Python implement RFC 8785 canonicalisation **separately**
for the same reason: a shared implementation would prove only that both call the same code.

The Java required-field annotations exist because of this check. Without `@Required`, an optional
`String` and a required `String` are indistinguishable by reflection, and the check would compare
two field lists and verify nothing.

## Java and Python are only compatible at the same commit

ADR-0024 §7. There is no cross-version compatibility contract between the two languages in V1. The
control plane and the agent runtime are deployed together from one repository, and inventing a
version negotiation for a boundary that does not skew would be solving a problem nobody has.
