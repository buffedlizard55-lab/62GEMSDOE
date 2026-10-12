#!/usr/bin/env python3
"""Render this session's markdown pages into the docs/ site.

Presentation only: the markdown files are the canonical, auditable documents; this script
wraps them in the site stylesheet so that the download page and the verdict are the first
thing a visitor sees.  It does *not* compute or substitute any number — every figure in the
pages is written by the scripts that measured it, and cross-checked by
``tests/test_site_20261011b.py`` against the evidence JSON.

Usage: python3 scripts/make_site_20261011b.py
"""
from __future__ import annotations

import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PAGES = [
    ("executive-summary-2026-10-11b.md", "executive-summary-2026-10-11b.html",
     "Executive summary — how to submit, and the verdict"),
    ("hypotheses-2026-10-11b.md", "hypotheses-2026-10-11b.html",
     "Five candidate hypotheses, ranked"),
    ("research/beating-02778-2026-10-11b.md", "research/beating-02778-2026-10-11b.html",
     "Why 0.2778 scores what it scores — and the exact condition for beating it"),
]

CSS = """
:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff;--ok:#3fb950;--no:#f85149;
--warn:#d29922;--card:#161b22;--bd:#30363d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:24px 20px 80px}
h1{font-size:1.8em;margin:.3em 0 .4em}h2{font-size:1.3em;margin:1.6em 0 .5em;
border-bottom:1px solid var(--bd);padding-bottom:.3em}h3{font-size:1.05em;margin:1.2em 0 .4em}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
code{background:#1f2630;padding:.12em .35em;border-radius:4px;font-size:.88em}
table{border-collapse:collapse;width:100%;margin:.9em 0;font-size:.9em}
th,td{border:1px solid var(--bd);padding:6px 9px;text-align:left;vertical-align:top}
th{background:#1f2630}blockquote{border-left:3px solid var(--acc);margin:1em 0;padding:.2em 1em;
background:var(--card)}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 8px}
nav a{background:var(--card);border:1px solid var(--bd);border-radius:20px;padding:5px 13px;font-size:.87em}
.btn{display:inline-block;background:#238636;color:#fff;font-weight:600;padding:12px 22px;
border-radius:8px;margin:8px 8px 8px 0}.btn:hover{background:#2ea043;text-decoration:none}
.btn.sec{background:#30363d}
"""

NAV_ITEMS = [
    ("index.html", "Overview &amp; download"),
    ("executive-summary-2026-10-11b.html", "How to submit"),
    ("hypotheses-2026-10-11b.html", "Hypotheses"),
    ("research/beating-02778-2026-10-11b.html", "Why 0.2778 won"),
    ("irregularities.html", "Irregularities"),
    ("https://www.drivendata.org/competitions/306/competition-doe-gems/", "Competition ↗"),
]


def nav_for(depth: int) -> str:
    """Relative links, correct for the depth the page is written at.

    The site is published from the repository root, so a page at ``docs/`` reaches a page at
    ``docs/research/`` with a plain path and a page at ``docs/research/`` needs ``../``.  Getting
    this wrong 404s the download button, which is the one failure that would matter.
    """
    up = "../" * depth
    items = []
    for href, label in NAV_ITEMS:
        if href.startswith("http"):
            items.append(f'<a href="{href}">{label}</a>')
        else:
            items.append(f'<a href="{up}{href}">{label}</a>')
    return "<nav>\n" + "\n".join(items) + "\n</nav>"


NAV = nav_for(0)  # kept for backwards compatibility with older callers


def md_to_html(md: str) -> str:
    def inline(t: str) -> str:
        t = html.escape(t, quote=False)
        t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
        return t

    out: list[str] = []
    in_tbl = in_ul = in_ol = in_bq = False

    def close() -> None:
        nonlocal in_tbl, in_ul, in_ol, in_bq
        if in_tbl:
            out.append("</tbody></table>"); in_tbl = False
        if in_ul:
            out.append("</ul>"); in_ul = False
        if in_ol:
            out.append("</ol>"); in_ol = False
        if in_bq:
            out.append("</blockquote>"); in_bq = False

    for line in md.split("\n"):
        s = line.rstrip()
        if s.startswith("|"):
            cells = [x.strip() for x in s.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not in_tbl:
                close()
                out.append("<table><thead><tr>"
                           + "".join(f"<th>{inline(x)}</th>" for x in cells)
                           + "</tr></thead><tbody>")
                in_tbl = True
            else:
                out.append("<tr>" + "".join(f"<td>{inline(x)}</td>" for x in cells) + "</tr>")
            continue
        if in_tbl:
            close()
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            close()
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            continue
        if s.startswith(">"):
            if not in_bq:
                close(); out.append("<blockquote>"); in_bq = True
            out.append(f"<p>{inline(s.lstrip('> '))}</p>")
            continue
        if in_bq:
            close()
        m = re.match(r"^\s*[-*]\s+(.*)$", s)
        if m:
            if not in_ul:
                close(); out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", s)
        if m:
            if not in_ol:
                close(); out.append("<ol>"); in_ol = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        if not s:
            close()
            continue
        close()
        out.append(f"<p>{inline(s)}</p>")
    close()
    return "\n".join(out)


def main() -> int:
    card = json.loads((ROOT / "evidence" / "run_card_20261011b.json").read_text())
    built = []
    for src, dst, title in PAGES:
        md = (DOCS / src).read_text()
        body = md_to_html(md)
        depth = dst.count("/")
        nav = nav_for(depth)
        page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"
                f"<div class=\"wrap\">{nav}{body}"
                "<p class=\"mut\" style=\"margin-top:3em;font-size:.85em\">Rendered by "
                "<code>scripts/make_site_20261011b.py</code> from "
                f"<code>docs/{src}</code>. Artifact sha256 "
                f"<code>{card['raster_sha256'][:16]}…</code>, verdict "
                f"<b>{card['verdict']}</b>.</p></div></body></html>\n")
        (DOCS / dst).write_text(page)
        built.append(str(DOCS / dst))
    print("\n".join(built))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
