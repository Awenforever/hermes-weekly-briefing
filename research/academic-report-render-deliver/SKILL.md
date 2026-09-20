---
name: academic-report-render-deliver
description: 将已完成的学术周报渲染为带可点击原文链接的中文 PDF，并仅通过邮件交付。
version: 4.1.0
related_skills:
  - academic-weekly-briefing-core
---

# Academic Report Render & Deliver

本技能只负责渲染、归档和邮件交付，不负责搜索、筛选、画像学习或微信发送。

## 渲染要求

- 首选 WeasyPrint 的 HTML/CSS 渲染。
- WeasyPrint 不可用时使用 ReportLab，并选择系统中的中文字体。
- 两种渲染路径都必须保留 DOI/arXiv 超链接。
- 方法流程使用步骤卡片；跨论文差异使用紧凑比较表；作者信息使用作者卡片。
- 避免单独一行的标题、被截断表格、不可读的小字和大面积无意义留白。

生成后必须检查：

1. 页数与目标篇幅相符；
2. 所有页面能正常渲染；
3. 中文字体无缺字；
4. 至少每篇论文有一个可点击原文链接；
5. 深度分析和作者团队内容均已进入 PDF。

## 邮件交付

- 收件人和发送命令来自用户配置。
- PDF 作为附件，正文只给出本期摘要和论文清单。
- 发送成功后写入投递回执；失败时保留产物供重试。
- 不得把周报正文、附件或失败补偿转发到微信。
