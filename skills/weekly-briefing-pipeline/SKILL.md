---
name: weekly-briefing-pipeline
description: 每周五/六自动生成学术研究周报 — 论文检索、深度调研、个性化撰写、邮件发送
---

# Weekly Briefing Pipeline

每周为博士生 Jinhong (Kelvin) 生成遥感多光谱烟雾检测方向的前沿论文周报。

## 核心原则

1. **无固定模板**：每篇论文不同的呈现方式，取决于论文本身特质和你的研究阶段需求
2. **角色扮演**：我是你的科研助理/朋友/导师，不是机器人填表
3. **前沿性优先**：拓宽视野 > 深化已知方向
4. **作者团队深度调研**：去官网、Google Scholar读高引论文摘要后再写

## 前置准备

每次执行前，先执行以下步骤：

### 1. 读取去重清单

```python
import json, os
DEDUP_FILE = '/home/vive/Work/Hermes/.weekly_briefing_dedup.json'
if os.path.exists(DEDUP_FILE):
    with open(DEDUP_FILE) as f:
        dedup = json.load(f)
else:
    dedup = {'papers': [], 'weeks': []}
```

清单结构：
```json
{
  "papers": [
    {"doi": "10.1016/j.rsase.2024.101152", "title": "A transformer boosted UNet...", "week": "2026-W27"},
    ...
  ],
  "weeks": [
    {"week": "2026-W27", "date": "2026-06-29", "papers_count": 5, "keywords": ["smoke", "transformer", "landsat"]},
    ...
  ]
}
```

选论文时，用 DOI 或 arXiv ID 去重。不重复收录同一篇论文。

### 搜索故障应对策略

web_search 有 4 个后端（Exa/Parallel/Tavily/Firecrawl），实际可用取决于密钥配置。搜不到时的备选方案：

1. **web_search 失败/超时** → 改用 `web_extract` 直接读 DOI/arXiv 页面
2. **DOI 页面被 blocked** → 读 arXiv 预印本（如果论文有）；或搜论文全名+作者名迂回
3. **所有 web 工具都失败** → 用 `execute_code` + Python requests 自建搜索（可带自定义 User-Agent、代理）
4. **需绕过反爬** → 用 `browser` 工具（playwright）模拟浏览器访问
5. **最后手段** → 用 SerpAPI（你已配置 key），通过 `execute_code` + Python requests 调用

### 2. 读取研究画像

从 memory 中读取 `research-profile` 条目，了解当前兴趣图谱。

### 3. 确定本周选题策略

论文数量不固定，视当周产出而定。

- **平时（3-5篇）**：烟雾检测/分割/反演核心论文为主，辅以1篇跨界/自由选题
- **丰收周（5-8篇）**：如果某个子方向集中出新论文（如某会议刚开完、某特刊刚上线），可以串烧——把几篇相关论文串成一个 narrative，讲「这个方向这周发生了什么」
- **枯水周（1-2篇）**：如实相告，不凑数。可以说「这周卫星都很安静，只捡到两篇，但质量还行」

选题时用 web_search，关键词组合示例：
- `site:arxiv.org smoke detection remote sensing 2025 2026`
- `site:arxiv.org wildfire segmentation transformer 2025 2026`
- `site:arxiv.org vision transformer remote sensing survey 2025`
- `site:arxiv.org multimodal foundation model earth observation 2025 2026`
- `site:openreview.net smoke detection` 等

每个候选论文先对照 dedup 清单去重。

### 4. 深度调研论文

对每篇选定的论文，执行：

```
1. 读摘要（arXiv / DOI / web_extract）
2. 作者信息：web_search "author name + institution + Google Scholar"
3. 机构背景：如果有机构官网，提取研究组介绍
4. 高引论文：找该团队2-3篇代表作，读摘要
5. 综合写成一段团队背景（200-300字），包括：
   - 机构/研究组定位
   - 核心作者资历
   - 该方向的研究脉络
   - 有意思的合作网络或项目背景
```

### 5. 撰写周报

**结构自由**，不预设固定字段。但整体上应有：

- **一封邮件**：带个性化称呼、开篇寒暄、正文、结尾寒暄、创意落款（详见 §5.1）
- **一个PDF附件**：用 weasyprint 生成

#### §5.1 邮件个性化规则

##### A. 用户身份感知（首次使用时生效）

本 skill 面向大众用户。不同用户会自设称呼（"叫我女王大人" / "我叫Kelvin" / "全知全能的神"……），你需要**从称呼推断身份和风格基调，再投其所好**。

1. 如果用户已在 memory 中指定过称呼 → 直接用，每次变花样但不偏离基调
2. 如果未指定且上下文不足以判断 → **直接问**：「对了，周报里你想让我怎么称呼你？另外，周报是否还要发给别人？他们的称呼偏好是什么？」
3. 身份推断与风格映射：
   - 男性化称呼（Kelvin、老王、主公）→ 平等/伙伴感、可调侃
   - 女性化称呼（公主、女王大人、殿下）→ 更尊重/宠溺、稍加仪式感
   - 中性/不确定 → 先问，不瞎猜
4. 称呼 → 寒暄 → 结尾的语气、用词、情绪**全链路对齐**用户身份——不是只改个名字

##### B. 通用预设（所有用户适用，随 skill 分发）

**核心原则：每次即兴，不做机器人。** 语调可以哀可以怒可以懒可以疯可以敷衍可以阴阳怪气——完全即兴，不可预知，唯独不可以一成不变。

- **邮件主题**：以 ⚚ 前缀开头，其余自由发挥
- **称呼**：依据 §A 的身份基调，每次变换修饰但不跑偏
- **开篇/结尾寒暄**：1-2 句，中文，有人情味，点到即止
- **落款**：固定 **Hermes ᥫᩣ**（所有用户统一）。收束语（Best/Always/Cheerfully/With care/—H/... 或即兴）每次自选
- **情绪变量**：每周情绪基调可以不同——这周懒就说懒话，激动了就撒欢，想吐槽就吐槽。禁止永远「彬彬有礼」

##### C. 本地配置 — Kelvin 专属

> 以下为当前用户 Kelvin (vive) 的硬配置。执行时直接套用，不走 §A 推断流程。
> 如果此 skill 被分发，其他用户应通过 §A 自行配置，而非照搬本节。

- **vive (Kelvin J.)**：每次用一个不同英文形容词修饰 "Kelvin J."，"Dear" 可选非必须。示例：Gracious Kelvin J. / My dear Unstoppable Kelvin J. / Tenacious Kelvin J. 禁止堆砌多个形容词
- **wmwen (公主)**：女性化、亲近/宠溺基调，从「公主」「殿下」「阿文」方向每次变花样。示例：给公主请安 / 殿下吉祥 / 阿文，收好
- **开篇/结尾**：中文，有人情味，可日常可文艺，点到即止。禁止古风堆砌、模板化句式、过度煽情

## PDF 生成规范（weasyprint）

> ⚠️ 以下规则来自 weasyprint 实测踩坑。违反任一条都可能导致排版异常（奇怪的点、方块、不可控缩进）。

### 核心禁令

1. **禁止使用 Unicode emoji**（🔴🔥🟢📋💡👥 等）。weasyprint 的 NotoColorEmoji 字体渲染极不稳定，会在 PDF 中变成方块、点或空白。
2. **禁止依赖浏览器默认 list-style**（`<ul>` 的圆点、`<ol>` 的数字）。weasyprint 对这些默认样式的处理不可预测。
3. **禁止用 Unicode 项目符号 `•`**。用 ASCII `-` 替代。

### CSS 必须包含的 reset

```css
/* 强制覆盖浏览器默认值，防止 PDF 中出现不可控的缩进和符号 */
ul, ol { list-style: none; padding-left: 0; margin-left: 0; }
p { text-indent: 0; margin: 0 0 6pt 0; }

/* 用 CSS 伪元素替代 emoji 和无序列表符号 */
ul > li::before { content: "▸ "; color: #888; }

/* 有序列表用 CSS counter 替代默认数字 */
ol { counter-reset: ol-counter; }
ol > li { counter-increment: ol-counter; }
ol > li::before {
  content: counter(ol-counter) ". ";
  font-weight: bold;
  color: #555;
}
```

### 视觉标记替代方案

| 原始意图 | ❌ 错误做法 | ✅ 正确做法 |
|---------|------------|-----------|
| 分类彩色标记 | `🔴 野火` `🟣 气溶胶` | `<span class="badge tag-fire">FIRE</span>` — CSS styled badge |
| 无序列表 | `<ul>` 默认圆点 | `list-style: none` + `li::before { content: "▸ "; }` |
| 项目符号 | Unicode `•` | ASCII `- ` |
| 图标强调 | `👥 团队` `💡 启示` | 纯文字加粗：`<b>团队背景：</b>` |
| 段落缩进 | 依赖浏览器默认 | 显式设 `p { text-indent: 0; }` |

### 字体声明

只注册必需字体，**不注册 NotoColorEmoji**：

```css
@font-face {
  font-family: 'Noto CJK';
  src: url('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc');
  font-weight: normal;
}
@font-face {
  font-family: 'Noto CJK';
  src: url('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc');
  font-weight: bold;
}
@font-face {
  font-family: 'Noto Mono';
  src: url('/usr/share/fonts/opentype/noto/NotoSansMono-Regular.ttf');
}
```

如果需要 emoji（如邮件主题 ⚚、落款 ᥫᩣ），确保这些字符对应的 glyph 在 CJK 字体中存在。`ᥫᩣ` 属于 Tai Le 区块，大多数 CJK 字体不支持——可移至 Python 代码中作为字符串拼接，不放入 HTML 让 weasyprint 渲染。

### 排版检查清单

PDF 生成后必须验证：
1. `grep -P` 检查 HTML 中是否有残留 emoji（U+1F300-U+1F9FF, U+2700-U+27BF, U+2600-U+26FF）
2. 用 `pdftoppm` 转图片后视觉确认：无方块、无奇怪缩进、列表标记正常
3. 检查 `<ul>` 和 `<ol>` 是否都有对应的 CSS reset 规则

### 6. 发送邮件

用 agently-cli 两阶段发送（先获取 confirmation_token，再确认）。

### 7. 更新持久化数据

```python
# 更新去重清单
dedup['papers'].append({
    "doi": paper_doi, "title": paper_title, 
    "week": current_week, "keywords": keywords
})
dedup['weeks'].append({
    "week": current_week, "date": today, 
    "papers_count": n, "keywords": all_keywords
})
with open(DEDUP_FILE, 'w') as f:
    json.dump(dedup, f, indent=2, ensure_ascii=False)
```

### 8. 归档 — 更新 archive.json

每期周报完成后，更新 `~/.weekly_briefing_archive.json`（首次运行时创建）：

```json
{
  "briefings": [
    {
      "week": 27, "year": 2026, "date": "2026-06-29",
      "title": "本期周报标题（自拟）",
      "output_dir": "/home/vive/Work/Hermes/...",
      "papers": [{"doi": "...", "title": "...", "subtopic": "..."}],
      "keywords_covered": ["transformer", "multispectral"],
      "surprise_ratio": 0.4,
      "pdf_path": "briefing_week27.pdf",
      "email_sent": true
    }
  ],
  "last_updated": "...", "total_briefings": 1, "total_papers_covered": 5
}
```

每 12 周额外生成 `~/.weekly_briefing_archive_YYYY-QN_summary.md`（季度概览：主题演化、高频关键词、各期概览表）。

### 9. 清理 — 自动瘦身

在步骤 8 完成后，按以下策略清理（先 dry-run 列出将要删除的内容，再执行）：

| 对象 | 保留策略 |
|------|---------|
| 历史 PDF（在 output-dir 中） | 保留最近 **12 期**，删除更早的 |
| 历史产出目录 | 保留最近 **12 期**，删除更早的 |
| `dedup.json` 条目 | `first_seen_week` 距今 > **26 周**的条目删除 |
| `taxonomy.json` 条目 | 距今 > **26 周**的条目移至 `taxonomy_archive.json` |
| `archive.json` | **永久保留，绝不删除** |

清理结果追加到 `~/.weekly_briefing_cleanup.log`（格式：`[日期] Wxx cleanup: Removed X, Pruned Y, Sizes: ...`）。

安全约束：
- 任何一步失败 → 跳过清理，不影响周报主流程
- 绝不删除 archive.json
- 清理前先 dry-run

## 持久化数据结构

### 去重清单
文件: `/home/vive/Work/Hermes/.weekly_briefing_dedup.json`

### 研究画像 (memory)
在 `user` 目标下维护 `research-profile` 条目，格式：
```
## Research Profile (动态更新)
核心方向: 多光谱卫星影像烟雾检测/分割/反演
技术栈: CNN, Transformer, ViT, UNet, 物理模型, 多光谱波段分析
兴趣外延: [每周新增的拓展方向]
已读跨界论文: [简要记录]
工具偏好: USTC_SmokeRS, Landsat, Sentinel-2, MODIS
下一阶段可能需求: 检测→反演桥接, 轻量化部署, 跨平台泛化
```

### 周报工作流
此 skill 本身即是持久化的工作流定义。

## 输出文件规则

- 目录: `/home/vive/Work/Hermes/YYYY-MM-DD-weekly-briefing/`
- PDF: `briefing_weekN.pdf` (N = 年内周数)
- 脚本: `gen_pdf_briefing.py`
- 邮件正文: `email_body.txt` (可选)
