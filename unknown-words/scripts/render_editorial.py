#!/usr/bin/env python3
"""Render an unknown-words markdown map as a Swiss editorial index / tree map.

Usage:
    python3 render_editorial.py primer.md -o primer.html [--layout TREE|SPREAD|INLINE|HOVER|REVIEW]

瑞士杂志排版风格:纸白底、衬线大标题、黑 + 一点红、词条编号(No.001…)。
5 种布局(--layout),默认 TREE:

  TREE    树状渐进关系图(默认):消费 md 可选「前置:」标注——前置边涉及的词按
          拓扑层铺开(层内按 频率→组序→词序),SVG 贝塞尔连线带箭头(方向=学习方向)。
          级联钻取:↑↓ 当前层兄弟(虚线框)内切换,→ 进子节点(红框预览),← 退一层,
          已走路径墨框保留、历史层兄弟范围累积保留(整体感知);独立词(无边)进底部
          按族折叠带,四向自由网格移动。空格标记,C 复制追问,Esc 回全图。
          按 Q(或报头按钮)进入 Quiz 全屏出题评分:从三件套自动出选择题,干扰项
          取同组/同频率词,答完出分 + 错题回顾;答错过的词下一轮优先再现。
          出题按前置拓扑序分层取样(频率→组序→词序),评级持久化。
          无前置标注的地图退化为纯词表(全部进折叠带),同样可键盘浏览。
  SPREAD  双栏跨页:左目录右内文页(sticky),悬停预览、点击固定,
          词条行内方块 1 击标记,键盘 ↑↓/空格。
  INLINE  行内展开:点词条原位展开三件套+标记按钮,再点收起,零遮挡。
  HOVER   悬停脚注:悬停出非模态脚注气泡读三件套,单击词条直接切换标记。
  REVIEW  复习模式:一屏一词的过卡流,会/不会两键(键盘 1/2/空格/方向键),
          自动前进,可对未掌握词再来一轮。

全部无弹窗。md stays the single source of truth.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

# ---- md parser (self-contained; formerly shared via render_primer.py) ----
ENCOUNTER_PREFIXES = ("遇到:", "遇到：")
COMMAND_PREFIXES = ("下命令:", "下命令：")
PREREQ_PREFIXES = ("前置:", "前置：")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def esc_attr(s: str) -> str:
    return html.escape(s, quote=True)


def split_name(raw: str):
    """'Modal(模态框 / 弹窗)' -> ('Modal', '模态框 / 弹窗')"""
    m = re.match(r"^(.*?)\s*[（(](.+?)[）)]\s*$", raw)
    return (m.group(1).strip(), m.group(2).strip()) if m else (raw.strip(), "")


def parse_table(lines):
    rows = [l.strip() for l in lines if l.strip().startswith("|")]
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    return [r for i, r in enumerate(cells) if i != 1]  # drop the |---| row


def md_inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)


def parse(md_text: str) -> dict:
    lines = md_text.splitlines()
    title, meta, footer = "术语地图", [], ""
    groups, overview = [], None

    # header: first '# ', then consecutive '> '
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("# "):
            title = s[2:].strip()
            i += 1
            break
        i += 1
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("> "):
            meta.append(s[2:].strip())
            i += 1
        elif s == "":
            i += 1
        else:
            break

    # body sections split on '## '
    sections, cur = [], None
    for line in lines[i:]:
        s = line.strip()
        if s.startswith("## "):
            if cur:
                sections.append(cur)
            cur = {"raw_title": s[3:].strip(), "lines": []}
        elif cur is not None:
            cur["lines"].append(line)
    if cur:
        sections.append(cur)

    for sec in sections:
        if "|---" in "\n".join(sec["lines"]):  # overview table block
            intro_src = "\n".join(l for l in sec["lines"]
                                  if not l.strip().startswith("|")
                                  and not l.strip() == "---").strip()
            overview = {"title": sec["raw_title"],
                        "table": parse_table(sec["lines"]),
                        "intro": md_inline(intro_src)}
            continue
        name, tag = split_name(sec["raw_title"])
        words, cur_word = [], None

        def flush():
            nonlocal cur_word
            if cur_word:
                words.append(cur_word)
                cur_word = None

        for line in sec["lines"]:
            s = line.strip()
            if s.startswith("### "):
                flush()
                en, cn = split_name(s[4:].strip())
                cur_word = {"name": en, "cn": cn, "def": [], "enc": "", "cmd": "",
                            "prereq": [], "list": False}
            elif s.startswith("- "):
                flush()
                m = re.match(r"^- \*\*(.+?)\*\*[::：]\s*(.*)$", s)
                if m:  # list-style word: - **Name(中文名)**:desc
                    en, cn = split_name(m.group(1))
                    words.append({"name": en, "cn": cn, "def": [m.group(2)],
                                  "enc": "", "cmd": "", "prereq": [],
                                  "list": True})
                else:
                    en, cn = split_name(s[2:].strip())
                    words.append({"name": en, "cn": cn, "def": [""],
                                  "enc": "", "cmd": "", "prereq": [],
                                  "list": True})
            elif cur_word is not None and s and not s.startswith("---"):
                if any(s.startswith(p) for p in ENCOUNTER_PREFIXES):
                    cur_word["enc"] = re.split("[::：]", s, maxsplit=1)[1].strip()
                elif any(s.startswith(p) for p in COMMAND_PREFIXES):
                    cur_word["cmd"] = re.split("[::：]", s, maxsplit=1)[1].strip()
                elif any(s.startswith(p) for p in PREREQ_PREFIXES):
                    cur_word["prereq"] = [x.strip() for x in
                                          re.split("[,，、]", re.split("[::：]", s, maxsplit=1)[1])
                                          if x.strip()]
                else:
                    cur_word["def"].append(s)
        flush()
        if words:
            groups.append({"name": name, "tag": tag, "words": words})

    for line in reversed(lines):  # footer: last *...* italic line
        s = line.strip()
        if s.startswith("*") and s.endswith("*") and len(s) > 2:
            footer = s.strip("*").strip()
            break

    return {"title": title, "meta": meta, "overview": overview,
            "groups": groups, "footer": footer}
# ---- end md parser ----


def resolve_prereqs(groups) -> None:
    """校验并就地收敛每组词块的 prereq 列表。

    规则(01 号票语法定稿):
    - 引用名 = split_name 主名(括号前部分),精确匹配全文所有 ### 词条主名;
    - 未命中的引用丢弃并 stderr 告警;
    - 重名主名先到先得,告警;
    - 按文档序尝试加边 p→w;若 w 沿已加入边可达 p(成环,典型是引用了
      文档序在后的词),丢弃该条并告警。无环的显式边保留给树/quiz 消费。
    """
    index = {}
    for g in groups:
        for w in g["words"]:
            if w["name"] in index:
                print(f"render_editorial: warning: 词条重名 '{w['name']}',"
                      f"前置引用将命中首个", file=sys.stderr)
            else:
                index[w["name"]] = w
    edges = {}  # p -> [w...],按文档序只收无环边
    for g in groups:
        for w in g["words"]:
            kept = []
            for p in w["prereq"]:
                if p in kept:
                    continue
                if p not in index:
                    print(f"render_editorial: warning: '{w['name']}' 的前置 '{p}'"
                          f" 未命中任何词条,已忽略", file=sys.stderr)
                    continue
                stack, seen = [w["name"]], set()
                reachable = False
                while stack:
                    cur = stack.pop()
                    if cur == p:
                        reachable = True
                        break
                    if cur in seen:
                        continue
                    seen.add(cur)
                    stack.extend(edges.get(cur, ()))
                if reachable:
                    print(f"render_editorial: warning: '{w['name']}' 的前置 '{p}'"
                          f" 与既有前置构成环(文档顺序优先),已忽略",
                          file=sys.stderr)
                    continue
                edges.setdefault(p, []).append(w["name"])
                kept.append(p)
            w["prereq"] = kept


def clean_group_name(name: str) -> str:
    return re.sub(r"^[一二三四五六七八九十]+、", "", name)


def entry_html(w, gi, idx) -> str:
    blob = esc_attr(" ".join([w["name"], w["cn"], " ".join(w["def"]),
                              w["enc"], w["cmd"]]).lower())
    return (f'<button class="entry" data-word="{esc_attr(w["name"])}" '
            f'data-group="{gi}" data-idx="{idx - 1}" data-search="{blob}">'
            f'<span class="mark" title="点击标记/取消"></span>'
            f'<span class="nm">{esc(w["name"])}</span>'
            f'<span class="cn">{esc(w["cn"])}</span>'
            f'<div class="inline-detail"></div></button>')


def chapter_html(g, gi, counter) -> str:
    entries, idx = [], counter
    for w in g["words"]:
        idx += 1
        entries.append(entry_html(w, gi, idx))
    tag = f'<span class="ctag">{esc(g["tag"])}</span>' if g["tag"] else ""
    return (f'<section class="chapter" id="g{gi}">'
            f'<header><h2>{esc(clean_group_name(g["name"]))}</h2>{tag}'
            f'<span class="cprog" data-lane="{gi}">0/{len(g["words"])}</span></header>'
            f'<div class="entries {entries_cls()}">{"".join(entries)}</div></section>'), idx


def entries_cls() -> str:
    return "cols" if LAYOUT == "hover" else ""


CSS_COMMON = """
:root{--paper:#faf9f5;--ink:#141414;--mut:#6f6a60;--red:#d92b2b;--line:#d8d3c8}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;color:var(--ink);background:var(--paper);
font:15px/1.8 Inter,system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
/* 报头:一行。标题 + 搜索 + 进度 + 重置 */
header.mast{border-bottom:2px solid var(--ink);padding:14px 32px;
display:flex;flex-wrap:wrap;gap:10px 20px;align-items:center;max-width:1240px;margin:0 auto}
h1{margin:0;font-family:"Playfair Display","Songti SC","STSong",serif;
font-size:22px;font-weight:900;letter-spacing:.5px;white-space:nowrap}
h1 em{font-style:normal;color:var(--red)}
.tools{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-left:auto}
#q{width:200px;padding:6px 11px;border:1px solid var(--ink);
background:#fff;color:var(--ink);font:inherit;font-size:13px}
#q:focus{outline:2px solid var(--red);outline-offset:-1px}
.prog{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--mut)}
.prog .track{width:90px;height:3px;background:var(--line)}
.prog .fill{height:100%;width:0;background:var(--red);transition:width .4s}
.prog .num{color:var(--ink)}
#reset{background:none;border:1px solid var(--line);color:var(--mut);
font:inherit;font-size:12px;padding:6px 12px;cursor:pointer}
#reset:hover{border-color:var(--ink);color:var(--ink)}
main{max-width:1240px;margin:0 auto;padding:6px 32px 40px}
.chapter{margin:26px 0;scroll-margin-top:16px}
.chapter header{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;
border-bottom:1px solid var(--ink);padding-bottom:7px;margin-bottom:2px}
.chapter h2{margin:0;font-family:"Playfair Display","Songti SC",serif;
font-size:17px;font-weight:700}
.ctag{color:var(--mut);font-size:11.5px}
.cprog{margin-left:auto;color:var(--mut);font-size:11.5px}
.entries{display:flex;flex-direction:column}
.entries.cols{display:grid;grid-template-columns:1fr 1fr;gap:0 36px}
.entry{position:relative;display:block;background:none;border:none;
border-bottom:1px solid var(--line);font:inherit;text-align:left;cursor:pointer;
padding:9px 6px 9px 24px;transition:background .12s}
.entry:hover{background:#f0ede4}
.entry:focus{outline:none}
.entry:focus-visible{outline:2px solid var(--ink);outline-offset:-2px}
.mark{position:absolute;left:4px;top:17px;
width:11px;height:11px;border:1.5px solid #a49e90}
.mark::after{content:"";position:absolute;inset:-9px}
.entry:hover .mark{border-color:var(--ink)}
.nm{display:block;font-family:"Playfair Display","Songti SC","STSong",serif;
font-size:17px;font-weight:700;line-height:1.4}
.cn{display:block;font-size:11px;color:var(--mut);line-height:1.5}
.entry.lit .mark{background:var(--red);border-color:var(--red)}
.entry.lit .nm{color:var(--red)}
.inline-detail{display:none}
body.filtering .entry{opacity:.16}
body.filtering .entry.hit{opacity:1}
.foot{max-width:1240px;margin:0 auto;color:var(--mut);font-size:10.5px;
padding:10px 32px 34px;border-top:2px solid var(--ink)}
body{--serif:"Playfair Display","Songti SC","STSong",serif}
/* 深挖:复制追问提示词按钮(不展示提示词文本本身) */
.copyq{font:inherit;font-size:12px;cursor:pointer;padding:6px 13px;
border:1px solid var(--ink);background:#fff;color:var(--ink);letter-spacing:.5px;
transition:background .15s,color .15s}
.copyq:hover{background:var(--ink);color:#fff}
.copyq.ok{background:#237a3a;border-color:#237a3a;color:#fff}
"""

# ---- shared JS: deep-dive copy button (prepended to every layout's script) ----
JS_COPY = """
const COPY_LABEL = '⧉ 复制追问提示词';
function resetCopy(btn){
  clearTimeout(btn._ct);
  btn.classList.remove('ok');
  btn.textContent = COPY_LABEL;
}
function deepdiveText(name){
  const w = words.find(x => x.name === name);
  const label = (w && w.cn) ? w.name + '(' + w.cn + ')' : name;
  return '深挖「' + label + '」:给我讲透它,再出一个能让我上手的小练习。';
}
function legacyCopy(text){
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
  document.body.appendChild(ta); ta.focus(); ta.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch(e) {}
  ta.remove();
  return ok;
}
function copyPrompt(name, btn){
  const text = deepdiveText(name);
  const done = () => {
    btn.classList.add('ok');
    btn.textContent = '✓ 已复制,去粘给 AI';
    clearTimeout(btn._ct);
    btn._ct = setTimeout(() => resetCopy(btn), 1600);
  };
  if (navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done, () => { if (legacyCopy(text)) done(); });
  } else if (legacyCopy(text)) done();
}
"""

# ============================== SPREAD ==============================
CSS_SPREAD = CSS_COMMON + """
.spread{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:44px;align-items:start}
.entry.selected{background:#f0ede4;box-shadow:inset 3px 0 0 var(--red)}
.page{position:sticky;top:16px;border:1.5px solid var(--ink);background:#fff;
padding:16px 20px 14px}
.page.preview{box-shadow:6px 6px 0 #00000010,0 0 0 1px #d92b2b2e}
.page h3{margin:0;font-family:var(--serif);font-size:25px;font-weight:900;line-height:1.3}
.page .gname{color:var(--mut);font-size:11.5px;margin:2px 0 10px;
padding-bottom:9px;border-bottom:1px solid var(--line)}
.page .pbody p{margin:9px 0;font-size:14px}
.page .enc,.page .cmd{display:flex;gap:9px;align-items:baseline}
.page .enc span,.page .cmd span{flex:none;font-size:10px;font-weight:700;letter-spacing:1px;
color:#fff;background:var(--red);padding:2px 8px}
.page .cmd code{background:#f4f1e8;border:1px solid var(--line);padding:2px 8px;
font-size:12.5px;font-family:ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
.page .prow{margin-top:14px}
#pToggle{width:100%;font:inherit;font-size:14px;cursor:pointer;padding:11px;
border:1.5px solid var(--red);background:#fff;color:var(--red);transition:.15s}
#pToggle:hover,#pToggle.on{background:var(--red);color:#fff}
.pcopy{margin-top:8px}
.pnav{display:flex;gap:8px;align-items:center;margin-top:9px}
.pnav button{font:inherit;font-size:13px;cursor:pointer;padding:5px 14px;
border:none;background:none;color:var(--mut)}
.pnav button:hover{color:var(--ink)}
.pnav button:disabled{opacity:.3;cursor:default}
.pnav .cnt{flex:1;text-align:center;font-size:11px;color:var(--mut);
font-family:ui-monospace,Menlo,monospace}
.keys{margin-top:10px;padding-top:8px;border-top:1px solid var(--line);
color:var(--mut);font-size:10.5px;text-align:center}
.keys b{color:var(--ink);font-weight:500;background:#f0ede4;padding:0 5px;
border:1px solid var(--line);border-radius:3px;font-family:ui-monospace,Menlo,monospace}
@media(max-width:999px){
.spread{display:block}
.page{display:none}
.entry.open{background:#f0ede4}
.entry.open .inline-detail{display:block;border-top:1px dashed var(--line);
margin-top:9px;padding:9px 2px 4px}
.inline-detail p{margin:7px 0;font-size:13.5px}
.inline-detail .drow{display:flex;gap:8px;margin-top:10px}
.inline-detail .drow .dbtn{flex:1;width:auto;margin-top:0}
.inline-detail .enc,.inline-detail .cmd{display:flex;gap:9px;align-items:baseline}
.inline-detail .enc span,.inline-detail .cmd span{flex:none;font-size:10px;font-weight:700;
color:#fff;background:var(--red);padding:2px 8px}
.inline-detail .cmd code{background:#f4f1e8;border:1px solid var(--line);padding:2px 8px;
font-size:12.5px;font-family:ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
.inline-detail .dbtn{margin-top:10px;width:100%;font:inherit;font-size:13px;
cursor:pointer;padding:9px;border:1.5px solid var(--red);background:#fff;color:var(--red)}
.inline-detail .dbtn.on{background:var(--red);color:#fff}
}
@media(max-width:760px){header.mast{padding:12px 18px}h1{font-size:18px}
main{padding:4px 18px 30px}.foot{padding:10px 18px 30px}}
"""

JS_SPREAD = JS_COPY + """
const KEY = 'domain-primer:' + document.title;
let lit = new Set(JSON.parse(localStorage.getItem(KEY) || '[]'));
const entries = [...document.querySelectorAll('.entry')];
const words = JSON.parse(document.getElementById('words').textContent);
const laneTotal = gi => entries.filter(e => e.dataset.group == gi).length;
const mobile = () => matchMedia('(max-width:999px)').matches;
let selected = 0;

function detailHTML(w){
  let b = '';
  if (w.def && w.def.join(' ').trim()) b += '<p>'+w.def.join(' ')+'</p>';
  if (w.enc) b += '<p class="enc"><span>遇到</span>'+w.enc+'</p>';
  if (w.cmd) b += '<p class="cmd"><span>下命令</span><code>'+w.cmd+'</code></p>';
  return b;
}
const page = document.getElementById('page');
function renderPage(i, preview){
  const e = entries[i]; if(!e) return;
  const w = words.find(x => x.name === e.dataset.word);
  const gi = +e.dataset.group;
  page.classList.toggle('preview', !!preview);
  page.querySelector('h3').textContent = w.name;
  page.querySelector('.gname').textContent =
    document.querySelectorAll('.chapter h2')[gi].textContent;
  page.querySelector('.pbody').innerHTML = detailHTML(w);
  syncPageToggle();
  resetCopy(document.getElementById('pCopy'));
  page.querySelector('.cnt').textContent = (i+1) + '/' + entries.length;
  document.getElementById('pPrev').disabled = i === 0;
  document.getElementById('pNext').disabled = i === entries.length - 1;
}
function syncPageToggle(){
  const e = entries[selected];
  const t = document.getElementById('pToggle');
  const on = lit.has(e.dataset.word);
  t.textContent = on ? '■ 已掌握 — 点击取消' : '■ 标记已掌握';
  t.classList.toggle('on', on);
}
let hoverTimer = null;
entries.forEach((e, i) => {
  e.addEventListener('mouseenter', () => {
    if (mobile()) return;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => renderPage(i, true), 180);
  });
  e.addEventListener('mouseleave', () => {
    clearTimeout(hoverTimer);
    if (!mobile()) renderPage(selected, false);
  });
});
function toggleMark(name){ lit.has(name) ? lit.delete(name) : lit.add(name); apply(); }
function apply(){
  entries.forEach(e => e.classList.toggle('lit', lit.has(e.dataset.word)));
  document.querySelectorAll('.cprog').forEach(p => {
    const gi = p.dataset.lane;
    const c = entries.filter(e => e.dataset.group == gi && lit.has(e.dataset.word)).length;
    p.textContent = c + '/' + laneTotal(gi);
  });
  const n = lit.size, all = entries.length;
  document.getElementById('fill').style.width = (all ? n*100/all : 0) + '%';
  document.getElementById('pc').textContent = n + ' / ' + all + ' 已标记';
  syncPageToggle();
  const open = document.querySelector('.entry.open');
  if (open){
    const btn = open.querySelector('.dbtn');
    const on = lit.has(open.dataset.word);
    btn.textContent = on ? '■ 已掌握 — 点击取消' : '■ 标记已掌握';
    btn.classList.toggle('on', on);
  }
  localStorage.setItem(KEY, JSON.stringify([...lit]));
}
function select(i, scroll){
  selected = Math.max(0, Math.min(entries.length - 1, i));
  entries.forEach(e => e.classList.remove('selected'));
  entries[selected].classList.add('selected');
  renderPage(selected, false);
  if (scroll) entries[selected].scrollIntoView({block:'nearest', behavior:'smooth'});
}
entries.forEach((e, i) => {
  e.addEventListener('click', ev => {
    if (ev.target.closest('.mark')){ toggleMark(e.dataset.word); return; }
    if (mobile()){ select(i, false); toggleOpen(e); return; }
    select(i, false);
  });
});
function toggleOpen(e){
  const wasOpen = e.classList.contains('open');
  document.querySelectorAll('.entry.open').forEach(x => {
    x.classList.remove('open'); x.querySelector('.inline-detail').innerHTML = '';
  });
  if (wasOpen) return;
  const w = words.find(x => x.name === e.dataset.word);
  const det = e.querySelector('.inline-detail');
  const on = lit.has(e.dataset.word);
  det.innerHTML = detailHTML(w) +
    '<div class="drow"><button class="dbtn'+(on?' on':'')+'">'+
    (on?'■ 已掌握 — 点击取消':'■ 标记已掌握')+'</button>'+
    '<button class="copyq">'+COPY_LABEL+'</button></div>';
  det.querySelector('.dbtn').addEventListener('click', () => toggleMark(e.dataset.word));
  det.querySelector('.copyq').addEventListener('click', ev2 => {
    ev2.stopPropagation();
    copyPrompt(e.dataset.word, ev2.currentTarget);
  });
  e.classList.add('open');
}
document.getElementById('pToggle').onclick = () => toggleMark(entries[selected].dataset.word);
document.getElementById('pCopy').onclick = ev =>
  copyPrompt(entries[selected].dataset.word, ev.currentTarget);
document.getElementById('pPrev').onclick = () => select(selected - 1, true);
document.getElementById('pNext').onclick = () => select(selected + 1, true);
document.addEventListener('keydown', ev => {
  if (document.activeElement === document.getElementById('q')) return;
  if (ev.key === 'ArrowDown' || ev.key === 'j'){ ev.preventDefault(); select(selected + 1, true); }
  else if (ev.key === 'ArrowUp' || ev.key === 'k'){ ev.preventDefault(); select(selected - 1, true); }
  else if (ev.key === ' '){ ev.preventDefault(); toggleMark(entries[selected].dataset.word); }
});
document.getElementById('reset').onclick = () => {
  if (confirm('清空全部标记?')){ lit.clear(); apply(); }
};
const q = document.getElementById('q');
q.addEventListener('input', () => {
  const v = q.value.trim().toLowerCase();
  document.body.classList.toggle('filtering', !!v);
  entries.forEach(e => e.classList.toggle('hit', !!v && e.dataset.search.includes(v)));
});
apply(); select(0, false);
"""

# ============================== INLINE ==============================
CSS_INLINE = CSS_COMMON + """
.entry.open{background:#f0ede4}
.entry.open .inline-detail{display:block;border-top:1px dashed var(--line);
margin-top:10px;padding:12px 2px 6px}
.inline-detail p{margin:8px 0;font-size:14px}
.inline-detail .enc,.inline-detail .cmd{display:flex;gap:9px;align-items:baseline}
.inline-detail .enc span,.inline-detail .cmd span{flex:none;font-size:10px;font-weight:700;
color:#fff;background:var(--red);padding:2px 8px}
.inline-detail .cmd code{background:#f4f1e8;border:1px solid var(--line);padding:3px 9px;
font-size:12.5px;font-family:ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
.inline-detail .drow{display:flex;gap:10px;margin-top:12px}
.inline-detail .dbtn{flex:1;font:inherit;font-size:13.5px;cursor:pointer;padding:10px;
border:1.5px solid var(--red);background:#fff;color:var(--red)}
.inline-detail .dbtn:hover,.inline-detail .dbtn.on{background:var(--red);color:#fff}
.inline-detail .dshut{flex:none;font:inherit;font-size:12.5px;cursor:pointer;padding:10px 16px;
border:1px solid var(--ink);background:#fff;color:var(--mut)}
.hint{color:var(--mut);font-size:12px;margin:4px 2px 14px}
@media(max-width:760px){header.mast{padding:20px 18px 14px}h1{font-size:30px}
main{padding:10px 18px 40px}.foot{padding:10px 18px 40px}}
"""

JS_INLINE = JS_COPY + """
const KEY = 'domain-primer:' + document.title;
let lit = new Set(JSON.parse(localStorage.getItem(KEY) || '[]'));
const entries = [...document.querySelectorAll('.entry')];
const words = JSON.parse(document.getElementById('words').textContent);
const laneTotal = gi => entries.filter(e => e.dataset.group == gi).length;
function detailHTML(w){
  let b = '';
  if (w.def && w.def.join(' ').trim()) b += '<p>'+w.def.join(' ')+'</p>';
  if (w.enc) b += '<p class="enc"><span>遇到</span>'+w.enc+'</p>';
  if (w.cmd) b += '<p class="cmd"><span>下命令</span><code>'+w.cmd+'</code></p>';
  return b;
}
function toggleMark(name){ lit.has(name) ? lit.delete(name) : lit.add(name); apply(); }
function apply(){
  entries.forEach(e => e.classList.toggle('lit', lit.has(e.dataset.word)));
  document.querySelectorAll('.cprog').forEach(p => {
    const gi = p.dataset.lane;
    const c = entries.filter(e => e.dataset.group == gi && lit.has(e.dataset.word)).length;
    p.textContent = c + '/' + laneTotal(gi);
  });
  const n = lit.size, all = entries.length;
  document.getElementById('fill').style.width = (all ? n*100/all : 0) + '%';
  document.getElementById('pc').textContent = n + ' / ' + all + ' 已标记';
  const open = document.querySelector('.entry.open');
  if (open){
    const btn = open.querySelector('.dbtn');
    const on = lit.has(open.dataset.word);
    btn.textContent = on ? '■ 已掌握 — 点击取消' : '■ 标记已掌握';
    btn.classList.toggle('on', on);
  }
  localStorage.setItem(KEY, JSON.stringify([...lit]));
}
entries.forEach(e => {
  e.addEventListener('click', ev => {
    if (ev.target.closest('.dbtn')){ toggleMark(e.dataset.word); return; }
    if (ev.target.closest('.dshut') || e.classList.contains('open')){
      e.classList.remove('open'); e.querySelector('.inline-detail').innerHTML = '';
      if (ev.target.closest('.dshut')) return;
      return;
    }
    document.querySelectorAll('.entry.open').forEach(x => {
      x.classList.remove('open'); x.querySelector('.inline-detail').innerHTML = '';
    });
    const w = words.find(x => x.name === e.dataset.word);
    const on = lit.has(e.dataset.word);
    const det = e.querySelector('.inline-detail');
    det.innerHTML = detailHTML(w) +
      '<div class="drow"><button class="dbtn'+(on?' on':'')+'">'+
      (on?'■ 已掌握 — 点击取消':'■ 标记已掌握')+'</button>'+
      '<button class="copyq">'+COPY_LABEL+'</button>'+
      '<button class="dshut">收起</button></div>';
    det.querySelector('.dbtn').addEventListener('click', ev2 => {
      ev2.stopPropagation(); toggleMark(e.dataset.word);
    });
    det.querySelector('.copyq').addEventListener('click', ev2 => {
      ev2.stopPropagation(); copyPrompt(e.dataset.word, ev2.currentTarget);
    });
    det.querySelector('.dshut').addEventListener('click', ev2 => {
      ev2.stopPropagation();
      e.classList.remove('open'); det.innerHTML = '';
    });
    e.classList.add('open');
  });
});
document.getElementById('reset').onclick = () => {
  if (confirm('清空全部标记?')){ lit.clear(); apply(); }
};
const q = document.getElementById('q');
q.addEventListener('input', () => {
  const v = q.value.trim().toLowerCase();
  document.body.classList.toggle('filtering', !!v);
  entries.forEach(e => e.classList.toggle('hit', !!v && e.dataset.search.includes(v)));
});
apply();
"""

# ============================== HOVER ==============================
CSS_HOVER = CSS_COMMON + """
#fn{position:absolute;z-index:40;width:320px;pointer-events:none;display:none;
background:#fff;border:1.5px solid var(--ink);box-shadow:6px 6px 0 #00000018;
padding:14px 17px 12px;font-size:13px;line-height:1.7}
#fn .fk{font-size:9.5px;letter-spacing:2px;color:var(--red);text-transform:uppercase;
display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:5px}
#fn h4{margin:8px 0 1px;font-family:var(--serif);font-size:21px;font-weight:900}
#fn .fc{color:var(--mut);font-size:11px;margin-bottom:6px}
#fn p{margin:6px 0}
#fn .enc,#fn .cmd{display:flex;gap:8px;align-items:baseline}
#fn .enc span,#fn .cmd span{flex:none;font-size:9.5px;font-weight:700;letter-spacing:1px;
color:#fff;background:var(--red);padding:1px 7px}
#fn .cmd code{background:#f4f1e8;border:1px solid var(--line);padding:2px 8px;
font-size:12px;font-family:ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
#fn .copyq{display:block;margin-top:10px;pointer-events:auto}
.hint{color:var(--mut);font-size:12px;margin:4px 2px 14px}
.hint b{color:var(--ink);font-weight:500}
@media(max-width:999px){.entries.cols{grid-template-columns:1fr}#fn{display:none!important}}
@media(max-width:760px){header.mast{padding:20px 18px 14px}h1{font-size:30px}
main{padding:10px 18px 40px}.foot{padding:10px 18px 40px}}
"""

JS_HOVER = JS_COPY + """
const KEY = 'domain-primer:' + document.title;
let lit = new Set(JSON.parse(localStorage.getItem(KEY) || '[]'));
const entries = [...document.querySelectorAll('.entry')];
const words = JSON.parse(document.getElementById('words').textContent);
const laneTotal = gi => entries.filter(e => e.dataset.group == gi).length;
const fn = document.getElementById('fn');
let hideTimer = null;
fn.addEventListener('mouseenter', () => clearTimeout(hideTimer));
fn.addEventListener('mouseleave', () => {
  hideTimer = setTimeout(() => fn.style.display = 'none', 120);
});
document.getElementById('fnCopy').onclick = ev => {
  ev.stopPropagation();
  copyPrompt(ev.currentTarget.dataset.word, ev.currentTarget);
};
function showFn(e){
  const w = words.find(x => x.name === e.dataset.word);
  const gi = +e.dataset.group;
  fn.querySelector('.fk').innerHTML = '<span>No.'+(+e.dataset.idx+1)+'</span><span>'+
    document.querySelectorAll('.chapter h2')[gi].textContent+'</span>';
  fn.querySelector('h4').textContent = w.name;
  fn.querySelector('.fc').textContent = w.cn;
  let b = '';
  if (w.def && w.def.join(' ').trim()) b += '<p>'+w.def.join(' ')+'</p>';
  if (w.enc) b += '<p class="enc"><span>遇到</span>'+w.enc+'</p>';
  if (w.cmd) b += '<p class="cmd"><span>下命令</span><code>'+w.cmd+'</code></p>';
  fn.querySelector('.fb').innerHTML = b;
  const fnCopy = document.getElementById('fnCopy');
  fnCopy.dataset.word = w.name;
  resetCopy(fnCopy);
  const r = e.getBoundingClientRect();
  fn.style.display = 'block';
  const fh = fn.offsetHeight, fw = fn.offsetWidth;
  let x = Math.min(Math.max(10, r.left + window.scrollX), window.scrollX + innerWidth - fw - 14);
  let y = r.top + window.scrollY - fh - 10;
  if (r.top - fh - 10 < 60) y = r.bottom + window.scrollY + 10;
  fn.style.left = x + 'px'; fn.style.top = y + 'px';
}
entries.forEach(e => {
  e.addEventListener('mouseenter', () => { clearTimeout(hideTimer); showFn(e); });
  e.addEventListener('mouseleave', () => { hideTimer = setTimeout(() => fn.style.display = 'none', 120); });
});
function apply(){
  entries.forEach(e => e.classList.toggle('lit', lit.has(e.dataset.word)));
  document.querySelectorAll('.cprog').forEach(p => {
    const gi = p.dataset.lane;
    const c = entries.filter(e => e.dataset.group == gi && lit.has(e.dataset.word)).length;
    p.textContent = c + '/' + laneTotal(gi);
  });
  const n = lit.size, all = entries.length;
  document.getElementById('fill').style.width = (all ? n*100/all : 0) + '%';
  document.getElementById('pc').textContent = n + ' / ' + all + ' 已标记';
  localStorage.setItem(KEY, JSON.stringify([...lit]));
}
entries.forEach(e => e.addEventListener('click', () => {
  lit.has(e.dataset.word) ? lit.delete(e.dataset.word) : lit.add(e.dataset.word);
  apply();
}));
document.getElementById('reset').onclick = () => {
  if (confirm('清空全部标记?')){ lit.clear(); apply(); }
};
const q = document.getElementById('q');
q.addEventListener('input', () => {
  const v = q.value.trim().toLowerCase();
  document.body.classList.toggle('filtering', !!v);
  entries.forEach(e => e.classList.toggle('hit', !!v && e.dataset.search.includes(v)));
});
apply();
"""

# ============================== REVIEW ==============================
CSS_REVIEW = CSS_COMMON + """
.modebar{display:flex;gap:8px;justify-content:center;margin:26px 0 0}
.modebar button{font:inherit;font-size:13px;cursor:pointer;padding:9px 22px;
border:1.5px solid var(--ink);background:#fff;color:var(--ink);letter-spacing:1px}
.modebar button.on{background:var(--ink);color:#fff}
.rwrap{display:none;max-width:760px;margin:0 auto}
body.reviewing .rwrap{display:block}
body.reviewing .browse{display:none}
.rhead{display:flex;align-items:center;gap:14px;margin:20px 0 26px}
.rhead .rcount{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--mut);
min-width:110px}
.rhead .track{flex:1;height:4px;background:var(--line)}
.rhead .fill{height:100%;width:0;background:var(--red);transition:width .25s}
.rcard{border:2px solid var(--ink);background:#fff;box-shadow:12px 12px 0 #00000012;
padding:44px 52px 34px;text-align:center;min-height:420px;display:flex;
flex-direction:column;justify-content:center}
.rcard .kicker{font-size:10px;letter-spacing:3px;color:var(--red);text-transform:uppercase}
.rcard h2{margin:16px 0 2px;font-family:var(--serif);font-size:52px;font-weight:900;line-height:1.2}
.rcard .rcn{color:var(--mut);font-size:15px;margin-bottom:20px}
.rcard .rbody{max-width:520px;margin:0 auto;text-align:left;font-size:15.5px}
.rcard .rbody p{margin:10px 0}
.rcard .enc,.rcard .cmd{display:flex;gap:9px;align-items:baseline}
.rcard .enc span,.rcard .cmd span{flex:none;font-size:10px;font-weight:700;letter-spacing:1px;
color:#fff;background:var(--red);padding:2px 8px}
.rcard .cmd code{background:#f4f1e8;border:1px solid var(--line);padding:3px 9px;
font-size:13px;font-family:ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
.rbtns{display:flex;gap:14px;margin-top:34px}
.rcopy{margin-top:14px;text-align:center}
.rbtns button{flex:1;font:inherit;font-size:17px;cursor:pointer;padding:16px;transition:.12s}
#rNo{border:1.5px solid var(--ink);background:#fff;color:var(--ink)}
#rNo:hover{background:var(--ink);color:#fff}
#rYes{border:1.5px solid var(--red);background:#fff;color:var(--red)}
#rYes:hover,#rYes.on{background:var(--red);color:#fff}
.rkeys{margin-top:16px;color:var(--mut);font-size:11.5px;text-align:center}
.rkeys b{color:var(--ink);font-weight:500;background:#f0ede4;padding:0 5px;
border:1px solid var(--line);border-radius:3px;font-family:ui-monospace,Menlo,monospace}
.rdone{text-align:center}
.rdone h2{font-family:var(--serif);font-size:34px;margin:10px 0 6px}
.rdone p{color:var(--mut);margin:4px 0 24px}
.rdone .rd2{display:flex;gap:12px;justify-content:center}
.rdone button{font:inherit;font-size:14px;cursor:pointer;padding:12px 24px;
border:1.5px solid var(--red);background:#fff;color:var(--red)}
.rdone button:hover{background:var(--red);color:#fff}
.rdone button.plain{border-color:var(--ink);color:var(--ink)}
@media(max-width:760px){header.mast{padding:20px 18px 14px}h1{font-size:30px}
.rcard{padding:28px 22px 24px;min-height:340px}.rcard h2{font-size:34px}
main{padding:10px 18px 40px}.foot{padding:10px 18px 40px}}
"""

JS_REVIEW = JS_COPY + """
const KEY = 'domain-primer:' + document.title;
let lit = new Set(JSON.parse(localStorage.getItem(KEY) || '[]'));
const entries = [...document.querySelectorAll('.entry')];
const words = JSON.parse(document.getElementById('words').textContent);
const laneTotal = gi => entries.filter(e => e.dataset.group == gi).length;
let queue = [], qi = 0, answered = 0;

function detailHTML(w){
  let b = '';
  if (w.def && w.def.join(' ').trim()) b += '<p>'+w.def.join(' ')+'</p>';
  if (w.enc) b += '<p class="enc"><span>遇到</span>'+w.enc+'</p>';
  if (w.cmd) b += '<p class="cmd"><span>下命令</span><code>'+w.cmd+'</code></p>';
  return b;
}
function applyBrowse(){
  entries.forEach(e => e.classList.toggle('lit', lit.has(e.dataset.word)));
  document.querySelectorAll('.cprog').forEach(p => {
    const gi = p.dataset.lane;
    const c = entries.filter(e => e.dataset.group == gi && lit.has(e.dataset.word)).length;
    p.textContent = c + '/' + laneTotal(gi);
  });
  const n = lit.size, all = entries.length;
  document.getElementById('fill').style.width = (all ? n*100/all : 0) + '%';
  document.getElementById('pc').textContent = n + ' / ' + all + ' 已标记';
  localStorage.setItem(KEY, JSON.stringify([...lit]));
}
function startReview(onlyUnknown){
  queue = entries.filter(e => !onlyUnknown || !lit.has(e.dataset.word))
                 .map(e => e.dataset.word);
  if (!queue.length){ alert('全部词都已标记,没有要复习的了。'); return; }
  qi = 0; answered = 0;
  document.body.classList.add('reviewing');
  showCard();
}
function showCard(){
  const name = queue[qi];
  const e = entries.find(x => x.dataset.word === name);
  const w = words.find(x => x.name === name);
  const gi = +e.dataset.group;
  const c = document.querySelector('.rcard');
  c.style.display = '';
  document.querySelector('.rdone').style.display = 'none';
  c.querySelector('.kicker').textContent = 'No.' + (+e.dataset.idx + 1) + ' · ' +
    document.querySelectorAll('.chapter h2')[gi].textContent;
  c.querySelector('h2').textContent = w.name;
  c.querySelector('.rcn').textContent = w.cn;
  c.querySelector('.rbody').innerHTML = detailHTML(w);
  resetCopy(document.getElementById('rCopy'));
  document.querySelector('.rcount').textContent = '复习 ' + (qi+1) + ' / ' + queue.length;
  document.querySelector('.rhead .fill').style.width = (qi*100/queue.length) + '%';
}
function answer(known){
  const name = queue[qi];
  if (known && !lit.has(name)){ lit.add(name); applyBrowse(); }
  qi++; answered++;
  if (qi >= queue.length) finish();
  else showCard();
}
function finish(){
  document.querySelector('.rcard').style.display = 'none';
  const d = document.querySelector('.rdone');
  d.style.display = '';
  const unknown = entries.filter(e => !lit.has(e.dataset.word)).length;
  d.querySelector('h2').textContent = '这一轮过完了';
  d.querySelector('p').textContent =
    '本轮 ' + queue.length + ' 词 · 总进度 ' + lit.size + '/' + entries.length +
    (unknown ? ' · 还有 ' + unknown + ' 个词没标记' : ' · 全部标记完成');
  d.querySelector('.again').style.display = unknown ? '' : 'none';
}
function exitReview(){ document.body.classList.remove('reviewing'); }
document.getElementById('rYes').onclick = () => answer(true);
document.getElementById('rNo').onclick = () => answer(false);
document.getElementById('rCopy').onclick = ev =>
  copyPrompt(queue[qi], ev.currentTarget);
document.getElementById('startR').onclick = () => startReview(false);
document.getElementById('startU').onclick = () => startReview(true);
document.getElementById('backBrowse').onclick = exitReview;
document.getElementById('againU').onclick = () => startReview(true);
document.addEventListener('keydown', ev => {
  if (document.activeElement === document.getElementById('q')) return;
  if (!document.body.classList.contains('reviewing')){
    if (ev.key === 'r'){ startReview(false); }
    return;
  }
  if (ev.key === '1' || ev.key === 'ArrowLeft') answer(false);
  else if (ev.key === '2' || ev.key === ' ' || ev.key === 'ArrowRight'){ ev.preventDefault(); answer(true); }
  else if (ev.key === 'Escape') exitReview();
});
document.getElementById('reset').onclick = () => {
  if (confirm('清空全部标记?')){ lit.clear(); applyBrowse(); }
};
const q = document.getElementById('q');
q.addEventListener('input', () => {
  const v = q.value.trim().toLowerCase();
  document.body.classList.toggle('filtering', !!v);
  entries.forEach(e => e.classList.toggle('hit', !!v && e.dataset.search.includes(v)));
});
applyBrowse();
"""

# ============================== TREE (默认) ==============================
# 树状渐进关系图:前置边涉及的词按拓扑层铺开(层内 频率→组序→词序),SVG 贝塞尔
# 连线带箭头(方向=学习方向);级联钻取:↑↓ 当前层兄弟(虚线框)内切换,→ 进子节点
# (红框预览下一步),← 退一层,已走路径墨框保留,历史层兄弟范围累积保留(整体感知);
# 独立词(无边)进底部按族折叠带,四向自由网格移动。空格标记,C 复制追问,Esc 回全图。
GROUP_COLORS = ["#d92b2b", "#b8641b", "#8a7d00", "#2e7d32", "#00796b",
                "#1565c0", "#6a1b9a", "#8e24aa", "#5d4037", "#455a64"]
FREQ_RANK = {"高频": 0, "中频": 1, "低频": 2}


def tree_data(data):
    """词表 + 前置边 + 拓扑层。layer = 最长前置链深度;缺省全序 = (频率,组序,词序)。"""
    words = []
    for gi, g in enumerate(data["groups"]):
        m = re.match(r"^(高频|中频|低频)", g["tag"] or "")
        freq = FREQ_RANK.get(m.group(1), 3) if m else 3
        for wi, w in enumerate(g["words"]):
            blob = " ".join([w["name"], w["cn"], " ".join(w["def"]),
                             w["enc"], w["cmd"]]).lower()
            words.append({"name": w["name"], "cn": w["cn"], "def": w["def"],
                          "enc": w["enc"], "cmd": w["cmd"],
                          "prereq": list(w["prereq"]),
                          "group": clean_group_name(g["name"]), "tag": g["tag"],
                          "freq": freq, "gi": gi, "wi": wi, "search": blob,
                          "list": w["list"]})
    index = {w["name"]: w for w in words}
    edges = [{"from": p, "to": w["name"]}
             for w in words for p in w["prereq"] if p in index]
    memo = {}

    def depth(name):
        if name in memo:
            return memo[name]
        ps = [p for p in index[name]["prereq"] if p in index]
        memo[name] = 0 if not ps else max(depth(p) for p in ps) + 1
        return memo[name]

    for w in words:
        w["layer"] = depth(w["name"])
    used = {e["from"] for e in edges} | {e["to"] for e in edges}
    stats = {"n_words": len(words), "n_edges": len(edges),
             "n_layers": max((w["layer"] for w in words), default=0) + 1,
             "n_free": sum(1 for w in words if w["name"] not in used)}
    return words, edges, stats


def tree_order(w):
    return (w["freq"], w["gi"], w["wi"])


def tree_node_html(w):
    gc = GROUP_COLORS[w["gi"] % len(GROUP_COLORS)]
    pq = ""
    if w["prereq"]:
        pq = ('<span class="pq">前置 <b>'
              + "</b>, <b>".join(esc(p) for p in w["prereq"]) + "</b></span>")
    cn = f'<span class="cn">{esc(w["cn"])}</span>' if w["cn"] else ""
    return (f'<div class="node" data-word="{esc_attr(w["name"])}" '
            f'data-search="{esc_attr(w["search"])}" style="--gc:{gc}">'
            f'<span class="markbox" title="标记已掌握"></span>'
            f'<span class="nm">{esc(w["name"])}</span>{cn}{pq}</div>')


def build_tree(data):
    """生成 tree layout 的 body / words JSON / hint。"""
    words, edges, stats = tree_data(data)
    used = {e["from"] for e in edges} | {e["to"] for e in edges}
    gwords = [w for w in words if w["name"] in used]
    maxL = max((w["layer"] for w in gwords), default=0)
    cols = []
    for l in range(maxL + 1):
        ws = sorted((w for w in gwords if w["layer"] == l), key=tree_order)
        if not ws:
            continue
        cols.append(f'<div class="layercol"><div class="layertag">第 {l} 层 · '
                    f'{len(ws)} 词</div>'
                    + "".join(tree_node_html(w) for w in ws) + "</div>")
    rest = [w for w in words if w["name"] not in used]
    if rest:
        blocks = [w for w in rest if not w["list"]]
        nb = sum(1 for w in words if not w["list"])
        pct = len(blocks) * 100 // nb if nb else 0
        msg = (f"render_editorial: 树图独立词 {len(rest)}/{len(words)}"
               f"(### 词块 {len(blocks)}/{nb} = {pct}%)")
        if blocks:
            msg += ": " + ", ".join(w["name"] for w in blocks)
        print(msg, file=sys.stderr)
        if nb and len(blocks) * 3 > nb:
            print("render_editorial: warning: ### 词块独立占比超过 1/3,树状图"
                  "渐进感弱——尽量给词挂真实上游锚点(平行词之间不造假边;"
                  "列表式低频词留在独立带属正常)", file=sys.stderr)
    bands = []
    for gi in sorted({w["gi"] for w in rest}):
        ws = sorted((w for w in rest if w["gi"] == gi), key=tree_order)
        bands.append(f'<div class="danggroup"><h4>{esc(ws[0]["group"])} · '
                     f'{len(ws)}</h4><div class="danggrid">'
                     + "".join(tree_node_html(w) for w in ws) + "</div></div>")
    hint = (f'{stats["n_words"]} 词 · {stats["n_edges"]} 条前置边 · '
            f'{stats["n_layers"]} 层 · 独立词 {stats["n_free"]} — '
            f'键盘 ↑↓←→ 钻取 · 空格 标记 · C 复制追问 · Q Quiz 自测 · '
            f'Esc 回全图 · 点词看详情')
    body = (f'<div class="layerswrap"><div class="layers">{"".join(cols)}</div>'
            f'<svg class="edges"></svg></div>'
            f'<div class="dangband open">'
            f'<div class="danghead"><span class="chev">▸</span>'
            f'独立词 {stats["n_free"]} 个 · 不在前置链上 · 点词看详情,再点此处收起'
            f'</div><div class="dangbody">{"".join(bands)}</div></div>')
    payload = {"words": [{k: w[k] for k in ("name", "cn", "def", "enc", "cmd",
                                            "prereq", "group", "tag", "freq",
                                            "gi", "wi", "layer")}
                         for w in words],
               "edges": edges}
    return body, json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"), hint


CSS_TREE = CSS_COMMON + """
main{padding:6px 372px 40px 32px;max-width:1400px}
header.mast{max-width:1400px;padding-right:372px}
.hint{max-width:996px;color:var(--mut);font-size:12px;margin:4px 32px 14px;
font-family:ui-monospace,Menlo,monospace}
.node{position:relative;background:#fff;border:1px solid var(--ink);cursor:pointer;
padding:7px 10px 7px 14px;z-index:1;overflow:hidden;
transition:background .12s,opacity .15s,transform .16s,box-shadow .16s}
.node::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
background:var(--gc,#999)}
.node:hover{background:#f0ede4}
.node.sel{outline:3px solid var(--ink);outline-offset:2px;z-index:5;
box-shadow:0 10px 26px #00000030;transform:scale(1.045);background:#fff}
.node .nm{font-family:var(--serif);font-weight:700;font-size:14px;line-height:1.35;
display:block}
.node .cn{font-size:10.5px;color:var(--mut);line-height:1.4;display:block}
.node .markbox{position:absolute;right:5px;top:6px;width:10px;height:10px;
border:1.5px solid #a49e90;background:#fff}
.node.lit .markbox{background:var(--red);border-color:var(--red)}
.node.lit .nm{color:var(--red)}
.node .pq{display:block;font-size:9.5px;color:var(--mut);margin-top:2px;
overflow-wrap:anywhere}
.node .pq b{color:var(--red);font-weight:600}
.node.dim{opacity:.15}
.node.up{box-shadow:inset 0 0 0 2px var(--ink)}
.node.down{box-shadow:inset 0 0 0 2px var(--red);background:#fff5f5}
.node.down .nm{color:var(--red)}
.node.sib{background:#f2eee3;outline:1.5px dashed #b8ae9a;outline-offset:-3.5px}
.node.sibh{background:#f6f2e8;outline:1px dotted #c9bfa9;outline-offset:-3px}
.layerswrap{position:relative}
.layers{display:flex;gap:44px;align-items:flex-start;position:relative;z-index:1}
.layercol{display:flex;flex-direction:column;gap:12px;width:164px;flex:none}
.layertag{font-size:10px;letter-spacing:2px;color:var(--red);font-weight:700;
border-bottom:1px solid var(--ink);padding-bottom:3px}
svg.edges{position:absolute;inset:0;z-index:0;pointer-events:none;overflow:visible}
svg.edges path{fill:none;stroke:var(--red);stroke-width:1.4;opacity:.14;
transition:opacity .15s}
svg.edges path.warm{opacity:.45}
svg.edges path.hot{stroke-width:2.2;opacity:1}
svg.edges marker path{fill:var(--red);stroke:none;opacity:1}
.dangband{margin-top:34px;border-top:2px solid var(--ink)}
.danghead{padding:10px 2px;cursor:pointer;font-size:12.5px;color:var(--mut);
display:flex;gap:8px;align-items:center;user-select:none}
.danghead:hover{color:var(--ink)}
.danghead .chev{display:inline-block;transition:transform .15s;font-size:11px}
.dangband.open .chev{transform:rotate(90deg)}
.dangbody{display:none;padding:4px 0 22px}
.dangband.open .dangbody{display:block}
.danggroup{margin:14px 0 4px}
.danggroup h4{margin:0 0 8px;font-size:11px;letter-spacing:1px;color:var(--mut);
font-weight:600;border-bottom:1px solid var(--line);padding-bottom:4px}
.danggrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));
gap:8px}
.danggrid .node{padding:6px 8px 6px 12px}
.danggrid .node .nm{font-size:13.5px}
#detail{position:fixed;right:0;top:0;bottom:0;width:320px;background:#fff;
border-left:2px solid var(--ink);box-shadow:-8px 0 24px #00000014;padding:22px 24px;
overflow-y:auto;z-index:50}
#detail h3{margin:0;font-family:var(--serif);font-size:24px;font-weight:900;
line-height:1.3}
#detail .dmeta{font-size:11px;color:var(--mut);margin:3px 0 12px;
padding-bottom:10px;border-bottom:1px solid var(--line)}
#detail p{margin:9px 0;font-size:13.5px}
#detail .enc,#detail .cmd{display:flex;gap:8px;align-items:baseline}
#detail .enc span,#detail .cmd span{flex:none;font-size:9.5px;font-weight:700;
letter-spacing:1px;color:#fff;background:var(--red);padding:1px 7px}
#detail .cmd code{background:#f4f1e8;border:1px solid var(--line);padding:2px 8px;
font-size:12px;font-family:ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
#detail .prow{margin-top:16px;display:flex;flex-direction:column;gap:8px}
#detail .prow button{font:inherit;font-size:13px;cursor:pointer;padding:9px;
border:1.5px solid var(--red);background:#fff;color:var(--red)}
#detail .prow button.on{background:var(--red);color:#fff}
#detail .copyq{font:inherit;font-size:12px;cursor:pointer;padding:8px 13px;
border:1px solid var(--ink);background:#fff;color:var(--ink)}
#detail .copyq.ok{background:#237a3a;border-color:#237a3a;color:#fff}
#detail .dkeys{margin-top:18px;padding-top:10px;border-top:1px solid var(--line);
color:var(--mut);font-size:10.5px;text-align:center}
#detail .dkeys b{color:var(--ink);font-weight:500;background:#f0ede4;padding:0 5px;
border:1px solid var(--line);border-radius:3px;font-family:ui-monospace,Menlo,monospace}
body.filtering .node{opacity:.15}
body.filtering .node.hit{opacity:1}
@media(max-width:999px){.layers{gap:24px;flex-wrap:wrap}}
@media(max-width:760px){header.mast{padding:12px 18px}h1{font-size:18px}
.hint{margin:4px 18px 12px}
main{padding:4px 18px 30px}
#detail{width:100%;border-left:none;padding:18px}}
"""

JS_TREE = JS_COPY + r"""
const DATA = JSON.parse(document.getElementById('words').textContent);
const words = DATA.words, edges = DATA.edges;
const index = Object.fromEntries(words.map(w => [w.name, w]));
const byDefault = (a,b) => (a.freq-b.freq)||(a.gi-b.gi)||(a.wi-b.wi);
const KEY = 'domain-primer:' + document.title;
let lit = new Set(JSON.parse(localStorage.getItem(KEY) || '[]'));

/* ---------- 邻接表 ---------- */
const downAdj = {}, upAdj = {};
for (const e of edges){
  (downAdj[e.from] = downAdj[e.from] || []).push(e.to);
  (upAdj[e.to] = upAdj[e.to] || []).push(e.from);
}
function isFree(name){
  return !((downAdj[name] || []).length || (upAdj[name] || []).length);
}

/* ---------- SVG 连线(箭头 = 前置 → 该词) ---------- */
function drawEdges(){
  const svg = document.querySelector('.layerswrap svg.edges');
  const scope = document.querySelector('.layerswrap');
  if (!svg || !scope) return;
  const sr = scope.getBoundingClientRect();
  svg.setAttribute('width', scope.scrollWidth);
  svg.setAttribute('height', scope.scrollHeight);
  svg.setAttribute('viewBox', `0 0 ${scope.scrollWidth} ${scope.scrollHeight}`);
  let d = `<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5"
    markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z"/></marker></defs>`;
  for (const e of edges){
    const a = scope.querySelector(`[data-word="${CSS.escape(e.from)}"]`);
    const b = scope.querySelector(`[data-word="${CSS.escape(e.to)}"]`);
    if (!a || !b) continue;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const x1 = ra.right - sr.left, y1 = ra.top + ra.height/2 - sr.top;
    const x2 = rb.left - sr.left - 3,  y2 = rb.top + rb.height/2 - sr.top;
    const dx = Math.max(28, (x2-x1)/2);
    d += `<path class="e" data-from="${escAttr(e.from)}" data-to="${escAttr(e.to)}"
      marker-end="url(#arr)"
      d="M${x1},${y1} C${x1+dx},${y1} ${x2-dx},${y2} ${x2},${y2}"/>`;
  }
  svg.innerHTML = d;
}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function escAttr(s){return esc(s).replace(/"/g,'&quot;');}

/* ---------- 级联钻取:path 每层一个选中词 ----------
   已走路径保留墨框;当前层高亮"上一层父节点在本层的全部子节点"(虚线,↑↓ 范围);
   下一层高亮当前词子节点(红框,随切换变换);历史层兄弟范围累积保留(弱高亮)。 */
let path = [], hoverName = null;
/* 图上的根 = 无上游且出现在边里(有下游);游离词(无边)不算根 */
function rootWords(){
  return words.filter(w => !(upAdj[w.name]) && (downAdj[w.name] || []).length);
}
function defaultPath(name){
  const chain = [name];
  let cur = name; const guard = new Set();
  while (true){
    const ups = (upAdj[cur] || []).filter(u => index[u]);
    if (!ups.length || guard.has(cur)) break;
    guard.add(cur);
    ups.sort((a,b) => byDefault(index[a], index[b]));
    cur = ups[0];
    chain.unshift(cur);
  }
  return chain;
}
function sibSet(effPath){
  const p = effPath.length > 1 ? effPath[effPath.length - 2] : null;
  return new Set(p ? (downAdj[p] || []) : rootWords().map(w => w.name));
}
function renderPath(effPath){
  const name = effPath[effPath.length - 1];
  const nodes = document.querySelectorAll('.node');
  const svgPaths = document.querySelectorAll('svg.edges path.e');
  if (!name){
    nodes.forEach(n => n.classList.remove('dim','up','down','sib','sibh','sel'));
    svgPaths.forEach(p => p.classList.remove('hot','warm'));
    return;
  }
  const last = effPath.length - 1;
  const roots = rootWords().map(w => w.name);
  const sibsOf = i => new Set(i === 0 ? roots : (downAdj[effPath[i - 1]] || []));
  const trail = new Set(effPath.slice(0, -1));
  const freeFocus = isFree(name);
  const curSibs = freeFocus
    ? new Set(words.filter(w => w.gi === index[name].gi && isFree(w.name)).map(w => w.name))
    : sibsOf(last);
  const histSibs = new Set();
  if (!freeFocus) for (let i = 0; i < last; i++) for (const w of sibsOf(i)) histSibs.add(w);
  const kids = freeFocus ? new Set() : new Set(downAdj[name] || []);
  nodes.forEach(n => {
    const w = n.dataset.word;
    const isTrail = trail.has(w);
    const isCurSib = w !== name && curSibs.has(w);
    const isHistSib = !isTrail && !isCurSib && histSibs.has(w);
    const isKid = w !== name && kids.has(w);
    n.classList.toggle('dim', !(w === name || isTrail || isCurSib || isHistSib || isKid));
    n.classList.toggle('up', isTrail);
    n.classList.toggle('sib', isCurSib);
    n.classList.toggle('sibh', isHistSib);
    n.classList.toggle('down', isKid);
    n.classList.toggle('sel', w === name);
  });
  const SEP = '\u0001';
  const hot = new Set(), warm = new Set();
  for (let i = 0; i + 1 < effPath.length; i++)
    hot.add(effPath[i] + SEP + effPath[i+1]);
  if (last > 0) for (const w of (downAdj[effPath[last-1]] || []))
    hot.add(effPath[last-1] + SEP + w);
  for (const k of kids) hot.add(name + SEP + k);
  for (let i = 1; i < last; i++)
    for (const w of (downAdj[effPath[i-1]] || []))
      if (!hot.has(effPath[i-1] + SEP + w)) warm.add(effPath[i-1] + SEP + w);
  svgPaths.forEach(p => {
    const k = p.dataset.from + SEP + p.dataset.to;
    p.classList.toggle('hot', hot.has(k));
    p.classList.toggle('warm', !hot.has(k) && warm.has(k));
  });
}
function applyFocus(){
  renderPath(hoverName && index[hoverName] && hoverName !== path[path.length-1]
             ? defaultPath(hoverName) : path);
}
function setFocus(name){
  path = defaultPath(name);
  applyFocus();
  showDetail(name);
}
function clickFocus(name){
  const last = path[path.length - 1];
  if (name === last) return;
  const idx = path.indexOf(name);
  if (idx >= 0) path = path.slice(0, idx + 1);
  else if ((downAdj[last] || []).includes(name)) path.push(name);
  else if (sibSet(path).has(name)) path[path.length - 1] = name;
  else path = defaultPath(name);
  applyFocus();
  showDetail(name);
}

/* ---------- 键盘导航 ---------- */
function navNodes(){
  return [...document.querySelectorAll('.node')]
    .map(n => {
      const r = n.getBoundingClientRect();
      return {name: n.dataset.word, x: r.left + r.width/2, y: r.top + r.height/2,
              hidden: r.width === 0};
    })
    .filter(n => !n.hidden);
}
function moveFocus(dx, dy){
  if (!path.length){
    const first = rootWords().sort(byDefault)[0] || words.slice().sort(byDefault)[0];
    if (first) setFocus(first.name);
    return;
  }
  const last = path[path.length - 1];
  const nodes = navNodes();
  const c = nodes.find(n => n.name === last);
  if (!c) return;
  if (isFree(last)){
    /* 独立词:带内网格自由四向移动 */
    const pool = nodes.filter(n => isFree(n.name));
    let best = null, bestScore = Infinity;
    for (const n of pool){
      if (n.name === last) continue;
      const vx = n.x - c.x, vy = n.y - c.y;
      if (dx && Math.sign(vx) !== dx) continue;
      if (dy && Math.sign(vy) !== dy) continue;
      const fwd = dx ? Math.abs(vx) : Math.abs(vy);
      const side = dx ? Math.abs(vy) : Math.abs(vx);
      if (fwd < 2) continue;
      const score = fwd + side * 2.5;
      if (score < bestScore){ bestScore = score; best = n; }
    }
    if (!best) return;
    path[path.length - 1] = best.name;
    applyFocus(); showDetail(best.name);
    return;
  }
  if (dy){
    const sibs = sibSet(path);
    const pool = nodes.filter(n => sibs.has(n.name));
    if (pool.length < 2) return;
    pool.sort((a,b) => a.y - b.y);
    const i = pool.findIndex(n => n.name === last);
    if (i < 0) return;
    const next = pool[i + dy];
    if (!next) return;
    path[path.length - 1] = next.name;
    applyFocus(); showDetail(next.name);
    return;
  }
  if (dx > 0){
    const kids = (downAdj[last] || []).filter(k => nodes.some(n => n.name === k));
    if (!kids.length) return;
    if (c) kids.sort((a,b) => {
      const na = nodes.find(n => n.name === a), nb = nodes.find(n => n.name === b);
      return Math.abs(na.y - c.y) - Math.abs(nb.y - c.y);
    });
    path.push(kids[0]);
    applyFocus(); showDetail(kids[0]);
    return;
  }
  if (dx < 0){
    if (path.length < 2) return;
    path.pop();
    applyFocus(); showDetail(path[path.length - 1]);
  }
}

/* ---------- 右页详情(跟随焦点) ---------- */
const detail = document.getElementById('detail');
function showDetail(name){
  const w = index[name];
  const prereqNames = w.prereq.filter(p => index[p]);
  let body = '';
  if (w.def.length && w.def.join(' ').trim())
    body += '<p>' + w.def.map(esc).join(' ') + '</p>';
  if (w.enc) body += `<p class="enc"><span>遇到</span>${esc(w.enc)}</p>`;
  if (w.cmd) body += `<p class="cmd"><span>下命令</span><code>${esc(w.cmd)}</code></p>`;
  detail.innerHTML = `
    <h3>${esc(w.name)}</h3>
    <div class="dmeta">${esc(w.cn)} · ${esc(w.group)}${w.tag?`(${esc(w.tag)})`:''}
      · 第 ${w.layer} 层</div>
    ${body}
    ${prereqNames.length ? `<p style="font-size:12px;color:var(--mut)">前置: <b style="color:var(--red)">${
      prereqNames.map(p=>`<span style="cursor:pointer;text-decoration:underline" data-jump="${escAttr(p)}">${esc(p)}</span>`).join(', ')}</b></p>` : ''}
    <div class="prow">
      <button class="dbtn ${lit.has(name)?'on':''}">${
        lit.has(name)?'■ 已掌握 — 点击取消':'■ 标记已掌握'}</button>
      <button class="copyq">⧉ 复制追问提示词</button>
    </div>
    <div class="dkeys"><b>↑↓←→</b> 钻取 · <b>空格</b> 标记 · <b>C</b> 复制追问 ·
      <b>Esc</b> 回全图</div>`;
  detail.querySelector('.dbtn').onclick = () => { toggleMark(name); showDetail(name); };
  detail.querySelector('.copyq').onclick = ev => copyPrompt(name, ev.currentTarget);
  detail.querySelectorAll('[data-jump]').forEach(el =>
    el.onclick = () => setFocus(el.dataset.jump));
  const el = document.querySelector(`.node[data-word="${CSS.escape(name)}"]`);
  if (el) el.scrollIntoView({block:'nearest', inline:'nearest', behavior:'smooth'});
  document.querySelectorAll('.node').forEach(n =>
    n.classList.toggle('sel', n.dataset.word === name));
}

/* ---------- 标记 / 进度 ---------- */
function toggleMark(name){
  lit.has(name) ? lit.delete(name) : lit.add(name);
  localStorage.setItem(KEY, JSON.stringify([...lit]));
  document.querySelectorAll(`.node[data-word="${CSS.escape(name)}"]`).forEach(n =>
    n.classList.toggle('lit', lit.has(name)));
  applyProgress();
}
function applyProgress(){
  const all = document.querySelectorAll('.node').length;
  const n = document.querySelectorAll('.node.lit').length;
  document.getElementById('fill').style.width = (all ? n*100/all : 0) + '%';
  document.getElementById('pc').textContent = n + ' / ' + all + ' 已标记';
}
function applyLit(){
  document.querySelectorAll('.node').forEach(n =>
    n.classList.toggle('lit', lit.has(n.dataset.word)));
  applyProgress();
}

/* ---------- 事件 ---------- */
document.getElementById('main').addEventListener('click', ev => {
  const mk = ev.target.closest('.markbox');
  if (mk){ toggleMark(mk.closest('.node').dataset.word); return; }
  const nd = ev.target.closest('.node');
  if (nd) clickFocus(nd.dataset.word);
});
document.querySelector('.danghead').addEventListener('click', ev => {
  ev.stopPropagation();
  document.querySelector('.dangband').classList.toggle('open');
});
document.getElementById('main').addEventListener('mouseover', ev => {
  const nd = ev.target.closest('.node');
  const w = nd ? nd.dataset.word : null;
  if (w === hoverName) return;
  hoverName = w;
  applyFocus();
});
document.getElementById('main').addEventListener('mouseout', ev => {
  if (ev.target.closest('.node') &&
      !(ev.relatedTarget && ev.relatedTarget.closest && ev.relatedTarget.closest('.node'))){
    hoverName = null;
    applyFocus();
  }
});
document.addEventListener('keydown', ev => {
  if (ev.target && ev.target.matches && ev.target.matches('input,textarea,[contenteditable]')) return;
  if (document.body.classList.contains('quizzing')) return;  /* quiz overlay 接管键盘 */
  if (ev.key === 'ArrowUp'){ ev.preventDefault(); moveFocus(0,-1); }
  else if (ev.key === 'ArrowDown'){ ev.preventDefault(); moveFocus(0,1); }
  else if (ev.key === 'ArrowLeft'){ ev.preventDefault(); moveFocus(-1,0); }
  else if (ev.key === 'ArrowRight'){ ev.preventDefault(); moveFocus(1,0); }
  else if (ev.key === ' ' && path.length){
    ev.preventDefault();
    const n = path[path.length - 1];
    toggleMark(n); showDetail(n);
  }
  else if ((ev.key === 'c' || ev.key === 'C') && path.length){
    copyPrompt(path[path.length - 1], detail.querySelector('.copyq'));
  }
  else if (ev.key === 'q' || ev.key === 'Q'){ ev.preventDefault(); quizOpen(); }
  else if (ev.key === 'Escape' && path.length){ path = []; hoverName = null; applyFocus(); }
});
document.getElementById('reset').onclick = () => {
  if (confirm('清空全部标记与 quiz 评级?')){
    lit.clear(); localStorage.setItem(KEY, '[]'); qw = {}; saveQW(); applyLit();
  }
};
const q = document.getElementById('q');
q.addEventListener('input', () => {
  const v = q.value.trim().toLowerCase();
  document.body.classList.toggle('filtering', !!v);
  document.querySelectorAll('.node').forEach(n =>
    n.classList.toggle('hit', !!v && n.dataset.search.includes(v)));
});

/* ---------- 初始化 ---------- */
applyLit();
drawEdges();
const rootFirst = rootWords().sort(byDefault)[0] || words.slice().sort(byDefault)[0];
if (rootFirst) setFocus(rootFirst.name);
addEventListener('resize', () => { drawEdges(); applyFocus(); });
"""

# ---- Quiz:出题评分(选择题),全屏 overlay,仅 tree 页 ----
# Q 直接开一轮(无首页):10 题(词库 ≤10 全出);答错过的词(w≥3)下一轮优先
# 入题,其余按拓扑序均匀分层取样(Kahn,就绪集按 缺省全序 频率→组序→词序;无标注
# 自然退化)。题干 def→enc→cmd 兜底(泄漏答案词的线索跳过),干扰项 同组→同频率→
# 全局;答完出分 + 错题回顾,对错同步升降权重;Esc / ✕ 关闭回树图。
CSS_QUIZ = """
#quizbtn{background:none;border:1px solid var(--ink);color:var(--ink);
font:inherit;font-size:12px;padding:6px 12px;cursor:pointer}
#quizbtn:hover{background:var(--ink);color:#fff}
#quiz{display:none;position:fixed;inset:0;z-index:100;background:var(--paper);
overflow-y:auto;padding:0 clamp(18px,6vw,90px) 46px}
body.quizzing #quiz{display:block}
body.quizzing main,body.quizzing .hint,body.quizzing #detail,body.quizzing footer.foot{visibility:hidden}
.qbar{max-width:760px;margin:0 auto;display:flex;align-items:baseline;gap:16px;
border-bottom:2px solid var(--ink);padding:20px 0 10px}
.qtitle{font-family:var(--serif);font-size:21px;font-weight:900}
#qexit{margin-left:auto;background:none;border:1px solid var(--line);color:var(--mut);
font:inherit;font-size:12px;padding:6px 12px;cursor:pointer}
#qexit:hover{border-color:var(--ink);color:var(--ink)}
.qbody{max-width:760px;margin:0 auto}
.qkind{font-size:10px;letter-spacing:3px;color:var(--red);text-transform:uppercase}
.qstem{font-family:var(--serif);font-size:17px;line-height:1.85;margin:12px 0 24px}
.qopts{display:grid;gap:10px}
.qopt{text-align:left;font:inherit;font-size:15.5px;cursor:pointer;background:#fff;
border:1.5px solid var(--ink);padding:13px 16px;transition:.12s}
.qopt i{font-style:normal;font-family:ui-monospace,Menlo,monospace;font-size:12px;
color:var(--mut);margin-right:10px}
.qopt:hover{background:var(--ink);color:#fff}
.qopt:hover i{color:#fff}
.qopt.right{background:#237a3a;border-color:#237a3a;color:#fff}
.qopt.wrong{background:var(--red);border-color:var(--red);color:#fff}
.qopt.right i,.qopt.wrong i{color:#fff}
.qdone{text-align:center;margin-top:44px}
.qdone h3{font-family:var(--serif);font-size:44px;margin:0 0 6px}
.qdone p{color:var(--mut);margin:4px 0 10px}
.qbtns{display:flex;gap:12px;justify-content:center;margin-top:24px}
.qbtns button{font:inherit;font-size:14px;cursor:pointer;padding:12px 24px;
border:1.5px solid var(--red);background:#fff;color:var(--red)}
.qbtns button:hover{background:var(--red);color:#fff}
.qbtns button.plain{border-color:var(--ink);color:var(--ink)}
.qreview{text-align:left;margin:20px auto 0;max-width:580px;
border-top:1px solid var(--line);padding-top:14px}
.qreview h4{margin:0 0 10px;font-size:12px;letter-spacing:1px;color:var(--mut)}
.qwrong{margin:0 0 14px}
.qwrong p{margin:3px 0;font-size:13.5px}
.qwrong .qa span{color:var(--red);font-weight:700}
.qwrong .qa b{color:#237a3a;font-weight:600}
"""

JS_QUIZ = r"""
/* ---------- Quiz:出题评分(选择题) ---------- */
const QKEY = 'domain-primer-quiz:' + document.title;
let qw = {};
try { qw = JSON.parse(localStorage.getItem(QKEY) || '{}') || {}; } catch(e) { qw = {}; }
function saveQW(){ localStorage.setItem(QKEY, JSON.stringify(qw)); }
const quizEl = document.getElementById('quiz');

/* 出题取样序 = 前置拓扑序:Kahn,就绪集按缺省全序 (频率,组序,词序) 取最小;
   无前置标注 → 全部入度为 0,自然退化为缺省全序;极端成环时整体兜底同序 */
const TOPO = (() => {
  const indeg = {};
  for (const w of words) indeg[w.name] = 0;
  for (const e of edges) if (indeg[e.to] !== undefined) indeg[e.to]++;
  const ready = words.filter(w => !indeg[w.name]).sort(byDefault);
  const out = [];
  while (ready.length){
    const w = ready.shift();
    out.push(w);
    for (const k of (downAdj[w.name] || [])){
      if (indeg[k] === undefined || --indeg[k] !== 0) continue;
      const kw = index[k];
      let i = ready.findIndex(x => byDefault(kw, x) < 0);
      if (i < 0) ready.push(kw); else ready.splice(i, 0, kw);
    }
  }
  return out.length === words.length ? out : words.slice().sort(byDefault);
})();

function quizOpen(){ document.body.classList.add('quizzing'); startChoice(false); }
function quizClose(){ document.body.classList.remove('quizzing'); }
document.getElementById('quizbtn').onclick = () =>
  document.body.classList.contains('quizzing') ? quizClose() : quizOpen();
document.getElementById('qexit').onclick = quizClose;
function clueFor(w){
  const def = (w.def && w.def.join(' ').trim()) || '';
  const leak = t => t.toLowerCase().includes(w.name.toLowerCase()) ||
                    (w.cn && t.toLowerCase().includes(w.cn.toLowerCase()));
  if (def && !leak(def)) return {q: `以下哪个词指:「${def}」`, kind: '定义'};
  if (w.enc && !leak(w.enc))
    return {q: `遇到这种情况:「${w.enc}」— 该用哪个词?`, kind: '场景'};
  if (w.cmd && !leak(w.cmd))
    return {q: `哪个词的「下命令」是:${w.cmd}`, kind: '命令'};
  if (def) return {q: `以下哪个词指:「${def}」`, kind: '定义'};
  return null;
}
function distractors(w, n){
  const pool = words.filter(x => x.name !== w.name);
  const sh = a => a.slice().sort(() => Math.random() - .5);
  return sh(pool.filter(x => x.gi === w.gi))
    .concat(sh(pool.filter(x => x.gi !== w.gi && x.freq === w.freq)),
            sh(pool.filter(x => x.gi !== w.gi && x.freq !== w.freq)))
    .slice(0, n);
}
let qs = [], qi = 0, qscore = 0, qwrong = [], qlocked = false, qAllFlag = false;
function startChoice(all){
  const bank = TOPO.filter(w => clueFor(w));
  if (bank.length < 2){ alert('可出题的词太少,先回地图补充三件套。'); return; }
  qAllFlag = all || bank.length <= 10;  /* 词库不超 10 就全出 */
  /* 答错过的词(w≥3)优先入题,其余按拓扑序均匀分层取样补足;呈现仍按拓扑序 */
  let pick = bank.filter(w => (qw[w.name] || 1) >= 3);
  if (qAllFlag) pick = bank.slice();
  else {
    const rest = bank.filter(w => (qw[w.name] || 1) < 3);
    const slots = Math.max(0, 10 - pick.length);
    for (let i = 0; i < slots && rest.length; i++)
      pick.push(rest[Math.floor(i * rest.length / slots)]);
  }
  pick = [...new Set(pick)].sort((a, b) => TOPO.indexOf(a) - TOPO.indexOf(b));
  qs = pick.map(w => {
    const c = clueFor(w);
    const opts = distractors(w, 3).map(x => x.name).concat([w.name]);
    for (let i = opts.length - 1; i > 0; i--){
      const j = Math.floor(Math.random() * (i + 1));
      [opts[i], opts[j]] = [opts[j], opts[i]];
    }
    return {w, q: c.q, kind: c.kind, opts, ans: w.name};
  });
  qi = 0; qscore = 0; qwrong = [];
  showChoiceQ();
}
function showChoiceQ(){
  if (qi >= qs.length) return choiceDone();
  qlocked = false;
  quizEl.dataset.state = 'choice';
  const item = qs[qi];
  quizEl.querySelector('.qtitle').textContent =
    `出题评分 · 第 ${qi + 1} / ${qs.length} 题 · 对 ${qscore}`;
  quizEl.querySelector('.qbody').innerHTML = `
    <div class="cq">
      <span class="qkind">${item.kind}</span>
      <p class="qstem">${esc(item.q)}</p>
      <div class="qopts">${item.opts.map((o, i) =>
        `<button class="qopt" data-o="${escAttr(o)}"><i>${'ABCD'[i]}</i>${esc(o)}</button>`
      ).join('')}</div>
    </div>`;
  quizEl.querySelectorAll('.qopt').forEach(b => b.onclick = () => answerChoice(b));
}
function answerChoice(btn){
  if (qlocked) return;
  qlocked = true;
  const item = qs[qi], pickName = btn.dataset.o;
  const ok = pickName === item.ans;
  quizEl.querySelectorAll('.qopt').forEach(b => {
    if (b.dataset.o === item.ans) b.classList.add('right');
    else if (b === btn) b.classList.add('wrong');
  });
  if (ok) qw[item.ans] = Math.max(1, (qw[item.ans] || 2) - 1);
  else {
    qwrong.push({q: item.q, pick: pickName, ans: item.ans});
    qw[item.ans] = Math.min(3, (qw[item.ans] || 2) + 1);
  }
  saveQW();
  if (ok) qscore++;
  setTimeout(() => { qi++; showChoiceQ(); }, 850);
}
function choiceDone(){
  quizEl.dataset.state = 'choicedone';
  const pct = qs.length ? Math.round(qscore * 100 / qs.length) : 0;
  quizEl.querySelector('.qtitle').textContent = '出题评分 · 完成';
  quizEl.querySelector('.qbody').innerHTML = `
    <div class="qdone"><h3>${qscore} / ${qs.length}</h3>
    <p>正确率 ${pct}%${qwrong.length ? ' · 答错 ' + qwrong.length + ' 题' : ' · 全对,漂亮'}</p>
    ${qwrong.length ? `<div class="qreview"><h4>错题回顾</h4>${qwrong.map(x =>
      `<div class="qwrong"><p>${esc(x.q)}</p>
       <p class="qa"><span>✗</span> ${esc(x.pick)}&nbsp;&nbsp;<b>✓ ${esc(x.ans)}</b></p></div>`
    ).join('')}</div>` : ''}
    <div class="qbtns">
      <button id="cAgain">↻ 再出一轮</button>
      <button id="cClose" class="plain">收工回图(Esc)</button></div></div>`;
  quizEl.querySelector('#cAgain').onclick = () => startChoice(qAllFlag);
  quizEl.querySelector('#cClose').onclick = quizClose;
}

/* ---------- Quiz 键盘(树图键位在 quizzing 时已让路) ---------- */
document.addEventListener('keydown', ev => {
  if (!document.body.classList.contains('quizzing')) return;
  if (ev.target && ev.target.matches && ev.target.matches('input,textarea,[contenteditable]')) return;
  if (ev.key === 'Escape'){ ev.preventDefault(); quizClose(); return; }
  if (quizEl.dataset.state === 'choice' && !qlocked){
    const ki = '1234abcd'.indexOf(ev.key.toLowerCase());
    const b = quizEl.querySelectorAll('.qopt')[ki];
    if (ki >= 0 && ki < 4 && b) answerChoice(b);
  }
});
"""

PAGE_TREE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body>
<header class="mast">
<h1>{h1}<em>.</em></h1>
<div class="tools">
<input id="q" type="search" placeholder="搜索词、定义、命令…">
<div class="prog"><div class="track"><div class="fill" id="fill"></div></div>
<span class="num" id="pc"></span></div>
<button id="quizbtn">Q·自测</button>
<button id="reset">重置</button>
</div></header>
<p class="hint">{hint}</p>
<main id="main">{body}</main>
<aside id="detail"></aside>
<div id="quiz" data-state="choice">
<div class="qbar"><span class="qtitle">Quiz</span>
<button id="qexit">✕ 退出(Esc)</button></div>
<div class="qbody"></div></div>
<footer class="foot">进度存本机浏览器,换设备不同步。</footer>
<script type="application/json" id="words">{words}</script>
<script>{js}</script></body></html>"""

LAYOUTS = {
    "tree": (CSS_TREE + CSS_QUIZ, JS_TREE + JS_QUIZ, True),
    "spread": (CSS_SPREAD, JS_SPREAD, True),
    "inline": (CSS_INLINE, JS_INLINE, True),
    "hover": (CSS_HOVER, JS_HOVER, True),
    "review": (CSS_REVIEW, JS_REVIEW, False),
}
LAYOUT = "tree"

PAGE_BROWSE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body>
<header class="mast">
<h1>{h1}<em>.</em></h1>
<div class="tools">
<input id="q" type="search" placeholder="搜索词、定义、命令…">
<div class="prog"><div class="track"><div class="fill" id="fill"></div></div>
<span class="num" id="pc"></span></div>
<button id="reset">重置</button>
</div></header>
<main>{body}</main>
<footer class="foot">进度存本机浏览器,换设备不同步。</footer>
<div id="fn"><div class="fk"></div><h4></h4><div class="fc"></div><div class="fb"></div>
<button id="fnCopy" class="copyq">⧉ 复制追问提示词</button></div>
<script type="application/json" id="words">{words}</script>
<script>{js}</script></body></html>"""

BODY_SPREAD = """<div class="spread">
<div class="toc">{chapters}</div>
<aside class="page" id="page">
<h3></h3><div class="gname"></div><div class="pbody"></div>
<div class="prow"><button id="pToggle"></button></div>
<div class="pcopy"><button id="pCopy" class="copyq">⧉ 复制追问提示词</button></div>
<div class="pnav"><button id="pPrev">←</button><span class="cnt"></span>
<button id="pNext">→</button></div>
<div class="keys"><b>↑↓</b> 换词 · <b>空格</b> 标记 · 行首方块直接点</div>
</aside>
</div>"""

BODY_INLINE = """<p class="hint">点词条原位展开释义与标记,再点收起;全程不弹窗。</p>
{chapters}"""

BODY_HOVER = """<p class="hint">悬停词条读<b>脚注释义</b>,<b>单击词条</b>即标记/取消 — 一击一词。</p>
{chapters}"""

PAGE_REVIEW = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body>
<header class="mast">
<h1>{h1}<em>.</em></h1>
<div class="tools">
<input id="q" type="search" placeholder="搜索词、定义、命令…">
<div class="prog"><div class="track"><div class="fill" id="fill"></div></div>
<span class="num" id="pc"></span></div>
<button id="reset">重置</button>
</div></header>
<main>
<div class="modebar"><button id="startR">▶ 开始复习(全部词)</button>
<button id="startU">只过未标记的</button></div>
<div class="rwrap">
<div class="rhead"><span class="rcount"></span>
<div class="track"><div class="fill"></div></div></div>
<div class="rcard"><div class="kicker"></div><h2></h2><div class="rcn"></div>
<div class="rbody"></div>
<div class="rbtns"><button id="rNo">← 不会</button><button id="rYes">会 →</button></div>
<div class="rcopy"><button id="rCopy" class="copyq">⧉ 复制追问提示词</button></div>
<div class="rkeys"><b>1</b>/<b>←</b> 不会 · <b>2</b>/<b>空格</b>/<b>→</b> 会 · <b>Esc</b> 回目录</div>
</div>
<div class="rdone" style="display:none"><h2></h2><p></p>
<div class="rd2"><button id="againU">↻ 再来一轮未标记的</button>
<button id="backBrowse" class="plain">回目录浏览</button></div></div>
</div>
<div class="browse">{chapters}</div>
</main>
<footer class="foot">进度存本机浏览器,换设备不同步。键盘 R 进入复习。</footer>
<script type="application/json" id="words">{words}</script>
<script>{js}</script></body></html>"""


def build(data) -> str:
    h1 = re.split(r"[(（]", data["title"])[0].strip() or data["title"]
    if LAYOUT == "tree":
        body, words_js, hint = build_tree(data)
        css, js, _ = LAYOUTS["tree"]
        return PAGE_TREE.format(title=esc(data["title"]), css=css, h1=esc(h1),
                                body=body, hint=hint, words=words_js, js=js)
    chapters, idx = [], 0
    for gi, g in enumerate(data["groups"]):
        c, idx = chapter_html(g, gi, idx)
        chapters.append(c)
    chapters = "".join(chapters)
    words = [{"name": w["name"], "cn": w["cn"], "def": w["def"], "enc": w["enc"],
              "cmd": w["cmd"], "prereq": w["prereq"]}
             for g in data["groups"] for w in g["words"]]
    meta = " · ".join(html.unescape(md_inline(m)) for m in data["meta"])
    footer = md_inline(data["footer"]) if data["footer"] else ""
    words_js = json.dumps(words, ensure_ascii=False).replace("</", "<\\/")

    if LAYOUT == "review":
        page = PAGE_REVIEW
        body = chapters
    else:
        page = PAGE_BROWSE
        body = {"spread": BODY_SPREAD, "inline": BODY_INLINE,
                "hover": BODY_HOVER}[LAYOUT].format(chapters=chapters)
    hints = {"spread": "", "inline": "", "hover": "", "review": "键盘 R 也可随时进入复习。"}
    css, js, _ = LAYOUTS[LAYOUT]
    return page.format(title=esc(data["title"]), css=css, h1=esc(h1), meta=meta,
                       body=body, chapters=chapters, footer=footer,
                       hint=hints[LAYOUT] + " " if hints[LAYOUT] else "",
                       words=words_js, js=js)


def main():
    global LAYOUT
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--layout", choices=list(LAYOUTS), default="tree")
    a = ap.parse_args()
    LAYOUT = a.layout
    data = parse(Path(a.input).read_text(encoding="utf-8"))
    resolve_prereqs(data["groups"])
    Path(a.output).write_text(build(data), encoding="utf-8")
    n = sum(len(g["words"]) for g in data["groups"])
    print(f"{a.output}: editorial {LAYOUT}, {len(data['groups'])} chapters, {n} entries")


if __name__ == "__main__":
    main()
