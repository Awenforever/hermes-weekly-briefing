#!/usr/bin/env bash
set -euo pipefail

MODULE_NAME="${MODULE_NAME:-gateway-module-name}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATEWAY_DIR="${HERMES_GATEWAY_SRC:-${HERMES_GATEWAY_DIR:-/opt/hermes}}"
PRISTINE_TAG="${MODULE_NAME}/pristine"
STASH_NAME="${MODULE_NAME}-pre-update-$(date +%Y%m%d%H%M%S)"
TEMP_STASH_NAME="${MODULE_NAME}-old-installed-edits-$(date +%Y%m%d%H%M%S)"
STASH_REF=""

die() { echo "[FAIL] $*" >&2; exit 1; }
warn() { echo "[WARN] $*" >&2; }
ok() { echo "[OK] $*"; }
info() { echo "[INFO] $*"; }
run_git() { git -C "$GATEWAY_DIR" "$@"; }

detect_version() {
    [[ -x "$MODULE_DIR/scripts/install.sh" ]] || die "Missing executable install.sh for version detection"
    "$MODULE_DIR/scripts/install.sh" --detect-version
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

revert_current_patches() {
    run_git reset --hard "$PRISTINE_TAG"
}

stash_user_changes_against_pristine() {
    local temp_ref=""
    if [[ -z "$(run_git status --porcelain)" ]]; then
        return 0
    fi

    run_git stash push -u -m "$TEMP_STASH_NAME"
    temp_ref="$(run_git stash list | grep -F "$TEMP_STASH_NAME" | head -n1 | cut -d: -f1)"
    [[ -n "$temp_ref" ]] || die "Failed to create temporary stash"
    info "Saved local changes temporarily: $TEMP_STASH_NAME"

    revert_current_patches
    if ! run_git stash pop "$temp_ref"; then
        warn "Could not replay local changes onto pristine source before update."
        warn "Gateway path: $GATEWAY_DIR"
        warn "Resolve conflicts, then rerun update.sh. Inspect stashes with: git -C '$GATEWAY_DIR' stash list"
        exit 3
    fi

    run_git stash push -u -m "$STASH_NAME"
    run_git reset --hard "$PRISTINE_TAG"
    STASH_REF="$(run_git stash list | grep -F "$STASH_NAME" | head -n1 | cut -d: -f1)"
    [[ -n "$STASH_REF" ]] || die "Failed to create pristine-based stash"
}

pop_stash_or_report() {
    local stash_ref="$1"
    [[ -n "$stash_ref" ]] || return 0
    if run_git stash pop "$stash_ref"; then
        ok "Restored stashed local changes"
        return 0
    fi
    warn "Stash pop conflicted while restoring local changes."
    warn "Gateway path: $GATEWAY_DIR"
    warn "Resolve conflicts in the files shown by: git -C '$GATEWAY_DIR' status --short"
    warn "After resolving, run: git -C '$GATEWAY_DIR' add <files> && git -C '$GATEWAY_DIR' commit"
    warn "The stash entry is kept if Git could not drop it; inspect with: git -C '$GATEWAY_DIR' stash list"
    exit 3
}

main() {
    [[ -d "$GATEWAY_DIR" ]] || die "Gateway directory not found: $GATEWAY_DIR"
    run_git rev-parse -q --verify "refs/tags/$PRISTINE_TAG" >/dev/null || die "Missing pristine tag: $PRISTINE_TAG"

    local version patch_dir
    version="$(detect_version)"
    [[ -n "$version" ]] || die "Cannot detect Hermes version; set HERMES_VERSION"
    patch_dir="$(find_patch_dir "$version")" || die "No patch set for $version"

    stash_user_changes_against_pristine
    [[ -n "$STASH_REF" ]] && info "Saved pristine-based local changes in stash: $STASH_NAME"

    revert_current_patches
    apply_patch_series "$patch_dir"
    run_git add -A
    run_git commit -m "${MODULE_NAME} updated for ${version}" || true
    run_git tag -f "${MODULE_NAME}/installed"
    pop_stash_or_report "$STASH_REF"

    [[ -x "$MODULE_DIR/scripts/install.sh" ]] && "$MODULE_DIR/scripts/install.sh" --hooks-only || true
    [[ -x "$MODULE_DIR/scripts/check-consistency.sh" ]] && "$MODULE_DIR/scripts/check-consistency.sh"
    [[ -x "$MODULE_DIR/scripts/verify.sh" ]] && "$MODULE_DIR/scripts/verify.sh"

    ok "Update complete"
}

main "$@"
