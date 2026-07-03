# Hermes Weekly Briefing Skills

学术研究周报技能包。`hermes skills install` 一键安装。

## 包含技能

| 技能 | 角色 |
|------|------|
| `weekly-briefing-v2` | 🏃 生产入口：执行 runner、渲染 PDF、发送邮件 |
| `academic-weekly-briefing-core` | 📐 分析规范：Venue 分级、评分公式、Anti-Bias |
| `academic-briefing-ops` | 🔧 运维：初始化、维护脚本、archive 恢复 |
| `academic-report-render-deliver` | 📄 渲染交付：Typst PDF、邮件 |
| `research-profile-engine` | 🧠 画像演化：每日/每周/每月语义分析 |

## 安装

```bash
hermes skills install https://github.com/Awenforever/hermes-weekly-briefing
```

## 初始化（安装后执行）

```bash
# 1. 设置数据目录（建议写入 ~/.hermes/.env 持久化）
export HERMES_WEEKLY_DATA_DIR=~/.hermes/weekly-briefing

# 2. 创建目录结构
mkdir -p $HERMES_WEEKLY_DATA_DIR/{papers/candidates,reports,profile/{daily,weekly,monthly},teams,logs,exports,indices/quarterly}

# 3. 从模板创建配置
SKILL_DIR=~/.hermes/skills/research/weekly-briefing-v2
cp $SKILL_DIR/templates/config.json.template $HERMES_WEEKLY_DATA_DIR/config.json
cp $SKILL_DIR/templates/venues.json.template $HERMES_WEEKLY_DATA_DIR/venues.json

# 4. 编辑 config.json — 必须填写：
#    - user.display_name, user.research_identity
#    - research.core_keywords, research.method_keywords
#    - style.signature, paths.data_dir

# 5. 运行健康检查
python3 $SKILL_DIR/../academic-briefing-ops/scripts/health_check.py

# 6. 试跑
python3 $SKILL_DIR/scripts/run_weekly_e2e.py --discovery-only --max-selected 3
```

## 升级

技能更新通过重新安装完成。**数据安全：** `HERMES_WEEKLY_DATA_DIR` 与技能目录完全分离，升级不会覆盖你的配置、论文库或历史周报。

```bash
# 一行升级（覆盖技能文件，保留数据）
hermes skills install https://github.com/Awenforever/hermes-weekly-briefing

# 建议：升级后运行健康检查确认无回归
python3 ~/.hermes/skills/research/academic-briefing-ops/scripts/health_check.py
```

### 升级覆盖范围

| 内容 | 是否覆盖 | 说明 |
|------|----------|------|
| SKILL.md（AI 指令） | ✅ 覆盖 | 新版本的行为规则和流程 |
| scripts/*.py（运行脚本） | ✅ 覆盖 | 含 runner、维护、恢复脚本 |
| templates/*.template（配置模板） | ✅ 覆盖 | 新版本可能有新配置项 |
| references/*.md（参考文档） | ✅ 覆盖 | 陷阱文档、覆盖率报告等 |
| `$DATA_DIR/config.json` | ❌ 不覆盖 | 用户填写的个人配置 |
| `$DATA_DIR/papers/`（论文库） | ❌ 不覆盖 | archive、dedup、taxonomy 等 |
| `$DATA_DIR/reports/`（历史周报） | ❌ 不覆盖 | 过往生成的 PDF 和 markdown |
| `$DATA_DIR/profile/`（研究画像） | ❌ 不覆盖 | daily/weekly/monthly 画像数据 |

### 如果你修改了技能文件

如果你在本地改了技能脚本，升级会覆盖你的修改。贡献改进的正确路径：

1. Fork 本仓库
2. 提交你的改进到你的 fork
3. 发 PR 到源仓库
4. 合并后所有用户通过 re-install 获得更新

## 依赖

| 依赖 | 用途 | 必需？ |
|------|------|--------|
| Typst | PDF 渲染 | ✅ 必需 |
| WeasyPrint | 后备 PDF | ✅ 建议 |
| agently-cli | 邮件发送 | ⚠️ 无邮件可跳过 |
| CJK 字体 (Noto Sans/Serif CJK SC) | 中文排版 | ✅ 必需 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HERMES_WEEKLY_DATA_DIR` | `~/.hermes/weekly-briefing/` | 数据存储目录 |
| `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM` | `0` | 设为 `1` 跳过邮件确认 |
| `AGENTLY_CLI_PATH` | (PATH 搜索) | agently-cli 路径 |

## 架构

```
weekly-briefing-v2 (执行入口)
  ├── run_weekly_e2e.py     — arXiv + Crossref 论文发现
  ├── LLM 深度分析           — 作者调研、跨论文综合
  ├── Typst PDF              — 精美排版
  └── agently-cli 邮件       — 个性化发送

academic-weekly-briefing-core (分析规范)
  └── Venue 分级 / 6因子评分 / Anti-Bias / 关系图谱

academic-briefing-ops (运维)
  └── 初始化 / 健康检查 / archive 恢复 / 清理

academic-report-render-deliver (渲染)
  └── Typst 模板 / WeasyPrint 后备 / 两阶段邮件

research-profile-engine (画像)
  └── 每日/每周/每月语义分析
```