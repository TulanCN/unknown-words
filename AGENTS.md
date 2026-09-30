# AGENTS.md

本仓库是 unknown-words skill 的发布仓库。开发态正本在 `~/.agents/skills/unknown-words/`，任一侧改动后同步拷贝到另一侧；地图的生长只改 md 重跑脚本，HTML 是生成物、不入库。

## 结构

- `unknown-words/` — skill 本体，自包含可整目录安装：`SKILL.md`（入口）、`FULL-MAP.md`（全图流程）、`scripts/render_editorial.py`（渲染器）。
- 渲染验证：`python3 unknown-words/scripts/render_editorial.py <任意>.md -o /tmp/x.html`，stderr 无告警即通过；告警文案即修复指引（游离词超 1/3 → 给词补 `前置:` 上游锚点，平行词之间不造假边）。

## 历史兼容

渲染器内 localStorage 键以 `domain-primer` 开头——skill 更名前的旧键，保留以兼容已存的 quiz 评级，**勿改**。
