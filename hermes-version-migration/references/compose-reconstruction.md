# Compose 文件重建

当 compose 文件被意外清空/损坏时，从运行中容器反向重建。

## 方法

```bash
# 从容器 inspect 重建完整 compose yaml
docker inspect hermes-hermes-1 | python3 -c "
import json, sys
data = json.load(sys.stdin)[0]
config = data['Config']
hc = data['HostConfig']

# 提取所有 env vars
envs = '\n'.join(f'      - {e}' for e in config.get('Env', []))

# 提取所有 volumes
vols = '\n'.join(f'      - {m[\"Source\"]}:{m[\"Destination\"]}' if m['Type'] == 'bind' 
    else f'      - {m[\"Name\"]}:{m[\"Destination\"]}' 
    for m in data.get('Mounts', []))

print(f'''services:
  gateway:
    image: {config[\"Image\"]}
    container_name: hermes-hermes-1
    restart: {hc[\"RestartPolicy\"][\"Name\"]}
    network_mode: {hc[\"NetworkMode\"]}
    user: \"{config.get(\"User\", \"0:0\")}\"
    security_opt:
      - seccomp=unconfined
      - apparmor=unconfined
    cap_add:
      - SYS_ADMIN
    entrypoint: {config.get(\"Entrypoint\", [\"/bin/sh\"])}
    environment:
{envs}
    volumes:
{vols}

volumes:
  hermes-v018-data:
    external: true
''')
" > /tmp/compose-recovered.yaml
```

## 陷阱

- 不要用 heredoc (`cat << 'EOF'`) 配合 `sudo`，密码提示会混入文件内容
- 先写到 `/tmp/` 再 `sudo cp` 到目标路径
- 写入后立即 `python3 -c 'import yaml; yaml.safe_load(open("file"))'` 验证 YAML 合法性