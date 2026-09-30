# unknown-words

Give you a vocabulary-map for stepping into unfamiliar domains · 进入陌生技术领域前的第一张词汇地图

一个 agent skill（适用于 ZCode / Claude Code 及兼容 Agent Skills 规范的工具），治的是 **unknown-unknowns**：跨进新领域时，真正的障碍不是生词难懂——多数词听过一次就懂——而是**不知道这些词存在，连提问的入口都没有**。

## 它做什么

| 能力 | 说明 |
|---|---|
| 词汇地图 | 按组分层次一次铺全领域行话（高频/中频/低频），每个词给"人话定义 + 什么场景遇到 + 怎么发命令"三件套 |
| 树状渐进图 | 词间可标注 `前置:` 依赖，渲染成拓扑分层的树状图；游离词超阈值渲染器会告警 |
| Quiz 自测 | 树状图页按 <kbd>Q</kbd> 进全屏出题评分，从三件套自动出选择题，答错的词下一轮优先再现 |
| 深挖途径 | 词卡一键复制追问提示词，粘进任意 agent 会话即可深挖 |

## 安装

把 [`unknown-words/`](unknown-words/) 整个目录复制到个人技能目录：

```bash
git clone https://github.com/TulanCN/unknown-words.git
cp -r unknown-words/unknown-words ~/.agents/skills/   # ZCode / Claude Code 个人技能目录
```

重启会话后说"我要开始写前端了 / 接手 K8s 运维 / 我是刚转来的新手"即可自动触发，也可显式调用 `/unknown-words`。

## 使用

- **全图**：让 agent 为你的领域铺一张词汇地图，产出 `<domain>.md`（事实源）+ `<domain>.html`（渲染产物），落在当前工作目录
- **快答**：单个词直接问（"这个报错里的词是什么意思"），已有地图会自动把词补进去
- **渲染**：地图生长只改 md、重跑脚本，HTML 永远是生成物

```bash
python3 unknown-words/scripts/render_editorial.py <domain>.md -o <domain>.html [--layout tree|spread|inline|hover|review]
```

## 结构

```
.
├── unknown-words/            # skill 本体:自包含,整目录拷走即装
│   ├── SKILL.md              # 技能入口:分档规则、三件套格式、前置标注语法
│   ├── FULL-MAP.md           # 全图模式流程:摸底 → 分组铺词 → 校验 → 落盘 → 交付
│   ├── LICENSE
│   └── scripts/
│       └── render_editorial.py   # 渲染器:树状图(默认) + 4 种瑞士编辑风版式,单文件自足
├── AGENTS.md                 # agent 协作约定(开发态正本、验证命令)
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## License

[Apache-2.0](LICENSE)
