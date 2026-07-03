# Hermes Weekly Briefing Skills

学术研究周报技能包。通过 `hermes skills install` 安装。

## 包含技能

| 技能 | 角色 |
|------|------|
| `weekly-briefing-v2` | 生产入口：执行 runner、渲染 PDF、发送邮件 |
| `academic-weekly-briefing-core` | 分析规范：Venue 分级、评分公式、Anti-Bias |
| `academic-briefing-ops` | 运维：初始化、维护脚本、archive 恢复 |
| `academic-report-render-deliver` | 渲染交付：Typst PDF、邮件 |
| `research-profile-engine` | 画像演化：每日/每周/每月语义分析 |

## 安装

```bash
hermes skills install https://github.com/Awenforever/hermes-weekly-briefing
```

## 初始化

```bash
export HERMES_WEEKLY_DATA_DIR=~/.hermes/weekly-briefing
mkdir -p $HERMES_WEEKLY_DATA_DIR
# 从模板创建配置...
```

## 依赖

- Typst (PDF 渲染)
- WeasyPrint (后备 PDF)
- agently-cli (邮件发送)
- CJK 字体 (Noto Sans/Serif CJK SC)
