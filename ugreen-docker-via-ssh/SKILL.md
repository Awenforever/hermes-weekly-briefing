---
name: ugreen-docker-via-ssh
description: |
  Manage Docker containers on UGREEN NAS host from inside the Hermes container 
  via SSH. Hermes SSH key and docker group membership eliminate the need for sudo.
category: devops
---

# UGREEN NAS Docker via SSH

Use when Hermes inside a Docker container needs to manage Docker on the UGREEN NAS host.

## Prerequisites
- Hermes SSH key at `/opt/data/ssh/hermes_host_ed25519`
- Host SSH accessible at `vive@192.168.125.12`
- **User `vive` is in `docker` group** → no sudo needed for Docker commands

## SSH Command Pattern

```bash
ssh -i /opt/data/ssh/hermes_host_ed25519 -o StrictHostKeyChecking=no vive@192.168.125.12 \
  '. /etc/profile.d/99-local-proxy.sh 2>/dev/null; docker <command>'
```

- `. /etc/profile.d/99-local-proxy.sh` — needed for non-login SSH sessions; loads HTTP_PROXY/HTTPS_PROXY/NO_PROXY
- `StrictHostKeyChecking=no` — skip host key prompt
- No sudo required — `vive` is in `docker` group

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

## Pitfalls
- Host DNS hijacks blocked domains to 127.0.0.1 (dnsmasq). Use explicit `--proxy` flag for curl or ensure proxy env is loaded.
- Docker daemon has its own proxy config (systemd override), so `docker pull` works regardless of shell env.
- Long-running operations should use terminal background mode.
- Non-login SSH sessions don't load `/etc/profile.d/` — always source proxy env explicitly if needed.
- **`docker restart` ≠ `docker compose restart`**: `docker restart hermes-hermes-1` restarts the container process but `docker compose restart hermes` is the canonical way for compose-managed containers. Both work, but compose is preferred for consistency.
- **Config changes to auxiliary models** (vision, approval, etc.) require a Hermes restart to take effect — `hermes config set` writes the file but the running process caches config at startup.

## Network Topology (for context)
- Host eth1: 192.168.125.12/24 (physical LAN)
- Host bridge0: 192.168.124.12/24 (bridged to iStoreOS VM)
- iStoreOS proxy: 192.168.124.88:7890
- Docker bridge: 172.17.0.0/16
- Default route: via 192.168.124.1 (iStoreOS)