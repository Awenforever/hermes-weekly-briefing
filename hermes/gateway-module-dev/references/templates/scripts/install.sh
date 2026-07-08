#!/usr/bin/env bash
set -euo pipefail

MODULE_NAME="${MODULE_NAME:-gateway-module-name}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATEWAY_DIR="${HERMES_GATEWAY_SRC:-${HERMES_GATEWAY_DIR:-/opt/hermes}}"
HOOKS_DIR="${HERMES_HOOKS_DIR:-$HOME/.hermes/hooks}"
PRISTINE_TAG="${MODULE_NAME}/pristine"
INSTALLED_TAG="${MODULE_NAME}/installed"

die() { echo "[FAIL] $*" >&2; exit 1; }
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

detect_version() {
    local raw=""
    if [[ -n "${HERMES_VERSION:-}" ]]; then normalize_version "$HERMES_VERSION" && return 0; fi
    if [[ -f "$GATEWAY_DIR/VERSION" ]]; then normalize_version "$(cat "$GATEWAY_DIR/VERSION")" && return 0; fi
    if [[ -f "$GATEWAY_DIR/pyproject.toml" ]]; then
        raw="$(sed -n 's/^[[:space:]]*version[[:space:]]*=[[:space:]]*["'\\'']\([^"'\\'']*\)["'\\''].*/\1/p' "$GATEWAY_DIR/pyproject.toml" | head -n1)"
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

ensure_pristine_anchor() {
    if run_git rev-parse -q --verify "refs/tags/$PRISTINE_TAG" >/dev/null; then
        ok "Pristine tag exists: $PRISTINE_TAG"
        return 0
    fi
    if [[ -n "$(run_git status --porcelain)" ]]; then
        run_git add -A
        run_git commit -m "pristine before ${MODULE_NAME}" || die "Cannot create pristine commit"
    elif ! run_git rev-parse --verify HEAD >/dev/null 2>&1; then
        run_git commit --allow-empty -m "pristine before ${MODULE_NAME}"
    fi
    run_git tag "$PRISTINE_TAG"
    ok "Created pristine tag: $PRISTINE_TAG"
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
}

main() {
    if [[ "${1:-}" == "--detect-version" ]]; then
        detect_version
        return
    fi
    if [[ "${1:-}" == "--hooks-only" ]]; then
        install_hooks
        return
    fi
    ensure_gateway_repo
    HERMES_VERSION_DETECTED="$(detect_version)" || die "Cannot detect Hermes version; set HERMES_VERSION"
    info "Detected Hermes version: $HERMES_VERSION_DETECTED"
    PATCH_DIR="$(find_patch_dir "$HERMES_VERSION_DETECTED")" || die "No patch set for $HERMES_VERSION_DETECTED"
    info "Using patch dir: $PATCH_DIR"
    ensure_pristine_anchor
    apply_patch_series "$PATCH_DIR"
    install_hooks
    commit_installed_state
    [[ -x "$MODULE_DIR/scripts/check-consistency.sh" ]] && "$MODULE_DIR/scripts/check-consistency.sh"
    [[ -x "$MODULE_DIR/scripts/verify.sh" ]] && "$MODULE_DIR/scripts/verify.sh"
    ok "Installation complete"
}

main "$@"
