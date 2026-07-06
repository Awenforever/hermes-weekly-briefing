<div align="center">

# Hermes Alive

**Hermes Agent 的 gateway-native 主动 AI 伴侣。**

![version](https://img.shields.io/badge/version-v2.3.0-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![license](https://img.shields.io/badge/license-Hermes%20Project-green)

[English README](./README.md)

</div>

---

## 🧬 这是什么

Hermes Alive 是 Hermes Agent 的零侵入式主动伴侣 skill。
它以 Hermes gateway hook 形式安装，作为后台 `asyncio` 任务运行，定期发现内容，用 LLM 生成中文消息，并推送到微信。

它不是聊天机器人。不提问、不建议、不报天气、不关心，也不承担对话义务。

> **核心理念：**“什么都不负责的人”  
> LLM 负责创意输出，代码只处理硬约束。

---

## ⚡ 快速开始

```bash
cd /opt/data/skills/hermes/hermes-alive
bash scripts/deploy.sh --all

# 配置 /opt/data/.env
docker-compose up -d hermes
```

最小 `.env`：

```bash
HERMES_PROACTIVE_PLATFORM_ENABLED=true
HERMES_PROACTIVE_WEIXIN_CHAT_ID=<wechat_chat_id>
TZ=Asia/Shanghai
```

推荐开启：

```bash
VOICE_ENABLED=true
HERMES_DREAM_ENABLED=true
```

---

## 🧭 架构

```text
Hook (gateway:startup) -> ProactivePlatformWatcher (asyncio)
  tick() every 300s
  ├─ voice.load()           -> Personality Genome (9维)
  ├─ activity guard         -> 对话静默不足30分钟则跳过
  ├─ cooldown.check()       -> social_urge 驱动动态间隔
  ├─ discovery.collect()    -> 10个内容源，每4h
  ├─ dream.run_cycle()      -> 记忆整合，每24h
  └─ LLM.compose()          -> 生成消息 -> 推送到微信
```

---

## 🔥 核心特性

| 特性 | 行为 |
|---|---|
| 🧠 Personality Genome | 9维性格向量，事件驱动进化。 |
| ⏱️ Voice-linked Cooldown | `social_urge` 驱动发送间隔：`max(30, 120 - urge × 90)` 分钟。 |
| 🛑 Activity Guard | 仅当 idle 时发送：Hermes 不在执行任务 + 最后发言者为Hermes + 对话静默30+分钟。 |
| 🌐 Discovery Mesh | 覆盖 arXiv、GitHub、HN、V2EX、Bilibili、少数派、知乎、papers.cool、煎蛋、小红书。 |
| 🧩 Context Freshness | 30min-6h 余弦衰减：`1.0 -> ~0.7 -> 0`。 |
| 💬 Multi-message Burst | LLM 可生成 1-5 条消息，使用 `---` 分隔，间隔 2-5 秒发送。 |
| 🌙 Claude Dreaming | 4阶段记忆整合：Orient -> Gather -> Consolidate -> Prune。 |
| 📝 Dream Auto-apply | 高置信度操作（`>=0.7`）直接写入 `MEMORY.md`，并影响 voice genome。 |
| 🔎 Pipeline Trace | 单个 `tick_id` 串联 discovery、compose、sent 全链路日志。 |

---

## 🧱 模块地图

| 模块 | 职责 |
|---|---|
| `voice_engine.py` | Personality Genome、9维性格向量、事件进化、社交欲望。 |
| `proactive_watcher.py` | 主循环、多消息突发、pipeline 日志、activity guard。 |
| `discovery.py` | 10平台内容发现。 |
| `llm_message_composer.py` | Prompt 构建、消息清洗、多消息分割。 |
| `context_tracker.py` | 跨 session 上下文追踪、余弦新鲜度衰减。 |
| `dream_engine.py` | 4阶段 Claude Dreaming 记忆整合。 |
| `cooldown_manager.py` | `social_urge` 驱动动态冷却。 |
| `handler.py` | Hook 事件分发：`startup`、`session:start`、`agent:end`。 |
| `safe_io.py` | 线程安全 I/O：`fcntl` 锁、原子写入。 |
| `dream_prompt.py` | Dream prompt 模板。 |
| `dream_diff_store.py` | Dream diff 持久化。 |
| `log_rotate.py` | 日志每日轮转，保留 7 天。 |
| `alive_control.py` | 运行时生命周期控制。 |

---

## ⚙️ 配置

| 配置项 | 必需 | 默认 / 范围 | 作用 |
|---|---:|---|---|
| `HERMES_PROACTIVE_PLATFORM_ENABLED` | 是 | `false` | 开启 Hermes Alive 主动循环。 |
| `HERMES_PROACTIVE_WEIXIN_CHAT_ID` | 是 | - | 目标微信 chat ID。 |
| `VOICE_ENABLED` | 否 | `false` | 开启 Personality Genome。 |
| `HERMES_DREAM_ENABLED` | 否 | `false` | 开启 Dream 记忆整合。 |
| `TZ` | 推荐 | `Asia/Shanghai` | 运行时区。 |
| Quiet hours | 内置 | `00:30-08:30` | 该时间段不主动发送。 |
| Tick interval | 内置 | `300s` | 主 watcher 循环频率。 |
| Discovery interval | 内置 | `4h` | 内容发现频率。 |
| Dream interval | 内置 | `24h` | 记忆整合频率。 |

---

## 🧠 设计原则

### 1. LLM 管内容

Prompt 决定声音、节奏、话题和意图。sanitizer 只拦截空消息和超长输出。

### 2. 代码管硬约束

Python 只处理生命周期、冷却、安静时段、activity guard、投递、持久化和日志链路。

### 3. 零对话义务

Hermes Alive 不提问、不建议、不寒暄、不解释自己，也不以“有帮助”为首要目标。自我表达优先。

### 4. 用户沉默是边界

watcher 只有在以下条件同时满足时才继续 tick：
- Hermes 当前未在执行任务（session idle），且
- 最后发言者是 Hermes，且
- 整个对话已静默 30+ 分钟。

避免打断长任务执行或刚活跃过的对话。

### 5. 记忆会改变行为

Dream 结果不是装饰。高置信度 memory diff 会写入 `MEMORY.md`，再被 voice genome 反映到表达方式里。

---

## 🧩 扩展点

| 方向 | 修改位置 |
|---|---|
| 新内容源 | 在 `discovery.py` 增加 collector。 |
| 声音动态 | 在 `voice_engine.py` 扩展 genome 维度或事件规则。 |
| 消息策略 | 修改 `llm_message_composer.py` 的 prompt 和 sanitizer。 |
| 记忆行为 | 调整 `dream_engine.py` 的周期阶段和 `dream_prompt.py` 模板。 |
| 运行时控制 | 在 `alive_control.py` 增加生命周期命令。 |

---

## 📜 许可

Hermes Alive 是 Hermes Agent skill，遵循 Hermes 项目许可。
