#!/bin/bash
# verify-v18.sh — Verify all v0.18 WeChat enhancements after patching
# Usage: ./verify-v18.sh [--gateway-dir /opt/hermes/gateway]
# Returns: 0 if all checks pass, 1 if any fail

set -euo pipefail
GATEWAY_DIR="${1:-/opt/hermes/gateway}"
PASS=0
FAIL=0

check() {
    local desc="$1"; shift
    if "$@"; then
        echo "  ✅ $desc"
        ((PASS++))
    else
        echo "  ❌ $desc"
        ((FAIL++))
    fi
}

echo "=== Hermes v0.18 WeChat Enhancement Verification ==="
echo "Gateway dir: $GATEWAY_DIR"
echo ""

# --- File existence ---
check "weixin.py exists" test -f "$GATEWAY_DIR/platforms/weixin.py"
check "base.py exists" test -f "$GATEWAY_DIR/platforms/base.py"
check "run.py exists" test -f "$GATEWAY_DIR/run.py"

# --- Compilation ---
check "weixin.py compiles" python3 -c "import py_compile; py_compile.compile('$GATEWAY_DIR/platforms/weixin.py', doraise=True)" 2>/dev/null
check "base.py compiles" python3 -c "import py_compile; py_compile.compile('$GATEWAY_DIR/platforms/base.py', doraise=True)" 2>/dev/null
check "run.py compiles" python3 -c "import py_compile; py_compile.compile('$GATEWAY_DIR/run.py', doraise=True)" 2>/dev/null

# --- weixin.py features ---
WX="$GATEWAY_DIR/platforms/weixin.py"
check "ReplyBudgetStore class" grep -q "class ReplyBudgetStore" "$WX"
check "MessageSendQueue class" grep -q "class MessageSendQueue" "$WX"
check "_drain_pending method" grep -q "async def _drain_pending" "$WX"
check "_budget_store init" grep -q "self._budget_store = ReplyBudgetStore" "$WX"
check "_send_queue init" grep -q "self._send_queue = MessageSendQueue" "$WX"
check "budget restore in connect" grep -q "self._budget_store.restore" "$WX"
check "context_token → budget" grep -q "self._budget_store.update_token" "$WX"
check "/continue intercept with drain" grep -q "/continue: drain pending" "$WX"
check "/continue returns early" grep -A2 "/continue: drain pending" "$WX" | grep -q "return"
check "_footer_model_name exists" grep -q "def _footer_model_name" "$WX"
check "_is_system_meta exists" grep -q "def _is_system_meta" "$WX"
check "footer format with count + model" grep -q "chunk_with_footer" "$WX"
check "control command dedup bypass" grep -q "_hermes_v017_control_commands" "$WX"
check "content heuristic disabled" grep -q "_content_looks_like_system_error" "$WX"

# --- base.py features ---
BASE="$GATEWAY_DIR/platforms/base.py"
check "_mark_hermes_system_notify_metadata" grep -q "_mark_hermes_system_notify_metadata" "$BASE"
check "model prop: event → metadata" grep -q "getattr(event.*resolved_model" "$BASE" 2>/dev/null || grep -q "getattr(event.*model_name" "$BASE"

# --- run.py features ---
RUN="$GATEWAY_DIR/run.py"
check "_non_conversational_metadata" grep -q "_non_conversational_metadata" "$RUN"
check "agent result model propagation" grep -q "setattr(event.*model_name.*_result_model" "$RUN" 2>/dev/null || grep -q "setattr.*event.*model_name" "$RUN"
check "model thread metadata" grep -q "_model_thread_metadata" "$RUN"
check "startup ready notify env" grep -q "HERMES_WEIXIN_STARTUP_READY_NOTIFY" "$RUN"

# --- Summary ---
echo ""
echo "========================================"
echo "Results: $PASS passed, $FAIL failed"
echo "========================================"

if [ "$FAIL" -gt 0 ]; then
    echo "❌ VERIFICATION FAILED — $FAIL check(s) did not pass"
    exit 1
else
    echo "✅ ALL CHECKS PASSED"
    exit 0
fi