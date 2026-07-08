#!/usr/bin/env bash
set -euo pipefail

MODULE_NAME="${MODULE_NAME:-gateway-module-name}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATEWAY_DIR="${HERMES_GATEWAY_SRC:-${HERMES_GATEWAY_DIR:-/opt/hermes}}"
HOOKS_DIR="${HERMES_HOOKS_DIR:-$HOME/.hermes/hooks}"
PRISTINE_TAG="${MODULE_NAME}/pristine"
INSTALLED_TAG="${MODULE_NAME}/installed"
INSTALLING_TAG="${MODULE_NAME}/installing"
DRY_RUN=0
FORCE=0

die() { echo "[FAIL] $*" >&2; exit 1; }
warn() { echo "[WARN] $*" >&2; }
info() { echo "[INFO] $*"; }
ok() { echo "[OK] $*"; }

run_git() { git -C "$GATEWAY_DIR" "$@"; }

normalize_version() {
    local raw="$1"
    raw="${raw#Hermes gateway }"
    raw="${raw#hermes }"
    raw="${raw#v}"
    raw="$(printf '%s' "$raw" | grep -oE '[0-9]+(\.[0-9]+){1,2}' | head -n1 || true)"
    [[ -n "$raw" ]] || return 1
    printf 'v%s\n' "$raw"
}

# Uses a quoted heredoc + Python to avoid sed quoting nightmares.
# \x27 = single quote (ASCII 39), safe inside any quoting.
_py_extract_version() {
    local gateway_dir="$1"
    python3 - "$gateway_dir" << 'PYEOF'
import sys
try:
    with open(sys.argv[1] + '/pyproject.toml') as f:
        for line in f:
            import re
            m = re.match(r'^\s*version\s*=\s*["\x27]([^"\x27]*)["\x27]', line)
            if m:
                print(m.group(1))
                break
except Exception:
    pass
PYEOF
}

detect_version() {
    local raw=""
    if [[ -n "${HERMES_VERSION:-}" ]]; then normalize_version "$HERMES_VERSION" && return 0; fi
    if [[ -f "$GATEWAY_DIR/VERSION" ]]; then normalize_version "$(cat "$GATEWAY_DIR/VERSION")" && return 0; fi
    if [[ -f "$GATEWAY_DIR/pyproject.toml" ]]; then
        raw="$(_py_extract_version "$GATEWAY_DIR" 2>/dev/null)"
        [[ -n "$raw" ]] && normalize_version "$raw" && return 0
    fi
    raw="$(cd "$GATEWAY_DIR" && python -m hermes --version 2>/dev/null || true)"
    [[ -n "$raw" ]] && normalize_version "$raw" && return 0
    raw="$(hermes --version 2>/dev/null || true)"
    [[ -n "$raw" ]] && normalize_version "$raw" && return 0
    raw="$(run_git describe --tags --abbrev=0 2>/dev/null || true)"
    [[ -n "$raw" ]] && normalize_version "$raw" && return 0
    return 1
}

find_patch_dir() {
    local version="$1"
    local short="${version%.*}"
    for dir in "$MODULE_DIR/patches/$version" "$MODULE_DIR/patches/$short"; do
        [[ -f "$dir/series" ]] && { printf '%s\n' "$dir"; return 0; }
    done
    return 1
}

ensure_gateway_repo() {
    [[ -d "$GATEWAY_DIR" ]] || die "Gateway directory not found: $GATEWAY_DIR"
    if ! run_git rev-parse --git-dir >/dev/null 2>&1; then
        run_git init
        run_git config user.email "${MODULE_NAME}@local"
        run_git config user.name "${MODULE_NAME} installer"
    fi
}

confirm_pristine_source() {
    run_git rev-parse --verify HEAD >/dev/null 2>&1 || return 0
    if [[ "$FORCE" -eq 1 || "${HERMES_ASSUME_PRISTINE:-}" == "1" || "${HERMES_ASSUME_PRISTINE:-}" == "true" ]]; then
        warn "Using current HEAD as pristine because --force or HERMES_ASSUME_PRISTINE is set"
        return 0
    fi
    if [[ -t 0 ]]; then
        echo "[WARN] This repository already has commits."
        echo "[WARN] Confirm current HEAD is unmodified gateway source before tagging $PRISTINE_TAG."
        read -r -p "Create pristine tag from current HEAD? [y/N] " answer
        [[ "$answer" == "y" || "$answer" == "Y" ]] || die "Pristine tag creation cancelled"
        return 0
    fi
    die "Repository already has commits and $PRISTINE_TAG is missing. Re-run with --force or HERMES_ASSUME_PRISTINE=1 only if current HEAD is pristine gateway source."
}

ensure_pristine_anchor() {
    if run_git rev-parse -q --verify "refs/tags/$PRISTINE_TAG" >/dev/null; then
        ok "Pristine tag exists: $PRISTINE_TAG"
        return 0
    fi
    confirm_pristine_source
    if [[ -n "$(run_git status --porcelain)" ]]; then
        run_git add -A
        run_git commit -m "pristine before ${MODULE_NAME}" || die "Cannot create pristine commit"
    elif ! run_git rev-parse --verify HEAD >/dev/null 2>&1; then
        run_git commit --allow-empty -m "pristine before ${MODULE_NAME}"
    fi
    run_git tag "$PRISTINE_TAG"
    ok "Created pristine tag: $PRISTINE_TAG"
}

series_patches_applied() {
    local patch_dir="$1"
    local checked=0
    while IFS= read -r entry || [[ -n "$entry" ]]; do
        entry="${entry%%#*}"
        entry="$(printf '%s' "$entry" | xargs)"
        [[ -z "$entry" ]] && continue
        checked=$((checked + 1))
        local patch="$patch_dir/$entry"
        [[ -f "$patch" ]] || return 1
        run_git apply --reverse --check "$patch" >/dev/null 2>&1 || return 1
    done < "$patch_dir/series"
    [[ "$checked" -gt 0 ]]
}

recover_interrupted_install() {
    local patch_dir="$1"
    if ! run_git rev-parse -q --verify "refs/tags/$PRISTINE_TAG" >/dev/null; then
        return 0
    fi
    if run_git rev-parse -q --verify "refs/tags/$INSTALLED_TAG" >/dev/null; then
        die "Module already appears installed: $INSTALLED_TAG exists. Use update.sh or uninstall.sh."
    fi
    if run_git rev-parse -q --verify "refs/tags/$INSTALLING_TAG" >/dev/null || series_patches_applied "$patch_dir"; then
        warn "Detected interrupted install without $INSTALLED_TAG; resetting to $PRISTINE_TAG before retry"
        run_git reset --hard "$PRISTINE_TAG"
        run_git tag -d "$INSTALLING_TAG" >/dev/null 2>&1 || true
    fi
}

list_installed_modules() {
    local tags
    tags="$(run_git tag -l '*/installed' || true)"
    [[ -n "$tags" ]] || tags="$(run_git tag -l '*/pristine' || true)"
    [[ -n "$tags" ]] && printf '%s\n' "$tags" | sed 's#/\(installed\|pristine\)$##' | sort -u
}

ensure_no_other_module_commits() {
    local commits modules
    commits="$(run_git log --oneline "${PRISTINE_TAG}..HEAD" 2>/dev/null || true)"
    [[ -z "$commits" ]] && return 0
    modules="$(list_installed_modules || true)"
    warn "Gateway has commits after $PRISTINE_TAG. Other gateway modules or manual edits may already be installed."
    [[ -n "$modules" ]] && { warn "Detected module tags:"; printf '%s\n' "$modules" >&2; }
    if [[ "$FORCE" -eq 0 ]]; then
        die "Refusing to apply patches on a modified gateway tree. Re-run with --force only after reviewing possible conflicts, or reset to $PRISTINE_TAG and install modules from a clean tree."
    fi
    warn "Continuing because --force was provided"
}

apply_patch_series() {
    local patch_dir="$1"
    while IFS= read -r entry || [[ -n "$entry" ]]; do
        entry="${entry%%#*}"
        entry="$(printf '%s' "$entry" | xargs)"
        [[ -z "$entry" ]] && continue
        local patch="$patch_dir/$entry"
        [[ -f "$patch" ]] || die "Series entry not found: $patch"
        run_git apply --check "$patch" || die "Patch check failed: $entry"
        if [[ "$DRY_RUN" -eq 1 ]]; then
            ok "Patch check passed: $entry"
            continue
        fi
        run_git apply "$patch"
        ok "Applied $entry"
    done < "$patch_dir/series"
}

install_hooks() {
    [[ -d "$MODULE_DIR/hooks" ]] || { info "No hooks directory"; return 0; }
    mkdir -p "$HOOKS_DIR"
    find "$MODULE_DIR/hooks" -mindepth 1 -maxdepth 1 -type d | while IFS= read -r hook; do
        ln -sfn "$hook" "$HOOKS_DIR/$(basename "$hook")"
        ok "Installed hook $(basename "$hook")"
    done
}

commit_installed_state() {
    if [[ -n "$(run_git status --porcelain)" ]]; then
        run_git add -A
        run_git commit -m "${MODULE_NAME} installed for ${HERMES_VERSION_DETECTED}"
    fi
    run_git tag -f "$INSTALLED_TAG"
    run_git tag -d "$INSTALLING_TAG" >/dev/null 2>&1 || true
}

parse_args() {
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --detect-version) detect_version; exit 0 ;;
            --hooks-only) install_hooks; exit 0 ;;
            --dry-run) DRY_RUN=1 ;;
            --force) FORCE=1 ;;
            *) die "Unknown option: $1" ;;
        esac
        shift
    done
}

main() {
    parse_args "$@"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        [[ -d "$GATEWAY_DIR" ]] || die "Gateway directory not found: $GATEWAY_DIR"
        HERMES_VERSION_DETECTED="$(detect_version)" || die "Cannot detect Hermes version; set HERMES_VERSION"
        info "Detected Hermes version: $HERMES_VERSION_DETECTED"
        PATCH_DIR="$(find_patch_dir "$HERMES_VERSION_DETECTED")" || die "No patch set for $HERMES_VERSION_DETECTED"
        info "Using patch dir: $PATCH_DIR"
        apply_patch_series "$PATCH_DIR"
        ok "Dry run complete; no patches applied"
        return
    fi
    ensure_gateway_repo
    HERMES_VERSION_DETECTED="$(detect_version)" || die "Cannot detect Hermes version; set HERMES_VERSION"
    info "Detected Hermes version: $HERMES_VERSION_DETECTED"
    PATCH_DIR="$(find_patch_dir "$HERMES_VERSION_DETECTED")" || die "No patch set for $HERMES_VERSION_DETECTED"
    info "Using patch dir: $PATCH_DIR"
    recover_interrupted_install "$PATCH_DIR"
    ensure_pristine_anchor
    ensure_no_other_module_commits
    run_git tag -f "$INSTALLING_TAG"
    apply_patch_series "$PATCH_DIR"
    install_hooks
    commit_installed_state
    [[ -x "$MODULE_DIR/scripts/check-consistency.sh" ]] && "$MODULE_DIR/scripts/check-consistency.sh"
    [[ -x "$MODULE_DIR/scripts/verify.sh" ]] && "$MODULE_DIR/scripts/verify.sh"
    ok "Installation complete"
}

main "$@"
