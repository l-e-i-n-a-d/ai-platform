#!/usr/bin/env python3
"""Cross-language contract conformance check (ADR-0024).

Verifies that the Java models, the Python models and the canonical JSON Schemas
describe the same contracts, and that both languages reproduce the canonical
hashing vectors of ADR-0020 §6.

The check is three-way rather than two-way. Comparing Java against Python would
show only that the two emitters agree with each other, which they trivially do,
since one generator produces both. The third participant is the generator's own
reading of the schemas: if either emitter drifts from that reading, or if the
committed code stops matching the schemas, the comparison fails.

    schemas/**/*.schema.json
             |
             v
      generator's type model  <-- authoritative here
         /            \\
        v              v
   Java (reflection)  Python (introspection)

Usage:
    python3 .github/scripts/contract_test.py
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / ".github" / "scripts"
JAVA_MODULE = ROOT / "contracts" / "java"
PYTHON_MODULE = ROOT / "contracts" / "python"
EXAMPLES = ROOT / "schemas" / "examples"
VECTORS = ROOT / "schemas" / "hashing" / "vectors.json"

# The contracts named in the M2 exit criteria. Every one must be exercised by the
# structural comparison, and the list is asserted rather than assumed so that
# deleting a contract cannot quietly reduce what is checked.
REQUIRED_COVERAGE = [
    "Graph",
    "GraphRun",
    "GraphNode",
    "NodeRun",
    "Agent",
    "Tool",
    "ToolRequest",
    "ToolResult",
    "ContextBundle",
    "ModelRequest",
    "ModelResponse",
    "ExecutionRequest",
    "ExecutionResult",
    "Checkpoint",
    "Approval",
    "Workspace",
]

# Value types that only ever appear nested inside another document. They are
# versioned by whatever contains them, and giving them their own schemaVersion
# would imply they can be stored or exchanged independently, which they cannot.
EMBEDDED_VALUE_TYPES = {"ArtifactRef", "Condition"}

problems: list[str] = []


def fail(message: str) -> None:
    problems.append(message)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# The three shape reports
# --------------------------------------------------------------------------


def generator_report() -> dict[str, dict]:
    codegen = load_module("codegen", SCRIPTS / "codegen.py")
    generator = codegen.Generator(codegen.load_schemas())
    generator.run()
    report: dict[str, dict] = {}
    for name, enum in generator.enums.items():
        report[name] = {"kind": "enum", "values": list(enum.values)}
    for name, record in generator.records.items():
        report[name] = {
            "kind": "record",
            "fields": [f.name for f in record.fields],
            "required": sorted(f.name for f in record.fields if f.required),
        }
    return report


def python_report() -> dict[str, dict]:
    sys.path.insert(0, str(PYTHON_MODULE))
    reserved = sys.modules["codegen"].PY_RESERVED
    models = load_module("aiplatform_contracts.models", PYTHON_MODULE / "aiplatform_contracts" / "models.py")
    report: dict[str, dict] = {}
    for name in models.__all__:
        obj = getattr(models, name)
        if isinstance(obj, type) and issubclass(obj, Enum):
            report[name] = {"kind": "enum", "values": [member.value for member in obj]}
        elif dataclasses.is_dataclass(obj):
            fields = dataclasses.fields(obj)

            def wire(field_name: str) -> str:
                # codegen suffixes an underscore when a JSON field name collides
                # with a Python keyword or builtin. Reverse it only for names that
                # were actually renamed, so a schema field genuinely ending in an
                # underscore would not be silently rewritten.
                stem = field_name[:-1]
                return stem if field_name.endswith("_") and stem in reserved else field_name

            report[name] = {
                "kind": "record",
                "fields": [wire(f.name) for f in fields],
                "required": sorted(
                    wire(f.name) for f in fields if f.default is dataclasses.MISSING
                ),
            }
    return report


def java_report(workdir: Path) -> dict:
    """Compile the generated Java plus the harness, then run it."""
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        fail("a JDK is required: javac and java were not found on PATH")
        return {}

    sources = sorted(str(p) for p in (JAVA_MODULE / "src").rglob("*.java"))
    classes = workdir / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    compile_result = subprocess.run(
        [javac, "-nowarn", "-d", str(classes), *sources],
        capture_output=True,
        text=True,
    )
    if compile_result.returncode != 0:
        fail(f"generated Java does not compile:\n{compile_result.stderr}")
        return {}

    run_result = subprocess.run(
        [java, "-cp", str(classes), "io.aiplatform.contracts.ConformanceHarness", str(ROOT)],
        capture_output=True,
        text=True,
    )
    if run_result.returncode != 0:
        fail(f"the Java conformance harness failed:\n{run_result.stderr}")
        return {}
    try:
        return json.loads(run_result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"the Java harness produced unparseable output: {exc}")
        return {}


# --------------------------------------------------------------------------
# Comparisons
# --------------------------------------------------------------------------


def compare_shapes(expected: dict[str, dict], actual: dict[str, dict], language: str) -> None:
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    for name in missing:
        fail(f"{language}: no type generated for {name}")
    for name in extra:
        fail(f"{language}: {name} exists but the schemas do not define it")
    for name in sorted(set(expected) & set(actual)):
        want, got = expected[name], actual[name]
        if want["kind"] != got["kind"]:
            fail(f"{language}: {name} is a {got['kind']}, expected a {want['kind']}")
            continue
        if want["kind"] == "enum":
            if want["values"] != got["values"]:
                fail(
                    f"{language}: {name} enum values differ\n"
                    f"      schema: {want['values']}\n"
                    f"      {language:<7}: {got['values']}"
                )
            continue
        if want["fields"] != got["fields"]:
            fail(
                f"{language}: {name} field names differ\n"
                f"      schema: {want['fields']}\n"
                f"      {language:<7}: {got['fields']}"
            )
        if want["required"] != got["required"]:
            fail(
                f"{language}: {name} required fields differ\n"
                f"      schema: {want['required']}\n"
                f"      {language:<7}: {got['required']}"
            )


def check_coverage(report: dict[str, dict]) -> None:
    for name in REQUIRED_COVERAGE:
        if name not in report:
            fail(f"coverage: {name} is named in the M2 exit criteria but no contract defines it")


def check_schema_versions(report: dict[str, dict]) -> None:
    """Every stored document carries schemaVersion; every wire message protocolVersion.

    ADR-0024 §5. Checked here rather than left to review because the rule is
    invisible in any single schema -- it is a property of the set.
    """
    for path in sorted((ROOT / "schemas").rglob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("type") != "object" or "properties" not in document:
            continue
        properties = document["properties"]
        title = document.get("title", path.name)
        if title in EMBEDDED_VALUE_TYPES:
            continue
        has_version = "schemaVersion" in properties or "protocolVersion" in properties
        if not has_version:
            fail(f"versioning: {title} carries neither schemaVersion nor protocolVersion")
            continue
        key = "schemaVersion" if "schemaVersion" in properties else "protocolVersion"
        if properties[key].get("const") != "1":
            fail(f"versioning: {title}.{key} is not const \"1\" (ADR-0024 §5)")
        if key not in document.get("required", []):
            fail(f"versioning: {title}.{key} is not required")


def check_python_round_trips() -> int:
    models = sys.modules["aiplatform_contracts.models"]
    checked = 0
    for example in sorted(EXAMPLES.glob("*.example.json")):
        document = json.loads(example.read_text(encoding="utf-8"))
        target = document.pop("$schema", None)
        document.pop("$comment", None)
        if not target:
            fail(f"{example.name}: example does not name its schema")
            continue
        schema = json.loads((example.parent / target).read_text(encoding="utf-8"))
        cls = getattr(models, schema["title"], None)
        if cls is None:
            fail(f"{example.name}: no Python model named {schema['title']}")
            continue
        try:
            parsed = cls.from_dict(document)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            fail(f"{example.name}: Python parse failed: {exc}")
            continue
        if parsed.to_dict() != document:
            fail(f"{example.name}: Python round trip is not identity")
        checked += 1
    return checked


def check_python_vectors() -> int:
    canonical = load_module("canonical", SCRIPTS / "canonical.py")
    suite = json.loads(VECTORS.read_text(encoding="utf-8"))
    for vector in suite["vectors"]:
        excluded = frozenset(vector.get("hashExclude", []))
        stripped = canonical.strip_excluded(vector["input"], excluded)
        produced = canonical.canonicalize(stripped)
        if produced != vector["canonical"]:
            fail(
                f"vector {vector['id']}: Python canonical form differs\n"
                f"      expected: {vector['canonical']}\n"
                f"      produced: {produced}"
            )
        digest = canonical.content_hash(vector["input"], excluded)
        if digest != vector["sha256"]:
            fail(f"vector {vector['id']}: Python digest {digest} != {vector['sha256']}")
    return len(suite["vectors"])


def check_java_results(report: dict) -> None:
    for name, result in report.get("examples", {}).items():
        if result.get("roundTrip") != "OK":
            fail(
                f"{name}: Java round trip is not identity\n"
                f"      expected: {result.get('expected')}\n"
                f"      actual:   {result.get('actual')}"
            )
    for vector in report.get("vectors", []):
        if not vector.get("canonicalMatches"):
            fail(
                f"vector {vector['id']}: Java canonical form differs\n"
                f"      produced: {vector.get('canonical')}"
            )
        if not vector.get("digestMatches"):
            fail(f"vector {vector['id']}: Java digest {vector.get('sha256')} does not match")


def main() -> int:
    expected = generator_report()
    check_coverage(expected)
    check_schema_versions(expected)

    actual_python = python_report()
    compare_shapes(expected, actual_python, "python")

    round_trips = check_python_round_trips()
    vectors = check_python_vectors()

    with tempfile.TemporaryDirectory(prefix="contract-test-") as tmp:
        report = java_report(Path(tmp))
        if report:
            compare_shapes(expected, report.get("types", {}), "java")
            check_java_results(report)

    if problems:
        print(f"contract-test: {len(problems)} problem(s)\n")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print(
        f"contract-test: {len(expected)} contract types agree across schemas, Java and "
        f"Python; {round_trips} examples round-trip in both languages; "
        f"{vectors} hashing vectors reproduce in both languages"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
