# Hermes Gateway Hook 部署模式

## 概述

Hermes v0.17.0 支持 `~/.hermes/hooks/` 目录下的生命周期 hook，可在不修改 Hermes 源码的情况下注入 Gateway 级行为。这是部署 gateway 扩展（如主动消息 watcher）的首选方式。

## 目录结构

```
$HERMES_HOME/hooks/<hook-name>/
├── HOOK.yaml      # 元数据：name, version, events, description
└── handler.py     # async def handle(event_type, context)
```

## HOOK.yaml 格式

```yaml
name: my-hook
version: "1.0"
events:
  - gateway:startup
description: "描述这个 hook 做什么"
```

## handler.py 签名

```python
async def handle(event_type: str, context: dict):
    """event_type: 如 'gateway:startup'
       context: {'platforms': ['weixin', 'telegram', ...]}
    
    注意：HookRegistry.emit() 会 await handler 的返回值。
    如果需要启动长期运行的 background task，必须在 handler 内
    用 asyncio.create_task() 启动，然后立即 return。
    否则会阻塞 Gateway 启动。
    """
```

## 访问 Gateway 内部资源

通过模块级 `_gateway_runner_ref()` 获取运行时 runner 引用：

```python
from gateway.run import _gateway_runner_ref

runner = _gateway_runner_ref()
if runner is not None:
    adapter = runner.adapters.get(Platform.WEIXIN)
    if adapter is not None:
        await adapter.send(chat_id, content, metadata={...})
```

此模式已被以下组件使用：
- `tools/send_message_tool.py` — 发送消息工具
- `cron/scheduler.py` — cron 定时投递
- `gateway/kanban_watchers.py` — kanban 通知

## 关键约束

1. **不要阻塞 startup**：handler 中创建 task 后立即 return
2. **门控**：用环境变量控制是否激活
3. **微信 footer**：传 `is_system: True` 等 metadata 确保系统消息正确标记
4. **adapter 缺失**：静默跳过，不抛异常
5. **回滚**：关 env var 或删除 hook 目录即可

## 验证

```bash
# 查看 hook 是否加载
grep "hooks\]" /opt/data/logs/gateway.log

# 查看 hook 执行
grep "<hook-name>" /opt/data/logs/gateway.log
```

## 与 Plugin 对比

| | Hook | Plugin |
|------|------|--------|
| 无需修改核心 | ✅ | ✅ |
| Gateway 生命周期 | ✅ gateway:startup/shutdown | ⚠️ pre/post_llm_call 等 |
| 可访问 adapter | ✅ 通过 _gateway_runner_ref | ❌ ctx 无此引用 |
| 主动推送 | ✅ | ❌ inject_message 仅 CLI |
| 复杂度 | 低（2 文件） | 中（需 plugin.yaml + __init__） |