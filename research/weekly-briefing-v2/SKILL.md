---
name: weekly-briefing-v2
description: 学术研究周报（统一版）— 论文搜索发现 + 深度分析 + 精美PDF + 个性化邮件。唯一周报技能，手动和cron通用。
version: 2.0.0
---

# Weekly Briefing v2 — Unified Pipeline

单一技能，覆盖完整周报流程。cron和手动同一入口，流程完全一致。

## 核心原则

- **搜索用直接API**：arXiv API + Crossref API，不走 Hermes web_search（会被block）
- **分析用LLM**：深度分析、作者调研、跨论文综合、个性化撰写
- **PDF用Typst**：精美排版，带色彩系统和论文卡片
- **邮件自动确认**：设 `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1` 即可无人值守
- **持续性数据完整更新**：dedup + archive + taxonomy + relations
- **遇到异常先验证再解释**：用户质疑时必须用实际命令重现/验证，不要推测原因。本次会话教训：`2>&1` 问题是被 `agently-cli ... 2>&1 |` vs `2>/dev/null |` 对比实验证实的，不是猜出来的。

## 执行流程

### 阶段0：前置检查

```bash
# 确认依赖
which typst && typst --version
python3 -c "from weasyprint import HTML; print('OK')"
ls /opt/data/home/.local/bin/agently-cli
fc-list :lang=zh | head -1
```

### 阶段1：论文发现（确定性）

运行E2E runner的发现模式：

```bash
python3 /opt/data/weekly-briefing/scripts/run_weekly_e2e.py \
  --week $(python3 -c "import datetime; y,w,_=datetime.date.today().isocalendar(); print(f'{y}-W{w:02d}')") \
  --discovery-only
```

这会输出 `selected_papers.json` 到 `/opt/data/weekly-briefing/papers/candidates/{week}_selected.json`。

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

**必须去重**：读 `/opt/data/weekly-briefing/papers/dedup.json`，确保不重复。

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
cd /opt/data/weekly-briefing/reports/{week}/
typst compile report.typ report.pdf
```

验证：`ls -lh report.pdf` 应 > 50KB。

### 阶段5：邮件发送

```bash
# 邮件正文：个性化、即兴、有人情味
# 称呼：vive = adjective + Kelvin J.
# 主题：⚚ 学术研究周报 {week} — {一句话概括}
# 落款：--- / {限定词} / 庄奕

export PATH="/opt/data/home/.local/bin:$PATH"
cd /opt/data/weekly-briefing/reports/{week}/

# 发送（两阶段确认）
agently-cli message +send \
  --to "vive@mail.ustc.edu.cn" \
  --subject "⚚ ..." \
  --body-file email_body.txt \
  --attachment report.pdf

# 如果返回 confirmation_required，用返回的token确认
agently-cli message +send ... --confirmation-token {token}
```

如果设了 `HERMES_WEEKLY_EMAIL_AUTO_CONFIRM=1`，runner会自动确认。

### 阶段6：数据持久化

更新以下文件：
- `/opt/data/weekly-briefing/papers/dedup.json` — 追加本期论文
- `/opt/data/weekly-briefing/papers/archive.json` — 追加本期记录
- `/opt/data/weekly-briefing/papers/taxonomy.json` — 更新方法标签
- `/opt/data/weekly-briefing/papers/relations.json` — 更新引用关系
- `/home/vive/Work/Hermes/.weekly_briefing_dedup.json` — 同步更新

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
- **落款**：限定词单独一行，换行后 `Hermes ᥫᩣ` 或 `庄奕 ᥫᩣ`。不要 `---` 分隔线，不要 `/` 符号
- **情绪可变化**：这周懒就说懒话，激动就撒欢，禁止永远彬彬有礼
- **主题前缀**：⚚

## 已知问题与陷阱

### arXiv API 零结果

runner 有时返回 `arxiv_api_candidates: 0`。原因：arXiv API 的 `all:"query"` 语法要求所有词匹配，多关键词查询过于严格。不是 bug，Crossref 通常能补上候选。如果整体候选 < 5 篇，用 `web_search` 补搜一轮。

### agently-cli 输出中混入 stderr

`agently-cli` 的提示文字（如 `tip: ...`）输出到 stderr。管道操作时**不要用 `2>&1`** 将 stderr 合并到 stdout，否则 `json.load()` 会报 `JSONDecodeError: Extra data`。正确做法：只用 stdout，或用 `2>/dev/null` 丢弃 stderr。详见 `references/agently-cli-pitfalls.md`。

### 新旧 cron 冲突

确保只有一个周报 cron 在运行。旧 cron `b7ed881d7f19`（用 `academic-weekly-briefing-core`）必须禁用，否则周五会跑两次周报。验证命令：`cronjob action=list | grep briefing`。

## 错误处理

- 搜索全部失败 → 写失败manifest，不编造论文
- PDF失败 → 用WeasyPrint后备，再失败用纯文本邮件
- 邮件失败 → 保存回执，不滚回本地文件
- 任一步失败 → 跳过清理，不影响主流程

## 参考文档

- `references/v2-capability-coverage.md` — 2026-07-03 dry-run 验证：全部13项能力覆盖通过