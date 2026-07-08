#!/usr/bin/env bash
set -euo pipefail

MODULE_NAME="${MODULE_NAME:-gateway-module-name}"
GATEWAY_DIR="${HERMES_GATEWAY_SRC:-${HERMES_GATEWAY_DIR:-/opt/hermes}}"

die() { echo "[FAIL] $*" >&2; exit 1; }
ok() { echo "[OK] $*"; }

verify_template_self_check() {
    if grep -q 'gateway-module-name' "${BASH_SOURCE[0]}" || grep -q 'Template verify_user_visible_goals is not implemented' "${BASH_SOURCE[0]}"; then
        die "verify.sh is still the template; replace MODULE_NAME and implement behavior tests before shipping"
    fi
    if awk '
        /verify_user_visible_goals[[:space:]]*\(\)[[:space:]]*\{/ { in_fn=1; body=""; next }
        in_fn && /^\}/ {
            gsub(/[[:space:]]/, "", body)
            exit (body == "" || body == ":") ? 0 : 1
        }
        in_fn && $0 !~ /^[[:space:]]*#/ { body = body $0 }
        END { if (!in_fn) exit 0 }
    ' "${BASH_SOURCE[0]}"; then
        die "verify_user_visible_goals is empty; replace it with module-specific user-visible behavior tests"
    fi
}

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
    die "Template verify_user_visible_goals is not implemented. Replace it with module-specific user-visible behavior tests."
}

main() {
    verify_template_self_check
    compile_gateway_files
    verify_user_visible_goals
    ok "Verification complete"
}

main "$@"
