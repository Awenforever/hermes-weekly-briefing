---
name: weekly-briefing
description: 学术研究周报——引导初始化 → 论文搜索 → 作者调研 → PDF 生成 → 邮件发送，全流程自动化
tags: [research, weekly, briefing, academic, paper, pdf, email]
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

初始化完成后，回复一条总结并询问是否有要调整的。

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

### 1.8 投稿时间线
读取 `research-profile.venues`，搜索近期关键节点：
- 未来 30 天内截稿的会议/期刊
- 相关的 Special issue 征稿
- 若有关键截稿日，邮件中加入醒目的截止提醒（如"⏰ *ICCV 2027 摘要截稿：8月15日*"）

### 1.9 内容撰写
- 正文（`email_body.txt`）：邮件概况 + 5 篇论文简介 + 趋势 + 下周关注
- 对于**"下周关注"板块**：内容应来自：
  - 本周论文引用的突破性工作（向前追溯）
  - 顶级会议/期刊的 upcoming 截稿日期
  - 研究热点新闻（来自 Exa 通用搜索）
  - **不得以本周论文方向作为下周关注的唯一来源**，必须至少包含 1 条来自不同方向的信号
- PDF（`gen_pdf_weasy.py`）：完整报告含方法对比表、参数统计、作者背景、配图
- 模板完全内容无关——由本周实际论文决定写什么

### 1.10 PDF 生成
```bash
cd <output-dir>
python3 gen_pdf_weasy.py
```
使用 WeasyPrint + NotoSansCJK 字体，中文排版正确。

### 1.11 邮件发送
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
| 周报文件 | `<output-dir>/` | email_body.txt, briefing_weekXX.pdf |
| 代码仓库 | GitHub: `Awenforever/hermes-weekly-briefing` | gen_pdf_weasy.py, email_template.txt |

## §3 研究画像在线更新

Hermes 应在对话中主动识别：
- 用户提到新方法、新数据集 → 追加到 `research-profile.methods`
- 用户表达对某方向兴趣 → 追加到 `research-profile.xfields`
- 研究重心变化 → 更新 `research-profile.description`

## §4 跨设备同步

另一台 Hermes：
1. 安装系统依赖：WeasyPrint + NotoSansCJK + agently-cli
2. Clone 仓库：`git clone git@github.com:Awenforever/hermes-weekly-briefing.git`
3. 安装本 skill
4. 配置 web_search（Exa 或 SearchX）
5. 加载 skill 后将自动执行初始化向导
6. 从本机 memory 和 `dedup.json` 同步（手动拷贝或通过 Syncthing）

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

## §6 常见问题

- PDF 中文乱码 → 用 weasyprint
- 搜索后端挂起 → `web: backend: exa`
- 代理 SSL 问题 → API 调 github 走 venv python
- 网络不稳推不上 GitHub → 重试，文件本地已落盘
