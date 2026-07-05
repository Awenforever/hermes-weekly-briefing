# 庄奕 Companion 架构

> 最后更新：2026-07-04 | 基于 hermes-companion v0.2.0 + Hermes v0.17.0

## 现状

庄奕的"主动性"由两层协作实现：

### 1. hermes-companion 插件（情绪+感知层）

**来源**：[gejifeng/Hermes_Soul_patch](https://github.com/gejifeng/Hermes_Soul_patch)（4⭐, 0 fork, v0.2.0）

**已启用功能：**
- `pre_llm_call` hook：每轮对话注入 [Companion状态] + [今日日程] + 时间上下文
- `post_llm_call` hook：基于 LLM 的情绪推断（valence/arousal/dominant 自动更新）
- `post_tool_call` hook：工具失败时小幅下调 valence
- `/mood` `/mood-set` `/heartbeat` `/agenda` `/recall` 命令
- 每日日程生成（daily_seed.py，LLM 基于 SOUL.md 生成事件）
- 跨日自动归档（world_state.py）

**未生效/未实现的功能：**
- ❌ 内置 heartbeat 线程 → Gateway 模式下 `ctx.inject_message()` 需 CLI ref（`hermes_cli/plugins.py:373`），不存在即返回 False。插件自动检测到 cron delivery 后跳过
- ❌ 人格演化（SOUL.md 自动更新）→ 只读不写，v0.2.0 未实现

**数据文件（均在 $HERMES_HOME，即 /opt/data）：**
- `EMOTION_STATE.md` — 情绪状态（JSON in markdown）
- `SOUL.md` — 人格定义（只被 daily_seed 读取）
- `companion/events.json` — 今日日程
- `companion/daily_seed.json` — 锚点事件模板
- `companion/companion_pending.txt` — 待发送主动消息队列

### 2. Cron 任务（推送层）

插件做不到的事交给 cron：

| ID | 名称 | 频率 | 职责 |
|----|------|------|------|
| `4ad1d03e1ad0` | companion-heartbeat | `0 */2 * * *` | 读情绪+日程，4种触发（日程到期/高激活/早安/晚间），决定是否主动搭话 |
| `066eab1cebf3` | companion-discovery | `0 10 * * *` | 刷 arXiv/HN/Reddit/GitHub，挑1-2个有趣内容分享 |

## 架构局限

根本问题：**Hermes 的插件 API 没有 `ctx.send_to_platform()` 接口。**

```
CLI 模式：inject_message → cli._pending_input.put(msg) → 对话循环读到 → ✅
Gateway 模式：inject_message → cli is None → return False → ❌ 退化为 pending 文件
```

Gateway 的 agent 生命周期是请求/响应式的（来消息→创建session→处理→返回→挂起），没有持久事件循环让 heartbeat 注入消息。cron 通过独立 session + `deliver: origin` 绕过了这个限制，但本质是外部定时器驱动，不是 agent 内部状态驱动的"自发行为"。

## 生态全景

| 方案 | 主动推送 | 实现 | 状态 |
|------|----------|------|------|
| OpenClaw | ✅ 原生 | heartbeat线程+gateway事件循环同进程 | ~30k⭐, 开源 |
| Hermes + cron | ⚠️ 模拟 | 外部定时器触发独立session | 当前方案 |
| Hermes only | ❌ | Issue #9645 (P3, 开半年未实现) | - |
| hermes-companion | ⚠️ 部分 | 情绪+感知可用，推送需cron | 4⭐ |
| Replika | ✅ | 闭源商业app | 非开源 |
| Meta主动聊天机器人 | ✅ | WhatsApp/Facebook原生 | 非开源 |

## 未来改进方向

1. 短期：把 cron 从固定 2h 改成随机间隔 + 基于状态触发（更自然）
2. 中期：关注 Hermes 是否给插件 API 加 `send_to_platform()` 能力
3. 长期：如 OpenClaw 在中文/微信生态成熟，可考虑迁移