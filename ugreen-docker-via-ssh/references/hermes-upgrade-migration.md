# Hermes 版本升级迁移参考

UGREEN NAS Docker 上 Hermes Agent 版本升级的迁移模式、风险点和操作步骤。

## 迁移模式

目标：新容器无缝继承旧容器的一切（容器名、compose labels、挂载、权限、应用中心链接）。

### 核心约束

- **容器名固定**：`hermes-hermes-1` (gateway) + `hermes-dashboard-1` (dashboard)。应用中心通过 compose project=hermes 标签关联，容器名改变会断开链接。
- **Compose labels 保留**：docker-compose 自动注入的标签（`com.docker.compose.project`, `com.docker.compose.service`, `com.docker.compose.project.config_files` 等）必须保持一致。
- **数据卷通过 symlink**：`/volume2/Hermes-v017-current` → 实际数据目录。升级时更新 symlink 指向新目录即可。
- **旧容器重命名保留**：不删除，改名为 `hermes-v0XX-gateway/dashboard`。已有 v0.10 容器按此模式保留。

### 标准流程

1. **全量审计**：检查当前容器 inspect、compose 文件、数据目录权限、state.db schema
2. **构建/拉取新镜像**：`hermes-agent:v0.18.0`
3. **创建新数据目录**：复制 state.db + config.yaml + .env + sessions/ + skills/ + hooks/ + cron/ + pairing/ + hermes_alive_shared/
4. **更新 docker-compose.yaml**：image 标签、数据卷路径、缓存路径
5. **停止旧容器**：`docker stop hermes-hermes-1 hermes-dashboard-1`
6. **重命名旧容器**：`docker rename hermes-hermes-1 hermes-v017-gateway` 等
7. **启动新容器**：`docker compose up -d`
8. **更新 symlink**：`ln -sfn /volume2/Hermes-v018-current /volume2/... → Hermes-v018-current`
9. **验证**：微信连通、hooks 加载、state.db 可读写

## 数据卷内容

```
/opt/data/ (HERMES_HOME)
├── config.yaml           # 生产配置
├── .env                  # API keys (644 root:root)
├── state.db              # SQLite session store (容器内 hermes:hermes)
├── sessions/sessions.json
├── skills/               # git repo
├── hooks/hermes-alive/   # 生产 hook
├── logs/                 # gateway.log, agent.log
├── cron/jobs.json
├── pairing/              # weixin-approved.json
├── auth.json
├── gateway_state.json
├── channel_directory.json
└── hermes_alive_shared/  # voice_state.json, context_queue.json
```

## 应用中心集成

- **appId**: `com.ugreen.docker.hermes`
- **compose project**: `hermes`
- **compose 目录**: `/volume2/@appstore/com.ugreen.docker.hermes/`
- **关键文件**: `docker-compose.yaml`, `config.json`, `docker-compose.tmpl`
- 应用中心通过 compose labels 发现容器，不通过容器名
- 在应用中心外手工起/停容器，应用中心可能显示状态不一致但功能不受影响

## 文件权限注意事项

- 容器内运行用户为 `root` (0:0)，但 `/opt/hermes/` 内部有 `hermes` 用户
- 数据目录 owner 在容器内显示为 `hermes:hermes` (UID/GID 可能与宿主机不同)
- NAS 宿主机可能显示 `UNKNOWN:UNKNOWN` — 不影响容器内访问
- `.env` 文件为 `root:root 644`，`config.yaml` 为 `hermes:hermes 700` — 权限不一致但功能正常
- 新镜像如果内部 UID 变化，可能导致旧数据文件无法访问 → 需要验证

## 风险点

### 阻断项
- state.db schema 跨版本 breaking change — 需在迁移前确认兼容性
- 新镜像 hermes 用户 UID 变化导致数据目录权限拒绝
- WeChat enhance patches 在新版 weixin.py 上需重新验证 `git apply --check`

### 需注意
- docker-compose 模板变量（`WORK_PATH`, `PATH`）来自应用中心安装参数，不能硬编码
- WeChat webhook 回调不依赖容器名，依赖的是网关端口/地址（host 网络下不变）
- 微信断线时间 = stop 旧容器 + start 新容器 + gateway 启动 (~30-60s)
- hermes-python-tools 容器独立，不受升级影响
- 测试脚本不能放在 `/volume2/Hermes-v017-current/` 下——该目录 mode 700 属主 UID 10000，NAS 用户 `vive` 无法读取。应放到 `/tmp/`。

## 升级前测试容器验证

在正式迁移前，必须先创建**测试容器**（不同容器名、独立数据目录副本）进行全量验证：

1. **复制数据目录**：`cp -a /volume2/Hermes-v017-current /volume2/Hermes-v018-test`
2. **构建带 patch 的镜像**：`FROM hermes-agent:v0.18.0` + `COPY patches/ + RUN git apply`
3. **创建测试容器**：
   - `hermes-test-gateway`：不加微信环境变量，不连真实微信
   - `hermes-test-dashboard`：端口 `19120` 避免冲突
   - 挂载测试数据目录 `/volume2/Hermes-v018-test:/opt/data`
4. **验证清单**（至少 20 项）：容器启动、数据兼容、hook 加载、weixin.py 编译、skills 同步、config 迁移、Hermes Alive state、dashboard HTTP、cron jobs、文件读写
5. 全部通过后才执行生产迁移

## WeChat Patch 版本管理

WeChat enhance patches 随 Hermes 版本升级可能需要重新适配。版本管理规范：

```
patches/
├── 001-weixin-continue-hook.patch        # 当前最新适配版本
├── 001-weixin-continue-hook.v017.patch   # v0.17 归档
├── 002-weixin-footer-hook.patch          # 当前最新适配版本
├── 002-weixin-footer-hook.v017.patch     # v0.17 归档
└── CHANGELOG.md
```

规则：
- 无后缀 `.patch` = 当前最新适配版本
- `.v017.patch` = 旧版归档
- 升级时 `git apply --check` 通过 → 不动；失败 → 生成新归档 + 重写当前版

## 历史容器/目录

- `hermes-v010-gateway` / `hermes-v010-dashboard`: UGREEN 官方 v1 镜像，Created 状态
- `/volume2/` 下有 20+ 个历史数据目录（不同迭代版本）
- v0.10 时期手动挂载了 weixin.py 和 run.py 单个文件；v0.17 起不再需要