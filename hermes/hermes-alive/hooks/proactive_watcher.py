
"""Gateway-native proactive platform watcher for Hermes Alive."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
# Hermes Alive import path bootstrap
_HOOK_DIR = "/opt/data/hooks/hermes-alive"
_SHARED_DIR = "/opt/data/hermes_alive_shared"
for _p in (_HOOK_DIR, _SHARED_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import time
import uuid
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


from safe_io import (
    append_jsonl,
    read_json,
    locked_read_json,
    locked_write_json,
    try_file_lock,
    sha256_text,
    redact_preview,
    atomic_write_text,
)

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 300.0
ENABLED_ENV = "HERMES_PROACTIVE_PLATFORM_ENABLED"
CHAT_ID_ENV = "HERMES_PROACTIVE_WEIXIN_CHAT_ID"
INTERVAL_ENV = "HERMES_PROACTIVE_PLATFORM_INTERVAL_SECONDS"
MOOD_ENABLED_ENV = "MOOD_ENABLED"
COOLDOWN_ENABLED_ENV = "COOLDOWN_ENABLED"
COMPOSER_ENABLED_ENV = "COMPOSER_ENABLED"
LLM_ENABLED_ENV = "HERMES_PROACTIVE_LLM_ENABLED"
LLM_MODEL_ENV = "HERMES_PROACTIVE_LLM_MODEL"
DISCOVERY_ENABLED_ENV = "HERMES_PROACTIVE_DISCOVERY_ENABLED"

BASE = Path("/opt/data/hermes_alive_shared")
WATCHER_LOCK = BASE / "locks" / "proactive_watcher.lock"
PROACTIVE_LOG = BASE / "proactive_log.jsonl"
CONTROL = BASE / "control.json"
QUEUE = BASE / "control_queue.jsonl"

SYSTEM_METADATA: dict[str, Any] = {
    "is_system": True,
    "actor": "system",
    "source": "system",
    "message_origin": "system",
    "origin": "system",
    "model_name": "hermes",
    "resolved_model": "hermes",
    "routed_model": "hermes",
    "model": "hermes",
}

class ProactivePlatformWatcher:
    """Send proactive messages through live gateway adapters."""

    def __init__(self, adapters: Mapping[Any, Any], config: Any) -> None:
        self.adapters = adapters
        self.config = config
        self._mood_engine: Any | None = None
        self._cooldown_manager: Any | None = None
        self._message_composer: Any | None = None
        self._llm_message_composer: Any | None = None
        self._discovery_engine: Any | None = None
        self._dream_engine: Any | None = None
        self._last_mood_tick = time.monotonic()
        self.watcher_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.started_at = datetime.now().astimezone().isoformat()

    async def run(self) -> None:
        with try_file_lock(WATCHER_LOCK) as acquired:
            if not acquired:
                logger.warning("Hermes Alive watcher already running; singleton lock unavailable")
                self._log("skip", reason="watcher_lock_unavailable")
                return
            from log_rotate import rotate_proactive_log
            rotate_proactive_log(BASE)
            self._log("start", reason="watcher_started")
            logger.info("Proactive platform watcher started id=%s", self.watcher_id)
            try:
                while True:
                    await self.tick()
                    await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                self._log("stop", reason="watcher_cancelled")
                raise
            except Exception as exc:
                self._log("error", reason="watcher_crashed", error=type(exc).__name__)
                logger.exception("Proactive platform watcher crashed")
                raise

    async def tick(self) -> bool:
        tick_id = uuid.uuid4().hex[:12]
        try:
            return await self._tick_impl(tick_id)
        except Exception as exc:
            self._log("error", tick_id=tick_id, reason="tick_exception", error=type(exc).__name__)
            logger.exception("Hermes Alive tick failed")
            return False

    async def _tick_impl(self, tick_id: str) -> bool:
        if not self.enabled:
            self._log("skip", tick_id=tick_id, reason="disabled")
            return False

        chat_id = self.weixin_chat_id
        if not chat_id:
            self._log("skip", tick_id=tick_id, reason="missing_chat_id")
            logger.warning("%s is required when proactive platform watcher is enabled", CHAT_ID_ENV)
            return False

        adapter = self._weixin_adapter()
        if adapter is None:
            self._log("skip", tick_id=tick_id, reason="adapter_unavailable")
            return False

        control_sent = await self._process_control_queue(adapter, chat_id, tick_id)
        if control_sent:
            return True

        mood = self._tick_mood()
        cooldown = self._cooldown()
        if cooldown is not None:
            allowed, reason = cooldown.can_send("proactive")
            if not allowed:
                self._log("skip", tick_id=tick_id, reason=reason, quiet_hours=(reason == "quiet_hours"))
                return False

        import random
        discovery_context = await self._check_discovery()
        if discovery_context is not None:
            self._log_discovery(tick_id, discovery_context)
        await self._check_dream()
        messages = await self._compose_message(mood, discovery_context)
        if not messages:
            self._log("skip", tick_id=tick_id, reason="empty_messages")
            return False

        msg_count = len(messages)
        for msg_index, (msg_type, content, generated_by) in enumerate(messages, start=1):
            self._log_compose(tick_id, mood, discovery_context, msg_type, generated_by)

            metadata = self._metadata(generated_by)
            try:
                await adapter.send(chat_id, content, metadata=metadata)
            except Exception as exc:
                self._log("error", tick_id=tick_id, reason="adapter_send_failed", error=type(exc).__name__, msg_type=msg_type, msg_index=msg_index, msg_count=msg_count)
                logger.exception("Failed to send proactive platform heartbeat")
                continue

            # Only record cooldown once (on the first message)
            if msg_index == 1 and cooldown is not None:
                cooldown.record_send(msg_type)

            self._log(
                "sent",
                tick_id=tick_id,
                reason="normal_proactive",
                msg_type=msg_type,
                msg_index=msg_index,
                msg_count=msg_count,
                generated_by=generated_by,
                message_hash=sha256_text(content),
                message_preview=redact_preview(content),
                adapter_result="ok",
            )
            logger.info("Sent proactive platform heartbeat to Weixin chat %s [%d/%d]", _redact_chat(chat_id), msg_index, msg_count)

            # Delay between messages (not after the last one)
            if msg_index < msg_count:
                await asyncio.sleep(random.uniform(2, 5))

        return True

    @property
    def enabled(self) -> bool:
        control = self._control()
        override = control.get("enabled_override")
        if override is False:
            return False
        if override is True:
            return True
        return _truthy(os.getenv(ENABLED_ENV))

    @property
    def weixin_chat_id(self) -> str | None:
        value = os.getenv(CHAT_ID_ENV)
        if value is None:
            return None
        value = value.strip()
        return value or None

    @property
    def interval_seconds(self) -> float:
        raw = os.getenv(INTERVAL_ENV)
        if raw is None or not raw.strip():
            return DEFAULT_INTERVAL_SECONDS
        try:
            interval = float(raw)
        except ValueError:
            return DEFAULT_INTERVAL_SECONDS
        return interval if interval > 0 else DEFAULT_INTERVAL_SECONDS

    def _control(self) -> dict[str, Any]:
        data = locked_read_json(CONTROL, {}, "control.lock")
        return data if isinstance(data, dict) else {}

    def _weixin_adapter(self) -> Any | None:
        for key, adapter in self.adapters.items():
            key_value = getattr(key, "value", key)
            if key_value == "weixin":
                return adapter
        return None

    async def _process_control_queue(self, adapter: Any, chat_id: str, tick_id: str) -> bool:
        if not QUEUE.exists():
            return False
        try:
            lines = QUEUE.read_text(encoding="utf-8").splitlines()
        except Exception:
            return False
        if not lines:
            return False
        remaining: list[str] = []
        sent_any = False
        for line in lines:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if item.get("type") == "test" and not sent_any:
                content = str(item.get("message") or "Hermes Alive 主动推送测试。")
                try:
                    await adapter.send(chat_id, content, metadata=self._metadata("hermes"))
                    self._log("sent", tick_id=tick_id, reason="alive_test", msg_type="test", generated_by="hermes", message_hash=sha256_text(content), message_preview=redact_preview(content), adapter_result="ok")
                    sent_any = True
                except Exception as exc:
                    self._log("error", tick_id=tick_id, reason="alive_test_send_failed", error=type(exc).__name__)
                    remaining.append(line)
            else:
                remaining.append(line)
        locked_write_json(BASE / "control_queue_state.json", {"last_processed_at": datetime.now().astimezone().isoformat()}, "control_queue.lock")
        atomic_write_text(QUEUE, "\n".join(remaining) + ("\n" if remaining else ""))
        return sent_any

    def _heartbeat_message(self) -> str:
        return "Hermes proactive platform heartbeat."

    def _tick_mood(self) -> Any | None:
        engine = self._mood()
        if engine is None:
            return None
        now = time.monotonic()
        hours_elapsed = (now - self._last_mood_tick) / 3600
        self._last_mood_tick = now
        return engine.tick(hours_elapsed)

    def _mood(self) -> Any | None:
        if not self._feature_enabled(MOOD_ENABLED_ENV):
            return None
        if self._mood_engine is None:
            try:
                from mood_engine import MoodEngine
                self._mood_engine = MoodEngine()
            except Exception:
                logger.exception("Failed to initialize mood engine")
                self._mood_engine = False
        return None if self._mood_engine is False else self._mood_engine

    def _cooldown(self) -> Any | None:
        if not self._feature_enabled(COOLDOWN_ENABLED_ENV):
            return None
        if self._cooldown_manager is None:
            try:
                from cooldown_manager import CooldownManager
                self._cooldown_manager = CooldownManager()
            except Exception:
                logger.exception("Failed to initialize cooldown manager")
                self._cooldown_manager = False
        return None if self._cooldown_manager is False else self._cooldown_manager

    async def _compose_message(self, mood: Any | None = None, discovery_context: dict[str, Any] | None = None) -> list[tuple[str, str, str]]:
        default_mood = self._mood_state_or_default(mood)
        if self._feature_enabled(LLM_ENABLED_ENV):
            llm_result = await self._compose_llm_message(default_mood, discovery_context)
            if llm_result is not None and len(llm_result) > 0:
                # Return list of (msg_type, content, generated_by)
                return [(msg_type, content, self._llm_model_name()) for msg_type, content in llm_result]
            logger.debug("LLM composer returned fallback; using template composer")
        msg_type, content = self._compose_template_message(default_mood)[0]
        return [(msg_type, content, "hermes")]

    async def _compose_llm_message(self, mood: Any, discovery_context: dict[str, Any] | None = None) -> list[tuple[str, str]] | None:
        if self._llm_message_composer is None:
            try:
                from llm_message_composer import LLMMessageComposer
                self._llm_message_composer = LLMMessageComposer()
            except Exception:
                logger.exception("Failed to initialize LLM message composer")
                self._llm_message_composer = False
        if self._llm_message_composer is False:
            return None
        try:
            return await self._llm_message_composer.compose(mood, context={"trigger": self._dominant_mood(mood)}, discovery_context=discovery_context)
        except Exception:
            logger.exception("LLM message composer failed")
            self._llm_message_composer = False
            return None

    async def _check_discovery(self) -> dict[str, Any] | None:
        if not self._feature_enabled(DISCOVERY_ENABLED_ENV):
            return None
        if self._discovery_engine is None:
            try:
                from discovery import DiscoveryEngine
                self._discovery_engine = DiscoveryEngine()
            except Exception:
                logger.exception("Failed to initialize discovery engine")
                self._discovery_engine = False
                return None
        if self._discovery_engine is False:
            return None
        engine = self._discovery_engine
        if engine.should_run():
            try:
                logger.debug("Running discovery engine")
                await engine.collect()
            except Exception:
                logger.exception("Discovery engine collection failed")
                return None
        if engine.has_fresh():
            return engine.get_recent()
        return None

    def _compose_template_message(self, mood: Any) -> list[tuple[str, str]]:
        if not self._feature_enabled(COMPOSER_ENABLED_ENV):
            return [("heartbeat", self._heartbeat_message())]
        if self._message_composer is None:
            try:
                from message_composer import MessageComposer
                self._message_composer = MessageComposer()
            except Exception:
                logger.exception("Failed to initialize message composer")
                self._message_composer = False
        if self._message_composer is False:
            return [("heartbeat", self._heartbeat_message())]
        return self._message_composer.compose(mood)

    def _mood_state_or_default(self, mood: Any | None) -> Any:
        if mood is not None:
            return mood
        if not hasattr(self, "_default_mood_state"):
            from mood_engine import MoodState
            self._default_mood_state = MoodState()
        return self._default_mood_state

    def _dominant_mood(self, mood: Any) -> str:
        try:
            from mood_engine import DIMENSIONS
            return max(DIMENSIONS, key=lambda dim: getattr(mood, dim))
        except Exception:
            return "proactive"

    def _is_llm_fallback(self, msg_type: str, content: str) -> bool:
        try:
            from llm_message_composer import FALLBACK_CONTENT, FALLBACK_MSG_TYPE
            return msg_type == FALLBACK_MSG_TYPE and content == FALLBACK_CONTENT
        except Exception:
            return False

    def _feature_enabled(self, env_name: str) -> bool:
        raw = os.getenv(env_name)
        if raw is None:
            return self.enabled
        return _truthy(raw)

    def _llm_model_name(self) -> str:
        return os.getenv(LLM_MODEL_ENV, os.getenv("HERMES_PROACTIVE_MODEL", "deepseek-v4-flash-ascend")).strip() or "deepseek-v4-flash-ascend"

    async def _check_dream(self) -> None:
        """Run dream memory consolidation if interval has elapsed."""
        if self._dream_engine is None:
            try:
                from dream_engine import DreamEngine
                self._dream_engine = DreamEngine()
            except Exception:
                logger.exception("Failed to initialize dream engine")
                self._dream_engine = False
                return
        if self._dream_engine is False:
            return
        engine = self._dream_engine
        if engine.should_run():
            try:
                logger.debug("Running dream consolidation cycle")
                diff = await engine.run_dream_cycle()
                mood_after = {}
                try:
                    from mood_engine import MoodEngine, DIMENSIONS
                    me = MoodEngine()
                    mood_after = {dim: round(float(getattr(me.state, dim, 0.0)), 2) for dim in DIMENSIONS}
                except Exception:
                    pass
                self._log("dream", reason="dream_cycle_complete",
                          ops=len(diff.operations),
                          prunes=len(diff.prune_candidates),
                          summary=diff.summary,
                          mood_after=mood_after)
            except Exception:
                logger.exception("Dream consolidation failed")

    def _metadata(self, generated_by: str) -> dict[str, Any]:
        metadata = dict(SYSTEM_METADATA)
        if generated_by and generated_by != "hermes":
            metadata.update({
                "actor": "model",
                "source": "model",
                "message_origin": "model",
                "origin": "model",
                "model_name": generated_by,
                "resolved_model": generated_by,
                "routed_model": generated_by,
                "model": generated_by,
            })
        return metadata

    def _log(self, decision: str, **extra: Any) -> None:
        record = {
            "decision": decision,
            "watcher_id": self.watcher_id,
            "pid": os.getpid(),
            "started_at": self.started_at,
        }
        record.update(extra)
        try:
            append_jsonl(PROACTIVE_LOG, record, "proactive_log.lock")
        except Exception:
            logger.exception("Failed to write proactive log entry")

    def _log_discovery(self, tick_id: str, ctx: dict[str, Any]) -> None:
        """Log discovery results: source names and item counts."""
        external = ctx.get("external", []) or []
        local = ctx.get("local", []) or []

        # Count by source
        source_counts: dict[str, int] = {}
        for item in external:
            src = item.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1

        self._log(
            "discovery",
            tick_id=tick_id,
            external_count=len(external),
            local_count=len(local),
            sources=list(source_counts.keys()),
            source_counts=source_counts,
        )

    def _log_compose(
        self,
        tick_id: str,
        mood: Any,
        discovery_context: dict[str, Any] | None,
        msg_type: str,
        generated_by: str,
    ) -> None:
        """Log compose context: mood snapshot, model, discovery availability, msg type."""
        mood_snapshot: dict[str, float] = {}
        if mood is not None:
            try:
                from mood_engine import DIMENSIONS
                mood_snapshot = {dim: round(float(getattr(mood, dim, 0.0)), 2) for dim in DIMENSIONS}
            except Exception:
                pass

        had_discovery = discovery_context is not None
        external_n = len(discovery_context.get("external", []) or []) if had_discovery else 0
        local_n = len(discovery_context.get("local", []) or []) if had_discovery else 0

        self._log(
            "compose",
            tick_id=tick_id,
            model=generated_by,
            msg_type=msg_type,
            mood=mood_snapshot,
            had_discovery=had_discovery,
            discovery_items=external_n + local_n,
        )

def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}

def _redact_chat(chat_id: str) -> str:
    if len(chat_id) <= 8:
        return "<redacted>"
    return chat_id[:4] + "..." + chat_id[-4:]
