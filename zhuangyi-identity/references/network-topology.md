# 网络拓扑 — DXP4800PLUS-RIN

> 审计日期: 2026-07-02
> 审计人: 庄奕 (Hermes Agent)

## 拓扑图

```
                        Internet
                           │
                    ┌──────┴──────┐
                    │  iStoreOS   │  192.168.124.88
                    │  proxy:7890 │  (mihomo/clash)
                    │  DHCP/DNS   │
                    └──────┬──────┘
                           │ bridge0: 192.168.124.0/24
              ┌────────────┼────────────┐
              ▼                         ▼
      192.168.124.220            eth1: 192.168.125.0/24
       DXP4800PLUS-RIN           192.168.125.12 (物理口)
       (bridge口, 默认网关)
              │
     Docker (host 网络模式)
     ├── hermes-hermes-1       gateway v0.17.0
     ├── hermes-dashboard-1    Web 面板
     ├── hermes-python-tools   Python 3.12
     └── ws-scrcpy             :8000 手机投屏

    Mounts:
     /volume2/Hermes-v017-current → /opt/data
     /home/vive/Work → /home/vive/Work
```

## 关键地址

| 项目 | 地址 |
|------|------|
| 宿主机 SSH | vive@192.168.125.12 (key: /opt/data/ssh/hermes_host_ed25519) |
| iStoreOS 代理 | http://192.168.124.88:7890 |
| Docker Compose | /volume2/@appstore/com.ugreen.docker.hermes/ |

## 代理规则

- 所有出站流量默认走 bridge0 → iStoreOS 192.168.124.88
- 代理配置文件: /etc/profile.d/99-local-proxy.sh
- NO_PROXY: api.llm.ustc.edu.cn, 本地网段
- 宿主机非登录 Shell 需手动 source 该文件

## Docker 操作

- 容器以 host 模式运行（共享宿主机网络栈）
- 可在宿主机上 docker run 新容器
- 持久化数据必须挂载到 /opt/data 或 /home/vive/Work
- 重启: `docker restart hermes-hermes-1` (不能从容器内部重启)