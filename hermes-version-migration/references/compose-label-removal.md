# Compose 标签清除：删容器 + 重建

## 背景

Docker 不支持修改已有容器的 Labels。以下方法都 **无效**：

- `docker container update --label ...`（命令不存在）
- `POST /containers/{id}/update` API（只支持 restart policy 和资源限制）
- 直接编辑 `/var/lib/docker/containers/<id>/config.v2.json`（daemon 缓存不刷新）
- `kill -HUP dockerd`（daemon 忽略此信号，不杀容器但也不刷新缓存）
- `docker rename` 改名（compose 按 label 匹配，不按名字）

**唯一有效方法**：`docker rm` 删容器 + `docker create` 重建，不带 compose 标签。

## 步骤

### 1. 导出旧容器完整配置

```bash
docker inspect hermes-v017-gateway > /tmp/v017-gateway.json
```

### 2. 从 inspect JSON 提取参数，构建 `docker create` 命令

所需字段：
- `Config.Entrypoint` → `--entrypoint`
- `Config.Env` → `-e`
- `Config.User` → `-u`
- `Config.WorkingDir` → `-w`
- `Config.Hostname` → `-h`
- `HostConfig.RestartPolicy.Name` → `--restart`
- `HostConfig.NetworkMode` → `--network`
- `Mounts` → `-v`（区分 bind/volume）
- `HostConfig.SecurityOpt` → `--security-opt`
- `HostConfig.CapAdd` → `--cap-add`
- `Config.Labels` → `-l`（**排除** `com.docker.compose.*` 前缀）

### 3. 删除旧容器 + 重建（完整示例）

```bash
docker rm hermes-v017-gateway hermes-v017-dashboard

# Gateway
docker create \
  --name hermes-v017-gateway \
  --entrypoint /bin/sh \
  -e HERMES_HOME=/opt/data \
  -e TZ=Asia/Shanghai \
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
  -lc 'export PATH=...; cd /opt/hermes; exec ... gateway run --replace --force --no-supervise --accept-hooks -v'
```

### 4. 验证

```bash
# compose 项目标签应为空
docker inspect hermes-v017-gateway --format '{{index .Config.Labels "com.docker.compose.project"}}'
# 应输出空行

# dry-run 不应包含 v0.17 容器
docker compose -p hermes down --dry-run | grep v017
# 应无输出
```

## 自动化（via Paramiko from inside container）

容器内无 Docker socket 时，通过 SSH + Paramiko 远程操作 NAS：

```python
import paramiko, json

client.connect("192.168.125.12", username="vive", password="...")

def sudo(cmd):
    stdin, stdout, stderr = client.exec_command(f"sudo -S {cmd}")
    stdin.write("password\n"); stdin.flush()
    return stdout.read().decode()

# 获取配置
data = json.loads(sudo("docker inspect hermes-v017-gateway"))
# 构建 docker create 参数（排除 compose 标签）
# 省略具体实现，参考 SKILL.md 迁移步骤
```

## 陷阱

- 重建时 Cmd 参数必须完整（多部分命令如 `-lc "export PATH=...; exec ..."`）
- 不要遗漏 env vars（特别是 `HERMES_HOME`、`TZ` 等）
- Volume 挂载的 Source 路径必须存在且可访问
- `docker compose -p hermes ps` 不显示 ≠ `down` 不会误删——`down` 按 label 匹配，比 `ps` 更宽