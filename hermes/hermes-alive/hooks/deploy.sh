#!/bin/bash
# Hermes Alive deploy script
# Usage: bash deploy.sh [--install-deps] [--create-cron]
# Assumes Hermes gateway is installed at /opt/hermes/

set -e

HOOK_DIR="${HOOK_DIR:-/opt/data/hooks/hermes-alive}"
SHARED_DIR="${SHARED_DIR:-/opt/data/hermes_alive_shared}"
HERMES_VENV="${HERMES_VENV:-/opt/hermes/.venv}"
BROWSER_DIR="${BROWSER_DIR:-/opt/data/.playwright-browsers}"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${RED}[!]${NC} $1"; }

# ── 1. Verify file structure ─────────────────────────────────────────────

verify_files() {
    log "Verifying hook files..."
    required=(
        "$HOOK_DIR/HOOK.yaml"
        "$HOOK_DIR/handler.py"
        "$HOOK_DIR/proactive_watcher.py"
        "$HOOK_DIR/discovery.py"
        "$HOOK_DIR/llm_message_composer.py"
        "$HOOK_DIR/message_composer.py"
        "$HOOK_DIR/cooldown_manager.py"
        "$HOOK_DIR/dream_engine.py"
        "$HOOK_DIR/dream_prompt.py"
        "$HOOK_DIR/dream_diff_store.py"
        "$SHARED_DIR/safe_io.py"
        "$SHARED_DIR/mood_engine.py"
        "$SHARED_DIR/sources.yaml"
    )
    missing=0
    for f in "${required[@]}"; do
        if [ ! -f "$f" ]; then
            warn "Missing: $f"
            missing=$((missing + 1))
        fi
    done
    [ $missing -eq 0 ] && log "All files present ($missing missing)" || exit 1
}

# ── 2. Install dependencies ──────────────────────────────────────────────

install_deps() {
    log "Installing Python dependencies..."
    "$HERMES_VENV/bin/python3" -c "import playwright" 2>/dev/null || {
        uv pip install playwright --python "$HERMES_VENV/bin/python3"
    }
    "$HERMES_VENV/bin/python3" -c "import yaml" 2>/dev/null || {
        uv pip install pyyaml --python "$HERMES_VENV/bin/python3"
    }
    "$HERMES_VENV/bin/python3" -c "import aiohttp" 2>/dev/null || {
        uv pip install aiohttp --python "$HERMES_VENV/bin/python3"
    }
    log "Python deps OK"
}

install_chromium() {
    log "Installing Chromium for Playwright..."
    if [ ! -d "$BROWSER_DIR/chromium-"* ]; then
        mkdir -p "$BROWSER_DIR"
        PLAYWRIGHT_BROWSERS_PATH="$BROWSER_DIR" \
            "$HERMES_VENV/bin/python3" -m playwright install chromium
    fi
    log "Chromium OK ($(du -sh "$BROWSER_DIR" | cut -f1))"
}

# ── 3. Environment ───────────────────────────────────────────────────────

show_env_required() {
    cat << 'EOF'

Required environment variables (add to .env or docker-compose):

# Core
# Weixin
HERMES_PROACTIVE_WEIXIN_CHAT_ID=<your-weixin-chat-id>
# Telegram
# HERMES_PROACTIVE_TELEGRAM_CHAT_ID=<your-telegram-chat-id>
# Discord
# HERMES_PROACTIVE_DISCORD_CHAT_ID=<your-discord-chat-id>
HERMES_PROACTIVE_PLATFORM_INTERVAL_SECONDS=300

# Subsystems
MOOD_ENABLED=true
COOLDOWN_ENABLED=true
COMPOSER_ENABLED=true

# LLM
HERMES_PROACTIVE_LLM_ENABLED=true
HERMES_PROACTIVE_LLM_MODEL=deepseek-v4-flash-ascend
HERMES_PROACTIVE_LLM_TIMEOUT=60
HERMES_PROACTIVE_LLM_FALLBACK_MODEL=deepseek-v4-flash

# Discovery
HERMES_PROACTIVE_DISCOVERY_ENABLED=true
HERMES_PROACTIVE_DISCOVERY_INTERVAL_SECONDS=14400

# Dream
HERMES_DREAM_ENABLED=true
HERMES_DREAM_INTERVAL_HOURS=24

# Cooldown
HERMES_PROACTIVE_COOLDOWN_MINUTES=120
HERMES_PROACTIVE_QUIET_START=0:30
HERMES_PROACTIVE_QUIET_END=8:30

# Playwright
PLAYWRIGHT_BROWSERS_PATH=/opt/data/.playwright-browsers
EOF
}

# ── 4. Verification ──────────────────────────────────────────────────────

verify_import_chain() {
    log "Verifying import chain..."
    "$HERMES_VENV/bin/python3" -c "
import sys
sys.path.insert(0, '$HOOK_DIR')
sys.path.insert(0, '$SHARED_DIR')
from proactive_watcher import ProactivePlatformWatcher
from discovery import DiscoveryEngine
from dream_engine import DreamEngine
from llm_message_composer import LLMMessageComposer
print('All imports OK')
" && log "Import chain OK" || warn "Import chain FAILED"
}

# ── 5. Cron creation (optional) ──────────────────────────────────────────

create_cron() {
    log "Cron creation: use 'hermes cronjob create' tool in Hermes chat"
    echo "  Task: dream consolidation (daily)"
    echo "  Prompt: 'Run the dream consolidation cycle: read MEMORY.md, analyze with dream system prompt, produce DreamDiff'"
    echo "  Schedule: every 24h"
}

# ── Main ─────────────────────────────────────────────────────────────────

verify_files
verify_import_chain

if [[ "$1" == "--install-deps" ]]; then
    install_deps
    install_chromium
elif [[ "$1" == "--create-cron" ]]; then
    create_cron
elif [[ "$1" == "--all" ]]; then
    install_deps
    install_chromium
    create_cron
else
    echo ""
    echo "Usage: bash deploy.sh [--install-deps] [--create-cron] [--all]"
    echo ""
    echo "Files are ready. To complete setup:"
    echo "  1. bash deploy.sh --install-deps   # Install playwright + chromium"
    echo "  2. Set env vars in .env"
    echo "  3. Restart gateway"
    show_env_required
fi

echo ""
log "Deploy check complete"
echo "  Hook dir:  $HOOK_DIR"
echo "  Shared:    $SHARED_DIR"
echo "  Browsers:  $BROWSER_DIR"
echo ""
echo "After setup: restart the gateway to load the hook."