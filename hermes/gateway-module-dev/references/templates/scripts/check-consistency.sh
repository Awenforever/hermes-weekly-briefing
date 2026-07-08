#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PATCHES_DIR="$MODULE_DIR/patches"
ERRORS=0
WARNINGS=0

err() { echo "[ERROR] $*"; ERRORS=$((ERRORS + 1)); }
warn() { echo "[WARN] $*"; WARNINGS=$((WARNINGS + 1)); }
ok() { echo "[OK] $*"; }

require_file() {
    [[ -f "$1" ]] || err "Missing required file: ${1#$MODULE_DIR/}"
}

collect_series_entries() {
    local series="$1"
    sed 's/#.*$//' "$series" | awk '{$1=$1}; NF {print}'
}

check_required_layout() {
    require_file "$MODULE_DIR/CUSTOMIZATIONS.md"
    require_file "$MODULE_DIR/IMPACT_MATRIX.md"
    require_file "$MODULE_DIR/scripts/install.sh"
    require_file "$MODULE_DIR/scripts/update.sh"
    require_file "$MODULE_DIR/scripts/uninstall.sh"
    require_file "$MODULE_DIR/scripts/verify.sh"
    [[ -d "$PATCHES_DIR" ]] || err "Missing patches/ directory"
}

check_patch_series() {
    [[ -d "$PATCHES_DIR" ]] || return 0
    local version_dirs=0
    while IFS= read -r -d '' dir; do
        version_dirs=$((version_dirs + 1))
        local series="$dir/series"
        [[ -f "$series" ]] || { err "Missing series in ${dir#$MODULE_DIR/}"; continue; }
        local seen=()
        while IFS= read -r entry; do
            [[ -f "$dir/$entry" ]] || err "Series references missing patch: ${dir#$MODULE_DIR/}/$entry"
            case "$entry" in
                *.patch) ;;
                *) err "Series entry is not a .patch file: ${dir#$MODULE_DIR/}/$entry" ;;
            esac
            if printf '%s\n' "${seen[@]}" | grep -qx "$entry"; then
                err "Duplicate series entry in ${series#$MODULE_DIR/}: $entry"
            fi
            seen+=("$entry")
        done < <(collect_series_entries "$series")
    done < <(find "$PATCHES_DIR" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
    [[ "$version_dirs" -gt 0 ]] || err "No versioned patch directories found under patches/"
}

check_orphan_patches() {
    [[ -d "$PATCHES_DIR" ]] || return 0
    while IFS= read -r -d '' patch; do
        local dir series base
        dir="$(dirname "$patch")"
        series="$dir/series"
        base="$(basename "$patch")"
        if [[ ! -f "$series" ]]; then
            err "Patch has no sibling series file: ${patch#$MODULE_DIR/}"
        elif ! collect_series_entries "$series" | grep -qx "$base"; then
            err "Patch not referenced by sibling series: ${patch#$MODULE_DIR/}"
        fi
    done < <(find "$PATCHES_DIR" -mindepth 2 -type f -name '*.patch' -print0)

    while IFS= read -r -d '' flat_patch; do
        warn "Flat patches are not allowed for new modules: ${flat_patch#$MODULE_DIR/}"
    done < <(find "$PATCHES_DIR" -maxdepth 1 -type f -name '*.patch' -print0 2>/dev/null || true)
}

check_scripts_are_series_driven() {
    for script in "$MODULE_DIR/scripts/install.sh" "$MODULE_DIR/scripts/update.sh"; do
        [[ -f "$script" ]] || continue
        grep -q 'series' "$script" || err "${script#$MODULE_DIR/} must apply patches from a series file"
        if grep -Eq '[0-9]{3}-[-_a-zA-Z0-9]+\.patch' "$script"; then
            err "${script#$MODULE_DIR/} appears to hard-code patch filenames"
        fi
    done
}

check_hook_lifecycle() {
    [[ -d "$MODULE_DIR/hooks" ]] || return 0
    local hook_count
    hook_count="$(find "$MODULE_DIR/hooks" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
    [[ "$hook_count" = "0" ]] && return 0
    grep -Rqs 'ln -sfn\|cp -R\|install_hooks' "$MODULE_DIR/scripts/install.sh" || err "hooks/ exists but install.sh does not appear to install hooks"
    grep -Rqs 'rm .*\$HOOKS_DIR\|remove_hooks' "$MODULE_DIR/scripts/uninstall.sh" || err "hooks/ exists but uninstall.sh does not appear to remove hooks"
}

check_docs_reference_patches() {
    [[ -f "$MODULE_DIR/CUSTOMIZATIONS.md" ]] || return 0
    while IFS= read -r -d '' patch; do
        local base
        base="$(basename "$patch")"
        grep -qs "$base" "$MODULE_DIR/CUSTOMIZATIONS.md" || warn "CUSTOMIZATIONS.md does not mention $base"
    done < <(find "$PATCHES_DIR" -mindepth 2 -type f -name '*.patch' -print0 2>/dev/null || true)
}

main() {
    check_required_layout
    check_patch_series
    check_orphan_patches
    check_scripts_are_series_driven
    check_hook_lifecycle
    check_docs_reference_patches

    echo "Consistency check: $ERRORS errors, $WARNINGS warnings"
    [[ "$ERRORS" -eq 0 ]] || exit 2
    [[ "$WARNINGS" -eq 0 ]] || exit 1
    ok "Consistency check passed"
}

main "$@"
