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

After copying, replace `MODULE_NAME`, hook names, and module-specific behavior tests. Keep patch discovery and lifecycle logic `series`-driven.

## Script Rules

Every lifecycle script must be idempotent enough for interrupted installs and explicit enough to fail before damaging source state.

- `install.sh`: detect gateway source directory, detect Hermes version, find `patches/<version>/series`, create the pristine anchor if absent, `git apply --check` each patch before applying it, install hooks, run consistency and behavior verification.
- `update.sh`: preserve uncommitted local edits with a named stash, return to the pristine anchor, apply the selected version patch set, reinstall hooks, run verification, then attempt stash pop and report conflicts clearly.
- `uninstall.sh`: require evidence that this module was installed, reset to the pristine anchor, remove hooks and module-owned env/profile markers, then report remaining untracked files without deleting unknown user files.
- `verify.sh`: compile/import only as a smoke check; primary assertions must be goal-oriented user-visible behavior.
- `check-consistency.sh`: check that patch directories have `series`, every series entry exists, every patch is referenced by exactly one version series, docs mention current patches, lifecycle scripts use `series` rather than hard-coded patch lists, hooks are paired with install/uninstall handling, and IMPACT_MATRIX exists.

## Git Pristine Workflow

Use a tag as the stable anchor because commit hashes vary by environment:

```bash
git -C "$GATEWAY_DIR" init
git -C "$GATEWAY_DIR" add -A
git -C "$GATEWAY_DIR" commit -m "pristine before ${MODULE_NAME}"
git -C "$GATEWAY_DIR" tag "${MODULE_NAME}/pristine"
```

If the gateway repo already exists, do not rewrite its history. If `${MODULE_NAME}/pristine` is absent, create it from the current unmodified gateway state. If the tree is already patched or dirty, stop and ask for an explicit source tree or cleanup instruction.

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

## Reference Cases

For context on the origin of this pattern, read `references/existing-blueprints.md`. Treat referenced modules as examples only; do not copy their module-specific patch lists into new modules.
