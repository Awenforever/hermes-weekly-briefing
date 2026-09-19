---
name: weekly-briefing-v2
description: 每周发现、分析并通过邮件交付个人研究方向的论文简报。包含作者团队调研、可点击原文链接和中文 PDF。
version: 4.0.0
related_skills:
  - academic-weekly-briefing-core
  - academic-report-render-deliver
---

# Weekly Briefing

这是周报的唯一生产入口。手动运行和计划任务都调用 `scripts/run_weekly_e2e.py`。

## 固定边界

- 只通过邮件交付，不生成或发送微信消息。
- 每期选择 3–5 篇，目标报告长度 6–10 页。
- 没有逐篇深度分析时，生产交付必须失败；`--allow-shallow` 仅限调试。
- “下周关注”只写追踪建议，不得自动修改核心研究方向。
- 历史画像只有在 `research.use_profile_weights=true` 时才影响排序。
- 反馈只有在 `research.use_user_feedback=true` 且来源明确为用户时才生效。

## 执行

```bash
python3 {skill_dir}/scripts/run_weekly_e2e.py \
  --week 2026-W38 \
  --data-dir "$HERMES_WEEKLY_DATA_DIR"
```

需要只验证发现阶段时使用 `--discovery-only`。

## 内容要求

每篇论文必须包含：

1. 可点击的 DOI 或 arXiv 原文链接；
2. 研究问题与重要性；
3. 方法的分步说明；
4. 主要证据、对照和局限；
5. 与本期其他论文的关系；
6. 作者团队的机构、研究主题、代表性或近期工作及影响力线索。

跨论文部分使用结构化比较表。不要用模型推测补齐缺失的实验数据、作者履历或引用指标。

## 数据

所有运行数据位于 `HERMES_WEEKLY_DATA_DIR`；在插件模式下默认使用当前 profile 的
`plugin-data/hermes-weekly-briefing/`。插件升级不得覆盖配置、作者缓存、论文库、报告或投递回执。

## 失败处理

- 任一论文缺少深度分析：停止生产交付。
- PDF 渲染失败：尝试 ReportLab 降级；仍失败则保留 Markdown 并报告错误，不发送残缺附件。
- 邮件发送失败：保留报告和投递状态，禁止改走微信。
- 外部作者数据缺失：明确标记缺失，不臆测。
