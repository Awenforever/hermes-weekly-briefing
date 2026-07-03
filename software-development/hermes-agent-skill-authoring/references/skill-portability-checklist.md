# Skill Portability Checklist

在发布 skill 供 `hermes skills install` 使用前，逐项验证。

## 1. 脚本包含性

`hermes skills install` 只拉取 skill 目录内的文件。外部脚本不会随 skill 安装。

- [ ] 所有运行时脚本在 `scripts/` 子目录下（不在 `~/.hermes/scripts/` 或 `/opt/data/` 等外部路径）
- [ ] `run_*.py`、`daily_*.py`、`health_check.py` 等关键脚本全部归位
- [ ] SKILL.md 中引用脚本时使用 `{skill_dir}/scripts/` 占位符，不硬编码绝对路径

## 2. 路径可配置性

- [ ] 数据目录通过环境变量控制（如 `HERMES_WEEKLY_DATA_DIR`），提供合理默认值（`~/.hermes/<name>/`）
- [ ] 关键工具路径用 `shutil.which()` 或 PATH 搜索，不用硬编码 `/opt/data/home/.local/bin/`
- [ ] 脚本接受 `--data-dir` 参数覆盖环境变量
- [ ] SKILL.md 中用 `$DATA_DIR` 占位符替代具体路径

## 3. 种子配置

- [ ] 提供 `templates/config.json.template` 含占位符（`$YOUR_NAME`、`$DATA_DIR` 等）
- [ ] 首次安装初始化步骤明确写在 SKILL.md 中

## 4. 硬编码审查

- [ ] `grep -rn '/opt/data\|/home/<user>\|/Users/<user>' scripts/ SKILL.md` 零结果（或仅在注释/示例中出现）

## 5. 依赖声明

- [ ] SKILL.md 列出所有外部依赖（Typst、WeasyPrint、agently-cli、CJK 字体等）
- [ ] 提供依赖检查命令（`which typst`、`fc-list :lang=zh`）

## 6. Skill 关系清晰

- [ ] 多 skill 组成系统时，每个 SKILL.md 头部标注角色（"生产入口" / "分析规范" / "运维"），消除"双唯一"冲突
- [ ] `related_skills` 正确指向互补 skill
- [ ] 生产入口 skill 明确引用规范 skill 的分析规则

## 7. 隐私审查

在发布前扫描所有 skill 文件中的个人信息：

- [ ] `grep -rn 'vive\|Kelvin\|庄奕\|@.*\.edu\.cn\|github\.com/<username>' **/*.md **/*.py` 零结果
- [ ] 邮件地址不在 SKILL.md 或脚本中硬编码；使用 `config.json` 字段或 `your@email.com` 占位符
- [ ] 姓名/签名不在 SKILL.md 中硬编码；引用 `config.json` → `user.display_name` / `style.signature`
- [ ] 研究关键词不在 `config.json.template` 中硬编码（即使它们是你自己的研究方向）；全部改为 `$YOUR_*` 占位符
- [ ] 用户特有路径（`/home/<user>/Obsidian/`、`/Users/<user>/`）引用 `$DATA_DIR/` 或 `~/.hermes/`

## 8. 隔离环境测试

发布前在独立环境验证 skill 安装流程：

- [ ] 创建临时 `HERMES_WEEKLY_DATA_DIR`（或对应变量），不与生产数据共用
- [ ] 从模板创建 config.json，填写测试值，验证 runner 能读取
- [ ] 运行 `run_*_e2e.py --discovery-only --max-selected 2`（验证论文发现逻辑）
- [ ] 运行 `health_check.py` 和 `daily_maintenance.py`（验证运维脚本）
- [ ] 确认所有错误是"首次缺失数据文件"类（`dedup.json not found`），不是"找不到脚本/配置"类
- [ ] 验证引导流程：新用户按 SKILL.md 初始化步骤能否独立完成设置