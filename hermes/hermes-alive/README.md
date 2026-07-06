<div align="center">

# Hermes Alive

**Gateway-native proactive AI companion for Hermes Agent.**

![version](https://img.shields.io/badge/version-v2.3.0-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![license](https://img.shields.io/badge/license-Hermes%20Project-green)

[中文文档](./README_CN.md)

</div>

---

## 🧬 What It Is

Hermes Alive is a zero-intrusion proactive companion skill for Hermes Agent.
It installs as a Hermes gateway hook, runs as a background `asyncio` task, discovers content periodically, composes Chinese messages with an LLM, and pushes them to WeChat.

It is not a chatbot. It does not ask questions, provide advice, report weather, or maintain conversational obligations.

> **Design core:** "A person responsible for nothing."  
> The LLM owns creative expression. Code enforces only hard constraints.

---

## ⚡ Quick Start

```bash
cd /opt/data/skills/hermes/hermes-alive
bash scripts/deploy.sh --all

# Configure /opt/data/.env
docker-compose up -d hermes
```

Minimum `.env`:

```bash
HERMES_PROACTIVE_PLATFORM_ENABLED=true
HERMES_PROACTIVE_WEIXIN_CHAT_ID=<wechat_chat_id>
TZ=Asia/Shanghai
```

Recommended:

```bash
VOICE_ENABLED=true
HERMES_DREAM_ENABLED=true
```

---

## 🧭 Architecture

```text
Hook (gateway:startup) -> ProactivePlatformWatcher (asyncio)
  tick() every 300s
  ├─ voice.load()           -> Personality Genome (9 dimensions)
  activity guard         -> skip if conversation not silent 30+ min
  ├─ cooldown.check()       -> dynamic interval driven by social_urge
  ├─ discovery.collect()    -> 10 content sources, every 4h
  ├─ dream.run_cycle()      -> memory consolidation, every 24h
  └─ LLM.compose()          -> message(s) -> WeChat push
```

---

## 🔥 Core Features

| Feature | Behavior |
|---|---|
| 🧠 Personality Genome | 9-dimensional voice vector with event-driven evolution. |
| ⏱️ Voice-linked Cooldown | `social_urge` controls send interval: `max(30, 120 - urge × 90)` minutes. |
| 🛑 Activity Guard | Sends only when conversation fully silent 30+ min (last message by Hermes, no message from either side in 30 min). |
| 🌐 Discovery Mesh | Collects from arXiv, GitHub, HN, V2EX, Bilibili, SSPAI, Zhihu, papers.cool, Jandan, Xiaohongshu. |
| 🧩 Context Freshness | Cosine decay over 30min-6h: `1.0 -> ~0.7 -> 0`. |
| 💬 Multi-message Burst | LLM may emit 1-5 messages separated by `---`, sent 2-5 seconds apart. |
| 🌙 Claude Dreaming | 4-stage memory cycle: Orient -> Gather -> Consolidate -> Prune. |
| 📝 Dream Auto-apply | High-confidence operations (`>=0.7`) write directly to `MEMORY.md` and affect voice genome. |
| 🔎 Pipeline Trace | One `tick_id` links discovery, composition, and delivery logs. |

---

## 🧱 Module Map

| Module | Responsibility |
|---|---|
| `voice_engine.py` | Personality Genome, 9D voice vector, event evolution, social urge. |
| `proactive_watcher.py` | Main loop, burst sending, pipeline logs, activity guard. |
| `discovery.py` | 10-platform content discovery. |
| `llm_message_composer.py` | Prompt construction, sanitizer, multi-message splitting. |
| `context_tracker.py` | Cross-session context tracking and cosine freshness decay. |
| `dream_engine.py` | 4-stage Claude Dreaming memory consolidation. |
| `cooldown_manager.py` | Dynamic cooldown from `social_urge`. |
| `handler.py` | Hook dispatch: `startup`, `session:start`, `agent:end`. |
| `safe_io.py` | Thread-safe I/O with `fcntl` locks and atomic writes. |
| `dream_prompt.py` | Dream prompt templates. |
| `dream_diff_store.py` | Dream diff persistence. |
| `log_rotate.py` | Daily log rotation, 7-day retention. |
| `alive_control.py` | Runtime lifecycle control. |

---

## ⚙️ Configuration

| Key | Required | Default / Range | Purpose |
|---|---:|---|---|
| `HERMES_PROACTIVE_PLATFORM_ENABLED` | Yes | `false` | Enables Hermes Alive proactive loop. |
| `HERMES_PROACTIVE_WEIXIN_CHAT_ID` | Yes | - | Target WeChat chat ID. |
| `VOICE_ENABLED` | No | `false` | Enables Personality Genome. |
| `HERMES_DREAM_ENABLED` | No | `false` | Enables Dream memory consolidation. |
| `TZ` | Recommended | `Asia/Shanghai` | Runtime timezone. |
| Quiet hours | Built-in | `00:30-08:30` | No proactive messages during this window. |
| Tick interval | Built-in | `300s` | Main watcher loop cadence. |
| Discovery interval | Built-in | `4h` | Content collection cadence. |
| Dream interval | Built-in | `24h` | Memory consolidation cadence. |

---

## 🧠 Design Principles

### 1. LLM Owns Content

Prompt controls voice, rhythm, topics, and intent. The sanitizer blocks only empty messages and overlong output.

### 2. Code Owns Hard Constraints

Python handles lifecycle, cooldowns, quiet hours, activity guard, delivery, persistence, and log traceability.

### 3. No Conversation Duty

Hermes Alive does not ask, suggest, check in, explain itself, or optimize for helpfulness. Self-expression comes first.

### 4. User Silence Is a Boundary

The watcher skips the whole tick unless:
- Hermes sent the last message, AND
- The entire conversation has been silent for 30+ minutes (no message from either side).

This prevents Alive from interrupting when Hermes just replied after a long LLM delay.

### 5. Memory Changes Behavior

Dream output is not decorative. High-confidence memory diffs are applied to `MEMORY.md`, then reflected by the voice genome.

---

## 🧩 Extension Points

| Area | Where to Extend |
|---|---|
| New content source | Add collector logic in `discovery.py`. |
| Voice dynamics | Extend genome dimensions or event rules in `voice_engine.py`. |
| Message policy | Modify prompt templates and sanitizer in `llm_message_composer.py`. |
| Memory behavior | Tune cycle stages in `dream_engine.py` and templates in `dream_prompt.py`. |
| Runtime controls | Add lifecycle commands in `alive_control.py`. |

---

## 📜 License

Hermes Alive is a Hermes Agent skill and follows the Hermes project license.
