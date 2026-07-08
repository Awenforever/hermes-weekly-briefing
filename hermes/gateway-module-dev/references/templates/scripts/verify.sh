#!/usr/bin/env bash
set -euo pipefail

MODULE_NAME="${MODULE_NAME:-gateway-module-name}"
GATEWAY_DIR="${HERMES_GATEWAY_SRC:-${HERMES_GATEWAY_DIR:-/opt/hermes}}"

die() { echo "[FAIL] $*" >&2; exit 1; }
ok() { echo "[OK] $*"; }

# Keep smoke checks small. They are not a substitute for behavior verification.
compile_gateway_files() {
    [[ -d "$GATEWAY_DIR" ]] || die "Gateway directory not found: $GATEWAY_DIR"
    find "$GATEWAY_DIR/gateway" -name '*.py' -print0 2>/dev/null |
        xargs -0 -r python3 -m py_compile
    ok "Gateway Python files compile"
}

# Replace these examples with module-specific, user-visible behavior tests.
verify_user_visible_goals() {
    # Goal: when the module's trigger input is received, the user-visible output changes as documented.
    # Example implementation patterns:
    # - run a small Python harness that imports the patched adapter and feeds a synthetic event
    # - call a local gateway endpoint and assert response text/status
    # - inspect a hook output file after invoking the hook with a fixture event
    #
    # Do not stop at "function exists" or "patch marker exists".
    :
}

main() {
    compile_gateway_files
    verify_user_visible_goals
    ok "Verification complete"
}

main "$@"
