---
name: weekly-briefing-v2
description: 学术研究周报（统一版）— 论文搜索发现 + 深度分析 + 精美PDF + 个性化邮件。当前唯一生产入口，手动和cron通用。
version: 2.0.0
related_skills:
  - academic-weekly-briefing-core
---

# Weekly Briefing v2 — Active Production Entrypoint

**当前唯一运行时入口。** 所有 cron 和手动触发均通过本 skill。

## 与 academic-weekly-briefing-core 的关系

本 skill 负责**执行**（跑 runner、渲染 PDF、发邮件）。以下分析规范由 `academic-weekly-briefing-core` 定义，除非本 skill 显式覆盖：

- **Venue 质量分级**（T1-T4 + Reject）
- **6 因子综合评分**（venue×0.30 + citation×0.15 + relevance×0.25 + novelty×0.15 + reproducibility×0.10 + author×0.05）
- **Anti-Bias 护栏**（topic_feedback 权重边界、话题漂移检测、多样性硬约束）
- **论文类型自适应分析模板**（方法/数据集/综述/理论/应用）
- **文献关系图谱**（cites/cited_by/extends/contradicts/complements/supersedes）
- **季度索引与趋势归纳**

在搜索→筛选→分析阶段，遵循 core 的质量控制规则判断论文价值。

## 架构冻结（观察期）

**2026-07-03 起生效，持续 2-3 周至 cron 连续稳定运行。**

刚经历误删 6 个 skill + 恢复后，周报系统进入观察期。硬性约束：

| 允许 | 禁止 |
|------|------|
| 修 bug | 合并 skill |
| 更新 SKILL.md 文档 | 删除任何周报相关 skill |
| 调整 cron 参数 | 重命名 cron |
| 数据修复（archive/dedup 等） | 大改入口流程 |
| | 修改 skill 间职责边界 |

观察期内所有修改先 git commit，再操作。

## 核心原则

- **搜索用直接API**：arXiv API + Crossref API，不走 Hermes web_search（会被block）
- **分析用LLM**：深度分析、作者调研、跨论文综合、个性化撰写
- **PDF用Typst**：精美排版，带色彩系统和论文卡片
- **邮件自动确认**：设 `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1` 即可无人值守
- **持续性数据完整更新**：dedup + archive + taxonomy + relations

## 执行流程

**Scripts location:** 所有脚本在本 skill 的 `scripts/` 目录下（`hermes skills install` 会自动拉取）。

## 首次安装初始化

```bash
# 1. 创建数据目录
mkdir -p $DATA_DIR/{papers/candidates,reports,profile/daily,profile/weekly,profile/monthly,teams,logs,exports,indices/quarterly}

# 2. 从模板创建配置
cp {skill_dir}/templates/config.json.template $DATA_DIR/config.json
cp {skill_dir}/templates/venues.json.template $DATA_DIR/venues.json
# 编辑 config.json：填好 display_name、research_identity、core_keywords、data_dir

# 3. 依赖检查
which typst && typst --version
python3 -c "from weasyprint import HTML; print('OK')"
fc-list :lang=zh | head -1
# agently-cli 需单独安装和 OAuth 认证
```

### 阶段1：论文发现（确定性）

运行E2E runner的发现模式：

```bash
python3 {skill_dir}/scripts/run_weekly_e2e.py \
  --week $(python3 -c "import datetime; y,w,_=datetime.date.today().isocalendar(); print(f'{y}-W{w:02d}')") \
  --data-dir $DATA_DIR \
  --discovery-only
```

这会输出 `selected_papers.json` 到 `$DATA_DIR/papers/candidates/{week}_selected.json`。

### 阶段2-7

深度分析→撰写→PDF→邮件→持久化→清理，按 config.json 配置执行。

## 邮件个性化规则

- **称呼**：按 `config.json` → `user.display_name` 和 `style.role` 设置
- **落款**：按 `config.json` → `style.signature` 设置
- **情绪可变化**：按 `style.allow_variable_mood` 控制
- **主题前缀**：⚚（可在 config.json 中修改）

## 已知问题与陷阱

- **arXiv API 零结果**：多关键词查询严格，Crossref 通常能补上
- **agently-cli stderr**：管道操作不要用 `2>&1`，用 `2>/dev/null`
- **agently-cli --body-file**：必须用相对路径，先 cd 到文件目录

## 参考文档

- `references/v2-capability-coverage.md` — dry-run 验证
- `references/agently-cli-pitfalls.md` — 常见陷阱