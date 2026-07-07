#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATEWAY_SRC="${HERMES_GATEWAY_SRC:-/opt/hermes}"
HOOKS_DIR="${HOME}/.hermes/hooks"

# --- 1. Detect Hermes version ---
detect_version() {
    # Try git tag first, then VERSION file, then fallback
    cd "$GATEWAY_SRC"
    if git describe --tags 2>/dev/null; then return; fi
    if [ -f VERSION ]; then cat VERSION; return; fi
    echo "unknown"
}

# --- 2. Find matching patch set ---
find_patch_dir() {
    local ver="$1"
    local candidates=(
        "$SKILL_DIR/patches/$ver"
        "$SKILL_DIR/patches/v${ver#v}"
    )
    for d in "${candidates[@]}"; do
        if [ -f "$d/series" ]; then
            echo "$d"
            return
        fi
    done
    # fallback: patches/ (flat layout)
    if ls "$SKILL_DIR/patches/"*.patch >/dev/null 2>&1; then
        echo "$SKILL_DIR/patches"
        return
    fi
    echo ""
}

# --- 3. Git init + pristine ---
git_init_pristine() {
    cd "$GATEWAY_SRC"
    if git log --oneline 2>/dev/null | grep -q "hermes-wechat-enhance"; then
        echo "[SKIP] Already installed (found hermes-wechat-enhance commit)"
        return 1
    fi
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        git init
        git config user.email "install@hermes-wechat-enhance.local"
        git config user.name "Hermes WeChat Enhance Installer"
        git add -A
        git commit -m "pristine"
        echo "[OK] Pristine commit created"
    else
        if git log --oneline 2>/dev/null | grep -q "^[a-f0-9]* pristine$"; then
            echo "[SKIP] Pristine commit already exists"
        else
            git add -A
            git commit -m "pristine"
            echo "[OK] Pristine commit created"
        fi
    fi
}

# --- 4. Apply patches ---
apply_patches() {
    local patch_dir="$1"
    cd "$GATEWAY_SRC"
    if [ -f "$patch_dir/series" ]; then
        while read -r patch_id; do
            [ -z "$patch_id" ] && continue
            local patch_file="$patch_dir/${patch_id}-*.patch"
            if ! ls $patch_file >/dev/null 2>&1; then
                echo "[FAIL] Patch $patch_id not found"
                exit 1
            fi
            for f in $patch_file; do
                if git apply --check "$f" 2>/dev/null; then
                    git apply "$f"
                    echo "[OK] Applied $patch_id"
                else
                    echo "[FAIL] Cannot apply $patch_id (version mismatch?)"
                    exit 1
                fi
            done
        done < "$patch_dir/series"
    else
        # Flat layout: apply in correct dependency order (NOT alphabetical!)
        local ORDERED=(002 003 004 005 001)
        for patch_id in "${ORDERED[@]}"; do
            local matched=()
            for f in "$patch_dir"/${patch_id}-*.patch; do
                [ -f "$f" ] && matched+=("$f")
            done
            if [ ${#matched[@]} -eq 0 ]; then
                echo "[WARN] No patch found for $patch_id"
                continue
            fi
            for f in "${matched[@]}"; do
                local name="$(basename "$f")"
                if git apply --check "$f" 2>/dev/null; then
                    git apply "$f"
                    echo "[OK] Applied $name"
                else
                    echo "[FAIL] Cannot apply $name (version mismatch?)"
                    exit 1
                fi
            done
        done
    fi
    git add -A
    git commit -m "hermes-wechat-enhance installed (version: $(detect_version))"
    echo "[OK] All patches applied"
}

# --- 5. Install hooks ---
install_hooks() {
    mkdir -p "$HOOKS_DIR"
    local hook_src="$SKILL_DIR/hooks/hermes-wechat-enhance"
    local hook_dst="$HOOKS_DIR/hermes-wechat-enhance"
    if [ -d "$hook_src" ]; then
        ln -sfn "$hook_src" "$hook_dst"
        echo "[OK] Hook installed: $hook_dst -> $hook_src"
    else
        echo "[WARN] Hook source not found: $hook_src"
    fi
}

# --- 6. PYTHONPATH ---
setup_pythonpath() {
    local profile="${HOME}/.hermes/profiles/default/.bashrc"
    if grep -q "hermes-wechat-enhance" "$profile" 2>/dev/null; then
        echo "[SKIP] PYTHONPATH already configured"
        return
    fi
    echo "export PYTHONPATH=\"$SKILL_DIR:\${PYTHONPATH:-}\"" >> "$profile"
    echo "[OK] PYTHONPATH added to $profile"
}

# --- Main ---
main() {
    echo "=== Hermes WeChat Enhance Installer ==="

    echo -n "Detecting Hermes version... "
    local VERSION
    VERSION="$(detect_version)"
    echo "$VERSION"

    echo -n "Finding patch set... "
    local PATCH_DIR
    PATCH_DIR="$(find_patch_dir "$VERSION")"
    if [ -z "$PATCH_DIR" ]; then
        echo "[FAIL] No matching patch set for version $VERSION"
        echo "Available: $(ls -d "$SKILL_DIR/patches/"*/ 2>/dev/null || echo 'flat layout')"
        exit 1
    fi
    echo "$PATCH_DIR"

    echo -n "Initializing git pristine... "
    git_init_pristine || true

    echo "Applying patches..."
    apply_patches "$PATCH_DIR"

    echo "Installing hooks..."
    install_hooks

    echo "Setting up PYTHONPATH..."
    setup_pythonpath

    # Verify
    if [ -x "$SKILL_DIR/scripts/check-consistency.sh" ]; then
        echo "Running consistency check..."
        "$SKILL_DIR/scripts/check-consistency.sh" || true
    fi

    echo ""
    echo "=== Installation complete ==="
    echo "Restart Hermes gateway to apply changes."
}

main "$@"