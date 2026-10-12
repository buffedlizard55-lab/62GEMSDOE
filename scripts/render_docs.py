#!/usr/bin/env python3
import html
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]

def md_to_html(text: str) -> str:
    lines = text.split('\n')
    out = []
    in_table = False
    in_code = False
    in_list = False

    for line in lines:
        if line.startswith('```'):
            if in_code:
                out.append('</code></pre>')
                in_code = False
            else:
                out.append('<pre><code>')
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue

        if line.startswith('|') and line.endswith('|'):
            if '---' in line:
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if not in_table:
                out.append('<table><thead><tr>' + ''.join(f'<th>{html.escape(c)}</th>' for c in cells) + '</tr></thead><tbody>')
                in_table = True
            else:
                out.append('<tr>' + ''.join(f'<td>{html.escape(c)}</td>' for c in cells) + '</tr>')
            continue
        else:
            if in_table:
                out.append('</tbody></table>')
                in_table = False

        if line.startswith('- ') or line.startswith('* '):
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append(f'<li>{html.escape(line[2:])}</li>')
            continue
        else:
            if in_list:
                out.append('</ul>')
                in_list = False

        if line.startswith('# '):
            out.append(f'<h1>{html.escape(line[2:])}</h1>')
        elif line.startswith('## '):
            out.append(f'<h2>{html.escape(line[3:])}</h2>')
        elif line.startswith('### '):
            out.append(f'<h3>{html.escape(line[4:])}</h3>')
        elif line.strip() == '---':
            out.append('<hr>')
        elif line.strip():
            # Format bold and code inline
            p = html.escape(line)
            p = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', p)
            p = re.sub(r'`(.+?)`', r'<code>\1</code>', p)
            out.append(f'<p>{p}</p>')

    if in_table: out.append('</tbody></table>')
    if in_list: out.append('</ul>')
    if in_code: out.append('</code></pre>')
    return '\n'.join(out)

for name in ['docs/research/why-02778-scored', 'docs/hypotheses-2026-10-12']:
    src_file = ROOT / f'{name}.md'
    if not src_file.exists():
        continue
    src = src_file.read_text()
    title = src.split('\n')[0].replace('#', '').strip()
    body = md_to_html(src)
    nav_prefix = "../" if "research/" in name else ""
    doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — 62GEMSDOE</title>
<style>
:root{{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff;--ok:#3fb950;--no:#f85149;--warn:#d29922;--card:#161b22;--bd:#30363d}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
.wrap{{max-width:1040px;margin:0 auto;padding:24px 20px 80px}}
h1{{font-size:1.9em;margin:.2em 0 .1em}}h2{{font-size:1.35em;margin:1.6em 0 .5em;border-bottom:1px solid var(--bd);padding-bottom:.3em}}
h3{{font-size:1.1em;margin:1.2em 0 .4em}}a{{color:var(--acc);text-decoration:none}}a:hover{{text-decoration:underline}}
code{{background:#1f2630;padding:.12em .35em;border-radius:4px;font-size:.9em}}pre{{background:#1f2630;padding:12px;border-radius:6px;overflow:auto}}
table{{border-collapse:collapse;width:100%;margin:.8em 0;font-size:.9em}}th,td{{border:1px solid var(--bd);padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:#1f2630}}.mut{{color:var(--mut)}}nav{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 20px}}
nav a{{background:var(--card);border:1px solid var(--bd);border-radius:20px;padding:5px 13px;font-size:.87em}}
</style></head><body><div class="wrap">
<header><h1>{title}</h1><p class="mut">DOE GEMS Prize · 62GEMSDOE · Session 2026-10-12</p></header>
<nav>
  <a href="{nav_prefix}index.html">← Overview</a>
  <a href="{nav_prefix}executive-summary.html">How to Submit (Download)</a>
  <a href="{nav_prefix}research/why-02778-scored.html">Why 0.2778 Scored</a>
  <a href="{nav_prefix}hypotheses-2026-10-12.html">Candidate Hypotheses</a>
</nav>
<main>{body}</main>
<footer><p class="mut">62GEMSDOE · Datum-offset lane</p></footer>
</div></body></html>'''
    (ROOT / f'{name}.html').write_text(doc)
    print('Wrote', f'{name}.html')
