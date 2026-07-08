# Compose Label Stripping

Docker does NOT support modifying labels on existing containers — `docker container update` only handles restart policy and resource limits, not labels. To remove compose labels you must delete and recreate.

## Full Script

```python
import paramiko, json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname="192.168.125.12", username="vive", password="<password>", timeout=20)

def sudo(cmd):
    stdin, stdout, stderr = client.exec_command(f"sudo -S {cmd}", timeout=20)
    stdin.write("<password>\n")
    stdin.flush()
    return stdout.read().decode(), stderr.read().decode()

for cname in ["hermes-v017-gateway", "hermes-v017-dashboard"]:
    out, _ = sudo(f"docker inspect {cname}")
    data = json.loads(out)[0]
    config = data["Config"]
    host_config = data["HostConfig"]

    # Build docker create args from inspect output
    args = []
    for e in (config.get("Entrypoint") or []):
        args.append(f'--entrypoint {e}')
    for e in (config.get("Env") or []):
        args.append(f'-e {e}')
    if config.get("User"):
        args.append(f'-u {config["User"]}')
    if config.get("WorkingDir"):
        args.append(f'-w {config["WorkingDir"]}')
    
    rp = (host_config.get("RestartPolicy") or {}).get("Name", "")
    if rp:
        args.append(f'--restart {rp}')
    
    nm = host_config.get("NetworkMode", "default")
    if nm != "default":
        args.append(f'--network {nm}')
    
    for m in (data.get("Mounts") or []):
        if m["Type"] == "bind":
            args.append(f'-v {m["Source"]}:{m["Destination"]}:{m.get("Mode","rw")}')
        elif m["Type"] == "volume":
            args.append(f'-v {m["Name"]}:{m["Destination"]}:{m.get("Mode","rw")}')
    
    for s in (host_config.get("SecurityOpt") or []):
        args.append(f'--security-opt {s}')
    for c in (host_config.get("CapAdd") or []):
        args.append(f'--cap-add {c}')
    
    # Labels: keep all EXCEPT compose labels
    labels = config.get("Labels") or {}
    for k, v in labels.items():
        if not k.startswith("com.docker.compose."):
            args.append(f'-l {k}={v}')
    
    image = config["Image"]
    cmd_parts = config.get("Cmd") or []
    
    # Delete and recreate
    sudo(f"docker rm {cname}")
    create_cmd = f"docker create --name {cname} {' '.join(args)} {image}"
    if cmd_parts:
        for c in cmd_parts:
            create_cmd += f" {c}"
    out, err = sudo(create_cmd)
    print(f"{cname}: {out.strip()[:60]}")

client.close()
```

## Verification

```bash
# Check labels are gone
docker inspect hermes-v017-gateway --format '{{index .Config.Labels "com.docker.compose.project"}}'
# Should output empty string

# Check compose no longer tracks them
docker compose -p hermes down --dry-run
# Should NOT include the stripped containers
```

## Why Not Just Rename?

`docker rename` changes the container name but compose tracks by LABEL, not name. Renaming alone does NOT remove a container from a compose project. Labels MUST be stripped.