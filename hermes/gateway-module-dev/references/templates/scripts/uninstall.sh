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
FORCE=0

die() { echo "[FAIL] $*" >&2; exit 1; }
ok() { echo "[OK] $*"; }
run_git() { git -C "$GATEWAY_DIR" "$@"; }

remove_hooks() {
    [[ -d "$MODULE_DIR/hooks" ]] || return 0
    find "$MODULE_DIR/hooks" -mindepth 1 -maxdepth 1 -type d | while IFS= read -r hook; do
        local dst="$HOOKS_DIR/$(basename "$hook")"
        if [[ -L "$dst" ]]; then
            rm "$dst"
            ok "Removed hook $(basename "$hook")"
        fi
    done
}

remove_profile_markers() {
    local marker_begin="# ${MODULE_NAME} begin"
    local marker_end="# ${MODULE_NAME} end"
    local targets=()
    [[ -f "${HERMES_CONFIG_FILE:-$HOME/.hermes/config.yaml}" ]] && targets+=("${HERMES_CONFIG_FILE:-$HOME/.hermes/config.yaml}")
    [[ -f "${HERMES_ENV_FILE:-$HOME/.hermes/.env}" ]] && targets+=("${HERMES_ENV_FILE:-$HOME/.hermes/.env}")
    local target
    for target in "${targets[@]}"; do
        if grep -qF "$marker_begin" "$target"; then
            sed -i.bak "/$(printf '%s' "$marker_begin" | sed 's/[][\/.^$*]/\\&/g')/,/$(printf '%s' "$marker_end" | sed 's/[][\/.^$*]/\\&/g')/d" "$target"
            ok "Removed module markers from $target"
        fi
    done
}

parse_args() {
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --force) FORCE=1 ;;
            *) die "Unknown option: $1" ;;
        esac
        shift
    done
}

main() {
    parse_args "$@"
    [[ -d "$GATEWAY_DIR" ]] || die "Gateway directory not found: $GATEWAY_DIR"
    run_git rev-parse -q --verify "refs/tags/$PRISTINE_TAG" >/dev/null || die "Missing pristine tag: $PRISTINE_TAG"
    if [[ "$FORCE" -eq 0 ]]; then
        run_git rev-parse -q --verify "refs/tags/$INSTALLED_TAG" >/dev/null || die "Module does not appear installed: $INSTALLED_TAG missing. Use --force to roll back to $PRISTINE_TAG anyway."
    fi

    run_git reset --hard "$PRISTINE_TAG"
    remove_hooks
    remove_profile_markers
    run_git tag -d "$INSTALLED_TAG" >/dev/null 2>&1 || true
    run_git tag -d "$INSTALLING_TAG" >/dev/null 2>&1 || true

    if [[ -n "$(run_git status --porcelain)" ]]; then
        echo "[WARN] Remaining untracked or local files:"
        run_git status --short
    fi
    ok "Uninstall complete"
}

main "$@"
