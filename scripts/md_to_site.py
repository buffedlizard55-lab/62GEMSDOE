#!/usr/bin/env python3
"""Render the session's markdown pages as HTML in the site's own style.

Deliberately small and closed: it supports exactly the constructs the pages in
``docs/`` use -- ATX headings, pipe tables, `-` and `1.` lists, fenced and inline
code, **bold**, *italic*, [links](url), `>` blockquotes, `---` rules and paragraphs.
Anything it does not recognise is emitted as an escaped paragraph, so a construct it
cannot render can never silently disappear (the failure mode that produced
``IR-62-12``, a figure that "succeeded" while writing nothing).

Usage:  .venv/bin/python scripts/md_to_site.py docs/executive-summary-h62r.md ...
"""
from __future__ import annotations

import html
import pathlib
import re
import sys

CSS = """
:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff;--ok:#3fb950;--no:#f85149;--warn:#d29922;--card:#161b22;--bd:#30363d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
 font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1020px;margin:0 auto;padding:24px 20px 90px}
h1{font-size:1.85em;margin:.2em 0 .1em}h2{font-size:1.3em;margin:1.7em 0 .5em;border-bottom:1px solid var(--bd);padding-bottom:.3em}
h3{font-size:1.06em;margin:1.2em 0 .4em}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
code{background:#1f2630;padding:.12em .35em;border-radius:4px;font-size:.9em;word-break:break-word}
pre{background:#1f2630;padding:12px;border-radius:6px;overflow:auto;font-size:.85em}
table{border-collapse:collapse;width:100%;margin:.9em 0;font-size:.9em;display:block;overflow-x:auto}
th,td{border:1px solid var(--bd);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#1f2630}
blockquote{border-left:3px solid var(--bd);margin:1em 0;padding:.2em 1em;color:var(--mut)}
hr{border:0;border-top:1px solid var(--bd);margin:1.6em 0}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 6px}
nav a{background:var(--card);border:1px solid var(--bd);border-radius:20px;padding:5px 13px;font-size:.87em}
.mut{color:var(--mut)}
"""

NAV = """
<nav>
<a href="index.html">Home</a>
<a href="executive-summary-h62r.html">How to submit (H62-R)</a>
<a href="hypotheses-h62r.html">Hypotheses (H62-R)</a>
<a href="h62r/h62r_shoreline_profiles.png">Profiles (first deliverable)</a>
<a href="h62r/h62r_level_spectrum.png">Level spectrum</a>
<a href="h62r/h62r_field_map.png">Field map</a>
<a href="downloads/gems62-h62r-multilevel-datum-repeat-offset-zeros.tif">⬇ Download GeoTIFF</a>
<a href="irregularities.html">Irregularities</a>
<a href="research/leaderboard-arithmetic.html">Why 0.2778 won</a>
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Leaderboard ↗</a>
</nav>
"""


def _inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def convert(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre>" + html.escape("\n".join(buf)) + "</pre>")
            continue
        if re.match(r"^#{1,3} ", ln):
            lvl = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{lvl}>{_inline(ln[lvl + 1:])}</h{lvl}>")
            i += 1
            continue
        if ln.strip() == "---":
            out.append("<hr>"); i += 1; continue
        if ln.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").strip()); i += 1
            out.append("<blockquote>" + _inline(" ".join(buf)) + "</blockquote>")
            continue
        if ln.startswith("|"):
            buf = []
            while i < len(lines) and lines[i].startswith("|"):
                buf.append(lines[i]); i += 1
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in buf]
            body = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
            head, rest = body[0], body[1:]
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{_inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r)
                                 + "</tr>" for r in rest)
                       + "</tbody></table>")
            continue
        m = re.match(r"^\s*[-*] (.*)$", ln)
        m2 = re.match(r"^\s*\d+\. (.*)$", ln)
        if m or m2:
            ordered = bool(m2)
            items = []
            while i < len(lines):
                a = re.match(r"^\s*[-*] (.*)$", lines[i])
                b = re.match(r"^\s*\d+\. (.*)$", lines[i])
                if ordered and b:
                    items.append(b.group(1)); i += 1
                elif not ordered and a:
                    items.append(a.group(1)); i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if ln.strip() == "":
            i += 1
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,3} |\||>|```|\s*[-*] |\s*\d+\. |---$)", lines[i]):
            buf.append(lines[i]); i += 1
        para = " ".join(buf)
        if para.startswith("*") and para.endswith("*") and not para.startswith("**"):
            out.append(f'<p class="mut">{_inline(para)}</p>')
        else:
            out.append(f"<p>{_inline(para)}</p>")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    for src in argv:
        p = pathlib.Path(src)
        title = p.stem.replace("-", " ")
        body = convert(p.read_text())
        out = p.with_suffix(".html")
        out.write_text(
            "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)} · 62GEMSDOE</title><style>{CSS}</style></head>"
            f"<body><div class=\"wrap\">{NAV}{body}</div></body></html>\n")
        print(f"{src} -> {out}  ({len(body)} chars of body)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
