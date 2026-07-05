"""Persistent send limits for Hermes Alive proactive messages.

Supports quiet hours, minimum spacing (cooldown), and daily send limits.
Cooldown is dynamically shortened when the user has been recently active.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from typing import Callable

_SHARED_DIR = "/opt/data/hermes_alive_shared"
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)

from safe_io import locked_read_json, locked_write_json

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path("/opt/data/hermes_alive_shared/cooldown.json")
COOLDOWN_LOCK_NAME = "cooldown.lock"

# Context file written by context_tracker.py
RECENT_CONTEXT_PATH = Path("/opt/data/hermes_alive_shared/recent_context.json")


class CooldownManager:
    """Applies quiet hours, minimum spacing, and daily send limits."""

    def __init__(self, state_path: Path | None = None, now_fn: Callable[[], datetime] | None = None) -> None:
        self.state_path = state_path or DEFAULT_STATE_PATH
        self.now_fn = now_fn or datetime.now
        self.last_sent: datetime | None = None
        self.daily_count = 0
        self.day = self.now_fn().date().isoformat()
        self.type_counts: dict[str, int] = defaultdict(int)
        self._load()
        self._reset_if_new_day()

    def can_send(self, msg_type: str) -> tuple[bool, str]:
        _ = msg_type  # unused but kept for signature compatibility
        self._reset_if_new_day()
        if self.is_quiet_hours():
            return False, "quiet_hours"
        if self.last_sent is not None:
            effective_cooldown = self._get_effective_cooldown()
            elapsed = (self.now_fn() - self.last_sent).total_seconds() / 60
            if elapsed < effective_cooldown:
                return False, "cooldown"
        return True, "ok"

    def _get_effective_cooldown(self) -> int:
        """Determine the effective cooldown minutes based on user activity.

        ── P4: Idle-aware cooldown ──
        - If user has had activity within the last 30 minutes: shorten to 15 min
          (configurable via HERMES_PROACTIVE_ACTIVE_COOLDOWN_MINUTES)
        - If user 30min–2h since activity: keep original cooldown
        - If user >2h since activity: no change (use default)
        - If recent_context.json is missing/unreadable: fallback to original cooldown
        """
        active_cooldown = _env_int("HERMES_PROACTIVE_ACTIVE_COOLDOWN_MINUTES", 15)
        default_cooldown = _env_int("HERMES_PROACTIVE_COOLDOWN_MINUTES", 90)

        try:
            if not RECENT_CONTEXT_PATH.exists():
                return default_cooldown

            with open(RECENT_CONTEXT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            messages = data.get("messages", [])
            if not messages:
                return default_cooldown

            # Find the most recent user message
            last_user_ts = None
            for msg in messages:
                if msg.get("role") == "user":
                    msg_ts = msg.get("timestamp")
                    if msg_ts is not None:
                        # Convert to datetime
                        try:
                            # timestamps appear to be float seconds from epoch
                            msg_dt = datetime.fromtimestamp(float(msg_ts))
                        except (OSError, ValueError):
                            continue
                        if last_user_ts is None or msg_dt > last_user_ts:
                            last_user_ts = msg_dt

            if last_user_ts is None:
                return default_cooldown

            now = self.now_fn()
            minutes_since_last_user = (now - last_user_ts).total_seconds() / 60

            if minutes_since_last_user < 30:
                # User recently active — shorten cooldown
                return min(active_cooldown, default_cooldown)
            elif minutes_since_last_user < 120:
                # 30min–2h: keep default
                return default_cooldown
            else:
                # >2h: no change
                return default_cooldown

        except Exception:
            logger.exception("Failed to read recent_context.json for idle-aware cooldown")
            return default_cooldown

    def record_send(self, msg_type: str) -> None:
        self._reset_if_new_day()
        self.last_sent = self.now_fn()
        self.daily_count += 1
        self.type_counts[msg_type] += 1
        self._save()

    def status(self) -> dict:
        self._reset_if_new_day()
        effective = self._get_effective_cooldown() if self.last_sent else None
        return {
            "state_path": str(self.state_path),
            "last_sent": self.last_sent.isoformat() if self.last_sent else None,
            "daily_count": self.daily_count,
            "day": self.day,
            "type_counts": dict(self.type_counts),
            "quiet_hours": self.is_quiet_hours(),
            "effective_cooldown_minutes": effective,
        }

    def is_quiet_hours(self) -> bool:
        now = self.now_fn().time()
        start = _env_time("HERMES_PROACTIVE_QUIET_START", time(0, 30))
        end = _env_time("HERMES_PROACTIVE_QUIET_END", time(8, 30))
        if start <= end:
            return start <= now < end
        return now >= start or now < end

    def _reset_if_new_day(self) -> None:
        today = self.now_fn().date().isoformat()
        if self.day != today:
            self.day = today
            self.daily_count = 0
            self.type_counts = defaultdict(int)
            self._save()

    def _load(self) -> None:
        data = locked_read_json(self.state_path, {}, COOLDOWN_LOCK_NAME)
        if not isinstance(data, dict):
            return
        self.day = str(data.get("day") or self.day)
        self.daily_count = int(data.get("daily_count") or 0)
        self.type_counts = defaultdict(int, {str(k): int(v) for k, v in data.get("type_counts", {}).items()})
        raw_last_sent = data.get("last_sent")
        if raw_last_sent:
            try:
                self.last_sent = datetime.fromisoformat(raw_last_sent)
            except ValueError:
                self.last_sent = None

    def _save(self) -> None:
        data = {
            "last_sent": self.last_sent.isoformat() if self.last_sent else None,
            "daily_count": self.daily_count,
            "day": self.day,
            "type_counts": dict(self.type_counts),
        }
        locked_write_json(self.state_path, data, COOLDOWN_LOCK_NAME)


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, ""))
    except ValueError:
        return default
    return value if value >= 0 else default


def _env_time(name: str, default: time) -> time:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        hour, minute = raw.split(":", 1)
        return time(int(hour), int(minute))
    except (TypeError, ValueError):
        return default