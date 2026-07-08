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
    local profile="${HERMES_PROFILE_RC:-$HOME/.hermes/profiles/default/.bashrc}"
    [[ -f "$profile" ]] || return 0
    sed -i.bak "/# ${MODULE_NAME} begin/,/# ${MODULE_NAME} end/d" "$profile"
    ok "Removed profile markers from $profile"
}

main() {
    [[ -d "$GATEWAY_DIR" ]] || die "Gateway directory not found: $GATEWAY_DIR"
    run_git rev-parse -q --verify "refs/tags/$PRISTINE_TAG" >/dev/null || die "Missing pristine tag: $PRISTINE_TAG"
    run_git rev-parse -q --verify "refs/tags/$INSTALLED_TAG" >/dev/null || die "Module does not appear installed: $INSTALLED_TAG missing"

    run_git reset --hard "$PRISTINE_TAG"
    remove_hooks
    remove_profile_markers
    run_git tag -d "$INSTALLED_TAG" >/dev/null 2>&1 || true

    if [[ -n "$(run_git status --porcelain)" ]]; then
        echo "[WARN] Remaining untracked or local files:"
        run_git status --short
    fi
    ok "Uninstall complete"
}

main "$@"
