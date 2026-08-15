# ADR-0023: Multi-Repository Workspace Layout and Path Scoping

## Status

Accepted — 2026-08-15

Closes OQ-07 and resolves DEF-02 from `docs/contracts/v1-domain-contracts.md`. Refines the
workspace contract of ADR-0003 §1/§6, the isolation model of ADR-0006, and the `pathScope`
component of capability grants in ADR-0005 §4. Uses the repository identity rule of ADR-0014 §1.

---

## Context

Cross-repository change is an explicit platform goal: a Jira issue that alters a Quarkus API and
the Angular client that consumes it is the flagship benchmark in `EVALUATION.md`. Accordingly
`GraphRun.repositories[]`, `WorkspaceSpec.repositories[]` and `CapabilityGrant.repositoryScope[]`
are all plural.

But nothing states how several repositories occupy one workspace. No document defines the
directory layout, how `cwd` is rooted, or what a workspace-relative path means when there is more
than one repository.

`CapabilityGrant.pathScope` is consequently ambiguous, and dangerously so. It is a flat set of
globs over one unqualified namespace:

```json
"repositoryScope": ["repo_orderservice", "repo_webclient"],
"pathScope": { "allow": ["src/**"] }
```

With two repositories materialised, `src/**` matches `src/` in *both*. A grant intended to permit
writes to the service also permits writes to the client. The authorization decision is made on a
string that does not identify what it is authorising.

This is a privilege-boundary defect, not a modelling inelegance. ADR-0005 builds an authorization
choke point whose whole purpose is that a grant states exactly what an attempt may touch, and
`pathScope` is the part of the grant that constrains the filesystem. An ambiguous `pathScope`
means an agent working on one repository can modify another in the same run — including its CI
configuration, its build scripts and its instruction files.

The checkpoint format depends on the answer as well: `workspaceState.repositories[].patchSeries`
already attributes patches per repository, and that attribution only makes sense against a defined
layout.

---

## Decision

### 1. One directory per repository, named by `repositoryId`

```text
<workspace root>/
  repo_orderservice/        a complete checkout
  repo_webclient/           a complete checkout
```

The workspace root contains nothing but these directories. Every repository is a full, independent
checkout at its own `commitSha`.

Directories are named by `repositoryId`, not by repository name or remote path. ADR-0014 §1
already requires `repositoryId` to be platform-assigned and never derived from the remote URL,
which gives three properties that matter here: names cannot collide, the directory name cannot be
influenced by anyone who can name a remote, and the layout cannot change because someone renamed a
repository upstream.

The absolute location of the workspace root is **not part of any contract**. ADR-0003 §3 makes
`workspaceId` opaque and states that anything parsing it is a defect. Only the relative structure
below the root is contractual.

### 2. Every contract path is workspace-relative and canonical

A path appearing in any contract — grant, tool input, checkpoint, audit record — must satisfy all
of:

| Rule | Rejects |
|---|---|
| POSIX separators only | `src\main` |
| No leading separator | `/etc/passwd` |
| No `.` or `..` segment | `repo_a/../repo_b/x` |
| No empty segment | `repo_a//x` |
| No NUL or control characters | embedded `\u0000` |
| Unicode NFC | visually identical non-NFC duplicates |
| First segment is a `repositoryId` | `src/main/java/...` |

Paths are **rejected, never normalised**. A path that is not already canonical is refused with an
error rather than rewritten into a canonical one.

This is the security-critical choice in the decision. Path-normalisation routines are a recurring
source of traversal bypasses, because the check and the normalisation can disagree — the canonical
form used for the authorization decision differs from the form eventually passed to the filesystem.
Refusing non-canonical input removes the gap entirely: there is exactly one spelling of any path,
and it is the one that was authorised. The cost is an occasional error for a caller that could
have been accommodated, which is the right trade.

### 3. `pathScope` is keyed by repository

```json
"repositoryScope": ["repo_orderservice"],
"pathScope": {
  "repo_orderservice": {
    "allow": ["src/main/java/**", "src/test/java/**"],
    "deny":  ["**/*.env", "src/main/resources/secrets/**"]
  }
}
```

Globs inside an entry are **repository-relative**: `src/main/java/**` means that path inside
`repo_orderservice` and cannot mean it inside any other repository.

The keys of `pathScope` must equal `repositoryScope` exactly. A grant therefore cannot mention a
repository it does not scope, and cannot scope a repository whose paths it does not constrain.

This is what makes DEF-02 structurally impossible rather than merely discouraged. Under the flat
model, "a grant for repository A must not permit writes to repository B" was a property of the
glob strings, enforceable only by review. Under the keyed model there is no string that expresses
the mistake: authority for B is not representable in a grant that does not scope B. A rule that
cannot be written wrong does not need to be reviewed for being written wrong.

### 4. Authorization is default-deny and evaluated in a fixed order

For a path `P` in a grant `G`:

```text
1. split P into (repositoryId R, remainder T)
2. R ∈ G.repositoryScope            otherwise DENY
3. T matches any glob in pathScope[R].deny    → DENY
4. T matches any glob in pathScope[R].allow   → ALLOW
5. otherwise                                  → DENY
```

Deny is evaluated before allow, and an absent match denies. Both were already the intent of
ADR-0005; stating the order here removes the possibility of two components implementing it
differently.

Glob semantics are fixed to avoid a second ambiguity: `*` matches within one segment and does not
cross `/`; `**` matches zero or more whole segments; there is no brace expansion and no regular
expression syntax. A restricted glob language is easier to reason about at a privilege boundary
than an expressive one, and neither `**` nor `*` can escape the repository directory because the
repository is selected before the glob is applied.

### 5. Symlinks may not leave their repository

ADR-0006 and INV-86 already refuse symlinks that escape the workspace, at materialisation and at
write time. That is now insufficient: a symlink from `repo_a/link` to `../repo_b/src` stays inside
the workspace while defeating §3 entirely.

Symlinks are therefore confined to their own repository directory. A symlink whose resolved target
leaves the repository that contains it is refused at materialisation and rejected at write time.

Enforcement is by resolved real path, not by inspecting the link text, because a chain of
individually innocuous links can leave the repository while no single link appears to.

### 6. `cwd` is rooted at the workspace, not at a repository

`ExecutionRequest.cwd` remains workspace-relative and must name a repository directory or a path
beneath one. A command intended to build one repository runs with `cwd = "repo_orderservice"`.

Keeping `cwd` workspace-rooted rather than repository-rooted means a single rule governs every
path in every contract. A cross-repository command — a script that compares an API contract with
its client — remains expressible, and remains subject to the same grant.

### 7. Checkpoints and artifacts are already repository-attributed

`Checkpoint.workspaceState.repositories[]` carries `repoRef`, `baseSha` and `patchSeries` per
repository. That structure was already correct and needs no change; this decision supplies the
layout that gives it meaning.

Patches are repository-relative, matching how Git produces them, so a patch series can be applied
inside the repository directory without rewriting paths. Reconstruction is therefore: create the
root, materialise each repository into `<repositoryId>/` at `baseSha`, apply that repository's
patch series inside it.

### 8. The layout is executor-independent

Nothing above names a host path, a mount, a volume or a container. The contract fixes the
structure below an opaque root, and ADR-0003 §6 already guarantees that workspace state is a
function of `(repoRef, baseSha, patchSeries)` held in durable state.

A future Kubernetes executor materialises the same relative structure into whatever volume it
chooses. Graph definitions, agents, grants and tool inputs are unchanged, because none of them can
observe where the root is. This is the property ADR-0003 exists to protect, and this decision is
careful not to spend it.

---

## Alternatives Considered

**Flat globs with a mandatory `<repositoryId>/` prefix.** The recommendation originally recorded
against OQ-07, and rejected on reflection. It is expressible but not enforceable in the schema: the
constraint "the first segment must be a repository in `repositoryScope`" is a cross-field rule that
JSON Schema cannot state, so it would be checked only at runtime, in one component, by code that
could be wrong. The keyed map makes the same rule structural.

**One repository per workspace, with several workspaces per run.** Simplest isolation, and
rejected because it makes the platform's flagship benchmark impossible: a command cannot compare
an API contract with its client if they are never present together. It would also multiply the
lease, checkpoint and reconstruction machinery of ADR-0003 §7 by the repository count.

**Name directories by repository name or `owner/repo`.** Rejected. Names collide across
organisations, change upstream, and are attacker-influenceable in the sense that matters — a path
segment derived from an external system is a poor foundation for an authorization decision.
ADR-0014 §1 already forbids deriving `repositoryId` from the remote for this reason.

**Normalise paths instead of rejecting non-canonical ones.** Rejected. Normalisation before
authorization is the standard traversal-bypass pattern; the only reliable defence is to have one
accepted spelling.

**Allow symlinks anywhere inside the workspace.** Rejected: it reintroduces cross-repository
access below the authorization layer, where nothing would record that it happened.

---

## Consequences

- `CapabilityGrant.pathScope` changes from `{allow, deny}` to a map keyed by `repositoryId`. The
  `pathScope` definition in `common.schema.json` becomes the per-repository entry type.
- A grant is invalid unless `pathScope` keys equal `repositoryScope`, checked at mint time.
- Tool inputs naming paths inherit the canonical-path rules, and tool `inputSchema`s that accept
  paths should use the shared definition rather than a bare string.
- The executor gains materialisation-time and write-time symlink containment per repository.
- Single-repository runs are unaffected in substance but gain one path segment: `src/main/java/X`
  becomes `repo_x/src/main/java/X`. Contract examples change accordingly.
- The workspace reconstruction procedure of ADR-0003 §6 is now fully specified.
- Nothing about the layout is visible to a future Kubernetes executor beyond the relative
  structure, so executor substitutability is preserved.

---

## Security / Operational Impact

This decision closes a privilege-boundary defect. Before it, a grant scoped to one repository
authorised identical paths in every repository in the workspace. The practical exploit needs no
sophistication: an agent working on the service repository writes to `.github/workflows/` — the
grant permits it, because the glob never said which repository — and CI in a second repository now
runs attacker-influenced configuration on the next push.

Three properties are added, in decreasing order of strength:

1. **Structural.** Authority for a repository outside `repositoryScope` cannot be expressed in a
   grant. This is the durable defence, because it survives implementation mistakes.
2. **Canonical-only paths.** One spelling per path removes the check/use gap that traversal
   defences usually fall through.
3. **Symlink containment per repository.** Closes the below-the-contract route to the same result,
   enforced on resolved real paths so link chains cannot launder it.

The layout is also what makes ADR-0006's credential-free workspace meaningful in a multi-repository
run: material excluded from one repository by `contextPolicy.excludePaths` (ADR-0014 §11) is not
reachable through a sibling repository's grant.

Operationally, run-scoped workspaces containing several full checkouts consume more disk. ADR-0003
§6 keeps this recoverable rather than precious: a collected workspace is reconstructible from
durable state, so reclaiming space is safe.

---

## Follow-up

- Change `pathScope` in `common.schema.json` and `CapabilityGrant` to the keyed form, and add the
  canonical relative-path definition.
- Add the `pathScope` keys ≡ `repositoryScope` check, with an invalid example that proves it.
- Update `ExecutionRequest.cwd` documentation with the repository-rooted rule.
- Update `docs/architecture/execution-plane.md` and `security-model.md` with the layout, the
  evaluation order and symlink containment.
- Update contract examples to repository-qualified paths.
- ADR-0006 — symlink containment is tightened from workspace scope to repository scope.
- ADR-0005 §4 — `pathScope` shape is superseded by §3 here.
