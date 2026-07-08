---
name: gateway-module-dev
description: Standard Hermes gateway module development workflow for invasive gateway source changes. Use when working on Hermes gateway source modifications, versioned patch sets, install/update/uninstall/verify/check-consistency scripts, hooks, IMPACT_MATRIX.md, CUSTOMIZATIONS.md, or any skill/module that must patch Hermes gateway behavior rather than only add SKILL.md knowledge.
---

# Gateway Module Dev

Use this skill to build installable Hermes gateway modules: skills that change gateway source code through versioned patches, install hooks, and provide reversible lifecycle scripts.

Do not encode module-specific behavior in this standard. The module owns its patches and behavioral tests; this skill owns the lifecycle pattern.

## Core Paradigm

Always anchor invasive gateway edits on:

1. **Git pristine anchor**: initialize or reuse a Git repository in the gateway source tree, create a stable `pristine` tag/commit before applying module patches, then commit the installed module state.
2. **Version detection**: detect the target Hermes/gateway version at install/update time and select `patches/<version>/series`.
3. **Versioned patches**: store one patch set per gateway version; never rely on a flat patch directory for new modules.

The canonical lifecycle:

```text
install:   detect version -> create pristine anchor -> apply patches/<version>/series -> install hooks -> verify
update:    save local changes -> reset to pristine -> apply patches/<version>/series -> restore compatible local changes -> verify
uninstall: reset to pristine -> remove hooks -> remove module profile/env markers
audit:     check-consistency.sh -> IMPACT_MATRIX review -> goal-oriented tests
```

## Standard Layout

Create gateway modules with this structure:

```text
module-name/
├── SKILL.md
├── scripts/
│   ├── install.sh
│   ├── update.sh
│   ├── uninstall.sh
│   ├── verify.sh
│   └── check-consistency.sh
├── patches/
│   ├── v0.18/
│   │   ├── series
│   │   └── 001-short-purpose.patch
│   └── v0.19/
│       ├── series
│       └── 001-short-purpose.patch
├── hooks/
├── CUSTOMIZATIONS.md
└── IMPACT_MATRIX.md
```

Copy templates from `references/templates/`:

- `references/templates/scripts/install.sh`
- `references/templates/scripts/update.sh`
- `references/templates/scripts/uninstall.sh`
- `references/templates/scripts/verify.sh`
- `references/templates/scripts/check-consistency.sh`
- `references/templates/CUSTOMIZATIONS.md`
- `references/templates/IMPACT_MATRIX.md`

After copying, replace `MODULE_NAME`, hook names, and module-specific behavior tests. `verify.sh` must not ship with the template `verify_user_visible_goals`; replace it with behavior tests that exercise the module's user-visible goals. Keep patch discovery and lifecycle logic `series`-driven.

## Script Rules

Every lifecycle script must be idempotent enough for interrupted installs and explicit enough to fail before damaging source state.

- `install.sh`: detect gateway source directory, detect Hermes version, find `patches/<version>/series`, create the pristine anchor if absent, `git apply --check` each patch before applying it, install hooks, run consistency and behavior verification. Support `--dry-run` to run only patch checks, and `--force` only for reviewed multi-module or pre-existing-commit cases.
- `update.sh`: delegate version detection to `install.sh --detect-version`; preserve uncommitted local edits by converting them to a pristine-based stash, return to the pristine anchor, apply the selected version patch set, attempt stash pop, reinstall hooks, and run verification. If stash pop conflicts, print the gateway path, `git status` command, and recovery commands.
- `uninstall.sh`: require evidence that this module was installed unless `--force` is passed, reset to the pristine anchor, remove hooks and module-owned env/config markers, then report remaining untracked files without deleting unknown user files.
- `verify.sh`: compile/import only as a smoke check; primary assertions must be goal-oriented user-visible behavior. The template must fail until `verify_user_visible_goals` is replaced.
- `check-consistency.sh`: check that `SKILL.md`, scripts, docs, and patch directories exist; patch directories have `series`; every series entry exists; every patch is referenced by exactly one version series; docs mention current patches; lifecycle scripts use `series` rather than hard-coded patch lists; hooks are paired with install/uninstall handling; template placeholders are gone; and `verify_user_visible_goals` is not empty. Warnings do not fail by default; pass `--strict` to treat warnings as errors.

## Git Pristine Workflow

Use a tag as the stable anchor because commit hashes vary by environment:

```bash
git -C "$GATEWAY_DIR" init
git -C "$GATEWAY_DIR" add -A
git -C "$GATEWAY_DIR" commit -m "pristine before ${MODULE_NAME}"
git -C "$GATEWAY_DIR" tag "${MODULE_NAME}/pristine"
```

If the gateway repo already exists, do not rewrite its history. If `${MODULE_NAME}/pristine` is absent, create it from the current unmodified gateway state. If the repo already has commits, prompt the user to confirm that current HEAD is pristine gateway source; in non-interactive environments require `--force` or `HERMES_ASSUME_PRISTINE=1`. If the tree is already patched or dirty, stop and ask for an explicit source tree or cleanup instruction.

Installed state should be a normal commit:

```bash
git -C "$GATEWAY_DIR" add -A
git -C "$GATEWAY_DIR" commit -m "${MODULE_NAME} installed for ${HERMES_VERSION}"
git -C "$GATEWAY_DIR" tag -f "${MODULE_NAME}/installed"
```

Uninstall and update reset only to the module pristine tag:

```bash
git -C "$GATEWAY_DIR" reset --hard "${MODULE_NAME}/pristine"
```

Never run destructive Git commands outside the resolved gateway source directory. Never reset a user repository unless the module pristine tag exists and the user intended to operate on that gateway tree.

Interrupted installs must be recoverable. `install.sh` writes `${MODULE_NAME}/installing` before patch application and deletes it only after `${MODULE_NAME}/installed` is written. On the next install, if `${MODULE_NAME}/pristine` exists, `${MODULE_NAME}/installed` is absent, and the module patches or installing tag are present, reset hard to pristine before retrying. `uninstall.sh --force` must also reset to pristine and remove hook/profile markers when only the pristine tag exists.

## Version Detection

Implement version detection in this order:

1. `HERMES_VERSION` env var, when set.
2. `VERSION` file in the gateway source root.
3. `pyproject.toml` project version, when present.
4. `python -m hermes --version`, `hermes --version`, or gateway CLI version output if available.
5. `git describe --tags --abbrev=0`.

Normalize to `vX.Y` or `vX.Y.Z` by stripping prefixes like `Hermes gateway ` and preserving a leading `v`. Patch directories must match the normalized value exactly, with fallback from `vX.Y.Z` to `vX.Y` only when explicitly implemented.

## Patch Rules

- Use one patch for one responsibility.
- Number patches in dependency order: `001-purpose.patch`, `002-purpose.patch`.
- Apply only by reading `patches/<version>/series`.
- Keep `series` entries as filenames, one per line; allow blank lines and `#` comments.
- Do not hard-code patch filenames in install/update scripts.
- When upstream changes break a patch, create or update only the affected version directory.

## Testing Rule

Tests must be goal-oriented. Do not test that a function, class, or marker exists unless that is only a small smoke check before behavior tests.

Good:

```text
Given a user sends /continue while queued messages exist,
the gateway drains the queue and does not route /continue to the agent.
```

Bad:

```text
Assert _drain_pending exists.
```

Every `verify.sh` assertion should map to user-visible behavior: command routing, rendered message text, hook side effects, env-controlled behavior, startup notification, queue behavior, error text, or persisted state.

After copying the template `verify.sh`, remove the sample comments and replace `verify_user_visible_goals` with behavior tests for the module. A copied template that still contains `MODULE_NAME`, example comments, or an empty/failing `verify_user_visible_goals` must fail verification and consistency checks.

## Anti-Sprawl Rules

Apply these on every module change:

1. **One in, one out**: for substantial net additions, look for equivalent dead code, obsolete patch hunks, or stale docs to remove.
2. **One patch, one responsibility**: split patches when a hunk serves a different user-visible goal.
3. **Quarterly audit**: run `scripts/check-consistency.sh`, review `CUSTOMIZATIONS.md`, delete obsolete patches/docs/hooks, and update `IMPACT_MATRIX.md`.

## IMPACT_MATRIX Rules

Before modifying a module, inspect `IMPACT_MATRIX.md` and identify affected columns. After modifying, update or explicitly confirm every checked file.

The matrix must include at least these change types:

- Add/remove/reorder patch
- Add/remove hook
- Add/remove env var or profile marker
- Change installed source behavior
- Change version support
- Change verification behavior
- Change lifecycle script behavior

Use the template at `references/templates/IMPACT_MATRIX.md`.

## Pitfalls

- **pyproject.toml version extraction**: Never use `sed` for extracting the version from `pyproject.toml`. Shell quoting makes the regex fragile — escaped single quotes inside single-quoted sed expressions always break. The template's `install.sh` uses a Python heredoc helper (`_py_extract_version`) with `\x27` (ASCII 39) to avoid all quoting issues.

## Reference Cases

For context on the origin of this pattern, read `references/existing-blueprints.md`. Treat referenced modules as examples only; do not copy their module-specific patch lists into new modules.

## Multi-Module Conflicts

When multiple gateway modules patch the same source files, install order matters:

1. **Check for existing modules:** before applying, compare `HEAD` to `${MODULE_NAME}/pristine`. Commits after pristine mean another module or manual gateway edits may be present.
2. **List installed modules:** show `git tag -l '*/installed'` and `git tag -l '*/pristine'` with module names normalized, so the operator can see what is already anchored.
3. **Patch conflict detection:** run `git apply --check` for every series entry before applying. If checks fail, stop before mutating the tree.
4. **Default resolution path:** install modules on a clean gateway tree, not stacked. If coexistence is unavoidable, ensure patches modify disjoint file regions and document overlap in `CUSTOMIZATIONS.md`.
5. **Force path:** `install.sh --force` may continue after the warning, but only after the operator has reviewed the listed modules and likely overlap. Manual conflict resolution should produce a new version-specific patch set instead of editing installed source ad hoc.

## Creating Patches

From zero, create a patch set like this:

```bash
mkdir -p "$MODULE_DIR/patches/v0.XX"
cd "$GATEWAY_DIR"
git reset --hard "${MODULE_NAME}/pristine"
# edit gateway source for one user-visible responsibility
git diff > "$MODULE_DIR/patches/v0.XX/001-description.patch"
printf '%s\n' 001-description.patch > "$MODULE_DIR/patches/v0.XX/series"
git apply --check "$MODULE_DIR/patches/v0.XX/001-description.patch"
```

For staged diffs, stage only one responsibility:

```bash
git add <files>
git diff --cached > "$MODULE_DIR/patches/v0.XX/001-description.patch"
```

For commit-oriented patch generation with metadata:

```bash
git add <files>
git commit -m "NNN: short purpose"
git format-patch -1 -o "$MODULE_DIR/patches/v0.XX/"
```

Rules:
- Stage ONLY the files belonging to one patch responsibility
- Use `git diff > patches/v0.XX/001-description.patch` for simple working-tree patches, or `git diff --cached` when you intentionally staged the exact hunk set
- Keep `patches/v0.XX/series` updated in dependency order, one patch filename per line
- Verify every patch applies cleanly against pristine: `git reset --hard "${MODULE_NAME}/pristine" && git apply --check path/to/patch`
- Never generate final patches from an unrelated dirty working tree

## Environment Awareness

`GATEWAY_DIR` defaults differ by deployment:

| Environment | Typical `GATEWAY_DIR` |
|---|---|
| Docker (Hermes official) | `/opt/hermes` |
| Docker (UGREEN NAS) | `/opt/hermes` inside container |
| Linux/macOS pip install | `~/.hermes/hermes-agent/` or venv site-packages |
| Git clone | wherever the repo was cloned |

Set `HERMES_GATEWAY_SRC` or `HERMES_GATEWAY_DIR` to override. The install script template defaults to `/opt/hermes` (Docker target). Non-Docker users must set the env var before running install.
