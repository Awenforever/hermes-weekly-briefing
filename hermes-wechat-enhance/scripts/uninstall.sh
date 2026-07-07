#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATEWAY_SRC="${HERMES_GATEWAY_SRC:-/opt/hermes}"
HOOKS_DIR="${HOME}/.hermes/hooks"
HOOK_NAME="hermes-wechat-enhance"

# === Uninstall logic ===

main() {
    echo "=== Hermes WeChat Enhance Uninstaller ==="

    # 1. cd to gateway source
    if [ ! -d "$GATEWAY_SRC" ]; then
        echo "[FAIL] Gateway source not found: $GATEWAY_SRC"
        echo "Set HERMES_GATEWAY_SRC to the correct path."
        exit 1
    fi
    cd "$GATEWAY_SRC"
    echo "[OK] Working in $GATEWAY_SRC"

    # 2. Confirm that hermes-wechat-enhance was installed
    if git log --oneline 2>/dev/null | grep -q "hermes-wechat-enhance installed"; then
        echo "[OK] Found hermes-wechat-enhance installation commits"
    else
        echo "[WARN] No 'hermes-wechat-enhance installed' commits found in git log."
        echo "       The gateway may not have been patched by this skill."
        echo "       Proceeding with cleanup anyway..."
    fi

    # 3. git checkout pristine — restore to original state
    if git rev-parse --verify pristine 2>/dev/null; then
        echo "Checking out pristine commit..."
        git checkout pristine
        echo "[OK] Restored to pristine commit"
    else
        echo "[WARN] No 'pristine' ref found. Skipping git restore."
        echo "       The gateway source may need manual restoration."
    fi

    # 4. Remove hooks symlink
    local hook_dst="$HOOKS_DIR/$HOOK_NAME"
    if [ -L "$hook_dst" ]; then
        rm "$hook_dst"
        echo "[OK] Removed hooks symlink: $hook_dst"
    elif [ -e "$hook_dst" ]; then
        echo "[WARN] $hook_dst exists but is not a symlink. Removing anyway..."
        rm -rf "$hook_dst"
        echo "[OK] Removed: $hook_dst"
    else
        echo "[SKIP] No hooks symlink found at $hook_dst"
    fi

    echo ""
    echo "=== Uninstall complete ==="
    echo "The gateway has been restored to its pristine state."
    echo "Restart Hermes gateway to apply changes."
}

main "$@"