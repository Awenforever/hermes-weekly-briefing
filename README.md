# Hermes Weekly Briefing

> 把散落在一周里的新论文，变成一份真正值得读的个人研究周报。

Weekly Briefing 会围绕你的研究方向发现并筛选论文，完成基于原文元数据的深度分析与作者团队调研，生成适合中文阅读的 PDF，并按你的时间表通过邮件交付。

[![Hermes](https://img.shields.io/badge/Hermes-%E2%89%A50.21.3-111827)](https://github.com/NousResearch/hermes-agent)
[![Delivery](https://img.shields.io/badge/delivery-email--only-2563eb)](#交付边界)
[![License](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)

## 一眼看懂

| 能力 | 你会得到什么 |
|---|---|
| 论文发现 | 围绕固定研究主线检索、去重和筛选，而不是追逐泛化热点 |
| 深度解读 | 研究问题、方法步骤、证据、对照、局限与跨论文关系 |
| 团队画像 | 作者机构、研究主题、代表性工作与研究路径线索 |
| 精美报告 | 中文 PDF、方法卡片、比较表、作者卡片和可点击原文链接 |
| 稳定交付 | 邮件发送、投递回执、失败可诊断、历史报告可追溯 |
| 防止漂移 | “下周关注”只用于持续追踪，不会自行改写你的核心方向 |

## 让 Hermes 帮你安装

把仓库链接交给 Hermes，并直接说：

> 帮我安装 Weekly Briefing。请先了解我的研究方向、收件邮箱、期望篇数、发送时间和时区，再引导我完成邮件登录；全部检查通过后先试运行，不要直接开启计划任务。

Hermes 读取本 README 与插件 Skill 后，会主动完成以下流程：

1. 检查旧版数据并安全迁移，不覆盖已有配置和历史报告；
2. 逐项询问尚未确定的个性化设置，而不是让你手写配置文件；
3. 检查分析模型、PDF 渲染器与 Agently 邮件工具；
4. 如缺少 Agently，在征得同意后安装；
5. 打开 Agently 的交互式登录流程，由你在终端或浏览器中完成授权；
6. 验证登录状态，生成一份测试周报；
7. 经你确认后再安装每周计划任务。

> [!IMPORTANT]
> 邮件密码、令牌、Cookie 或 OAuth 验证码不应发送给 Hermes。需要人工授权时，Hermes 会明确告诉你在哪个终端或浏览器完成，并在你确认后继续检查。

## 个性化内容

首次设置会围绕你的真实需求确认：

- 核心研究方向与关键词；
- 每期论文数量（默认 5 篇）；
- 收件邮箱；
- 每周发送时间与时区；
- 分析模型与备用模型；
- 是否允许显式维护的研究画像或用户反馈影响排序。

默认不会让历史周报自己“训练”出新的兴趣。只有你明确开启画像权重或反馈学习后，历史偏好才会参与筛选。

计划任务按 Hermes profile 的 IANA 时区运行。若你选择的时区与 profile 不一致，体检会明确拦截，而不会在错误的本地时间悄悄发送。

## 报告长什么样

每篇入选论文都会尽可能包含：

- 可点击的 DOI 或 arXiv 原文链接；
- 研究问题及其价值；
- 清晰的方法步骤；
- 摘要能够支持的证据、对照与局限；
- 与本期其他论文的联系；
- 作者团队的机构、研究主题、近期工作与影响力线索。

缺失的信息会明确标为“摘要未说明”或“需阅读全文核验”，不会由模型猜测补齐。

## 交付边界

Weekly Briefing **只负责生成周报并发送邮件**，不直接向微信发送任何周报或失败通知。若 Email Watchdog 监测到这封周报邮件并将其提醒到微信，那是另一个完全独立插件的行为。

## 手动管理

通常让 Hermes 操作即可；下面的命令适合排障和自动化：

```bash
# 查看还缺哪些设置
hermes weekly-briefing setup

# 完整体检：研究配置、模型、PDF 与邮件登录
hermes weekly-briefing doctor

# 手动生成；加 --send-email 才会投递
hermes weekly-briefing run
hermes weekly-briefing run --send-email

# 体检通过后安装计划任务
hermes weekly-briefing schedule-install --schedule "0 2 * * 5"
hermes weekly-briefing schedule-status
```

Agently 邮件工具由插件显式管理：

```bash
hermes weekly-briefing mail-status
hermes weekly-briefing mail-install --yes
hermes weekly-briefing mail-login
```

`mail-login` 是交互步骤，可能打开浏览器或要求在当前终端确认。插件不会伪造登录成功；只有身份检查真实通过，计划任务才允许安装。

## 数据、升级与恢复

个人配置、论文索引、作者缓存、报告、投递回执和运行日志都保存在当前 Hermes profile 的：

```text
plugin-data/hermes-weekly-briefing/
```

插件升级不会覆盖该目录。重新安装会优先识别已有数据；计划任务只能在完整体检通过后启用。发送失败时，报告仍保留在本地，且不会偷偷改走微信。

## 运行要求

- Hermes `>=0.21.3,<0.22`
- Python 3.11+
- 可用的 Hermes OpenAI-compatible 模型提供方
- WeasyPrint 或 ReportLab，以及可显示中文的系统字体
- Node.js/npm（仅在需要安装 Agently CLI 时）
- Agently CLI 的有效邮件登录

## License

[MIT](LICENSE)
