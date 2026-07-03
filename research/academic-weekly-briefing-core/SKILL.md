---
name: academic-weekly-briefing-core
description: 学术研究周报核心编排器：搜索、去重、质量评估、论文选择、作者团队深挖、文献关系图谱、自适应分析、跨论文综合、周报撰写。唯一周报业务逻辑来源，手动/cron 仅通过 mode 区分。
version: 3.0.0
related_skills:
  - research-profile-engine
  - academic-report-render-deliver
  - academic-briefing-ops
---

# Academic Weekly Briefing Core

## 单一职责

负责一次完整周报生产流程。所有搜索、选择、分析的唯一来源。

## 核心原则

1. cron 不复制业务流程，只传 mode 参数
2. 手动和 cron 通过 mode 参数区分

## 运行模式

- `mode=weekly_cron` — 每周正式周报（周五 10:00 cron）
- `mode=manual` — 用户手动触发
- `mode=dry_run` — 初始化试跑
- `mode=retrospective` — 回看补报
- `mode=trend_only` — 只生成趋势综合

## 输入

所有数据来自 `/opt/data/weekly-briefing/`：
- `config.json` — 全局配置
- `venues.json` — 关注会议/期刊 + 分级信息
- `profile/current.json` — 当前画像
- `profile/topic_feedback.json` — 搜索偏向
- `papers/archive.json` — 历史论文索引
- `papers/dedup.json` — 去重表
- `papers/taxonomy.json` — 分类体系
- `papers/relations.json` — 文献关系图谱

## 输出

- `reports/YYYY-Www/report.md` — 周报正文
- `reports/YYYY-Www/manifest.json` — 运行清单
- `reports/YYYY-Www/team_profiles/` — 作者团队深挖结果
- `papers/archive.json` — 更新
- `papers/dedup.json` — 更新
- `papers/taxonomy.json` — 更新
- `papers/relations.json` — 更新
- `papers/candidates/YYYY-Www.json` — 候选论文
- `indices/quarterly/YYYY-Qn.json` — 季度索引

---

## 主流程（28 步）

### 第一阶段：搜索与筛选（步骤 1-8）
1. 加载上下文
2. 检查配置和数据完整性
3. 读取研究画像和 topic_feedback
4. 生成搜索计划（4 类信号）
5. 多源搜索（Semantic Scholar / arXiv / Exa / Crossref）
   - **直连优先**：用 `run_weekly_e2e.py --discovery-only` 获取候选
   - **后备**：web_search + web_extract
6. 搜索失败 5 层 fallback
7. 论文标准化
8. DOI/arXiv ID 去重

### 第二阶段：质量过滤（步骤 8.5-10）
8.5. **Venue 质量分级**
- T1: CCF-A / SCI一区 / 顶会 (CVPR, ICCV, T-PAMI, RSE, TGRS)
- T2: CCF-B / SCI二区 (IEEE GRSL, RS, JSTARS)
- T3: CCF-C / SCI三四区
- T4: 仅 arXiv 未发表
- Reject: 已知掠夺性期刊

9. 综合质量评分（venue 0.30 + citation 0.15 + relevance 0.25 + novelty 0.15 + reproducibility 0.10 + author 0.05）
10. 可复现性检查

### 第三阶段：深度分析（步骤 11-14）
11. 作者团队深挖（搜索轨迹 + 引用网络 + 机构竞争力）
12. 文献关系图谱交叉验证
13. 3周回看窗口
14. 引用爆炸检测（≥15 citations/week）

### 第四阶段：选择与综合（步骤 15-18）
15. 论文选择（默认 3核心 + 1跨界 + 1自由探索）
16. 论文类型检测 + 自适应分析
17. 投稿时间线扫描
18. 竞争实验室映射

### 第五阶段：撰写与交付（步骤 19-21）
19. 周报撰写（含文献定位回顾 + 团队画像 + 竞争地图）
20. 调用 academic-report-render-deliver
21. 写入 manifest + 更新 relations.json

---

## 文献关系图谱

`/opt/data/weekly-briefing/papers/relations.json`

关系类型：
- `cites` — 新论文引用了已归档论文
- `cited_by` — 已归档论文引用了新论文
- `extends` — 同一方向但新论文推进了
- `contradicts` — 结论冲突
- `complements` — 不同角度解决同一问题
- `supersedes` — 同一团队后续工作

## 自适应分析：按论文类型切换模板

| 类型 | 判断信号 | 分析重心 |
|------|----------|----------|
| 方法论文 | 新架构/新loss | 消融实验、计算成本、泛化证据 |
| 数据集论文 | 新数据集/benchmark | 数据规模、标注质量、互补性 |
| 综述论文 | survey/review | 分类框架、遗漏方向、时间截断 |
| 理论论文 | 数学推导为主 | 假设现实性、与经验差距 |
| 应用论文 | 已有方法→新领域 | Domain gap、迁移fidelity |

## "论文与我"标签

🔧 可借鉴 / ⚖️ 须对比 / ⚠️ 竞争 / 🎯 空白

## Anti-Bias 机制

- 反馈环隔离："下周关注"不自动反馈搜索
- topic_feedback 安全护栏（权重边界 ≤1.3 / ≥0.3）
- 话题漂移检测：连续3周相同 → 触发远邻域注入
- 多样性硬约束（重叠 ≤2，force_explore ≥1）