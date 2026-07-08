#!/usr/bin/env bash
set -euo pipefail

MODULE_NAME="${MODULE_NAME:-gateway-module-name}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATEWAY_DIR="${HERMES_GATEWAY_SRC:-${HERMES_GATEWAY_DIR:-/opt/hermes}}"
PRISTINE_TAG="${MODULE_NAME}/pristine"
STASH_NAME="${MODULE_NAME}-pre-update-$(date +%Y%m%d%H%M%S)"

die() { echo "[FAIL] $*" >&2; exit 1; }
ok() { echo "[OK] $*"; }
info() { echo "[INFO] $*"; }
run_git() { git -C "$GATEWAY_DIR" "$@"; }

local_detect_version() {
    if [[ -x "$MODULE_DIR/scripts/install.sh" ]]; then
        "$MODULE_DIR/scripts/install.sh" --detect-version 2>/dev/null && return 0
    fi
    if [[ -n "${HERMES_VERSION:-}" ]]; then printf '%s\n' "$HERMES_VERSION"; return 0; fi
    if [[ -f "$GATEWAY_DIR/VERSION" ]]; then sed -n 's/.*\([0-9][0-9]*\.[0-9][^[:space:]]*\).*/v\1/p' "$GATEWAY_DIR/VERSION" | head -n1; return 0; fi
    git -C "$GATEWAY_DIR" describe --tags --abbrev=0 2>/dev/null | sed 's/^/v/; s/^vv/v/' && return 0
}

find_patch_dir() {
    local version="$1"
    local short="${version%.*}"
    for dir in "$MODULE_DIR/patches/$version" "$MODULE_DIR/patches/$short"; do
        [[ -f "$dir/series" ]] && { printf '%s\n' "$dir"; return 0; }
    done
    return 1
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

main() {
    [[ -d "$GATEWAY_DIR" ]] || die "Gateway directory not found: $GATEWAY_DIR"
    run_git rev-parse -q --verify "refs/tags/$PRISTINE_TAG" >/dev/null || die "Missing pristine tag: $PRISTINE_TAG"

    local version patch_dir
    version="$(local_detect_version)"
    [[ -n "$version" ]] || die "Cannot detect Hermes version; set HERMES_VERSION"
    patch_dir="$(find_patch_dir "$version")" || die "No patch set for $version"

    if [[ -n "$(run_git status --porcelain)" ]]; then
        run_git stash push -u -m "$STASH_NAME"
        info "Saved local changes in stash: $STASH_NAME"
    fi

    run_git reset --hard "$PRISTINE_TAG"
    apply_patch_series "$patch_dir"
    run_git add -A
    run_git commit -m "${MODULE_NAME} updated for ${version}" || true
    run_git tag -f "${MODULE_NAME}/installed"

    [[ -x "$MODULE_DIR/scripts/install.sh" ]] && "$MODULE_DIR/scripts/install.sh" --hooks-only || true
    [[ -x "$MODULE_DIR/scripts/check-consistency.sh" ]] && "$MODULE_DIR/scripts/check-consistency.sh"
    [[ -x "$MODULE_DIR/scripts/verify.sh" ]] && "$MODULE_DIR/scripts/verify.sh"

    if run_git stash list | grep -q "$STASH_NAME"; then
        run_git stash pop || die "Stash pop conflicted. Resolve conflicts in $GATEWAY_DIR, then rerun verify."
    fi
    ok "Update complete"
}

main "$@"
