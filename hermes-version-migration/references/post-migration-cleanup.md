# 迁移后宿主机清理清单

迁移完成后 `~/` 会残留大量一次性文件。按此清单清理。

## 删除：迁移脚本（一次性）

```
migrate-final.sh  migrate-v018.sh  migrate-v018-v3.sh
test-v018.sh      test-v018-v4.sh
restore-v017.sh   rollback-final.sh  rollback-v018.sh
start-v18.sh      swap-final.sh
```

## 删除：日志和状态文件

```
migrate-final-stdout.log  migrate-status.txt
migrate-v018-*.log        migrate-v018-status.txt
test-v018.log             test-v018-stdout.log
swap-final.log            swap-status.txt  swap-stdout.log
```

## 删除：一次性文件

```
closing-prompt.txt   grab-v18-logs.sh   .sudo_as_admin_successful
```

## 删除：空目录和测试数据

```
hermes-v018-patches/   (空的)
hermes-alive-test-data/
```

## 归档到 Work/Hermes/

补丁文件（三处来源，可能有差异，全部保留不合并）：
- `v18-patches/` → `Work/Hermes/YYYY-MM-DD-v018-migration/patches/v18-patches/`
- `vive/` → `Work/Hermes/YYYY-MM-DD-v018-migration/patches/vive/`

其他 artifact：
- `Hermes-v018-data/docker-compose-v018.yaml` → 如果文件完好
- `Hermes-v018-data/startup-notify-check.txt`

## 镜像瘦身

```bash
# 悬空镜像
docker image prune -a

# 旧版构建 tag
docker rmi hermes-agent:v0.18.0-patched-v2 \
  hermes-agent:v0.18.0-weixin-enhanced-audit1 \
  hermes-agent:v0.18.0 \
  hermes-agent:v0.17.0-footerfix1 \
  hermes-agent:v0.17.0-dsmlfix1 \
  ...（所有不再需要的中间 tag）

# 不用的基础镜像
docker rmi python:latest debian:13.4 ...
```

## 暂不删除

- `~/Hermes-v018-data/` — compose 元数据引用，删了破坏 `docker compose` 维护
- `~/base.py run.py weixin.py` — 用户源码快照，git 未追踪，需确认

## 最终状态

清理后 `~/` 应只剩：
```
Augenstern/  Backups/  Photos/  Temp/  Work/
Hermes-v018-data/  base.py  run.py  weixin.py
.ssh/  .git/  .config/  .docker/  .cache/
```