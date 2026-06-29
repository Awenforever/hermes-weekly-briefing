---
name: weekly-briefing
description: 学术研究周报——引导初始化 → 论文搜索 → 作者调研 → PDF 生成 → 邮件发送，全流程自动化
tags: [research, weekly, briefing, academic, paper, pdf, email]
related_skills: [generate-pdf-with-cjk, weekly-briefing-pipeline, research-profile-evolution, himalaya]
---

# Weekly Academic Paper Briefing

为 Hermes Agent 设计的学术周报自动化系统。skill 加载后**首先执行初始化向导**，引导用户设定研究画像和偏好；之后每周自动搜索论文、深度调研作者团队、生成 PDF、发送邮件。

---

## §0 初始化向导（首次加载时执行）

Hermes 加载此 skill 后，必须逐项向用户询问以下配置。**每项单独问，等用户回复后再问下一项。**

### 0.1 研究关键词（必填）
> 请用 3-5 个关键词描述你的研究方向（中英文均可），我会用它们从 Semantic Scholar / arXiv 搜索每周新论文。
- 存储位置：memory → key: `research-profile.keywords`
- 示例：`smoke detection, remote sensing, multispectral, transformer, wildfire`

### 0.2 一句话研究描述（必填）
> 用一句话描述核心研究问题或目标，用于论文筛选的语义匹配。
- 存储位置：memory → key: `research-profile.description`

### 0.3 技能/方法流派（建议）
> 你主要使用哪些技术方法？（如 Transformer, CNN, GNN, RL, diffusion…）这会帮助我判断一篇论文是否在你的能力范围内。
- 存储位置：memory → key: `research-profile.methods`

### 0.4 跨学科兴趣（可选）
> 除了核心领域，有没有你希望偶尔关注的邻近领域？（如 NLP、CV、多模态、边缘计算…）用于"跨界论文"选题。
- 存储位置：memory → key: `research-profile.xfields`

### 0.5 产出目录（必填）
> 周报文件和 PDF 保存在哪里？默认 `/home/vive/Work/Hermes/YYYY-MM-DD-描述性名称/`
- 存储位置：memory → key: `weekly-briefing.output-dir`

### 0.6 称呼与落款（必填）
> 邮件正文中，称呼写什么（如"老师您好"）？落款写什么（如"—— Hermes 学术助理"）？
- 存储位置：memory → key: `weekly-briefing.email-greeting` 和 `email-signature`

### 0.7 收件人列表（必填）
> 周报发送给哪些邮箱？用逗号分隔，如 `vive@mail.ustc.edu.cn, xxx@mail.com`
- 存储位置：memory → key: `weekly-briefing.email-recipients`

### 0.8 风格偏好（可选）
> 希望周报偏学术严谨，还是通俗易读？需要英文术语保留原文还是全翻译？
- 存储位置：memory → key: `weekly-briefing.style`

### 0.9 必含板块（可选）
> 除了默认板块（本期焦点、精选论文、趋势判断、下周关注），有无额外必含内容？如"方法对比表""参数统计""配图说明"
- 存储位置：memory → key: `weekly-briefing.sections`

### 0.10 自身研究描述（强烈建议）
> 用 2-3 句话描述你目前正在做的具体工作（实验到什么阶段、用什么数据、目标是什么）。这对"论文与我"关联判断至关重要。
- 存储位置：memory → key: `research-profile.my-work`

### 0.11 关注会议/期刊（建议）
> 你关注或准备投稿的顶级会议和期刊有哪些？（如 CVPR/ICCV/NeurIPS/ICLR、TGRS/RS/IEEE TIP…）用逗号分隔。
- 存储位置：memory → key: `research-profile.venues`

### 0.12 自动化设置（建议）

> 要不要我帮你创建自动化的 cron job？
> - **周报**：每周跑一次完整流程（搜索→PDF→邮件）。你希望哪天的几点？（默认周五 10:00）
> - **研究画像演化**：每天 23:55 分析对话、每周日合成、每月初做轨迹分析
> 
> 需要我帮你创建哪些？（可以选"全部"、"只要周报"、"先都不要"、"自定义时间"）

如果用户选择创建 cron job，Hermes 用 `cronjob` 工具创建对应的 job，skill 设为 `weekly-briefing-pipeline` 和 `research-profile-evolution`。

### 0.13 依赖检查（自动执行）

用户完成配置后，**自动执行**（不额外提问，只报告结果）：

1. **PDF 生成依赖**：
   ```bash
   which typst && typst --version    # 首选
   python3 -c "import weasyprint"    # 后备
   ```
   检查 NotoSansCJK 字体：`fc-list | grep -i "Noto.*CJK"`

2. **邮件发送依赖**：
   ```bash
   which agently-cli
   ```

3. **搜索后端可用性**：用 `web_search` 测试一个简单查询（如 "smoke detection"），确认至少一个后端可用。如果全部不可用，提示用户配置 API key。

报告格式：
```
🔍 依赖检查结果：
✅ Typst v0.15.0
✅ WeasyPrint
✅ NotoSansCJK SC 字体
⚠️ agently-cli 未安装 → 我会在需要时提醒你安装
✅ 搜索后端：Exa（可用）、SearchX（可用）
```

如果有缺失，给出安装命令但不强制。

### 0.14 试跑验证（建议）

> 配好了！要不要现在试跑一次？我会搜索 2 篇论文生成一份迷你周报（不发送邮件），5 分钟内验证整个流程是否通畅。

如果用户同意：
1. 搜索 2 篇核心方向论文（跳过完整 5 篇流程）
2. 生成简化 PDF（Typst 或 WeasyPrint）
3. 报告结果：PDF 路径、文件大小、页数、有无错误
4. 如有错误，逐项排查修复

初始化完成后，回复一条完整总结，列出所有配置项、依赖状态、cron 计划、试跑结果（如有）。

---

## §1 每周执行流程

加载 skill 时从 memory 读取所有 `research-profile.*` 和 `weekly-briefing.*`。若缺少必填项，原地重新引导补全。

### 1.1 选题策略
#### 核心原则
**"下周关注"只写给用户看，不作为下周的搜索指令。** 下周的每一轮搜索都重新从研究画像的原始关键词出发，不看上周写过什么。

#### Anti-Bias 机制
- **基线重置**：每 4 周用研究画像的原始关键词严格执行一次搜索，作为"锚定"——对比发现高相关但未被选入的论文
- **多样性约束**：论文集合中，与过去 4 周任何一篇论文方向重叠的 ≤ 2 篇。若超过，人为替换方向最近的
- **强迫探索**：5 篇论文中至少 1 篇来自研究画像之外的新方向搜索（改变搜索源/改变数据库/改变时间范围）
- **惊喜率跟踪**：memory 记录每期"与历史不相似"的论文比例。若连续 2 周该比例 < 20%，自动提高探索配额到 2 篇

#### 搜索源多样化
每期论文必须来自至少 **2 个不同的搜索源**，避免单一 API 的固有偏见：
- Semantic Scholar（学术主搜索）
- arXiv（最新预印本）
- Exa（通用语义搜索，可发现跨界/非学术来源）
- Crossref（DOI 检索，用于回溯追踪）

#### 选文结构
- **3 篇核心**：用研究画像的原始关键词搜索，优先近 4 周新论文
- **1 篇跨界**：用 `research-profile.xfields` 搜索邻近领域
- **1 篇自由探索**：切换搜索源（如只用 Exa 不用 Semantic Scholar）+ 移除所有关键词，用领域大类宽泛搜索

### 1.2 去重检查
- 读取 `~/.weekly_briefing_dedup.json`，以 DOI（优先）或 arXiv ID 为主键
- 本期候选论文若已出现在历史中，自动排除并换一篇
- 选完后将本期 5 篇写入去重 JSON

### 1.3 论文初筛与质量评估
对每篇候选提取：标题、作者、摘要、DOI、期刊/会议、发表日期、被引量
用研究画像做语义匹配，淘汰明显不相关的。

**质量信号**（写入 PDF，标记而非淘汰）：
- 期刊/会议等级：CCF A/B/C 或 SCI Q1/Q2/Q3，标注在论文标题旁
- 预印本标记：arXiv 论文注明"预印本，未同行评审"
- 被引量：Semantic Scholar 取 citationCount，0 引用 vs 高引论文区别对待
- 批判性速评：一句话指出潜在局限（如"仅在小数据集验证""无消融实验""与论文 [X] 结论矛盾"）

### 1.4 可复现性检查
对每篇入选论文：
- 搜索 GitHub 仓库 → 标注 star 数、最后更新日期
- 数据集公开性 → 可下载链接 / 需申请 / 未公开
- 预训练权重 → 有/无，下载链接
- 实验设置清晰度 → 是否足以复现（关键超参、硬件配置）

### 1.5 论文与我关联（核心板块）
读取 `research-profile.my-work`，对每篇论文写一段 <80 字的关联判断：
- 🔧 **可借鉴**：方法/模块能否用在我的问题上？
- ⚖️ **须对比**：是否应加入我的 baseline？
- ⚠️ **竞争**：是否与我的工作高度重叠？
- 🎯 **空白**：这篇论文没解决什么？这是不是我的切入点？

### 1.6 作者团队深度调研
对每篇最终入选论文：
1. Web search 第一作者和通讯作者的姓名 + institution
2. 访问个人主页 / Google Scholar，了解其研究方向和高引论文
3. Web search 该团队的相关项目、数据集、开源代码
4. 汇总写入 PDF 的"作者背景"板块

### 1.7 回看窗口
**不能只看本周新论文。** 每期执行前：
- 用原始关键词搜索近 3 周的所有论文，若某篇被引量在本周爆炸增长（≥15 引用/周），增补入选
- 若上周搜漏的高相关论文在本周讨论度高，补列入"补录"板块
- 从去重清单中随机抽查 1 篇 4 周前入选的论文，看其后续引用、代码更新状态，写入"跟踪"板块

### 1.8 跨论文综合与归类 🔗

周报不能永远只做"单篇摘要"——当相似论文积累到一定量，**必须主动合并、归类、对比、串联**，把碎片变成知识图谱。这是博士生文献综述的自动化前哨。

#### 1.8.1 数据追踪

维护 `~/.weekly_briefing_taxonomy.json`，记录每篇入选论文的：

```json
{
  "doi": {
    "title": "Paper Title",
    "week": 27,
    "year": 2026,
    "subtopics": ["wildfire smoke segmentation", "transformer"],
    "approach_tags": ["ViT", "U-Net", "multispectral"],
    "dataset": "USTC-SmokeRS",
    "key_metric": {"name": "mIoU", "value": "78.3"},
    "cites": ["doi_cited_1", "doi_cited_2"],
    "cited_by_covered": []
  }
}
```

每次生成周报后更新此文件。

#### 1.8.2 触发条件（满足任一即触发综合）

| 条件 | 阈值 | 动作 |
|------|------|------|
| **主题聚集** | 同一 sub-topic 下 6 周内累计 ≥3 篇 | 生成该类论文的 **对比表 + 方法树** |
| **引用链** | 新论文引用了历史周报中的论文，或被其引用 | 标注引用关系，写一句话串联 |
| **数据集重叠** | ≥2 篇论文使用同一数据集 | 并列指标数值，标注最优 |
| **结论冲突** | ≥2 篇论文在相似设定下指标/结论矛盾 | **高亮矛盾**，提醒读者审慎判断 |
| **方法演进** | 同一团队在同一方向发表 ≥2 篇 | 标注演进路径（改进点 + 时间线） |

#### 1.8.3 综合输出格式

当触发综合后，在 PDF 中生成 **「跨论文综合」** 板块，包含：

**A. 方法归类树**（以缩进文本或简单 ASCII 树呈现）
```
烟雾分割
├── CNN 方法
│   ├── U-Net 变体 (Paper A, C)
│   └── DeepLab 变体 (Paper D)
├── Transformer 方法
│   ├── ViT-based (Paper B, E)
│   └── Swin-based (Paper F)
└── 混合方法
    └── CNN+Attention (Paper G)
```

**B. 核心对比表**

| 论文 | 方法 | 数据集 | 关键指标 | 亮点 | 局限 |
|------|------|--------|----------|------|------|
| ... | ... | ... | ... | ... | ... |

**C. 趋势叙事**（2-4 句自然语言）
> 近 6 周烟雾分割方向出现明显的方法迁移：从纯 CNN 架构转向 Transformer 或 CNN-Transformer 混合。数据集方面，USTC-SmokeRS 成为主流 benchmark。但所有方法在薄烟场景下性能仍不理想——这可能是突破点。

**D. 引用关系图**（文本箭头表示）
```
Paper A (2024) → Paper C (2026)  [C 改进了 A 的 backbone]
Paper B (2025) ↔ Paper E (2026)  [同期工作，结论互补]
```

#### 1.8.4 归类-复习周期

- **每 6 周**：对 taxonomy.json 中所有论文做一次全面归类整理，更新方法树和趋势叙事
- **每 12 周**：基于历史综合输出，生成一份 **「12 周研究趋势简报」**（独立 PDF），作为文献综述的初稿骨架
- **触发式综合**（满足 1.8.2 任一条件）：在当周周报中立即执行，不等待周期

#### 1.8.5 综合质量约束

- 对比表中的指标必须来自原文，不得推算
- 冲突标注必须在原文中引用具体数值
- 趋势叙事保持审慎——不夸大、不做预测（如"Transformer 将取代 CNN"），只描述已有事实
- 若触发条件不满足，则本期无跨论文综合板块，不强行生成
- 归类标签（approach_tags）由 Hermes 从摘要中提取，应保持颗粒度一致

### 1.9 投稿时间线
读取 `research-profile.venues`，搜索近期关键节点：
- 未来 30 天内截稿的会议/期刊
- 相关的 Special issue 征稿
- 若有关键截稿日，邮件中加入醒目的截止提醒（如"⏰ *ICCV 2027 摘要截稿：8月15日*"）

### 2.0 内容撰写
- 正文（`email_body.txt`）：邮件概况 + 5 篇论文简介 + 趋势 + 下周关注
- 对于**"下周关注"板块**：内容应来自：
  - 本周论文引用的突破性工作（向前追溯）
  - 顶级会议/期刊的 upcoming 截稿日期
  - 研究热点新闻（来自 Exa 通用搜索）
  - **不得以本周论文方向作为下周关注的唯一来源**，必须至少包含 1 条来自不同方向的信号
- PDF（`briefing.typ` 或 `gen_pdf_weasy.py`）：完整报告含方法对比表、参数统计、作者背景、配图
- 模板完全内容无关——由本周实际论文决定写什么

### 2.1 PDF 生成

> 详细方案见 `generate-pdf-with-cjk` skill（v2.0.0），包含 Typst / WeasyPrint / fpdf2 三种方案对比。

**推荐流程：**

1. **首选 Typst**（CJK + Emoji 原生支持，PDF 小，排版美）：
   ```bash
   cd <output-dir>
   typst compile briefing.typ briefing_weekXX.pdf
   ```

2. **后备 WeasyPrint**（HTML/CSS 排版更灵活）：
   ```bash
   cd <output-dir>
   python3 gen_pdf_weasy.py
   ```

核心要点：
- Typst 字体设置：`#set text(font: ("Noto Sans CJK SC", "Noto Color Emoji"), size: 11pt)`
- WeasyPrint Emoji 必须用 `<span class="e">` 包裹 + CSS `.e { font-family: 'Noto Emoji', ...; }`
- 不注册 NotoColorEmoji 字体作为全局 font-family（会导致中文缺字）

### 2.2 邮件发送
```bash
agently-cli send --to "<recipients>" \
  --subject "学术研究周报 - 2026年第X周" \
  --body "$(cat email_body.txt)" \
  --attach briefing_weekXX.pdf
```

---

## §2 持久化数据

| 数据 | 存储位置 | 内容 |
|------|---------|------|
| 研究画像 | memory: `research-profile.*` | keywords, description, methods, xfields |
| 用户偏好 | memory: `weekly-briefing.*` | email, style, sections, greeting |
| 去重清单 | `~/.weekly_briefing_dedup.json` | DOI/arXiv ID 为 key 的 JSON |
| 论文归类 | `~/.weekly_briefing_taxonomy.json` | 每篇论文的 sub-topic、方法标签、数据集、指标、引用关系 |
| 周报文件 | `<output-dir>/` | email_body.txt, briefing_weekXX.pdf |
| 代码仓库 | GitHub: `Awenforever/hermes-weekly-briefing` | briefing.typ, gen_pdf_weasy.py, email_template.txt |

## §3 研究画像在线更新（三层演化系统）

> **这是周报 skill 的"眼睛"**——没有它，周报就只是在关键词的圈子里打转，永远发现不了你真正在思考什么。

Hermes 不应只在周报执行时才更新画像，而应通过**三层时间粒度的语义分析**持续追踪用户的真实研究兴趣演化。

### 3.1 对话意图分类（关键前置步骤）

在分析用户对话之前，必须先分类，确保**只有 `research_core` 内容进入画像**：

| 类别 | 典型对话 | 影响画像？ |
|------|---------|:--:|
| `research_core` | "CNN vs ViT 在烟雾检测上的优劣？" | ✅ |
| `research_tooling` | "帮我写个 PyTorch DataLoader" | ❌ |
| `system_ops` | "帮我把服务开机自启" | ❌ |
| `life_general` | "明朝为什么灭亡？" | ❌ |
| `one_off` | "帮我发封邮件" | ❌ |
| `entertainment` | 闲聊、梗图 | ❌ |

**分类决策规则**：
1. 写代码 ≠ 研究，架构讨论 = 研究
2. 装工具 ≠ 研究，工具评估 = 研究
3. 数据加载代码 ≠ 研究，数据特性讨论 = 研究
4. 系统配置 ≠ 研究，方法超参讨论 = 研究
5. 长会话混合内容 → 分段分类，只取 `research_core` 部分
6. 模糊边界 → **宁缺毋滥**，排除

### 3.2 三层演化架构

```
Layer 1: Daily Digest（每天 23:55）
  session_search → 当天对话 → 意图分类 → 7 维度语义分析
  → daily/YYYY-MM-DD.md

Layer 2: Weekly Synthesis（每周日 00:30）
  读取 7 天 daily → 跨天模式检测 → memory 更新研究画像
  → weekly/YYYY-Www.md

Layer 3: Monthly Trajectory（每月 1 日 01:00）
  读取全月 weekly → 长期轨迹分析 → memory 重写研究画像
  → monthly/YYYY-MM.md
```

### 3.3 语义分析维度（超越关键词频率）

| 维度 | 日 | 周 | 月 |
|------|:--:|:--:|:--:|
| 主题线程（底层研究问题） | ✓ | ✓ | ✓ |
| 深度梯度（好奇→深挖→实现） | ✓ | ✓ | |
| 方法论品味（偏好什么、排斥什么） | ✓ | ✓ | |
| 跨域连接 | ✓ | ✓ | |
| 兴趣速度（加速/减速） | | ✓ | |
| 种子问题（隐含的下一步） | ✓ | | |
| 范式振荡（对立方法间的摇摆） | | | ✓ |
| 知识债检测 | | | ✓ |
| 身份转变 | | | ✓ |
| 未探索邻域 | | | ✓ |

### 3.4 与周报的联动

- 每周周报执行前，读取最近的 daily digest 和 weekly synthesis，**调整搜索关键词的权重和方向**
- 如果 weekly synthesis 检测到某个方向正在升温 → 本期周报增加该方向的论文配额
- 如果 monthly trajectory 检测到方向漂移 → 提示用户是否需要更新研究画像的核心描述
- 画像更新的结果反过来影响下一期周报的选题策略

### 3.5 部署方式

完整的自动化部署需要两个组件：
1. **本 skill**（`weekly-briefing`）— 周报生成主流程，现已包含对话分类逻辑
2. **`research-profile-evolution` skill** — 三层 cron 作业，负责日常对话分析和画像演化

### 3.6 手动更新（对话中触发）

Hermes 应在对话中主动识别：
- 用户提到新方法、新数据集 → 追加到画像
- 用户表达对某方向兴趣 → 追加到兴趣外延
- 研究重心变化 → 更新核心方向描述

## §4 跨设备同步

另一台 Hermes：
1. 安装系统依赖：Typst + WeasyPrint + NotoSansCJK 字体 + agently-cli
2. Clone 仓库：`git clone git@github.com:Awenforever/hermes-weekly-briefing.git`
3. 安装本 skill 和 `generate-pdf-with-cjk` skill
4. 配置 web_search（Exa 或 SearchX）
5. 加载 skill 后将自动执行初始化向导
6. 从本机 memory 和 `dedup.json` + `taxonomy.json` 同步（手动拷贝或通过 Syncthing）

## §5 博士生须知：周报的边界

这份周报是**你的侦察兵**，不是**你的审判官**。以下是它不能也不会代替你做的事：

- **不替你判断创新性**：批判性速评是信号，不是结论。你应该读摘要后自己判断。
- **不替你决定投稿目标**：投稿时间线提供信息，选哪个会/期刊是你和导师的决定。
- **不替你的导师**：空白点分析是启发，不是命令。导师可能告诉你那方向不值得做。
- **不深读论文正文**：周报基于摘要+公开元数据+网页搜索，不会下载 PDF 全文精读。若你需要深度对比，应手动精读原文。
- **不对重复/低质论文负责**：Semantic Scholar 和 arXiv API 可能返回低质或重复论文，周报尽力初筛但不保证。

**你应该做的事**：
- 收到周报后，挑 1-2 篇最有价值的通读全文
- 若"与我关联"板块标记了 ⚠️竞争，立刻精读并考虑调整计划
- 用"回看"和"跟踪"板块的论文来验证你的文献综述是否完整
- 如果连续 3 周惊喜率走低，考虑拓宽你的研究方向

## §6 Archive — 自动归档与索引

周报生成完毕后自动执行，保证历史可追溯、可检索。

### 6.1 主索引文件

维护 `~/.weekly_briefing_archive.json`：

```json
{
  "briefings": [
    {
      "week": 27,
      "year": 2026,
      "date": "2026-06-29",
      "title": "烟雾检测方法演进：ViT+CNN 混合架构",
      "output_dir": "/home/vive/Work/Hermes/2026-06-29-weekly-briefing-sample/",
      "papers": [
        {"doi": "10.xxxx", "title": "VTrUNet...", "subtopic": "wildfire smoke segmentation"},
        ...
      ],
      "keywords_covered": ["transformer", "multispectral", "ViT", "CNN"],
      "surprise_ratio": 0.4,
      "pdf_path": "briefing_week27.pdf",
      "email_sent": true
    }
  ],
  "last_updated": "2026-06-29T22:00:00+08:00",
  "total_briefings": 1,
  "total_papers_covered": 5
}
```

每期周报完成后追加一条记录。

### 6.2 检索能力

用户可用自然语言查询：
- "哪些期覆盖了 ViT？" → 搜索 `keywords_covered` 和 `papers[].subtopic`
- "最近一次提到 MODIS 是什么时候？" → 全文搜索 `papers[].title`
- "给我今年 Q2 的周报摘要" → 按 `date` 过滤

Hermes 读取 `archive.json` 后用 LLM 理解用户意图并匹配，无需额外搜索基础设施。

### 6.3 季度索引

每 12 周（≈ 一个季度）自动生成 `~/.weekly_briefing_archive_YYYY-QN_summary.md`：

```markdown
# 周报季度归档 — 2026 Q2

## 覆盖论文: 15 篇
## 核心主题演化
W14-W17: CNN 架构优化 → W18-W22: Transformer 入侵 → W23-W26: 混合架构 + 物理模型

## 高频关键词
ViT (8期), Transformer (7期), 多光谱 (6期), 物理模型 (4期), 边缘部署 (2期)

## 各期概览
| 周 | 日期 | 标题 | 论文数 | 惊喜率 |
|----|------|------|--------|--------|
| ... | ... | ... | ... | ... |
```

## §7 Clean — 自动清理策略

为防止存储膨胀，每期周报完成后自动执行清理。

### 7.1 清理优先级

| 优先级 | 对象 | 保留策略 | 操作 |
|--------|------|---------|------|
| P0 | 当期周报文件 | 永久保留（直到被策略覆盖） | 不做任何操作 |
| P1 | 历史 PDF | 保留最近 **12 期** | 删除第 13 期及更早的 PDF 文件 |
| P2 | 历史产出目录 | 保留最近 **12 期** | 删除更早的整个目录（含 email_body.txt 等） |
| P3 | `dedup.json` | 保留最近 **26 周**（半年）的条目 | 删除 DOI/arxiv_id 对应 `first_seen_week` 距今 >26 周的条目 |
| P4 | `taxonomy.json` | 保留最近 **26 周**的论文条目 | 更早的条目移至 `taxonomy_archive.json`，主文件瘦身 |
| P5 | `archive.json` | **永久保留**（每条记录仅 ~200 bytes） | 不做清理 |

### 7.2 清理执行时机

在每期周报的 PDF 生成 + 邮件发送 + archive.json 更新 **全部完成之后**，作为最后一个步骤执行。

### 7.3 清理日志

每期清理结果追加到 `~/.weekly_briefing_cleanup.log`：

```
[2026-06-29 22:30] W27 cleanup:
  - Removed PDF: briefing_week14.pdf (13th oldest)
  - Removed dir: /home/vive/Work/Hermes/2026-03-23-weekly-briefing/ (13th oldest)
  - Pruned dedup.json: 5 entries older than 26 weeks
  - Archived taxonomy: 3 entries to taxonomy_archive.json
  - Current sizes: dedup.json (1.2KB), taxonomy.json (3.4KB), archive.json (2.1KB)
```

### 7.4 安全约束

- **绝不删除 archive.json** — 这是唯一不可恢复的索引文件
- **清理前先 dry-run** — 列出将要删除的文件和条目，确认后再执行
- **删除是不可逆的** — 不在 NAS 回收站范围内的文件直接消失
- **如果任何一步失败** — 跳过当次清理，不影响周报主流程

## §8 常见问题

- PDF 中文乱码 → 用 Typst（`generate-pdf-with-cjk` v2.0.0）
- 搜索后端挂起 → `web: backend: exa`
- 代理 SSL 问题 → API 调 github 走 venv python
- 网络不稳推不上 GitHub → 重试，文件本地已落盘