# Post-Migration Self-Check from Inside Container

When you've migrated Hermes to a new version/container and can't access the Docker host
(e.g., SSH key missing from new data volume), verify what you CAN from inside.

## Two-Tier Verification

### Tier 1: Internal (always possible)

Run from inside the new container:

```bash
# 1. Gateway process — verify command matches expected
ps aux | grep "hermes gateway"

# 2. WeChat connectivity — check startup log
grep "weixin connected" /opt/data/logs/gateway.log | tail -3

# 3. Environment variable diff — compare against v0.17 reference
cat /proc/1/environ | tr '\0' '\n' | grep -iE "HERMES|TZ" | sort

# 4. Data directory integrity
ls /opt/data/skills/ /opt/data/hooks/ /opt/data/cron/ /opt/data/weixin/accounts/ /opt/data/memories/

# 5. Config file presence
head -5 /opt/data/config.yaml
grep -c "HERMES" /opt/data/.env

# 6. Cache path — confirms version
ls /tmp/hermes-v0180*/
```

### Tier 2: Host-level (requires Docker access)

These CANNOT be verified from inside. Give the user this consolidated block — ONE copy-paste operation:

```bash
echo "========== 1. 容器清单 =========="
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.State}}' | grep -iE 'hermes|NAMES'

echo "========== 2. 容器名 & compose 项目 =========="
docker inspect hermes-hermes-1 --format '容器: {{.Name}} | 项目: {{index .Config.Labels "com.docker.compose.project"}} | Compose文件: {{index .Config.Labels "com.docker.compose.config_files"}}' 2>/dev/null
docker inspect hermes-dashboard-1 --format '容器: {{.Name}} | 项目: {{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null

echo "========== 3. 镜像版本 =========="
docker inspect hermes-hermes-1 --format 'Gateway: {{.Config.Image}}'
docker inspect hermes-dashboard-1 --format 'Dashboard: {{.Config.Image}}'

echo "========== 4. v0.17 残留检查 =========="
docker ps -a --format '{{.Names}} {{.Status}}' | grep -i v017 || echo "无残留 ✓"

echo "========== 5. 关键参数 =========="
docker inspect hermes-hermes-1 --format '
entrypoint:  {{.Config.Entrypoint}}
cmd:         {{.Config.Cmd}}
restart:     {{.HostConfig.RestartPolicy.Name}}
network:     {{.HostConfig.NetworkMode}}
user:        {{.Config.User}}
security:    {{.HostConfig.SecurityOpt}}
cap_add:     {{.HostConfig.CapAdd}}'

echo "========== 6. 挂载详情 =========="
docker inspect hermes-hermes-1 --format '{{range .Mounts}}类型:{{.Type}} 源:{{.Source}} → 目标:{{.Destination}}
{{end}}'

echo "========== 7. 镜像详情 =========="
docker images hermes-agent:v0.18.0-patched-v3 --format '{{.Repository}}:{{.Tag}} 大小:{{.Size}} 创建:{{.CreatedAt}}' 2>/dev/null
```

**⚠️ CRITICAL: Always give these as a single consolidated block, not as individual multi-line commands.** Long multi-line commands get mangled when copy-pasted in WeChat terminals. Each `echo`/`docker` line is short enough to survive wrapping.

### Tier 2 Verification Fields

| # | Check | Key field to inspect |
|---|-------|---------------------|
| 1 | Container names match expected | `docker ps --format '{{.Names}}'` |
| 2 | Compose project label | `com.docker.compose.project` |
| 3 | Image version (both gateway + dashboard) | `{{.Config.Image}}` |
| 4 | Old containers stopped | `docker ps -a` for v017/v016 prefixes |
| 5 | Entrypoint override (/bin/sh) | `{{.Config.Entrypoint}}` |
| 6 | Security options inherited | `{{.HostConfig.SecurityOpt}}`, `{{.HostConfig.CapAdd}}` |
| 7 | Volumes correct (bind + docker volume) | `{{.Mounts}}` |
| 8 | Network mode (host) | `{{.HostConfig.NetworkMode}}` |
| 9 | User (0:0) | `{{.Config.User}}` |
| 10 | Restart policy (unless-stopped) | `{{.HostConfig.RestartPolicy.Name}}` |

## Report Format

Present results in a structured table:

- ✅ = verified, matches expected
- ❓ = needs host access
- ⚠️ = known issue, acknowledged

## Common Pitfall: Missing SSH Key

If `/opt/data/ssh/` doesn't exist in the new data volume, the SSH key wasn't copied
during migration. This blocks all Tier 2 checks.

**Recovery via docker cp (preferred — works with running container):**

```bash
sudo docker exec hermes-hermes-1 mkdir -p /opt/data/ssh
sudo docker cp /volume2/Hermes-v017-current/ssh/hermes_host_ed25519 hermes-hermes-1:/opt/data/ssh/hermes_host_ed25519
sudo docker exec hermes-hermes-1 chmod 600 /opt/data/ssh/hermes_host_ed25519
```

**Recovery via docker run (if old volume still mounted):**

```bash
docker run --rm -v old-volume:/src:ro -v new-volume:/dst alpine \
  cp -a /src/ssh /dst/
```

**Verify:**

```bash
# From inside the container
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no -o ConnectTimeout=10 vive@<nas-ip> "echo OK"
```