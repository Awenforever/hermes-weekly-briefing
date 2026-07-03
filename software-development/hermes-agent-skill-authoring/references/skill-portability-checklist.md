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