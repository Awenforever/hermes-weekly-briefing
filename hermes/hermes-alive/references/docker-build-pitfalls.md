# Docker Build Pitfalls

Use this reference when deployment issues are caused by image rebuilds, missing browsers, or filesystem permissions rather than watcher logic.

## Build and Runtime Pitfalls

- **Playwright persistence**: Chromium must live on a persistent volume such as `/opt/data/.playwright-browsers`. Rebuilding the image without restoring browser binaries will break Playwright-backed discovery sources.
- **Python package drift**: Reinstall Playwright Python dependencies after image rebuilds if the environment was recreated.
- **Timezone**: `deploy.sh` auto-detects timezone from `timedatectl`, `/etc/timezone`, or `/etc/localtime`. Do not hardcode `Asia/Shanghai`.
- **File permissions**: deployed hook `.py` files should be world-readable (`644`) so non-root gateway users can import them.
- **Shared-dir consistency**: all runtime state should resolve through `HERMES_ALIVE_SHARED_DIR`, not mixed hardcoded paths.

## Fast Checks

```bash
find /opt/data/hooks/hermes-alive -name '*.py' ! -perm 644
bash scripts/verify.sh
```
