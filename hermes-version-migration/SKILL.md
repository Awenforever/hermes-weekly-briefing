---
name: hermes-version-migration
description: >
  Proven playbook for migrating Hermes Agent between major versions on UGREEN NAS
  (Docker Compose). Covers pre-flight checks, data volume preparation, container
  naming strategy, entrypoint pitfalls, post-migration verification, and v0.17
  container preservation. Based on v0.17→v0.18 migration experience.
category: devops
---

# Hermes Agent 版本迁移（UGREEN NAS Docker Compose）

## 核心原则

1. **新容器先进，旧容器保留**：先起 v0.18，确认存活后才停 v0.17
2. **容器名继承**：旧容器改名（如 `hermes-v017-gateway`），新容器用原名（`hermes-hermes-1`）
3. **不改 compose 目录**：UGREEN `/volume2/@appstore/com.ugreen.docker.hermes/` 只读，用自己的 compose 文件
4. **数据卷用 Docker volume**（非 bind mount），避免 UID 权限问题
5. **必须设 `entrypoint: /bin/sh`**，绕过 s6-overlay

## 前置检查

```bash
# 在 NAS 上执行
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker images | grep hermes-agent
docker volume ls | grep hermes
```

## 迁移步骤

### 1. 准备 v0.18 数据卷

```bash
# 创建 Docker volume
docker volume create hermes-v018-data

# 从 v0.17 数据目录复制数据（在宿主机上）
sudo cp -r /volume2/Hermes-v017-current/{state.db,.env,config.yaml,skills,hooks,cron,weixin,memories,auth.json,SOUL.md} \
  /volume2/@docker/volumes/hermes-v018-data/_data/

# ⚠️ 关键：SSH key 必须复制
sudo mkdir -p /volume2/@docker/volumes/hermes-v018-data/_data/ssh
sudo cp /volume2/Hermes-v017-current/ssh/* /volume2/@docker/volumes/hermes-v018-data/_data/ssh/
sudo chmod 600 /volume2/@docker/volumes/hermes-v018-data/_data/ssh/*
```

**⚠️ Codex CLI 认证也必须迁移：**

```bash
# Codex OAuth 认证在旧数据的 .codex/ 目录中
sudo mkdir -p /volume2/@docker/volumes/hermes-v018-data/_data/home/.codex
sudo cp /volume2/Hermes-v017-current/home/.codex/auth.json \
  /volume2/@docker/volumes/hermes-v018-data/_data/home/.codex/
sudo cp /volume2/Hermes-v017-current/home/.codex/config.toml \
  /volume2/@docker/volumes/hermes-v018-data/_data/home/.codex/
```

没有这一步，新容器里的 `codex exec` 会 401 Unauthorized，所有 Codex 委托任务全部失败。

### 2. 准备 compose 文件

放在用户可写路径（非 `/volume2/@appstore/`）：

```yaml
# /home/vive/Hermes-v018-data/docker-compose-v018.yaml
services:
  hermes-v018-gateway:
    image: hermes-agent:v0.18.0-patched-v3
    container_name: hermes-hermes-1        # ⚠️ 继承原容器名
    entrypoint: /bin/sh                      # ⚠️ 必须绕过 s6-overlay
    command:
      - -lc
      - |
        export PATH="/opt/hermes/bin:/opt/hermes/.venv/bin:/usr/local/bin:/usr/bin:/bin:/usr/games"
        mkdir -p /tmp/hermes-v0180-gateway-cache/home ...
        cd /opt/hermes
        exec /opt/hermes/.venv/bin/hermes gateway run --no-supervise --accept-hooks -v
    restart: unless-stopped
    network_mode: host
    user: "0:0"
    security_opt:
      - seccomp=unconfined
      - apparmor=unconfined
    cap_add:
      - SYS_ADMIN
    volumes:
      - hermes-v018-data:/opt/data           # Docker volume
      - codex-auth:/opt/data/home/.codex     # Codex 认证独立 volume
      - /home/vive/Work:/home/vive/Work:rw   # bind mount
    environment:
      - HERMES_HOME=/opt/data
      - HERMES_ACCEPT_HOOKS=1
      - HERMES_ALLOW_ROOT_GATEWAY=1
      - HERMES_DASHBOARD=0
      - TZ=Asia/Shanghai
      - HERMES_WEIXIN_STARTUP_READY_NOTIFY=1
      - HERMES_PROACTIVE_PLATFORM_ENABLED=true
      - HERMES_PROACTIVE_WEIXIN_CHAT_ID=o9cq800ipxRzd6B0ooO0zo2DJ-MU@im.wechat

  hermes-v018-dashboard:
    image: hermes-agent:v0.18.0-patched-v3
    container_name: hermes-dashboard-1
    # ... 同上配置，command 改为 dashboard 命令
    command:
      - -lc
      - |
        ... exec /opt/hermes/.venv/bin/hermes dashboard --host 0.0.0.0 --port 19119 --insecure --no-open

volumes:
  hermes-v018-data:
    external: true
  codex-auth:
    external: true
```

### 3. 执行迁移

```bash
# 3a. 重命名旧容器（保留）
docker rename hermes-hermes-1 hermes-v017-gateway
docker rename hermes-dashboard-1 hermes-v017-dashboard

# 3b. 启动 v0.18
docker compose -f /home/vive/Hermes-v018-data/docker-compose-v018.yaml -p hermes up -d

# 3c. 监控 60 秒，每 5 秒检查
for i in $(seq 1 12); do
  echo "=== tick $i ==="
  docker ps --filter name=hermes-hermes-1 --format '{{.Status}}'
  docker logs hermes-hermes-1 --tail 5 2>&1 | grep -iE 'fatal|traceback|error|connected'
  sleep 5
done

# 3d. 确认存活（微信收到消息）后，停旧容器
docker stop hermes-v017-gateway hermes-v017-dashboard
```

### 4. 迁移后清理

```bash
# ⚠️ 旧容器的 compose 标签必须清除，否则 docker compose down 会误删
# 方法：删除旧容器并用 docker create 重建（不带 compose 标签）

# 获取旧容器配置
docker inspect hermes-v017-gateway > /tmp/v017-gateway.json

# 删除
docker rm hermes-v017-gateway hermes-v017-dashboard

# 重建（不带 compose 标签）
docker create \
  --name hermes-v017-gateway \
  --entrypoint /bin/sh \
  -e HERMES_HOME=/opt/data \
  ...（所有 env vars）... \
  --restart unless-stopped \
  --network host \
  -u 0:0 \
  --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \
  --cap-add SYS_ADMIN \
  -v /volume2/Hermes-v017-current:/opt/data \
  -v /home/vive/Work:/home/vive/Work \
  hermes-agent:v0.17.0 \
  -lc 'export PATH=...; cd /opt/hermes; exec ... gateway run ...'

# 验证
docker inspect hermes-v017-gateway --format '{{index .Config.Labels "com.docker.compose.project"}}'
# 应输出空行
```

### 5. 验证清单

| 检查项 | 命令 |
|--------|------|
| 容器名 | `docker ps --format '{{.Names}}' \| grep hermes` |
| compose 项目 | `docker inspect hermes-hermes-1 --format '{{index .Config.Labels "com.docker.compose.project"}}'` |
| 镜像版本 | `docker inspect hermes-hermes-1 --format '{{.Config.Image}}'` |
| entrypoint | 必须为 `/bin/sh` |
| 微信连通 | 发消息测试 |
| SSH key | `ls -la /opt/data/ssh/` |
| Codex 认证 | `codex doctor \| grep auth`（必须输出 `auth is configured`） |
| v0.17 不在 compose | `docker compose -p hermes ps` 不应显示 v0.17 |
| v0.17 不受 down 影响 | `docker compose -p hermes down --dry-run` 不应包含 v0.17 |

## 回滚

```bash
# 停 v0.18
docker stop hermes-hermes-1 hermes-dashboard-1

# 改回原名
docker rename hermes-v017-gateway hermes-hermes-1
docker rename hermes-v017-dashboard hermes-dashboard-1

# 启动 v0.17
docker start hermes-hermes-1 hermes-dashboard-1
```

## 迁移后清理

迁移完成后，宿主机 `~/` 会残留大量一次性文件。清理原则：

### 可立即删除
- 所有 `migrate-*.sh` `test-v018*.sh` `restore-*.sh` `rollback-*.sh` `start-v18.sh` `swap-final.sh`
- 所有 `*.log` `*-status.txt` 等日志文件
- `closing-prompt.txt` `grab-v18-logs.sh` `.sudo_as_admin_successful`
- 空的 `hermes-v018-patches/` 和 `hermes-alive-test-data/`

### 归档到 Work/Hermes/
- 补丁文件：`v18-patches/` `vive/` 中的 `.patch` 和 `Dockerfile`
- compose 文件备份
- `startup-notify-check.txt`

### 暂不删除
- `~/Hermes-v018-data/` — 容器 compose 元数据仍引用此路径，删了会破坏 `docker compose` 维护能力。等部署布局稳定后再清理。
- `~/base.py` `~/run.py` `~/weixin.py` — 可能是用户的源码快照，不在 git 中，需用户确认。

### 镜像瘦身
迁移会留下大量中间构建镜像。清理命令：
```bash
# 悬空镜像（无标签、无引用）
docker image prune -a

# 旧版构建标签（确认当前运行的镜像版本后执行）
docker rmi hermes-agent:v0.18.0-patched-v2 \
  hermes-agent:v0.18.0-weixin-enhanced-audit1 \
  hermes-agent:v0.18.0 \
  hermes-agent:v0.17.0-footerfix1 \
  hermes-agent:v0.17.0-dsmlfix1 \
  ...（所有中间 tag）
```

详见 [references/post-migration-cleanup.md](references/post-migration-cleanup.md)。

## 常见坑

| 坑 | 症状 | 解决 |
|----|------|------|
| s6-overlay 冲突 | 两个 gateway 进程 | `entrypoint: /bin/sh` |
| bind mount 权限 | hermes 用户 (UID 10000) 无法写入 | 用 Docker volume |
| compose 目录无写权限 | `/volume2/@appstore/` 归 root | 用自己的 compose 文件，`-p hermes` 保持项目名 |
| compose 标签残留 | `down` 误删旧容器 | 重建旧容器不带 compose 标签，详见 references/compose-label-removal.md |
| 改配置文件无效 | 编辑 config.v2.json 后 Docker daemon 缓存不刷新 | SIGHUP 无用，必须删容器重建。配置文件修改只在 daemon 启动时读取 |
| SSH key 未复制 | 容器内无法 SSH 到 NAS | 迁移数据卷时务必包含 `ssh/` 目录。如已遗漏，用 `docker cp` 补拷 |
| 两个 gateway 抢微信 | iLink 可能限制单连接 | 先停 v0.17 再起 v0.18，或先起 v0.18 确认后立即停 v0.17 |
| 脚本验证脆弱 | grep 匹配失败导致错误回滚 | 多维度验证（容器状态 + 日志 + 微信消息） |
| docker compose down | 会删除所有 `project=hermes` 标签的容器（含 v0.17 保留容器） | **绝对不要用 `docker compose down`**。停容器用 `docker stop`，删容器用 `docker rm` |
| compose 文件被清空 | 写入操作意外截断 compose yaml | 从 `docker inspect` 重建完整 compose，详见 references/compose-reconstruction.md |
| Codex 认证丢失 | `codex doctor` 显示 `no credentials`，`codex exec` 返回 401 | 迁移时未复制 `home/.codex/auth.json`。从旧数据卷补拷或创建独立 `codex-auth` volume |