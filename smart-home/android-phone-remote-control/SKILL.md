---
name: android-phone-remote-control
description: Connect and autonomously control a physical Android phone from Hermes in a NAS Docker container via WiFi ADB. Covers ws-scrcpy, MobileRun, SSH-based Docker access, and common pitfalls.
---

# Android Phone Remote Control from NAS Docker

## Overview

Connect a physical Android phone to Hermes Agent running in UGREEN NAS Docker for autonomous AI-driven control. Core constraint: **no USB passthrough**, must use **WiFi ADB**. Hermes container has **no Docker socket** — all Docker commands go through SSH to host.

## Layered Architecture

| Layer | Purpose | Technology | Location |
|-------|---------|------------|----------|
| **Connection** | Docker↔Phone communication | ADB over WiFi (Android 11+) | Hermes container |
| **Perception** | Screen viewing + touch input | ws-scrcpy (`scavin/ws-scrcpy`) | Host Docker (port 8000) |
| **Decision** | AI autonomous task execution | MobileRun (droidrun/mobilerun) | Hermes container |

```
Hermes Container (NAS)               Host NAS (SSH)
  ├── ADB ──WiFi──▶ Phone             ├── ws-scrcpy Docker ──WiFi──▶ Phone
  ├── MobileRun ──WiFi──▶ Phone        └── (port 8000 web UI)
  └── SSH (sshpass) → Host
```

## Step-by-Step Deployment

### 1. Install Dependencies in Hermes Container

```bash
apt-get update && apt-get install -y android-tools-adb sshpass
```

### 2. Deploy ws-scrcpy on Host via SSH

Hermes container has **no Docker socket**. Use SSH + `sshpass` + `sudo` to reach host Docker:

```bash
# Pull image
sshpass -p '<password>' ssh -o StrictHostKeyChecking=no <user>@<host_ip> \
  "echo '<password>' | sudo -S docker pull scavin/ws-scrcpy"

# Run container
sshpass -p '<password>' ssh <user>@<host_ip> \
  "echo '<password>' | sudo -S docker run -d --name ws-scrcpy \
  --restart unless-stopped -p 8000:8000 scavin/ws-scrcpy"
```

Access web UI at: `http://<host_ip>:8000`

### 3. Install MobileRun in Hermes Container

MobileRun has ~150 dependencies (~500MB). Use extended timeout:

```bash
pip3 install --break-system-packages --timeout 600 mobilerun
```

Verify: `mobilerun --version`

### 4. Phone Setup + ADB WiFi Pairing

**Phone side (user):**
1. Settings → About Phone → tap "Build Number" 7 times → Developer Options
2. Settings → Developer Options → Wireless Debugging → ON
3. Tap "Pair device with pairing code" → note: IP address, pair port, 6-digit code

**Hermes side:**
```bash
# Pair (one-time — uses pair port, NOT 5555)
adb pair <phone_ip>:<pairing_port>
# Enter 6-digit code when prompted

# Connect (uses port 5555)
adb connect <phone_ip>:5555

# Verify
adb devices  # should show "device", not "unauthorized"
```

**Connect ws-scrcpy to same phone:**
```bash
sshpass -p '<password>' ssh <user>@<host_ip> \
  "echo '<password>' | sudo -S docker exec ws-scrcpy adb connect <phone_ip>:5555"
```

## Common Pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| Docker permission denied | User not in `docker` group | `echo '<password>' \| sudo -S docker ...` |
| `host.docker.internal` unreachable | Not configured in Hermes container | Use SSH to host IP instead |
| pip install timeout | MobileRun has 150+ deps, ~500MB | `pip install --timeout 600` |
| Pairing fails | Wrong port used | Pair port (e.g., 37123) ≠ connect port (5555) |
| Device "unauthorized" | Multiple ADB servers conflict | `adb kill-server && adb connect <ip>:5555` |
| ws-scrcpy no device | ADB not connected in container | `docker exec ws-scrcpy adb connect <ip>:5555` |

## Phone-Side Requirements

- Android 11+ (for Wireless Debugging)
- Install ADB Keyboard APK for text input: https://github.com/senzhk/ADBKeyBoard
- Install MobileRun Portal app for UI tree extraction (optional, improves accuracy)

## Key Design Decisions

- **MobileRun** chosen over Mobile-Agent-v3: Docker-native, LLM-agnostic, no local GPU/VLM needed
- **ws-scrcpy** kept as independent visual layer for fallback manual control + debugging
- **Phone-side-only agents** (MANTIS, Neuron) rejected: cannot be orchestrated by Hermes on NAS
- **SSH bridge** pattern: Hermes container issues Docker commands on host via `sshpass` + `sudo`

## MobileRun Quick Start

MobileRun is LLM-agnostic. After connecting phone:

```bash
# List devices
mobilerun devices

# Run a task
mobilerun run --device <serial> "Open Settings and check WiFi status"
```

Provider configuration via environment variables or config file. Supports: OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter, Ollama, OpenAI-compatible APIs.

## References

- ws-scrcpy Docker: `scavin/ws-scrcpy` (AMD64) — https://hub.docker.com/r/scavin/ws-scrcpy
- MobileRun GitHub: https://github.com/droidrun/mobilerun
- MobileRun Docs: https://docs.mobilerun.ai
- ADB over WiFi: https://developer.android.com/tools/adb#wireless
- ADB Keyboard APK: https://github.com/senzhk/ADBKeyBoard