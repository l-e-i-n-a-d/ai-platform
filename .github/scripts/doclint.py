#!/usr/bin/env python3
"""Documentation consistency checks for the AI Engineering Platform.

This repository is documentation-first: the architecture lives in Markdown and, until
the control plane exists, nothing else enforces that it stays internally consistent.
These checks exist because the documentation *did* drift — diagrams contradicted
decisions, an ADR referenced states another ADR had not defined — and the drift was
only found by a manual review months later.

The checks are deliberately cheap and boring. They verify structure and cross-
references, not prose quality. Standard library only, so CI needs no dependencies.

Run locally with:

    python3 .github/scripts/doclint.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "docs" / "decisions"

SKIP_DIRS = {".git", "node_modules", "target", "__pycache__", ".venv"}

# Technologies excluded by explicit architectural decision. If one reappears outside a
# document that explains the exclusion, it is almost certainly drift.
FORBIDDEN_TERMS = {
    "PostgreSQL": "excluded technology — see ADR-0007 and copilot-instructions.md section 4",
    "Kafka": "excluded technology — see copilot-instructions.md section 4",
}

# Documents whose job is to explain the exclusions.
FORBIDDEN_ALLOWLIST = {
    ".github/copilot-instructions.md",
    "ARCHITECTURE.md",
    "CLAUDE.md",
    "PRINCIPLES.md",
    "docs/decisions/0007-operational-persistence-and-local-first-storage.md",
}

REQUIRED_ADR_SECTIONS = ("## Context", "## Decision", "## Consequences")

failures: list[str] = []


def fail(path: Path, message: str) -> None:
    failures.append(f"{path.relative_to(ROOT)}: {message}")


def markdown_files() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.md") if not any(part in SKIP_DIRS for part in p.parts)
    )


def adr_files() -> list[Path]:
    return sorted(DECISIONS.glob("[0-9][0-9][0-9][0-9]-*.md"))


def strip_code_blocks(text: str) -> str:
    """Remove fenced blocks so illustrative examples do not trigger prose checks."""
    return re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)


def status_of(text: str) -> str | None:
    match = re.search(r"^## Status\s*\n+(.+)$", text, flags=re.M)
    return match.group(1).strip() if match else None


def check_fences(path: Path, text: str) -> None:
    count = len(re.findall(r"^```", text, flags=re.M))
    if count % 2 != 0:
        fail(path, f"unbalanced code fences: found {count}, expected an even number")


def check_relative_links(path: Path, text: str) -> None:
    for match in re.finditer(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text):
        target = match.group(1).split("#")[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not (path.parent / target).exists():
            fail(path, f"broken relative link: {target}")


def check_forbidden_terms(path: Path, text: str) -> None:
    if str(path.relative_to(ROOT)) in FORBIDDEN_ALLOWLIST:
        return
    prose = strip_code_blocks(text)
    for term, reason in FORBIDDEN_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", prose):
            fail(path, f"mentions '{term}' — {reason}")


def check_adr_references(path: Path, text: str, known: set[str]) -> None:
    for match in re.finditer(r"\bADR-(\d{4})\b", text):
        number = match.group(1)
        if number not in known:
            fail(path, f"references ADR-{number}, which does not exist")


def check_adr_structure(path: Path, text: str) -> None:
    number = path.name[:4]

    if not re.match(rf"^# ADR-{number}: \S", text):
        fail(path, f"must start with '# ADR-{number}: <title>'")

    status = status_of(text)
    if status is None:
        fail(path, "missing a '## Status' section")
    elif not status.startswith(("Proposed", "Accepted", "Superseded", "Rejected", "Deprecated")):
        fail(path, f"unrecognised status: {status!r}")

    for section in REQUIRED_ADR_SECTIONS:
        if section not in text:
            fail(path, f"missing a '{section}' section")

    if "## Alternatives" not in text:
        fail(path, "missing an '## Alternatives Considered' section")


def check_adr_index() -> None:
    """The index and the filesystem must agree on which ADRs exist and their status."""
    index_path = DECISIONS / "README.md"
    index_text = index_path.read_text(encoding="utf-8")

    listed: dict[str, str] = {}
    for match in re.finditer(r"^\|\s*(?:\[)?(\d{4})\)?\]?[^|]*\|([^|]+)\|([^|]+)\|", index_text, flags=re.M):
        listed[match.group(1)] = match.group(3).strip().replace("*", "")

    on_disk = {p.name[:4]: p for p in adr_files()}

    for number, adr_path in on_disk.items():
        if number not in listed:
            fail(index_path, f"ADR {number} exists on disk but is not listed in the index")
            continue
        if f"({adr_path.name})" not in index_text:
            fail(index_path, f"ADR {number} is listed but does not link to {adr_path.name}")

        file_status = (status_of(adr_path.read_text(encoding="utf-8")) or "").split("—")[0].strip()
        if file_status and file_status.lower() not in listed[number].lower():
            fail(
                index_path,
                f"ADR {number} status mismatch: index says {listed[number]!r}, "
                f"the ADR says {file_status!r}",
            )

    for number, status in listed.items():
        if number not in on_disk and "planned" not in status.lower():
            fail(index_path, f"index lists ADR {number} as {status!r} but no file exists")


def main() -> int:
    known_adrs = {p.name[:4] for p in adr_files()}
    if not known_adrs:
        print("doclint: no ADRs found — is docs/decisions/ missing?", file=sys.stderr)
        return 1

    files = markdown_files()
    for path in files:
        text = path.read_text(encoding="utf-8")

        check_fences(path, text)
        check_relative_links(path, text)
        check_forbidden_terms(path, text)
        check_adr_references(path, text, known_adrs)

        if path.parent == DECISIONS and re.match(r"^\d{4}-", path.name):
            check_adr_structure(path, text)

    check_adr_index()

    if failures:
        print(f"doclint: {len(failures)} problem(s) across {len(files)} Markdown files\n")
        for failure in sorted(failures):
            print(f"  {failure}")
        print("\nThese conventions are described in CONTRIBUTING.md.")
        return 1

    print(f"doclint: {len(files)} Markdown files checked, {len(known_adrs)} ADRs, no problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
