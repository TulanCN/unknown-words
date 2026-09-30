# unknown-words

[![skills.sh](https://skills.sh/b/TulanCN/unknown-words)](https://skills.sh/TulanCN/unknown-words)

English | [中文](README_ZH.md)

A vocabulary-map for stepping into unfamiliar domains.

An agent skill (for ZCode / Claude Code and anything compatible with the Agent Skills spec) that cures **unknown-unknowns**: when you enter an unfamiliar technical domain, the real barrier isn't that the words are hard — most terms click after hearing them once — it's that **you don't know which words exist, so you don't even have an entry point for asking**.

## What it does

| Capability | Description |
|---|---|
| Vocabulary map | Lays out a domain's lingo in one pass, grouped and tiered (high / mid / low frequency). Every term gets a three-line primer: plain-language definition, where you'll meet it, and how to say it in a command. |
| Progressive tree | Terms can declare prerequisite edges and render as a topology-layered tree; the renderer warns when too many terms float unconnected. |
| Quiz | Press <kbd>Q</kbd> on the tree page for a full-screen quiz auto-generated from the primers; terms you miss resurface first next round, with ratings persisted in localStorage. |
| Deep-dive handoff | One click copies a follow-up prompt for any term — paste it into any agent session to go deeper. |

## Install

One command (via the [skills.sh](https://skills.sh/TulanCN/unknown-words) ecosystem; works with Claude Code / Codex / Cursor and more):

```bash
npx skills add TulanCN/unknown-words
```

Or copy the [`unknown-words/`](unknown-words/) directory into your personal skills directory:

```bash
git clone https://github.com/TulanCN/unknown-words.git
cp -r unknown-words/unknown-words ~/.agents/skills/   # ZCode / Claude Code personal skills dir
```

## Usage

- **Full map**: ask your agent to lay out the vocabulary map for your domain. It produces `<domain>.md` (the source of truth) plus `<domain>.html` (rendered), both in your current working directory.
- **Quick answer**: ask about a single term ("what does this word in the error message mean?"); if a map already exists, the term gets appended to it automatically.
- **Regrow**: the map grows by editing the md and re-running the script — the HTML is always a generated artifact.

```bash
python3 unknown-words/scripts/render_editorial.py <domain>.md -o <domain>.html [--layout tree|spread|inline|hover|review]
```

## Structure

```
.
├── unknown-words/            # the skill: self-contained, installable as a whole directory
│   ├── SKILL.md              # entry: triage rules, three-line primer format, prereq syntax
│   ├── FULL-MAP.md           # full-map workflow: scope → group & lay out → verify → write → deliver
│   ├── LICENSE
│   └── scripts/
│       └── render_editorial.py   # renderer: tree (default) + 4 Swiss-editorial layouts, single file
├── AGENTS.md                 # conventions for agents working on this repo
├── CHANGELOG.md
├── LICENSE
└── README.md
```

> Note: the skill's runtime content (SKILL.md, FULL-MAP.md, and renderer output) is Chinese-first — it is built for Chinese-speaking users entering new technical domains.

## License

[Apache-2.0](LICENSE)
