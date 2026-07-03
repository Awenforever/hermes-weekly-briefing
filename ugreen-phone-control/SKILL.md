---
name: ugreen-phone-control
description: Deploy phone remote control on UGREEN NAS — ws-scrcpy (screen mirror + touch) + MobileRun (AI autonomous operation) via ADB WiFi, orchestrated by Hermes through SSH to host.
category: ugreen-docker-via-ssh
---

# Phone Remote Control on UGREEN NAS

Enable Hermes to autonomously operate a physical Android phone via ADB WiFi.

## Architecture

```
Hermes (Docker container)
  └─ SSH ──▶ UGREEN Host (vive@192.168.125.12)
                ├─ ws-scrcpy (Docker :8000) ──ADB WiFi──▶ Phone
                ├─ ADB (host binary) ──ADB WiFi──▶ Phone
                └─ MobileRun (Hermes container) ──ADB──▶ Phone
```

## Recommended control layers

1. **Connection layer** — wireless debugging / ADB pairing.
2. **Observation layer** — ws-scrcpy for screen viewing and manual touch.
3. **Autonomy layer** — MobileRun for scripted/agentic phone actions.
4. **Policy layer** — per-app / per-action permissions and human confirmation rules.

Keep the layers separate: use ADB to connect, ws-scrcpy to inspect, and MobileRun only when you want Hermes to act autonomously.

## Components

### 1. ws-scrcpy — Browser-based screen mirror + touch

**Install (on host):**
```bash
sudo docker run -d --restart unless-stopped --name ws-scrcpy \
  -p 8000:8000 \
  scavin/ws-scrcpy
```

Access at: `http://192.168.125.12:8000`

### 2. MobileRun — AI autonomous phone agent

**Install (in Hermes container):**
```bash
pip install mobilerun
```

Version: v0.6.8+

### 3. ADB — Android Debug Bridge

Already installed in Hermes container (v34.0.5). Install on host if needed:
```bash
sudo apt install adb
```

## Phone Setup (Android 11+)

1. Enable Developer Options: Settings → About → Tap "Build number" 7 times
2. Enable Wireless Debugging: Settings → Developer Options → Wireless debugging → ON
3. Tap "Pair device with pairing code" → shows IP, port, 6-digit code
4. Provide pairing details to Hermes for ADB pairing

## Pairing from Hermes

```bash
adb pair <phone-ip>:<pairing-port> <6-digit-code>
adb connect <phone-ip>:<connect-port>
```

Verify: `adb devices` should show the phone as "device" (not "unauthorized").

## MobileRun Usage

```bash
# Run a task
mobilerun run "Open WeChat and send 'hello' to Zhang San"

# List connected devices
mobilerun devices
```

## Pitfalls

- ADB pairing port ≠ connection port — wireless debugging page shows both
- Phone and NAS must be on same network segment (192.168.125.x)
- ws-scrcpy needs port 8000 accessible from browser
- Host-level Docker commands require `sudo` (user `vive` not in docker group)
- MobileRun needs proxy to call LLM API — ensure HTTPS_PROXY is set
- After pairing, the connection persists across reboots if phone's wireless debugging stays on

## Current State

- [x] ws-scrcpy installed and running (host:8000)
- [x] ADB v34.0.5 installed (Hermes container)
- [x] MobileRun v0.6.8 installed (Hermes container)
- [ ] ADB pairing with phone — **pending user's pairing info**
- [ ] MobileRun task execution — not yet tested