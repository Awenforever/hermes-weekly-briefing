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

## Pitfalls
- Host DNS hijacks blocked domains to 127.0.0.1 (dnsmasq). Use explicit `--proxy` flag for curl or ensure proxy env is loaded.
- Docker daemon has its own proxy config (systemd override), so `docker pull` works regardless of shell env.
- Long-running operations should use terminal background mode.
- Non-login SSH sessions don't load `/etc/profile.d/` — always source proxy env explicitly if needed.

## Network Topology (for context)
- Host eth1: 192.168.125.12/24 (physical LAN)
- Host bridge0: 192.168.124.12/24 (bridged to iStoreOS VM)
- iStoreOS proxy: 192.168.124.88:7890
- Docker bridge: 172.17.0.0/16
- Default route: via 192.168.124.1 (iStoreOS)