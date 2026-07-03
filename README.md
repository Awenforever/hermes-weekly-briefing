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
# 1. 设置数据目录
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