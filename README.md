# Hermes Weekly Briefing

面向个人研究方向的每周论文简报插件。它发现并筛选论文，完成深度分析和作者团队调研，生成可点击原文链接的 PDF，并只通过邮件交付。

## 输出内容

- 每期默认精选 3–5 篇论文，形成约 6–10 页报告。
- 说明研究问题、价值、方法步骤、证据、局限与论文间差异。
- 介绍作者团队的机构、研究主题、近期论文、引用和学术影响线索。
- 论文标题、DOI 与 arXiv 地址可直接点击跳转原文。
- 使用适合中文阅读的方法卡片、比较表和作者卡片。

“下周关注”只是持续追踪提示，不会自动改变研究主线。只有显式启用画像权重或接受明确的用户反馈时，后续选题才会受历史偏好影响。

本插件不向微信发送周报；周报的唯一交付渠道是邮件。Email Watchdog 是独立插件，不参与周报生成或发送。

## 要求

- Hermes `>=0.21.3,<0.22`
- Python 3.11+
- 可用的 Hermes 模型配置
- WeasyPrint；ReportLab 用作降级渲染器
- 支持中文的系统字体
- 可用的邮件发送命令

## 安装

```bash
hermes plugins install Awenforever/hermes-weekly-briefing
hermes plugins enable hermes-weekly-briefing
```

查看状态并试运行：

```bash
hermes weekly-briefing init --email-to you@example.com --keyword "your research topic"
hermes weekly-briefing doctor
hermes weekly-briefing status
hermes weekly-briefing run
```

`init` 会优先迁移旧版 `weekly-briefing/` 数据；全新安装时则创建当前 profile 的最小生产配置。生产运行缺少深度分析时会停止交付；仅调试时才可显式允许浅层报告。

安装或修复每周计划任务：

```bash
hermes weekly-briefing schedule-install
hermes weekly-briefing schedule-status
```

该命令会把已有的 `weekly-briefing-v2` 任务原位升级为确定性、无 Agent 的邮件任务，清除失效的模型固定项，并把 Hermes 的计划任务输出限制在本地。它不会通过微信投递周报或失败通知。

## 研究偏好

| 选项 | 默认值 | 作用 |
|---|---:|---|
| `research.use_profile_weights` | `false` | 是否让历史画像影响检索排序 |
| `research.use_user_feedback` | `false` | 是否使用明确的用户反馈调整偏好 |

默认模式每周按固定研究配置独立筛选，不会因为模型自己写出的“关注点”而持续漂移。

## 数据与隐私

配置、论文元数据、作者缓存、报告和投递回执保存在当前 Hermes profile 的 `plugin-data/hermes-weekly-briefing/`。升级插件不应覆盖这些数据。报告可能包含个人研究兴趣和收件信息，应按私人研究资料保护。

## License

[MIT](LICENSE)
