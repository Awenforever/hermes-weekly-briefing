---
name: ugreen-network-diagnostics
description: Network proxy and DNS debugging for UGREEN NAS with iStoreOS/mihomo soft router. Covers interface mapping, DNS hijacking detection, proxy configuration locations, connectivity testing with/without proxy, GitHub token validation, and SSH-based Docker management from Hermes container.
category: devops
---

# Network Proxy & DNS Debugging for UGREEN NAS + iStoreOS

## When to use
When network connectivity issues arise — pip times out, curl fails on certain sites but not others, Docker pulls work but host commands don't, or DNS returns unexpected IPs (like 127.0.0.1 for external domains).

## Quick diagnosis checklist

### 1. Map the network topology
```bash
ip addr show | grep -E "inet |state"   # All interfaces and IPs
ip route                                # Routing table
```
Key interfaces on UGREEN NAS:
- `eth1`: physical LAN (192.168.125.x)
- `bridge0`: bridge to iStoreOS VM (192.168.124.x)
- `docker0`: Docker bridge (172.17.0.0/16)
- `virbr0-2`: libvirt/KVM bridges
- Default route usually goes through bridge0 → iStoreOS gateway

### 2. Check DNS hijacking
```bash
# Local DNS (likely dnsmasq on 127.0.0.1)
dig +short youtube.com @127.0.0.1
# External DNS for comparison
dig +short youtube.com @223.5.5.5
dig +short youtube.com @8.8.8.8
```
iStoreOS dnsmasq hijacks blocked domains to 127.0.0.1. If external DNS queries are also intercepted (iptables DNAT), the proxy must be used explicitly.

### 3. Test connectivity with and without proxy
```bash
# Without proxy
curl -s -o /dev/null -w "HTTP %{http_code}" --max-time 5 https://www.youtube.com
# With explicit proxy
curl -s -o /dev/null -w "HTTP %{http_code}" --proxy http://192.168.124.88:7890 --max-time 10 https://www.youtube.com
```

### 4. Check proxy configuration locations
```bash
env | grep -i proxy                    # Current session
cat /etc/environment                   # System-wide
grep -r proxy /etc/profile.d/          # Login shell scripts
cat /etc/systemd/system/docker.service.d/http-proxy.conf  # Docker daemon
cat /etc/docker/daemon.json            # Docker registry mirrors
```
On UGREEN: proxy at `192.168.124.88:7890` (iStoreOS/mihomo). Docker daemon proxy is configured via systemd override. Host proxy may be in `/etc/profile.d/99-local-proxy.sh` (only loaded in login shells).

### 5. Test GitHub token validity
```bash
# Must use proxy - GitHub API is blocked without it
curl -s -w "\n%{http_code}" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  --proxy http://192.168.124.88:7890 \
  https://api.github.com/user
```
HTTP 200 = valid token. HTTP 401 = invalid/expired. HTTP 000 = network blocked (need proxy).

## Common pitfalls

1. **Non-login SSH shells don't load /etc/profile.d/**: When running `ssh host 'command'`, proxy env vars from `/etc/profile.d/99-local-proxy.sh` are NOT loaded. Either source it explicitly (`. /etc/profile.d/99-local-proxy.sh`) or set env vars manually.

2. **DNS returns 127.0.0.1 for blocked sites**: iStoreOS hijacks DNS. Don't trust `nslookup`/`dig` for connectivity tests — use `curl` with explicit `--proxy`.

3. **Docker daemon proxy is separate from host proxy**: Docker uses systemd override, host uses profile.d. They have different NO_PROXY lists.

4. **pip timeout != proxy missing**: Check with `--proxy` explicitly to isolate DNS vs proxy issues.

## GitHub Models setup

GitHub Models is a separate service from GitHub Copilot:
- Endpoint: `https://models.github.ai/inference/chat/completions`
- Auth: Fine-grained PAT (`github_pat_`) with `models` scope
- Format: OpenAI-compatible API
- Requirements: Visit https://github.com/marketplace/models playground first to activate, then ensure PAT has `models` scope at https://github.com/settings/tokens

## SSH-based Docker management (Hermes → Host)

When Hermes container doesn't have Docker socket access:
```bash
# Install sshpass if needed
apt-get install -y sshpass

# Run Docker commands on host via SSH
sshpass -p 'PASSWORD' ssh vive@192.168.125.12 \
  'echo PASSWORD | sudo -S docker pull IMAGE'
```
Sudo is needed because `vive` may not be in `docker` group.