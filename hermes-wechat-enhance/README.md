# Hermes WeChat Enhance

## 中文

这是 Hermes 微信增强 skill，所有文件都位于 `/opt/data/skills/hermes-wechat-enhance/`，不会直接修改 `/opt/hermes/` 或 `/opt/data/hooks/`。

功能：

- 通过 `agent:start` 和 `agent:end` hook 旁路记录入站、出站消息。
- 使用独立 JSONL 文件 `~/.hermes/wechat_enhance/messages.jsonl` 存储消息。
- 提供 `/continue` patch，将命令显式透传给 gateway command router。
- 提供 footer 控制 patch，在 Weixin adapter 内直接根据 metadata/env 追加 footer。

安装 hook：

```bash
mkdir -p ~/.hermes/hooks
ln -sfn /opt/data/skills/hermes-wechat-enhance/hooks/hermes-wechat-enhance ~/.hermes/hooks/hermes-wechat-enhance
export PYTHONPATH="/opt/data/skills/hermes-wechat-enhance:${PYTHONPATH:-}"
```

检查 patch：

```bash
cd /opt/hermes
git apply --check /opt/data/skills/hermes-wechat-enhance/patches/001-weixin-continue-hook.patch
git apply --check /opt/data/skills/hermes-wechat-enhance/patches/002-weixin-footer-hook.patch
```

应用 patch：

```bash
cd /opt/hermes
git apply /opt/data/skills/hermes-wechat-enhance/patches/001-weixin-continue-hook.patch
git apply /opt/data/skills/hermes-wechat-enhance/patches/002-weixin-footer-hook.patch
```

## English

This Hermes WeChat enhancement skill lives entirely under `/opt/data/skills/hermes-wechat-enhance/`. It does not modify `/opt/hermes/` or `/opt/data/hooks/` directly.

Features:

- Captures inbound and outbound messages through `agent:start` and `agent:end`.
- Stores messages in the independent JSONL file `~/.hermes/wechat_enhance/messages.jsonl`.
- Provides a `/continue` patch that explicitly passes the command through to the gateway command router.
- Provides a footer-control patch that appends the footer inline from metadata/env inside the Weixin adapter.

Hook installation:

```bash
mkdir -p ~/.hermes/hooks
ln -sfn /opt/data/skills/hermes-wechat-enhance/hooks/hermes-wechat-enhance ~/.hermes/hooks/hermes-wechat-enhance
export PYTHONPATH="/opt/data/skills/hermes-wechat-enhance:${PYTHONPATH:-}"
```

Patch check:

```bash
cd /opt/hermes
git apply --check /opt/data/skills/hermes-wechat-enhance/patches/001-weixin-continue-hook.patch
git apply --check /opt/data/skills/hermes-wechat-enhance/patches/002-weixin-footer-hook.patch
```

Patch apply:

```bash
cd /opt/hermes
git apply /opt/data/skills/hermes-wechat-enhance/patches/001-weixin-continue-hook.patch
git apply /opt/data/skills/hermes-wechat-enhance/patches/002-weixin-footer-hook.patch
```
