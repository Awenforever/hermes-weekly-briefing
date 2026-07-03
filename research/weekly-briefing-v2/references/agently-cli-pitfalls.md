# agently-cli 常见陷阱

## stderr 混入 stdout 导致 JSON 解析失败

**现象：**
```
json.decoder.JSONDecodeError: Extra data: line 56 column 1 (char 1879)
```

**原因：**
`agently-cli` 的提示文字（`tip: agently-cli message +read --id ...`）输出到 **stderr**。当使用 `2>&1` 把 stderr 合并到 stdout 后管道给 `json.load()`，JSON 后面多了一段非 JSON 文本，解析炸了。

**复现：**
```bash
# 会炸
agently-cli message +list --limit 1 2>&1 | python3 -c "import json,sys; json.load(sys.stdin)"

# 正常（stderr 丢弃）
agently-cli message +list --limit 1 2>/dev/null | python3 -c "import json,sys; json.load(sys.stdin)"

# 正常（不合并）
agently-cli message +list --limit 1 | python3 -c "import json,sys; json.load(sys.stdin)"
```

**规则：** 永远不要对 agently-cli 使用 `2>&1` 管道到 JSON 解析器。如果需要同时捕获 stderr，分开处理：
```bash
agently-cli message +send ... > /tmp/stdout.txt 2> /tmp/stderr.txt
```

## 两阶段发送

agently-cli 的邮件发送需要两次调用：
1. 第一次：获取 `confirmation_token`
2. 第二次：带 `--confirmation-token {token}` 重新调用

设 `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1` 后 runner 会自动处理两次调用。

## 认证过期

如果 `agently-cli +me` 返回非 0，需要重新 OAuth 登录：
```bash
agently-cli auth login
```