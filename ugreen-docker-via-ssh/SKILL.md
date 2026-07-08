---
name: ugreen-docker-via-ssh
description: |
  Manage Docker containers on UGREEN NAS host from inside the Hermes container 
  via SSH. All docker commands require sudo. Never use 'docker compose down'.
category: devops
---

# UGREEN NAS Docker via SSH

Use when Hermes inside a Docker container needs to manage Docker on the UGREEN NAS host.

## Prerequisites
- Hermes SSH key at `/opt/data/ssh/hermes_host_ed25519`
- Host SSH accessible at `vive@192.168.125.12`
- **Docker commands require `sudo`** — `vive` is NOT in the `docker` group. Always use `sudo -S` with the vive password. For scripted multi-command SSH from inside the container, use paramiko-based Python SSH (see `references/paramiko-ssh-pattern.md`).

> ⚠️ **CRITICAL: NEVER use `docker compose down` to stop containers.**  
> `down` removes containers — it will delete running AND stopped containers labeled in the project.  
> Always use `docker stop <name>` to stop and `docker rm <name>` ONLY when explicitly intending to delete.  
> Before any `down`, always run `docker compose -p <project> down --dry-run` to see what WOULD be removed.

## SSH Command Pattern

```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  'sudo docker <command>'
```

- `StrictHostKeyChecking=no` — skip host key prompt
- `sudo` required for all docker commands
- For multi-command scripts, use paramiko-based Python SSH (see `references/paramiko-ssh-pattern.md`) to handle sudo password prompts programmatically

## Common Operations

### Pull image
```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  'docker pull <image>'
```

### Run container
```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  'docker run -d --name <name> --restart unless-stopped -p <host>:<container> <image>'
```

### Restart container
```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  'docker restart <name>'
```

### Check logs
```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  'docker logs <name> --tail 20'
```

### Execute in container
```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  'docker exec <name> <command>'
```

## Docker Compose Operations

Hermes containers (`hermes-hermes-1`, `hermes-dashboard-1`) are managed by docker compose. The compose file lives at:

```
/volume2/@appstore/com.ugreen.docker.hermes/docker-compose.yaml
```

### Find compose directory
```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  "docker inspect hermes-hermes-1 --format '{{index .Config.Labels \"com.docker.compose.project.working_dir\"}}'"
```

### Restart Hermes (picks up config changes)
```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  'cd /volume2/@appstore/com.ugreen.docker.hermes && docker compose restart hermes'
```

### Verify config inside Hermes container after restart
```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  'docker exec hermes-hermes-1 grep -A5 "pattern" /opt/data/config.yaml'
```

## Compose Label Management

### Stripping compose labels from stopped containers

Docker does NOT support modifying labels on existing containers. To remove compose labels without losing the container:

1. Export full config: `docker inspect <name>`
2. Delete the container: `docker rm <name>`
3. Recreate with `docker create --name <name>` using the same config but **excluding all `com.docker.compose.*` labels**

Key: use inspect output to reconstruct ALL config (entrypoint, env, volumes, restart, network, user, security_opt, cap_add, labels minus compose-ones, image, cmd). See `references/compose-label-stripping.md` for the full Python script.

After recreation, verify with:
```bash
docker compose -p <project> down --dry-run  # should NOT include the stripped containers
```

### Why this matters

Containers with `com.docker.compose.project=<project>` labels are tracked by compose. `docker compose -p <project> down` will DELETE them even if they're stopped and renamed. Stripping labels protects retired containers from accidental removal. ALWAYS dry-run first.

## Pitfalls
- Host DNS hijacks blocked domains to 127.0.0.1 (dnsmasq). Use explicit `--proxy` flag for curl or ensure proxy env is loaded.
- Docker daemon has its own proxy config (systemd override), so `docker pull` works regardless of shell env.
- Long-running operations should use terminal background mode.
- Non-login SSH sessions don't load `/etc/profile.d/` — always source proxy env explicitly if needed.
- **`docker restart` ≠ `docker compose restart`**: `docker restart hermes-hermes-1` restarts the container process but `docker compose restart hermes` is the canonical way for compose-managed containers. Both work, but compose is preferred for consistency.
- **Config changes to auxiliary models** (vision, approval, etc.) require a Hermes restart to take effect — `hermes config set` writes the file but the running process caches config at startup.
- **700 permission on data directory blocks `vive`**: The Hermes data directory is mode `700` owned by UID `10000`. The NAS user `vive` cannot read from or write to it directly. When deploying test scripts from inside the container, write them to `/tmp/` on the NAS instead of into the data directory. Docker commands still work with `sudo`.

- **Cross-permission file copy via Docker**: To copy files between a 700-protected directory and a `vive`-accessible directory, use `docker run --rm` with bind mounts (Docker runs as root inside the container, bypassing host file permissions):
  ```bash
  # Copy a single file out of the protected directory
  docker run --rm -v /volume2/Hermes-v017-current:/src:ro -v /tmp:/dst alpine cp /src/skills/hermes-wechat-enhance/patches/001.patch /dst/
  
  # Clone entire data directory
  docker run --rm -v /volume2/Hermes-v017-current:/src:ro -v /volume2:/dst alpine cp -a /src /dst/Hermes-v018-test
  ```

- **Docker build context path**: When building images with `docker build -f /tmp/Dockerfile /some/path`, the build context path must be accessible to `vive`. Protected Hermes data directories cannot be used directly — copy needed files to `/tmp/` first using the Docker `cp` pattern above.

## Hermes Version Upgrade / Migration

When upgrading Hermes to a new version on the UGREEN NAS, load the migration reference:

- `references/hermes-upgrade-migration.md` — full audit checklist, data volume layout, compose/app-center constraints, rollback strategy.

Key rules: never touch production without prior audit; preserve container names and compose labels; use data-directory symlink swap pattern; old containers get renamed, not deleted.

## Network Topology (for context)
- Host eth1: 192.168.125.12/24 (physical LAN)
- Host bridge0: 192.168.124.12/24 (bridged to iStoreOS VM)
- iStoreOS proxy: 192.168.124.88:7890
- Docker bridge: 172.17.0.0/16
- Default route: via 192.168.124.1 (iStoreOS)