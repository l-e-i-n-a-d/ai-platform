#!/usr/bin/env python3
"""Structural checks for the platform contract schemas in schemas/.

These schemas are the shared contracts between the Java control plane and the Python
agent runtime. Two languages will otherwise implement the ADR prose independently and
diverge, which is the specific failure this directory exists to prevent.

The checks here use the standard library only and verify structure:

  - every file parses as JSON
  - $id is present and agrees with the file's path
  - every relative $ref resolves to a file and, where given, a JSON pointer that exists
  - object schemas are closed, matching ADR-0005 §2's rule that undeclared fields are
    rejected rather than ignored
  - every enum referenced from an ADR is non-empty

Metaschema validation (is this a *valid* JSON Schema?) needs the `jsonschema` package
and runs as a separate CI step. It is skipped here when the package is absent so that
the structural checks still run with no dependencies.

Run with:

    python3 .github/scripts/schemalint.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
ID_PREFIX = "https://ai-platform.internal/schemas/v1/"

# Keywords whose values are subschemas rather than plain data.
SUBSCHEMA_KEYS = {
    "items", "contains", "not", "if", "then", "else",
    "additionalProperties", "propertyNames", "unevaluatedItems", "unevaluatedProperties",
}
SUBSCHEMA_LIST_KEYS = {"allOf", "anyOf", "oneOf", "prefixItems"}
SUBSCHEMA_MAP_KEYS = {"properties", "patternProperties", "$defs", "definitions"}

failures: list[str] = []


def fail(path: Path, message: str) -> None:
    failures.append(f"{path.relative_to(ROOT)}: {message}")


def schema_files() -> list[Path]:
    return sorted(SCHEMAS.rglob("*.schema.json"))


def walk(node: object, pointer: str = ""):
    """Yield (pointer, mapping) for every subschema position in the document."""
    if isinstance(node, dict):
        yield pointer, node
        for key, value in node.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            child = f"{pointer}/{escaped}"
            if key in SUBSCHEMA_MAP_KEYS and isinstance(value, dict):
                for name, sub in value.items():
                    name_escaped = name.replace("~", "~0").replace("/", "~1")
                    yield from walk(sub, f"{child}/{name_escaped}")
            elif key in SUBSCHEMA_LIST_KEYS and isinstance(value, list):
                for index, sub in enumerate(value):
                    yield from walk(sub, f"{child}/{index}")
            elif key in SUBSCHEMA_KEYS:
                yield from walk(value, child)


def resolve_pointer(document: object, pointer: str) -> bool:
    if pointer in ("", "#"):
        return True
    current = document
    for token in pointer.lstrip("#").lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return False
    return True


def check_id(path: Path, document: dict) -> None:
    expected = ID_PREFIX + str(path.relative_to(SCHEMAS)).replace("\\", "/")
    actual = document.get("$id")
    if actual is None:
        fail(path, "missing $id")
    elif actual != expected:
        fail(path, f"$id is {actual!r}, expected {expected!r}")

    if document.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail(path, "must declare $schema as draft 2020-12")

    if not document.get("description"):
        fail(path, "missing a top-level description — these schemas carry the rationale, not just the shape")


def check_refs(path: Path, document: dict, documents: dict[Path, dict]) -> None:
    for pointer, node in walk(document):
        ref = node.get("$ref")
        if not isinstance(ref, str):
            continue

        if ref.startswith("#"):
            if not resolve_pointer(document, ref):
                fail(path, f"at {pointer or '/'}: local $ref {ref!r} does not resolve")
            continue

        if ref.startswith(("http://", "https://")):
            fail(path, f"at {pointer or '/'}: absolute $ref {ref!r}; use a relative path so the set is portable")
            continue

        file_part, _, fragment = ref.partition("#")
        target = (path.parent / file_part).resolve()
        if target not in documents:
            fail(path, f"at {pointer or '/'}: $ref {ref!r} points at a file that is not a schema in schemas/")
            continue
        if fragment and not resolve_pointer(documents[target], fragment):
            fail(path, f"at {pointer or '/'}: $ref {ref!r} resolves to a file but not to that pointer")


def check_closed(path: Path, document: dict) -> None:
    """Object schemas must be closed. See ADR-0005 §2."""
    for pointer, node in walk(document):
        if node.get("type") != "object":
            continue
        if "properties" not in node:
            continue
        if node.get("additionalProperties") is False:
            continue
        if "additionalProperties" in node or "patternProperties" in node:
            continue
        fail(
            path,
            f"at {pointer or '/'}: object schema with properties but no "
            f"'additionalProperties: false' — undeclared fields must be rejected, not ignored",
        )


def check_enums(path: Path, document: dict) -> None:
    for pointer, node in walk(document):
        enum = node.get("enum")
        if enum is not None:
            if not isinstance(enum, list) or not enum:
                fail(path, f"at {pointer or '/'}: enum must be a non-empty list")
            elif len(enum) != len(set(map(repr, enum))):
                fail(path, f"at {pointer or '/'}: enum contains duplicate values")


def validate_examples(documents: dict[Path, dict]) -> str:
    """Validate the example documents in schemas/examples/.

    A schema that has never validated a document is unverified. The valid/ examples must
    pass; the invalid/ examples must fail, which is what proves the constraints actually
    bite rather than merely being written down.
    """
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError:
        return "example validation skipped: jsonschema/referencing not installed"

    examples = sorted((SCHEMAS / "examples").rglob("*.json"))
    if not examples:
        return "no examples found"

    registry = Registry()
    for path, document in documents.items():
        uri = document.get("$id")
        if uri:
            registry = registry.with_resource(uri, Resource.from_contents(document))

    checked = 0
    for path in examples:
        try:
            instance = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(path, f"invalid JSON: {exc}")
            continue

        target = instance.pop("$schema", None)
        expectation = instance.pop("$expect", None)
        expected_keyword = instance.pop("$expectKeyword", None)
        if not target:
            fail(path, "example must name the schema it exercises via a relative $schema")
            continue

        schema_path = (path.parent / target).resolve()
        schema = documents.get(schema_path)
        if schema is None:
            fail(path, f"$schema {target!r} does not point at a schema in schemas/")
            continue

        validator = Draft202012Validator(schema, registry=registry)
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        must_fail = path.parent.name == "invalid"

        if must_fail:
            if not expectation:
                fail(path, "an invalid example must state, in $expect, which rule it violates")
            if not expected_keyword:
                fail(path, "an invalid example must state the violated keyword in $expectKeyword")
            if not errors:
                fail(path, f"expected to be REJECTED but it validated. Rule: {expectation}")
            elif expected_keyword and not any(
                _mentions_keyword(error, expected_keyword) for error in errors
            ):
                # Rejected, but not for the stated reason. Left unchecked, a schema could
                # stop enforcing its rule and this example would still appear to pass.
                observed = sorted({e.validator for e in errors if e.validator})
                fail(
                    path,
                    f"was rejected, but not by {expected_keyword!r} as declared "
                    f"(observed: {', '.join(map(str, observed)) or 'none'}). "
                    f"The example may no longer test what it claims to.",
                )
        elif errors:
            first = errors[0]
            location = "/".join(str(p) for p in first.path) or "(root)"
            fail(path, f"expected to validate, but failed at {location}: {first.message}")
        checked += 1

    return f"{checked} examples validated"


def _mentions_keyword(error, keyword: str) -> bool:
    """True if this error, or any nested context error, was raised by the given keyword.

    Nested contexts matter because oneOf/allOf wrap the real cause.
    """
    if error.validator == keyword:
        return True
    return any(_mentions_keyword(child, keyword) for child in error.context or [])


def main() -> int:
    files = schema_files()
    if not files:
        print("schemalint: no schemas found under schemas/", file=sys.stderr)
        return 1

    documents: dict[Path, dict] = {}
    for path in files:
        try:
            documents[path.resolve()] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(path, f"invalid JSON: {exc}")

    for path in files:
        document = documents.get(path.resolve())
        if document is None:
            continue
        check_id(path, document)
        check_refs(path, document, documents)
        check_closed(path, document)
        check_enums(path, document)

    metaschema_note = validate_against_metaschema(documents)
    example_note = validate_examples(documents)

    if failures:
        print(f"schemalint: {len(failures)} problem(s) across {len(files)} schemas\n")
        for failure in sorted(failures):
            print(f"  {failure}")
        return 1

    print(
        f"schemalint: {len(files)} schemas checked, no problems found "
        f"({metaschema_note}; {example_note})"
    )
    return 0


def validate_against_metaschema(documents: dict[Path, dict]) -> str:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return "metaschema validation skipped: jsonschema not installed"

    for path, document in documents.items():
        try:
            Draft202012Validator.check_schema(document)
        except Exception as exc:  # noqa: BLE001 - the library raises several types
            fail(path, f"not a valid draft 2020-12 schema: {exc}")
    return "metaschema validated"


if __name__ == "__main__":
    sys.exit(main())
