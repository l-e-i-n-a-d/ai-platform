# Summary

<!-- What changes, and why. Link the Jira issue if there is one. -->

## Architectural impact

<!--
Tick what applies. If this change contradicts an accepted ADR, stop and raise the
ADR change first — the decisions are binding on every component, and silently
diverging from them is how the documentation drifted before.
-->

- [ ] This change is consistent with the accepted ADRs in `docs/decisions/`.
- [ ] This change introduces a new architectural decision, and an ADR is included.
- [ ] This change supersedes an existing ADR (which one, and is it marked Superseded?).
- [ ] No architectural impact.

**ADRs affected:** <!-- e.g. ADR-0005, ADR-0013, or "none" -->

## Documentation

- [ ] Component documentation under `docs/architecture/` is updated, or unaffected.
- [ ] `.github/copilot-instructions.md` and `CLAUDE.md` still reflect reality.
      *(These steer AI coding agents. If they go stale, future automated changes
      reintroduce decisions we deliberately removed.)*
- [ ] Implementation status is described honestly — nothing planned is described as
      implemented (see `.github/copilot-instructions.md` section 25).

## Verification

<!--
What did you actually run? `python3 .github/scripts/doclint.py` at minimum for
documentation changes. For code, name the targeted test or build command and its
result — not "should work".
-->
