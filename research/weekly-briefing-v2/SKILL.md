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

## 未来合并计划 (v3.1)

观察期结束后规划统一版本：

```
weekly-briefing-v3.1
= weekly-briefing-v2 runtime（执行入口）
+ academic-weekly-briefing-core quality framework（评分/anti-bias/关系图谱）
+ academic-report-render-deliver delivery details（渲染/邮件）
+ academic-briefing-ops recovery/maintenance references（运维）
```

合并流程（6 步，不可跳步）：

1. 打包备份所有涉及 skill（tar.gz 快照）
2. 创建 v3.1，不删除旧 skill（保留回滚能力）
3. dry-run 验证 v3.1 完整流程
4. cron 切换到 v3.1
5. 观察一周，确认无回归
6. 清理旧 skill（经用户确认）

## 核心原则

- **搜索用直接API**：arXiv API + Crossref API，不走 Hermes web_search（会被block）
- **分析用LLM**：深度分析、作者调研、跨论文综合、个性化撰写
- **PDF用Typst**：精美排版，带色彩系统和论文卡片
- **邮件自动确认**：设 `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1` 即可无人值守
- **持续性数据完整更新**：dedup + archive + taxonomy + relations
- **遇到异常先验证再解释**：用户质疑时必须用实际命令重现/验证，不要推测原因。本次会话教训：`2>&1` 问题是被 `agently-cli ... 2>&1 |` vs `2>/dev/null |` 对比实验证实的，不是猜出来的。

## 执行流程

**Scripts location:** 所有脚本在本 skill 的 `scripts/` 目录下（`hermes skills install` 会自动拉取）。

## 首次安装初始化

```bash
# 1. 创建数据目录
mkdir -p $HERMES_HOME/weekly-briefing/{papers/candidates,reports,profile/daily,profile/weekly,profile/monthly,teams,logs,exports,indices/quarterly}

# 2. 从模板创建配置（替换 $DATA_DIR 为实际路径）
cp {skill_dir}/templates/config.json.template $HERMES_HOME/weekly-briefing/config.json
cp {skill_dir}/templates/venues.json.template $HERMES_HOME/weekly-briefing/venues.json
# 编辑 config.json：填好 display_name、research_identity、data_dir

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

如果 runner 返回的论文数少于3篇，额外执行一次宽泛搜索（更换关键词）再跑一次。

### 阶段2：深度分析（LLM）

对每篇入选论文执行：

1. **读完整摘要**：runner已提供abstract字段
2. **作者调研**：`web_search "第一作者姓名 + institution + Google Scholar"`  
3. **团队背景**：搜索团队代表作和高引论文
4. **论文分类**：判断是方法论文/数据集论文/综述/应用论文，按类型切换分析模板
5. **"论文与我"标签**：🔧可借鉴 ⚖️须对比 ⚠️竞争 🎯空白

### 阶段3：撰写报告

结构自由，但必须包含：
- 本周总体判断（200-300字）
- 入选论文深度分析（每篇按类型自适应）
- 文献定位回顾（与历史论文的关系）
- 跨论文综合（方法树 + 对比表 + 趋势叙事）
- 投稿时间线
- 下周关注

**必须去重**：读 `$DATA_DIR/papers/dedup.json`，确保不重复。

### 阶段4：PDF生成

用 Typst 生成精美PDF。模板规范：

```typst
#set page(paper: "a4", margin: (top: 2cm, bottom: 1.8cm, left: 2cm, right: 2cm))
#set text(font: ("Noto Sans CJK SC", "Noto Serif CJK SC"), size: 10pt, lang: "zh")
```

**禁止事项**：
- 禁止 Unicode emoji（weasyprint不稳定）
- 禁止 `<ul>` 默认圆点，用 CSS `li::before { content: "▸ "; }`
- 禁止依赖浏览器默认样式，全部显式设置
- 不使用 `#sym.*`（容器字体不支持）

编译：
```bash
cd $DATA_DIR/reports/{week}/
typst compile report.typ report.pdf
```

验证：`ls -lh report.pdf` 应 > 50KB。

### 阶段5：邮件发送

```bash
# 邮件正文：个性化、即兴、有人情味
# 称呼：vive = adjective + Kelvin J.
# 主题：⚚ 学术研究周报 {week} — {一句话概括}
# 落款：--- / 限定词 / 庄奕

cd $DATA_DIR/reports/{week}/

# 发送（两阶段确认）
agently-cli message +send \
  --to "your@email.com" \
  --subject "⚚ ..." \
  --body-file email_body.txt \
  --attachment report.pdf

# 如果返回 confirmation_required，用返回的token确认
agently-cli message +send ... --confirmation-token {token}
```

如果设了 `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1`，runner会自动确认。

### 阶段6：数据持久化

更新以下文件：
- `$DATA_DIR/papers/dedup.json` — 追加本期论文
- `$DATA_DIR/papers/archive.json` — 追加本期记录
- `$DATA_DIR/papers/taxonomy.json` — 更新方法标签
- `$DATA_DIR/papers/relations.json` — 更新引用关系

### 阶段7：清理

- 候选文件：保留最近12周，删除更早的
- 历史PDF：保留最近12期
- dedup条目：first_seen > 26周的条目删除
- archive.json：永久保留，绝不删除

清理前先dry-run列出将要删除的内容。

## Cron设置

```bash
# 每周五10:00 CST
cronjob action=create \
  schedule="0 10 * * 5" \
  name="weekly-briefing-v2" \
  prompt="运行 unified weekly briefing 流程：先跑 run_weekly_e2e.py --discovery-only 获取候选论文，然后对每篇做深度分析（作者调研、跨论文综合、个性化撰写），生成Typst PDF，发送邮件到 vive@mail.ustc.edu.cn，更新所有持久化数据。"

# 环境变量
HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1
```

## 手动触发

在WeChat/终端说"跑一次周报"即可触发完整流程。流程与cron完全一致。

## 邮件个性化规则

- **vive (Kelvin J.)**：每次用不同英文形容词修饰，如 "Restless Kelvin J." / "Tenacious Kelvin J."
- **开篇1-2句中文寒暄**，有人情味，点到即止
- **落款**：`---` 分隔线 → 换行 → 限定词 → 换行 → `Hermes ᥫᩣ` 或 `庄奕 ᥫᩣ`。不要 `/` 符号
- **情绪可变化**：这周懒就说懒话，激动就撒欢，禁止永远彬彬有礼
- **主题前缀**：⚚

## 铁律

### Git 版本管理

**任何持久化修改前必须先 git commit。** 三个 repo：
- `/opt/data/skills/` — 技能文件
- `/opt/data/weekly-briefing/` — 周报数据
- `/opt/data/home/.hermes/` — 运维脚本

流程：修改 → `git add -A` → `git commit -m "..."` → 再操作。禁止无 commit 的修改。

### 禁止无验证删除 Skill

2026-07-03 教训：批量删除 6 个 skill 后才发现 `recover_archive.py` 永久丢失、cron 指向断裂。删 skill 前必须：
1. 列出该 skill 的 `scripts/`、`references/` 内容
2. 确认 cron 不依赖它
3. 确认功能已迁移或有备份
4. 先 git commit 当前状态

## 已知问题与陷阱

### Cron 手动触发可能不执行

`cronjob action=run` 在某些环境下不实际触发 cron。手动跑周报时应**直接走完整流程**（阶段0→6），不要依赖 cron 触发。cron 仅用于定时调度。

### arXiv API 零结果

runner 有时返回 `arxiv_api_candidates: 0`。原因：arXiv API 的 `all:"query"` 语法要求所有词匹配，多关键词查询过于严格。不是 bug，Crossref 通常能补上候选。如果整体候选 < 5 篇，用 `web_search` 补搜一轮。

### agently-cli 输出中混入 stderr

`agently-cli` 的提示文字（如 `tip: ...`）输出到 stderr。管道操作时**不要用 `2>&1`** 将 stderr 合并到 stdout，否则 `json.load()` 会报 `JSONDecodeError: Extra data`。正确做法：只用 stdout，或用 `2>/dev/null` 丢弃 stderr。详见 `references/agently-cli-pitfalls.md`。

### agently-cli `--body-file` 必须用相对路径

`agently-cli message +send` 的 `--body-file` 和 `--attachment` 不接受绝对路径。必须先 `cd` 到文件所在目录，再用相对路径传参。详见 `references/agently-cli-pitfalls.md`。

### 新旧 cron 冲突

确保只有一个周报 cron 在运行。旧 cron `b7ed881d7f19`（用 `academic-weekly-briefing-core`）必须禁用，否则周五会跑两次周报。验证命令：`cronjob action=list | grep briefing`。

## 错误处理

- 搜索全部失败 → 写失败manifest，不编造论文
- PDF失败 → 用WeasyPrint后备，再失败用纯文本邮件
- 邮件失败 → 保存回执，不滚回本地文件
- 任一步失败 → 跳过清理，不影响主流程

## 参考文档

- `references/v2-capability-coverage.md` — 2026-07-03 dry-run 验证：全部13项能力覆盖通过