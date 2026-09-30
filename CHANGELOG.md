# Changelog

## 2026-09-30

- 首次开源发布；skill 由 domain-primer 更名 **unknown-words**（渲染器 localStorage 键保留旧前缀，已存评级不受影响）。
- 游离词控制：渲染器 stderr 报告独立词占比（`###` 词块口径，超 1/3 告警）；存量地图回填上下游，frontend `###` 词块游离率 49% → 7%。
- 产物落盘规则改为**当前工作目录**（`<domain>.md` 与 `<domain>.html` 同名并排），废除 `~/.agents/primers/` 约定。

## 2026-09-29

- quiz 收敛为出题评分单模式（<kbd>Q</kbd> 直进，答错的词下一轮优先再现，评级持久化）。
- 两份存量 primer 回填前置标注；树状渐进图设为默认 layout；全部渲染能力收敛到单文件 `render_editorial.py`。
- 词卡「复制追问提示词」按钮；`前置:` 依赖标注语法（未命中/成环告警丢弃）。
