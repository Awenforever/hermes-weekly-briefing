# Hermes WeChat Enhance — 开发蓝图 (Development Blueprint)

> **目的：** 跨对话传递开发方向、架构决策、运维规范。任何新会话加载此 skill 后即知全貌。
>
> **创建日期：** 2026-07-07
>
> **关联 skill：** `hermes-wechat-enhance`、`hermes-alive`

---

## 1. 最终愿景

两个独立 skill，各可通过 GitHub README 一键安装到全新 Hermes 实例：

```
用户: "请阅读 https://github.com/Awenforever/hermes-wechat-enhance 的 README，为我安装这个技能"
Hermes: git clone → ./scripts/install.sh → 检测版本 → apply patches → 装 hooks → verify → 完成
```

**卸载：** `./scripts/uninstall.sh` → git checkout pristine → 恢复到安装前状态

**升级：** `./scripts/update.sh` → revert 旧 patches → apply 新版

---

## 2. 架构决策

### 2.1 为什么必须用 Git 管理 patch

`hermes-wechat-enhance` 的 patches 修改 gateway 源码（weixin.py、base.py、run.py），是侵入式的。文件和 hooks 不同——文件删了就行，但源码被改了必须能还原。

**方案：Git pristine commit 锚点**

```
install.sh:
  1. cd /opt/hermes && git init (如未初始化)
  2. git add -A && git commit -m "pristine"  ← 保存原始状态锚点
  3. 检测 Hermes 版本 → 选对应 patches/vX.YZ/
  4. 按 series 文件顺序 git apply
  5. git commit -m "hermes-wechat-enhance vX.Y.Z installed"

uninstall.sh:
  1. git log --oneline | grep "hermes-wechat-enhance installed" → 确认装过
  2. git checkout pristine → 全部还原

update.sh:
  1. git stash (保存用户手动改动)
  2. git checkout pristine
  3. apply 新版 patches
  4. git stash pop (尝试合并，冲突则提示)
```

### 2.2 跨版本兼容

```
patches/
├── v0.17/          ← 适配 Hermes v0.17
│   ├── series       ← apply 顺序
│   └── *.patch
├── v0.18/          ← 适配 Hermes v0.18
└── v0.19/          ← 未来
```

`install.sh` 自动检测 Hermes 版本，选择匹配的 patch 集。

### 2.3 非 Docker 用户兼容

install.sh 不假定 Docker。WSL/Mac/Linux 用户直接在 gateway 源码目录执行脚本即可。

---

## 3. 开发运维规范

### 3.1 联动检查

`check-consistency.sh` 自动扫描脚本、文档与 `patches/` 目录的交叉引用，不一致则报错。联动原则保留，由脚本和主文档共同承载。

### 3.2 测试铁律：Goal-Oriented Only

**禁止：** "ReplyBudgetStore 类存在吗？"

**要求：** "预算用完时，drain 拒绝发送并返回预算超限错误"

每个测试必须注释它验证的用户可见 goal。没有 goal 的测试 → 删。

### 3.3 防屎山三原则

1. **一个 patch 一个职责** — 001 只管 /continue，005 只管 Queue+Budget。禁止混合。
2. **一进一出** — 每加 50 行代码，找 50 行可以删的。净增长为零。
3. **季度审计** — 跑 `check-consistency.sh` → 列死代码 → 确认 → 删。

---

## 4. 当前状态（2026-07-07）

### hermes-wechat-enhance

| 组件 | 状态 | 备注 |
|------|:--:|------|
| patches (5个) | ✅ 存在 | 002→003→004→005→001，适配 v0.18 |
| patch 按版本组织 | ❌ 待做 | 当前 patches/ 目录平铺，未分版本子目录 |
| CUSTOMIZATIONS.md | ✅ 完成 | 完整修改清单 |
| SKILL.md | ✅ 存在 | 已补充标准章节与审计修复 |
| README.md | ⚠️ 需重写 | 需加入 install/update/uninstall 说明 |
| install.sh | ✅ 存在 | 版本检测 + git pristine + apply patches + hooks |
| update.sh | ✅ 存在 | revert 到 pristine 后重放当前 patch 集 |
| uninstall.sh | ✅ 存在 | git checkout pristine + 清理 hooks |
| check-consistency.sh | ✅ 存在 | 交叉引用审计脚本 |
| verify (goal-oriented) | ❌ 待重构 | 当前 63 项检查多是"存在性"，非行为验证 |
| hooks | ✅ 存在 | hermes-wechat-enhance hook |

### hermes-alive

| 组件 | 状态 | 备注 |
|------|:--:|------|
| 代码 | ✅ 存在 | v2.3，在 `/opt/data/skills/hermes-alive/` |
| 就绪通知 | ❌ 未生效 | `HERMES_PROACTIVE_PLATFORM_ENABLED` 未设 |
| footer 模型名 | ⚠️ 待验证 | `_metadata()` 需补全四字段 |
| 作为独立 skill 安装 | ❌ 待做 | 目前与 wechat-enhance 耦合 |

---

## 5. 待办（优先级排序）

| # | 任务 | 负责人 |
|:--:|------|:--:|
| 1 | 重构 patches/ 为版本子目录 (v0.17/, v0.18/) | Codex |
| 2 | 重构 verify 为 goal-oriented 行为测试 | Codex |
| 3 | 重写 README.md — 包含安装/卸载/升级说明 | Codex |
| 4 | 审计 Hermes Alive — 补全 _metadata 四字段 + 就绪通知 | Codex |
| 5 | Hermes Alive 独立化为可安装 skill | Codex |

---

## 6. 跨对话 Recall 机制

**为什么新对话能 recall：**

1. 此文件在 `hermes-wechat-enhance` skill 的 `references/` 目录下
2. Hermes 系统 prompt 指示：匹配到 skill 就加载 SKILL.md
3. SKILL.md 列出 `references/` 下所有文件
4. 新会话加载 skill → 读到本蓝图 → 知道全貌

**更新协议：** 每完成一个任务或做出架构决策，**立即**更新本文件对应章节。不做事后补写。

---

## 7. 技术债记录

| 项目 | 说明 | 优先级 |
|------|------|:--:|
| Patch 版本子目录 | patches/ 平铺，不便于多版本管理 | P1 |
| verify 存在性测试 → 行为测试 | 63 项检查中大量是 "类/函数存在?" | P2 |
| README 过时 | 安装/卸载/升级说明仍需刷新 | P1 |
| Hermes Alive 与 wechat-enhance 耦合 | 就绪通知、footer 模型名在两边都有逻辑 | P2 |
| PYTHONPATH hack | hook 需要 PYTHONPATH 指向 skill 目录才能 import | P3 |

---

> **原则：先文档后代码。先蓝图后施工。不改蓝图不动手。**
