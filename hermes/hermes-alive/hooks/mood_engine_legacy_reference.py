# DO NOT IMPORT. Legacy reference only. Canonical implementation is /opt/data/hermes_alive_shared/mood_engine.py

"""Small persistent mood model for Hermes Alive."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path


DIMENSIONS = ("energy", "curiosity", "social_urge", "care", "mischief")
DECAY_PER_HOUR = {
    "energy": 0.03,
    "curiosity": 0.01,
    "social_urge": -0.04,
    "care": 0.005,
    "mischief": 0.02,
}


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
        self.state_path = state_path or Path.home() / ".hermes" / "alive" / "mood.json"
        self.state = MoodState()
        self._load()

    def tick(self, hours_elapsed: float) -> MoodState:
        hours = max(0.0, hours_elapsed)
        for dim in DIMENSIONS:
            value = getattr(self.state, dim)
            value -= DECAY_PER_HOUR[dim] * hours
            value += random.uniform(-0.015, 0.015)
            setattr(self.state, dim, _clamp(value))
        self._save()
        return self.state

    def boost(self, dim: str, amount: float) -> MoodState:
        self._adjust(dim, abs(amount))
        return self.state

    def dampen(self, dim: str, amount: float) -> MoodState:
        self._adjust(dim, -abs(amount))
        return self.state

    def speak_score(self) -> float:
        state = self.state
        score = (
            state.social_urge * 0.35
            + state.curiosity * 0.25
            + state.care * 0.2
            + state.mischief * 0.1
            + state.energy * 0.1
        )
        return _clamp(score)

    def dominant_mood(self) -> str:
        return max(DIMENSIONS, key=lambda dim: getattr(self.state, dim))

    def _adjust(self, dim: str, delta: float) -> None:
        if dim not in DIMENSIONS:
            raise ValueError(f"unknown mood dimension: {dim}")
        setattr(self.state, dim, _clamp(getattr(self.state, dim) + delta))
        self._save()

    def _load(self) -> None:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        values = {dim: _clamp(float(data.get(dim, getattr(self.state, dim)))) for dim in DIMENSIONS}
        self.state = MoodState(**values)

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(asdict(self.state), ensure_ascii=False, indent=2), encoding="utf-8")


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))
