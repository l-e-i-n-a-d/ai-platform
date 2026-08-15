# Contributing

This repository is in the architectural scaffold phase. Most changes are still changes to
*documentation*, and documentation here is binding: the ADRs in `docs/decisions/` constrain
every component that will later be built.

## Before a significant change

Read, in order:

1. [CLAUDE.md](CLAUDE.md)
2. [ARCHITECTURE.md](ARCHITECTURE.md)
3. [PRINCIPLES.md](PRINCIPLES.md)
4. [ROADMAP.md](ROADMAP.md)
5. the relevant ADRs in [docs/decisions/](docs/decisions/README.md)

If implementation and documentation disagree, that is a finding. Say so and propose the
correction rather than quietly following whichever one is nearer to hand.

## For architectural changes

1. Describe the problem.
2. Identify the affected components.
3. Consider alternatives, and record the ones you rejected along with why.
4. Record the decision as an ADR when it is significant.
5. Update the component documentation under `docs/architecture/`.
6. Implement incrementally.
7. Add tests.
8. Update implementation status honestly.

Prefer small, independently verifiable changes. Do not introduce speculative infrastructure
or bypass platform security and policy boundaries.

## Working with ADRs

An ADR is required when a change affects a component boundary, a contract between
components, the security model, the persistence model, or the set of technologies in use.

- Copy the template at the bottom of [docs/decisions/README.md](docs/decisions/README.md).
- Use the next free four-digit number and a descriptive slug:
  `docs/decisions/0019-some-decision.md`.
- Every ADR needs `## Status`, `## Context`, `## Decision`, `## Alternatives Considered`
  and `## Consequences`.
- Add a row to the index table in `docs/decisions/README.md`. The status in the index and
  the status in the ADR must match — CI checks this.
- Never edit an accepted decision into a different decision. Write a new ADR and mark the
  old one `Superseded by ADR-XXXX`. The history of *why* is the point of the format.

## Keeping the AI instruction files current

`.github/copilot-instructions.md` and `CLAUDE.md` are read by AI coding agents at the start
of every session. If they go stale, future automated changes will confidently reintroduce
things we deliberately removed. Treat them as part of the change, not as follow-up work.

## Checks

Documentation consistency is enforced by a standard-library Python script — no dependencies
to install:

```bash
python3 .github/scripts/doclint.py
```

It verifies:

- code fences are balanced
- relative links resolve to files that exist
- `ADR-XXXX` references point at ADRs that exist
- ADRs have the required sections and a recognised status
- the ADR index and the filesystem agree on which ADRs exist and their status
- documents do not reintroduce excluded technologies

The contract schemas in [`schemas/`](schemas/README.md) have their own check:

```bash
python3 .github/scripts/schemalint.py
```

It verifies `$id`/path agreement, `$ref` resolution and closed object schemas, and validates
the example documents — including `schemas/examples/invalid/`, where each document must be
rejected *for the specific reason it declares*. That last part is what makes a deleted
security constraint fail loudly rather than silently.

Both run in CI via [.github/workflows/docs.yml](.github/workflows/docs.yml).

These checks catch structure, not judgement. They will not tell you that a decision is
wrong, only that the documentation is inconsistent with itself.
