"""DreamEngine — 4-phase memory consolidation for Hermes Alive.

Wired into the proactive_watcher tick loop. Reads current memory state
in Phase 1, sends a dream prompt to the auxiliary LLM in Phase 2–4,
and produces a non-destructive DreamDiff for review.

Usage:
    engine = DreamEngine()
    if engine.should_run():
        diff = await engine.run_dream_cycle()
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

# Absolute imports (hook files are loaded flat by importlib)
from dream_diff_store import DreamDiff, load_latest_diff, save_diff
from dream_prompt import (
    DEFAULT_DREAM_INTERVAL_HOURS,
    DREAM_ENABLED_ENV,
    DREAM_INTERVAL_ENV,
    DREAM_SYSTEM_PROMPT,
    MEMORY_CHAR_LIMIT,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dream_enabled() -> bool:
    val = os.getenv(DREAM_ENABLED_ENV, "false").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _dream_interval_seconds() -> int:
    hours = int(os.getenv(DREAM_INTERVAL_ENV, str(DEFAULT_DREAM_INTERVAL_HOURS)))
    return max(3600, hours * 3600)


class DreamEngine:
    """Orchestrates the 4-phase dream consolidation cycle."""

    def __init__(self, diff_path: str | None = None) -> None:
        self._diff_path = diff_path or os.getenv(
            "DREAM_DIFF_PATH", "/opt/data/hermes_alive_shared/dream_diff.json"
        )

    def should_run(self) -> bool:
        if not _dream_enabled():
            return False
        last = self._read_last_dream_timestamp()
        if last is not None:
            elapsed = time.time() - last
            if elapsed < _dream_interval_seconds():
                return False
        return True

    async def run_dream_cycle(self) -> DreamDiff:
        diff = DreamDiff()
        diff.timestamp = _now_iso()

        try:
            # Phase 1: Orient — read current memory state
            orient = self._orient()
            diff.orient_summary = orient

            # Phase 2–4: Gather + Consolidate + Prune via LLM
            operations = await self._gather(orient)
            ops, prunes = self._consolidate(operations, orient)
            diff.operations = ops or []
            diff.prune_candidates = prunes or []
            diff.summary = self._prune(diff)

            logger.info(
                "Dream cycle: %d ops, %d prunes — %s",
                len(diff.operations), len(diff.prune_candidates), diff.summary,
            )
        except Exception:
            logger.exception("Dream cycle failed")
            diff.summary = "Dream cycle failed with an error."

        save_diff(diff, self._diff_path)
        return diff

    # ── Phase 1: Orient ──────────────────────────────────────────────────

    def _orient(self) -> dict:
        """Scan current memory state from filesystem."""
        orient: dict = {
            "memory_files": 0,
            "fact_count": 0,
            "sessions_reviewed": 0,
            "memory_chars_used": 0,
            "memory_chars_limit": MEMORY_CHAR_LIMIT,
            "timestamp": _now_iso(),
            "memory_content": "",
            "user_content": "",
        }

        # Read MEMORY.md
        memory_paths = [
            os.getenv("HERMES_HOME", "/opt/data") + "/memories/MEMORY.md",
            "/opt/data/memories/MEMORY.md",
        ]
        for mp in memory_paths:
            try:
                if os.path.isfile(mp):
                    with open(mp, "r", encoding="utf-8") as f:
                        content = f.read()
                    orient["memory_content"] = content
                    orient["memory_chars_used"] = len(content)
                    orient["memory_files"] = 1
                    break
            except (OSError, UnicodeDecodeError):
                pass

        # Read proactive_context.md (user profile)
        context_paths = [
            os.getenv("HERMES_HOME", "/opt/data") + "/proactive_context.md",
            "/opt/data/proactive_context.md",
        ]
        for cp in context_paths:
            try:
                if os.path.isfile(cp):
                    with open(cp, "r", encoding="utf-8") as f:
                        orient["user_content"] = f.read()
                    break
            except (OSError, UnicodeDecodeError):
                pass

        return orient

    # ── Phase 2: Gather ──────────────────────────────────────────────────

    async def _gather(self, orient: dict) -> list[dict]:
        """Send dream prompt + memory state to auxiliary LLM for analysis."""
        try:
            from agent.auxiliary_client import async_call_llm
        except ImportError:
            logger.warning("agent.auxiliary_client not importable; dream skipped")
            return []

        user_prompt = self._build_dream_user_prompt(orient)
        try:
            response = await async_call_llm(
                task="dream",
                messages=[
                    {"role": "system", "content": DREAM_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
                timeout=30,
            )
        except Exception:
            logger.exception("Dream LLM call failed")
            return []

        content = response.choices[0].message.content
        return self._parse_dream_json(content)

    def _build_dream_user_prompt(self, orient: dict) -> str:
        mem = orient.get("memory_content", "")
        user = orient.get("user_content", "")
        parts = [
            "## 当前记忆状态",
            f"字符数: {orient.get('memory_chars_used', 0)} / {orient.get('memory_chars_limit', MEMORY_CHAR_LIMIT)}",
            f"文件数: {orient.get('memory_files', 0)}",
            "",
        ]
        if mem:
            truncated = mem[:3000] + ("…" if len(mem) > 3000 else "")
            parts.append(f"### MEMORY.md\n```\n{truncated}\n```")
        if user:
            truncated = user[:1000] + ("…" if len(user) > 1000 else "")
            parts.append(f"### 用户画像\n```\n{truncated}\n```")
        parts.append("\n请执行 dream consolidation 分析，返回 JSON。")
        return "\n".join(parts)

    def _parse_dream_json(self, raw: str) -> list[dict]:
        """Extract JSON operations from LLM response."""
        try:
            # Try direct JSON
            data = json.loads(raw.strip())
            if isinstance(data, dict):
                return data.get("operations", [])
            return []
        except json.JSONDecodeError:
            pass

        # Try to extract JSON block from markdown
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                if isinstance(data, dict):
                    return data.get("operations", [])
            except json.JSONDecodeError:
                pass

        logger.debug("Dream LLM returned non-JSON: %s", raw[:200])
        return []

    # ── Phase 3: Consolidate ─────────────────────────────────────────────

    def _consolidate(self, operations: list[dict], orient: dict) -> tuple[list[dict], list[dict]]:
        ops, prunes = [], []
        for op in operations:
            op_type = op.get("type", "noop")
            if op_type == "noop":
                continue
            if op_type in {"memory_remove", "fact_remove"}:
                prunes.append(op)
            else:
                ops.append(op)
        return ops, prunes

    # ── Phase 4: Prune ───────────────────────────────────────────────────

    def _prune(self, diff: DreamDiff) -> str:
        op_count = len(diff.operations)
        prune_count = len(diff.prune_candidates)
        if op_count == 0 and prune_count == 0:
            return "Memory tight — no changes needed."
        mem_used = diff.orient_summary.get("memory_chars_used", 0)
        mem_limit = diff.orient_summary.get("memory_chars_limit", MEMORY_CHAR_LIMIT)
        pct = int(mem_used / mem_limit * 100) if mem_limit else 0
        return (
            f"Consolidated {op_count} op(s), {prune_count} prune candidate(s). "
            f"Memory: {mem_used}/{mem_limit} chars ({pct}%)."
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    def _read_last_dream_timestamp(self) -> float | None:
        diff = load_latest_diff(self._diff_path)
        if diff and diff.timestamp:
            try:
                return datetime.fromisoformat(diff.timestamp).timestamp()
            except (ValueError, OSError):
                pass
        return None