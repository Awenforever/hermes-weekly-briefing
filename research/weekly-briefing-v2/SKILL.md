---
name: weekly-briefing-v2
description: 安装、个性化配置、运行并通过邮件交付研究论文周报；包含作者团队调研、可点击原文链接和中文 PDF。
version: 4.2.0
related_skills:
  - academic-weekly-briefing-core
  - academic-report-render-deliver
---

# Weekly Briefing

这是 Weekly Briefing 的唯一生产入口。插件完全独立，只生成研究周报并通过邮件交付。

## 安装与配置对话

当用户要求安装、配置、迁移或启用 Weekly Briefing 时，必须主动引导，而不是把 README 或配置模板丢给用户：

1. 先运行 `hermes weekly-briefing setup`，读取 `unresolved` 与 `next_action`。
2. 自动复用已存在的配置和报告数据；不要重复询问已经能够可靠检测到的信息。
3. 对尚未确定的内容逐项确认：
   - 一个或多个核心研究方向/关键词；
   - 收件邮箱；
   - 每期篇数；
   - 每周发送时间和时区；计划任务使用 Hermes profile 的 IANA 时区，若不一致须先说明影响并征得同意后调整 Hermes 时区；
   - 模型提供方、主模型和备用模型（用户无偏好时保留默认）；
   - 是否允许画像权重、是否允许明确的用户反馈影响排序。
4. 使用 `hermes weekly-briefing setup` 的对应参数写入设置。不要要求用户手写 JSON。
5. 检查 Agently：
   - 未安装时，说明将全局安装 `@tencent-qqmail/agently-cli`，获得同意后运行 `mail-install --yes`；
   - 未登录时，运行 `mail-login` 并告诉用户这是交互步骤；
   - 绝不要求用户把密码、令牌、Cookie 或 OAuth 验证码发到聊天中；
   - 用户完成交互后运行 `mail-status`，不能仅凭用户按了 Enter 就声称登录成功。
6. 运行 `doctor`。失败时只处理仍未通过的项目，不重复已完成的登录或配置。
7. 先运行一次不发送的测试；需要发送测试邮件时必须得到用户明确同意。
8. 只有 `doctor` 全部通过且用户确认后，才运行 `schedule-install`。
9. 最终只报告已验证状态、下次运行时间和数据位置；不得泄露完整邮箱、密钥或认证输出。

## 固定边界

- 只通过邮件交付，不生成或发送微信消息。
- 每期默认选择 3–5 篇，目标报告长度 6–10 页。
- 没有逐篇深度分析时，生产交付必须失败；`--allow-shallow` 仅限调试。
- “下周关注”只写追踪建议，不得自动修改核心研究方向。
- 历史画像只有在 `research.use_profile_weights=true` 时才影响排序。
- 反馈只有在 `research.use_user_feedback=true` 且来源明确为用户时才生效。

## 生产执行

手动运行和无 Agent 计划任务都调用同一确定性入口。入口会自行完成发现、模型分析、作者团队补充、渲染和投递：

```bash
python3 {skill_dir}/scripts/run_weekly_e2e.py \
  --week 2026-W38 \
  --data-dir "$HERMES_WEEKLY_DATA_DIR"
```

只验证发现阶段时使用 `--discovery-only`。

## 内容要求

每篇论文必须包含可点击原文、研究问题、方法步骤、证据与局限、跨论文关系，以及作者团队的机构、研究主题、代表性或近期工作。比较使用结构化表格。不得推测缺失的实验数据、作者履历或引用指标。

## 数据与失败处理

所有运行数据位于当前 profile 的 `plugin-data/hermes-weekly-briefing/`。升级不得覆盖配置、作者缓存、论文库、报告或投递回执。

- 任一论文缺少深度分析：停止生产交付。
- PDF 渲染失败：尝试 ReportLab 降级；仍失败则保留 Markdown，不发送残缺附件。
- 邮件发送失败：保留报告和投递状态，禁止改走微信。
- 外部作者数据缺失：明确标记缺失，不臆测。
