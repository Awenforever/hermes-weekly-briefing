#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PATCHES_DIR="$MODULE_DIR/patches"
ERRORS=0
WARNINGS=0
STRICT=0

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
    require_file "$MODULE_DIR/SKILL.md"
    require_file "$MODULE_DIR/CUSTOMIZATIONS.md"
    require_file "$MODULE_DIR/IMPACT_MATRIX.md"
    require_file "$MODULE_DIR/scripts/install.sh"
    require_file "$MODULE_DIR/scripts/update.sh"
    require_file "$MODULE_DIR/scripts/uninstall.sh"
    require_file "$MODULE_DIR/scripts/verify.sh"
    [[ -d "$PATCHES_DIR" ]] || err "Missing patches/ directory"
}

check_template_placeholders() {
    local file
    while IFS= read -r -d '' file; do
        if grep -Eq 'MODULE_NAME|vX\.Y|001-example\.patch|gateway-module-name|NNN-short-purpose\.patch' "$file"; then
            err "Template placeholder remains in ${file#$MODULE_DIR/}"
        fi
    done < <(find "$MODULE_DIR" -type f \( -name '*.md' -o -name '*.sh' -o -name 'series' \) -print0)
}

check_verify_implemented() {
    local verify="$MODULE_DIR/scripts/verify.sh"
    [[ -f "$verify" ]] || return 0
    if grep -q 'Template verify_user_visible_goals is not implemented' "$verify"; then
        err "scripts/verify.sh still contains the template behavior-test failure"
    fi
    if awk '
        /verify_user_visible_goals[[:space:]]*\(\)[[:space:]]*\{/ { in_fn=1; body=""; next }
        in_fn && /^\}/ {
            gsub(/[[:space:]]/, "", body)
            exit (body == "" || body == ":") ? 0 : 1
        }
        in_fn && $0 !~ /^[[:space:]]*#/ { body = body $0 }
        END { if (!in_fn) exit 1 }
    ' "$verify"; then
        err "scripts/verify.sh verify_user_visible_goals appears empty"
    fi
    if grep -Eq 'Goal: when the module|Example implementation patterns|Do not stop at "function exists"' "$verify"; then
        err "scripts/verify.sh still contains example comments"
    fi
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
    if [[ "${1:-}" == "--strict" ]]; then
        STRICT=1
    elif [[ "${1:-}" != "" ]]; then
        echo "Usage: $0 [--strict]" >&2
        exit 64
    fi
    check_required_layout
    check_template_placeholders
    check_verify_implemented
    check_patch_series
    check_orphan_patches
    check_scripts_are_series_driven
    check_hook_lifecycle
    check_docs_reference_patches

    echo "Consistency check: $ERRORS errors, $WARNINGS warnings"
    if [[ "$STRICT" -eq 1 && "$WARNINGS" -gt 0 ]]; then
        echo "[ERROR] Strict mode treats warnings as errors"
        exit 2
    fi
    [[ "$ERRORS" -eq 0 ]] || exit 2
    ok "Consistency check passed"
}

main "$@"
