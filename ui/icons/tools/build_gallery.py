#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка самодостаточной HTML-галереи набора иконок (без внешних ресурсов)."""

from __future__ import annotations

import base64
import html
import json
import os
import re
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_DIR = os.path.join(ROOT, "svg")

PALETTE = [
    ("#D9D9D9", "База", "Основной объект: геометрия, оси, листы"),
    ("#89CBFA", "Акцент", "Главное действие / результат команды"),
    ("#808080", "Нейтральный", "Источник данных, неактивное состояние"),
    ("#666666", "Контур", "Обводка базовых фигур, детали"),
    ("#82D99F", "Процесс", "Включение, автоматика, подтверждение"),
    ("#FFD580", "Модификатор", "Правка значения, редактирование"),
    ("#FF6666", "Статус", "Сброс, отключение, запрет"),
]

SRC_LABEL = {"lisp": "LISP", "python": "PYTHON", "ui": "UI"}


def inline(svg: str, suffix: str) -> str:
    """Вставка SVG в HTML с уникальными id (маски не конфликтуют между копияями)."""
    svg = re.sub(r"<title>.*?</title>", "", svg, flags=re.S)
    svg = re.sub(r'\s(width|height)="32"', "", svg, count=2)
    ids = re.findall(r'\sid="([^"]+)"', svg)
    for i in ids:
        svg = svg.replace(f'id="{i}"', f'id="{i}-{suffix}"')
        svg = svg.replace(f"url(#{i})", f"url(#{i}-{suffix})")
    return svg.strip()


def zip_store(files: list[tuple[str, bytes]]) -> bytes:
    """ZIP без сжатия — чтобы кнопка «скачать всё» работала офлайн."""
    out, central = bytearray(), bytearray()
    for name, data in files:
        nb = name.encode("utf-8")
        crc = zlib.crc32(data) & 0xFFFFFFFF
        off = len(out)
        out += struct.pack("<4s5H3I2H", b"PK\x03\x04", 20, 0, 0, 0, 0,
                           crc, len(data), len(data), len(nb), 0) + nb + data
        central += struct.pack("<4s6H3I5H2I", b"PK\x01\x02", 20, 20, 0, 0, 0, 0,
                               crc, len(data), len(data), len(nb), 0, 0, 0, 0, 0, off)
        central += nb
    end = struct.pack("<4s4H2IH", b"PK\x05\x06", 0, 0, len(files), len(files),
                      len(central), len(out), 0)
    return bytes(out + central + end)


def build():
    man = json.load(open(os.path.join(ROOT, "icons.json"), encoding="utf-8"))
    groups: dict[str, list] = {}
    for m in man:
        groups.setdefault(m["group"], []).append(m)

    # --- карточки ---
    sections = []
    for gi, (g, items) in enumerate(groups.items()):
        cards = []
        for k, m in enumerate(items):
            uid = f"{gi}-{k}"
            main = inline(m["svg"], f"m{uid}")
            mini = inline(m["svg"], f"s{uid}")
            cards.append(f"""
      <article class="card" data-cmd="{html.escape(m['cmd'].lower())}"
               data-title="{html.escape(m['title'].lower())}"
               data-file="{html.escape(m['file'].lower())}"
               data-desc="{html.escape(m['desc'].lower())}"
               data-src="{m['src']}" data-idx="{man.index(m)}">
        <div class="stage">{main}</div>
        <div class="mini"><span class="m16">{mini}</span><span class="mlab">16&nbsp;px</span></div>
        <code class="cmd">{html.escape(m['cmd'])}</code>
        <div class="ttl">{html.escape(m['title'])}</div>
        <div class="sub"><span class="tag {m['src']}">{SRC_LABEL[m['src']]}</span>
          <span class="org">{html.escape(m['origin'])}</span></div>
      </article>""")
        sections.append(f"""
    <section class="grp" data-group="{html.escape(g)}">
      <h2>{html.escape(g)} <span class="cnt">{len(items)}</span></h2>
      <div class="grid">{''.join(cards)}</div>
    </section>""")

    pal = "".join(
        f'<div class="chip"><i style="background:{c}"></i><b>{n}</b>'
        f'<code>{c}</code><span>{d}</span></div>'
        for c, n, d in PALETTE)

    rows = "".join(
        f'<tr><td><code>{html.escape(m["cmd"])}</code></td>'
        f'<td>{html.escape(m["title"])}</td>'
        f'<td><span class="tag {m["src"]}">{SRC_LABEL[m["src"]]}</span></td>'
        f'<td><code>{html.escape(m["origin"])}</code></td>'
        f'<td><code>{html.escape(m["file"])}.svg</code></td></tr>'
        for m in man)

    files = [(f"svg/{m['file']}.svg", m["svg"].encode("utf-8")) for m in man]
    files.append(("icons.json", json.dumps(
        [{k: v for k, v in m.items() if k != "svg"} for m in man],
        ensure_ascii=False, indent=1).encode("utf-8")))
    zb64 = base64.b64encode(zip_store(files)).decode()

    payload = json.dumps([{k: v for k, v in m.items()} for m in man], ensure_ascii=False)

    n_lisp = sum(1 for m in man if m["src"] == "lisp")
    n_py = sum(1 for m in man if m["src"] == "python")
    n_ui = sum(1 for m in man if m["src"] == "ui")

    return f"""<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IGI Tools — единый набор иконок ({len(man)})</title>
<style>
  :root {{
    --size: 48px;
    --acc:#89CBFA; --prc:#82D99F; --mod:#FFD580; --sta:#FF6666;
    --bg:#1e1e1e; --bg2:#262626; --card:#2b2b2b; --line:#3a3a3a;
    --fg:#e8e8e8; --fg2:#a8a8a8; --fg3:#7a7a7a; --stage:#242424;
  }}
  html[data-theme="light"] {{
    --bg:#f5f5f6; --bg2:#ffffff; --card:#ffffff; --line:#dcdce0;
    --fg:#1c1c1e; --fg2:#5a5a62; --fg3:#8a8a92; --stage:#fafafa;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif; }}
  code {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  header {{ position:sticky; top:0; z-index:20; background:var(--bg2);
    border-bottom:1px solid var(--line); padding:14px 22px; }}
  .hrow {{ display:flex; align-items:center; gap:14px; flex-wrap:wrap; }}
  .brand {{ display:flex; align-items:center; gap:10px; font-weight:650; font-size:16px; }}
  .brand svg {{ width:26px; height:26px; }}
  .sub2 {{ color:var(--fg2); font-size:12.5px; }}
  .spacer {{ flex:1; }}
  .tools {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-top:12px; }}
  input[type=search] {{ background:var(--card); border:1px solid var(--line); color:var(--fg);
    border-radius:8px; padding:8px 12px; min-width:250px; font-size:13px; outline:none; }}
  input[type=search]:focus {{ border-color:var(--acc); }}
  .seg {{ display:flex; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
  .seg button {{ background:var(--card); color:var(--fg2); border:0; padding:7px 11px;
    font-size:12.5px; cursor:pointer; border-right:1px solid var(--line); }}
  .seg button:last-child {{ border-right:0; }}
  .seg button.on {{ background:var(--acc); color:#10222e; font-weight:650; }}
  .btn {{ background:var(--card); border:1px solid var(--line); color:var(--fg);
    border-radius:8px; padding:8px 13px; font-size:12.5px; cursor:pointer; }}
  .btn:hover {{ border-color:var(--acc); }}
  main {{ padding:22px; max-width:1500px; margin:0 auto; }}
  .grp {{ margin-bottom:30px; }}
  h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.09em; color:var(--fg2);
    margin:0 0 12px; font-weight:650; display:flex; align-items:center; gap:9px; }}
  h2 .cnt {{ background:var(--card); border:1px solid var(--line); color:var(--fg3);
    border-radius:20px; padding:1px 9px; font-size:11px; letter-spacing:0; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(178px,1fr)); gap:12px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:11px;
    padding:12px; cursor:pointer; transition:border-color .14s, transform .14s; }}
  .card:hover {{ border-color:var(--acc); transform:translateY(-2px); }}
  .stage {{ height:88px; display:flex; align-items:center; justify-content:center;
    background:var(--stage); border-radius:8px; margin-bottom:9px; }}
  .stage svg {{ width:var(--size); height:var(--size); }}
  .mini {{ display:flex; align-items:center; gap:7px; margin-bottom:8px; }}
  .m16 {{ display:flex; width:16px; height:16px; }}
  .m16 svg {{ width:16px; height:16px; }}
  .mlab {{ font-size:10px; color:var(--fg3); }}
  .cmd {{ display:block; font-size:11px; color:var(--acc); word-break:break-all; line-height:1.35; }}
  .ttl {{ font-size:13px; font-weight:600; margin:4px 0 7px; }}
  .sub {{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; }}
  .tag {{ font-size:9.5px; font-weight:700; letter-spacing:.05em; padding:2px 6px;
    border-radius:4px; background:#3a3a3a; color:#d0d0d0; }}
  .tag.lisp {{ background:#4a3a52; color:#e0c4f0; }}
  .tag.python {{ background:#2f4a3a; color:#b8e8c8; }}
  .tag.ui {{ background:#4a4432; color:#f0dfae; }}
  .org {{ font-size:10px; color:var(--fg3); word-break:break-all; }}
  .panel {{ background:var(--card); border:1px solid var(--line); border-radius:11px;
    padding:16px 18px; margin-bottom:22px; }}
  .panel h3 {{ margin:0 0 12px; font-size:13px; text-transform:uppercase;
    letter-spacing:.09em; color:var(--fg2); }}
  .pal {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:10px; }}
  .chip {{ display:grid; grid-template-columns:26px 1fr; gap:3px 9px; align-items:center; }}
  .chip i {{ width:26px; height:26px; border-radius:6px; grid-row:span 2;
    border:1px solid rgba(128,128,128,.35); }}
  .chip b {{ font-size:12.5px; }}
  .chip code {{ font-size:10.5px; color:var(--fg2); }}
  .chip span {{ grid-column:2; font-size:10.5px; color:var(--fg3); line-height:1.35; }}
  details {{ margin-top:14px; }}
  summary {{ cursor:pointer; font-size:12.5px; color:var(--acc); }}
  table {{ width:100%; border-collapse:collapse; margin-top:12px; font-size:12px; }}
  th,td {{ text-align:left; padding:6px 9px; border-bottom:1px solid var(--line);
    vertical-align:top; }}
  th {{ color:var(--fg2); font-size:10.5px; text-transform:uppercase; letter-spacing:.06em; }}
  td code {{ font-size:11px; color:var(--fg2); }}
  ul.rules {{ margin:10px 0 0; padding-left:20px; color:var(--fg2); font-size:12.5px; }}
  ul.rules li {{ margin-bottom:5px; }}
  .empty {{ display:none; padding:40px; text-align:center; color:var(--fg3); }}
  /* модальное окно */
  .ov {{ position:fixed; inset:0; background:rgba(0,0,0,.62); display:none;
    align-items:center; justify-content:center; z-index:50; padding:22px; }}
  .ov.on {{ display:flex; }}
  .modal {{ background:var(--bg2); border:1px solid var(--line); border-radius:14px;
    max-width:720px; width:100%; max-height:88vh; overflow:auto; padding:22px; }}
  .mhead {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px; }}
  .mcmd {{ font-size:14px; color:var(--acc); word-break:break-all; }}
  .mttl {{ font-size:19px; font-weight:650; margin:5px 0 4px; }}
  .mdesc {{ color:var(--fg2); font-size:13px; }}
  .views {{ display:flex; gap:12px; margin:18px 0; flex-wrap:wrap; }}
  .view {{ flex:1; min-width:150px; border:1px solid var(--line); border-radius:10px;
    padding:14px; text-align:center; }}
  .view.dark {{ background:#242424; }}
  .view.light {{ background:#f3f3f3; }}
  .view svg {{ width:96px; height:96px; }}
  .vlab {{ font-size:10px; color:var(--fg3); margin-top:6px; }}
  .view.light .vlab {{ color:#8a8a92; }}
  .sizes {{ display:flex; align-items:flex-end; gap:16px; justify-content:center;
    padding:14px; background:var(--stage); border-radius:10px; margin-bottom:16px; }}
  .sizes div {{ text-align:center; }}
  .sizes span {{ display:block; font-size:9.5px; color:var(--fg3); margin-top:5px; }}
  pre {{ background:var(--stage); border:1px solid var(--line); border-radius:9px;
    padding:12px; overflow:auto; font-size:11px; line-height:1.45; max-height:210px;
    color:var(--fg2); }}
  .macts {{ display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }}
  .x {{ background:none; border:0; color:var(--fg2); font-size:24px; cursor:pointer;
    line-height:1; padding:0 4px; }}
  .note {{ font-size:12px; color:var(--fg3); margin-top:10px; line-height:1.5; }}
</style>
</head>
<body>
<header>
  <div class="hrow">
    <div class="brand">{inline(man[[m['file'] for m in man].index('IGI_Tools')]['svg'], 'brand')}
      IGI Tools · набор иконок</div>
    <div class="sub2">{len(man)} иконок · {n_lisp} LISP · {n_py} Python · {n_ui} UI ·
      сетка 32×32 · Flat 2.0</div>
    <div class="spacer"></div>
    <a class="btn" download="IGI-Tools-icons.zip"
       href="data:application/zip;base64,{zb64}">↓ Скачать всё (ZIP)</a>
    <button class="btn" id="theme">◐ Светлая тема</button>
  </div>
  <div class="tools">
    <input type="search" id="q" placeholder="Поиск: команда, название, файл…">
    <div class="seg" id="fsrc">
      <button class="on" data-v="all">Все</button>
      <button data-v="lisp">LISP</button>
      <button data-v="python">Python</button>
      <button data-v="ui">UI</button>
    </div>
    <div class="seg" id="fsize">
      <button data-v="16">16</button><button data-v="24">24</button>
      <button data-v="32">32</button><button class="on" data-v="48">48</button>
      <button data-v="64">64</button><button data-v="96">96</button>
    </div>
    <span class="sub2" id="count"></span>
  </div>
</header>
<main>
  <div class="panel">
    <h3>Палитра и правила стиля</h3>
    <div class="pal">{pal}</div>
    <ul class="rules">
      <li><b>Сетка 32×32</b>, прозрачный фон, живая область 3…29 (отступ 3 px).</li>
      <li><b>Flat 2.0</b> — только сплошные цвета, без градиентов, теней и текстур.</li>
      <li><b>Двухслойная композиция</b>: базовый объект снизу, глиф-модификатор
        в правом нижнем углу (центр 24,24) с чистой высечкой радиусом 7,6 px.</li>
      <li><b>Толщины</b>: 2,0 основная · 1,5 второстепенная · 1,2 контур · 2,4 модификатор.
        Скругления 1,4 px, концы и соединения линий — круглые.</li>
      <li><b>Единый знак отметки</b> (полка + выноска + остриё) повторяется во всех
        «отметочных» командах — главный носитель узнаваемости набора.</li>
      <li><b>Цвет = семантика</b>: акцент — результат действия, нейтральный — источник,
        зелёный — включение/процесс, жёлтый — правка, красный — сброс/отключение.</li>
    </ul>
    <div class="note">Палитра взята из <code>ui/icons/README.md</code> репозитория и рассчитана
      на тёмный интерфейс AutoCAD / Civil 3D. На светлой теме базовый слой
      <code>#D9D9D9</code> выглядит бледно — это свойство самой спеки (как и у прежних иконок).
      Переключите тему, чтобы сравнить.</div>
    <details>
      <summary>Таблица соответствия: команда → файл иконки ({len(man)})</summary>
      <table><thead><tr><th>Команда</th><th>Назначение</th><th>Источник</th>
        <th>Файл в репозитории</th><th>Иконка</th></tr></thead><tbody>{rows}</tbody></table>
    </details>
  </div>
  {''.join(sections)}
  <div class="empty" id="empty">Ничего не найдено</div>
</main>

<div class="ov" id="ov"><div class="modal" id="modal"></div></div>

<script id="data" type="application/json">{payload}</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const uniq = (s, sfx) => {{
  let out = s.replace(/<title>[\\s\\S]*?<\\/title>/, '').replace(/\\s(width|height)="32"/g, '');
  (out.match(/\\sid="([^"]+)"/g) || []).forEach(m => {{
    const id = m.slice(5, -1);
    out = out.split('id="' + id + '"').join('id="' + id + '-' + sfx + '"')
             .split('url(#' + id + ')').join('url(#' + id + '-' + sfx + ')');
  }});
  return out;
}};
const cards = [...document.querySelectorAll('.card')];
let fsrc = 'all', q = '';

function apply() {{
  let n = 0;
  cards.forEach(c => {{
    const ok = (fsrc === 'all' || c.dataset.src === fsrc) &&
      (!q || (c.dataset.cmd + ' ' + c.dataset.title + ' ' + c.dataset.file + ' ' +
              c.dataset.desc).includes(q));
    c.style.display = ok ? '' : 'none';
    if (ok) n++;
  }});
  document.querySelectorAll('.grp').forEach(g => {{
    const vis = [...g.querySelectorAll('.card')].some(c => c.style.display !== 'none');
    g.style.display = vis ? '' : 'none';
  }});
  document.getElementById('count').textContent = n + ' / ' + cards.length;
  document.getElementById('empty').style.display = n ? 'none' : 'block';
}}
document.getElementById('q').addEventListener('input', e => {{
  q = e.target.value.trim().toLowerCase(); apply();
}});
document.getElementById('fsrc').addEventListener('click', e => {{
  if (e.target.tagName !== 'BUTTON') return;
  [...e.currentTarget.children].forEach(b => b.classList.toggle('on', b === e.target));
  fsrc = e.target.dataset.v; apply();
}});
document.getElementById('fsize').addEventListener('click', e => {{
  if (e.target.tagName !== 'BUTTON') return;
  [...e.currentTarget.children].forEach(b => b.classList.toggle('on', b === e.target));
  document.documentElement.style.setProperty('--size', e.target.dataset.v + 'px');
}});
const tbtn = document.getElementById('theme');
tbtn.addEventListener('click', () => {{
  const light = document.documentElement.dataset.theme === 'light';
  document.documentElement.dataset.theme = light ? 'dark' : 'light';
  tbtn.textContent = light ? '◐ Светлая тема' : '◑ Тёмная тема';
}});

const ov = document.getElementById('ov'), modal = document.getElementById('modal');
function open(i) {{
  const m = DATA[i];
  const sizes = [16, 24, 32, 48, 64].map((s, k) =>
    '<div><span class="ic" style="display:inline-block;width:' + s + 'px;height:' + s + 'px">' +
    uniq(m.svg, 'z' + k) + '</span><span>' + s + '</span></div>').join('');
  modal.innerHTML =
    '<div class="mhead"><div><div class="mcmd">' + m.cmd + '</div>' +
    '<div class="mttl">' + m.title + '</div><div class="mdesc">' + m.desc + '</div>' +
    '<div class="sub" style="margin-top:9px"><span class="tag ' + m.src + '">' +
    m.src.toUpperCase() + '</span><span class="org">' + m.origin + '</span></div></div>' +
    '<button class="x" id="cx">&times;</button></div>' +
    '<div class="views"><div class="view dark">' + uniq(m.svg, 'vd') +
    '<div class="vlab">тёмная тема CAD</div></div>' +
    '<div class="view light">' + uniq(m.svg, 'vl') +
    '<div class="vlab">светлая тема CAD</div></div></div>' +
    '<div class="sizes">' + sizes + '</div>' +
    '<pre id="code"></pre>' +
    '<div class="macts"><button class="btn" id="cp">Копировать SVG</button>' +
    '<a class="btn" id="dl" download="' + m.file + '.svg">↓ Скачать SVG</a>' +
    '<span class="org" style="align-self:center">svg/' + m.file + '.svg</span></div>';
  modal.querySelector('#code').textContent = m.svg;
  modal.querySelector('#cx').onclick = close;
  modal.querySelector('#cp').onclick = async ev => {{
    try {{ await navigator.clipboard.writeText(m.svg); ev.target.textContent = '✓ Скопировано'; }}
    catch (_) {{
      const t = document.createElement('textarea'); t.value = m.svg; document.body.appendChild(t);
      t.select(); document.execCommand('copy'); t.remove(); ev.target.textContent = '✓ Скопировано';
    }}
    setTimeout(() => ev.target.textContent = 'Копировать SVG', 1600);
  }};
  modal.querySelector('#dl').href = 'data:image/svg+xml;base64,' +
    btoa(unescape(encodeURIComponent(m.svg)));
  modal.querySelectorAll('.view svg, .sizes svg').forEach(s => {{
    s.removeAttribute('width'); s.removeAttribute('height');
    s.style.width = '100%'; s.style.height = '100%';
  }});
  ov.classList.add('on');
}}
function close() {{ ov.classList.remove('on'); }}
cards.forEach(c => c.addEventListener('click', () => open(+c.dataset.idx)));
ov.addEventListener('click', e => {{ if (e.target === ov) close(); }});
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') close(); }});
apply();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    out = os.path.join(ROOT, "gallery.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build())
    print(f"gallery: {out} ({os.path.getsize(out) / 1024:.0f} KB)")
