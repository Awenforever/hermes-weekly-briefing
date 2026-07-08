# Paramiko SSH Pattern for Scripted NAS Operations

When you need to run multiple `sudo docker` commands on the NAS from inside the Hermes container, raw SSH with a key is fine for one-off commands. But multi-command scripts that need sudo password handling should use paramiko.

## Setup

```bash
# Install paramiko in a temp venv (no pip in system Python on Debian 13)
cd /tmp && uv venv .ssh-venv && uv pip install --python .ssh-venv/bin/python paramiko
```

## Pattern

```python
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname="192.168.125.12", username="vive", password="<password>", timeout=15)

def sudo(cmd):
    """Run command with sudo -S, pass password via stdin"""
    stdin, stdout, stderr = client.exec_command(f"sudo -S {cmd}", timeout=15)
    stdin.write("<password>\n")
    stdin.flush()
    return stdout.read().decode(), stderr.read().decode()

# Use it
out, err = sudo("docker ps --format '{{.Names}}'")
print(out)

client.close()
```

## Run via terminal (heredoc)

```bash
/tmp/.ssh-venv/bin/python3 << 'PYEOF'
import paramiko
# ... script ...
PYEOF
```

## Pitfalls

- System Python has no `pip` module (Debian 13 PEP 668) — use `uv` to create venv
- `sshpass` is NOT available and can't be apt-get installed (missing repo)
- Docker commands ALWAYS need `sudo -S` — vive is not in the docker group
- Long commands in heredoc can get mangled by terminal wrapping — keep lines short
- The `execute_code` sandbox can't access the venv — use `terminal()` with heredoc instead