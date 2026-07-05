
"""Canonical shared mood engine for Hermes Alive.

This module is the only canonical mood implementation. It uses locked atomic IO
under /opt/data/hermes_alive_shared so gateway watcher, session:start, and
agent:end hooks cannot corrupt mood_state.json.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from safe_io import locked_read_json, locked_write_json

DIMENSIONS = ("energy", "curiosity", "social_urge", "care", "mischief")
DECAY_PER_HOUR = {
    "energy": 0.03,
    "curiosity": 0.01,
    "social_urge": -0.04,
    "care": 0.005,
    "mischief": 0.02,
}
SHARED_STATE_PATH = Path("/opt/data/hermes_alive_shared/mood_state.json")
MOOD_LOCK_NAME = "mood_state.lock"

@dataclass
class MoodState:
    energy: float = 0.55
    curiosity: float = 0.45
    social_urge: float = 0.35
    care: float = 0.5
    mischief: float = 0.25

class MoodEngine:
    """Tracks and persists simple mood dimensions in the 0.0-1.0 range."""

    def __init__(self, state_path: Path | None = None) -> None:
        self.state_path = state_path or SHARED_STATE_PATH
        self.state = MoodState()
        self._load()

    def tick(self, hours_elapsed: float) -> MoodState:
        self._load()
        hours = max(0.0, float(hours_elapsed or 0.0))
        for dim in DIMENSIONS:
            value = getattr(self.state, dim)
            value -= DECAY_PER_HOUR[dim] * hours
            value += random.uniform(-0.015, 0.015)
            setattr(self.state, dim, _clamp(value))
        self._save()
        return self.state

    def on_interaction_start(self) -> MoodState:
        self._load()
        self._adjust("energy", 0.03)
        self._adjust("curiosity", 0.01)
        self._save()
        return self.state

    def on_interaction_end(self, duration_minutes: float, sentiment_hint: str | None = None) -> MoodState:
        self._load()
        duration = max(0.0, float(duration_minutes or 0.0))
        self._adjust("energy", -min(duration * 0.005, 0.15))
        self._adjust("social_urge", -min(duration * 0.003, 0.08))
        if sentiment_hint == "positive":
            self._adjust("care", 0.02)
            self._adjust("mischief", 0.01)
        elif sentiment_hint == "negative":
            self._adjust("care", 0.01)
            self._adjust("mischief", 0.02)
        self._adjust("curiosity", -min(duration * 0.002, 0.04))
        self._save()
        return self.state

    def get_mood_description(self) -> str:
        s = self.state
        parts: list[str] = []
        if s.energy < 0.25:
            parts.append("有点困")
        elif s.energy > 0.75:
            parts.append("精力充沛")
        elif s.energy < 0.45:
            parts.append("有点疲惫")
        else:
            parts.append("状态平稳")
        if s.curiosity > 0.7:
            parts.append("好奇心旺盛")
        elif s.curiosity < 0.3:
            parts.append("没什么好奇心")
        if s.social_urge > 0.6:
            parts.append("想找人聊天")
        elif s.social_urge < 0.25:
            parts.append("享受独处")
        if s.care > 0.7:
            parts.append("心情温柔")
        elif s.care < 0.3:
            parts.append("有点冷淡")
        if s.mischief > 0.65:
            parts.append("有点想吐槽")
        return "，".join(parts) + "。"

    def boost(self, dim: str, amount: float) -> MoodState:
        self._load()
        self._adjust(dim, abs(amount))
        self._save()
        return self.state

    def dampen(self, dim: str, amount: float) -> MoodState:
        self._load()
        self._adjust(dim, -abs(amount))
        self._save()
        return self.state

    def speak_score(self) -> float:
        s = self.state
        return _clamp(s.energy * 0.20 + s.curiosity * 0.20 + s.social_urge * 0.35 + s.care * 0.15 + s.mischief * 0.10)

    def dominant_mood(self) -> str:
        return max(DIMENSIONS, key=lambda dim: getattr(self.state, dim))

    def _adjust(self, dim: str, delta: float) -> None:
        if dim not in DIMENSIONS:
            return
        setattr(self.state, dim, _clamp(getattr(self.state, dim) + float(delta)))

    def _load(self) -> None:
        data = locked_read_json(self.state_path, {}, MOOD_LOCK_NAME)
        if isinstance(data, dict):
            values: dict[str, Any] = {}
            for dim in DIMENSIONS:
                try:
                    values[dim] = _clamp(float(data.get(dim, getattr(self.state, dim))))
                except Exception:
                    values[dim] = getattr(self.state, dim)
            self.state = MoodState(**values)

    def _save(self) -> None:
        locked_write_json(self.state_path, asdict(self.state), MOOD_LOCK_NAME)

def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
