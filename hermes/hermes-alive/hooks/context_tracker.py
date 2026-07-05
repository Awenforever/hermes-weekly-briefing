"""Context tracker for Hermes Alive -- captures recent conversation for proactive context injection.

Captures the last N messages from the state.db sessions database on agent:end events,
stores them with timestamps in a shared JSON file, and provides a freshness-decay
filter for the proactive composer to inject into the LLM prompt.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

# How many recent messages to keep
MAX_MESSAGES = 20

# Where to store context
SHARED_DIR = Path(os.getenv("HERMES_ALIVE_SHARED_DIR", "/opt/data/hermes_alive_shared"))
CONTEXT_FILE = SHARED_DIR / "recent_context.json"

# The main Weixin session prefix to filter by
WEIXIN_SESSION_PREFIX = "agent:main:weixin:dm:"

# Path to the session state database
STATE_DB = Path(os.getenv("HERMES_STATE_DB", "/opt/data/state.db"))


def freshness_decay(seconds_ago: float) -> float:
    """Compute freshness weight for a message based on how long ago it was sent.

    Returns:
        weight: 0.0 (ignore) to 1.0 (highest relevance)
    """
    if seconds_ago < 300:        # <5 minutes
        return 1.0
    elif seconds_ago < 3600:     # 5-60 minutes
        return 0.6
    elif seconds_ago < 10800:    # 1-3 hours
        return 0.2
    else:
        return 0.0


def freshness_label(seconds_ago: float) -> str:
    """Return a contextual label for the recency of a message."""
    if seconds_ago < 300:
        return "刚刚"
    elif seconds_ago < 1800:
        return "不久前"
    elif seconds_ago < 3600:
        return "大约一小时前"
    elif seconds_ago < 10800:
        return "之前"
    else:
        return "更早"


def capture_recent_context() -> None:
    """Read the last N messages from state.db and write them to the shared JSON file.

    This is called from handler.py _on_agent_end().
    """
    try:
        conn = sqlite3.connect(str(STATE_DB))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Find the session_key for the main Weixin DM session
        cursor.execute(
            "SELECT id FROM sessions WHERE id LIKE ? ORDER BY started_at DESC LIMIT 1",
            (f"{WEIXIN_SESSION_PREFIX}%",)
        )
        row = cursor.fetchone()
        if row is None:
            logger.debug("No Weixin session found for context capture")
            conn.close()
            return

        session_id = row["id"]

        # Get the last N messages from this session
        cursor.execute(
            "SELECT role, content, timestamp FROM messages "
            "WHERE session_id = ? AND active = 1 "
            "ORDER BY id DESC LIMIT ?",
            (session_id, MAX_MESSAGES)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.debug("No messages found for context capture (session=%s)", session_id)
            return

        now = time.time()
        messages: list[dict[str, Any]] = []
        for r in reversed(rows):  # chronological order
            ts = r["timestamp"]
            content = r["content"] or ""
            # Only keep user and assistant messages; skip tool calls
            role = r["role"]
            if role not in ("user", "assistant"):
                continue
            seconds_ago = now - ts
            weight = freshness_decay(seconds_ago)
            if weight == 0.0:
                continue  # skip old messages entirely
            messages.append({
                "role": role,
                "content": content[:500],  # cap content length
                "timestamp": ts,
                "seconds_ago": round(seconds_ago, 1),
                "weight": weight,
                "label": freshness_label(seconds_ago),
            })

        CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "captured_at": datetime.now(CST).isoformat(),
            "session_id": session_id,
            "message_count": len(messages),
            "messages": messages,
        }
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(
            "Context captured for session %s: %d messages (weights: %s)",
            session_id,
            len(messages),
            [m["weight"] for m in messages],
        )

    except Exception:
        logger.exception("Failed to capture recent context")
        # Don't let this crash the hook; it's best-effort


def read_recent_context() -> str:
    """Read the recent_context.json file and return a formatted string for prompt injection.

    Returns:
        A formatted string suitable for appending to _user_prompt, or empty string if no context.
    """
    if not CONTEXT_FILE.exists():
        return ""

    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.exception("Failed to read recent context file")
        return ""

    messages = data.get("messages", [])
    if not messages:
        return ""

    # Format as a prompt section
    lines: list[str] = [
        "## 你和停云的最近对话",
        "下面是你和停云最近聊过的内容（越近的越可能自然想起，远的只是模糊记忆）：",
    ]
    for m in messages:
        label = m.get("label", "")
        role = "你" if m["role"] == "assistant" else "停云"
        content = m["content"]
        # Truncate for readability
        if len(content) > 200:
            content = content[:197] + "..."
        lines.append(f"- [{label}][{role}] {content}")

    return "\n".join(lines)