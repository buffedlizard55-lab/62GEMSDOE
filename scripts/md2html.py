#!/usr/bin/env python3
"""Render a small, well-behaved subset of Markdown into the site's page shell.

Supported: ATX headings (#..######), fenced code blocks, tables (pipe rows with a --- separator),
unordered/ordered lists, blockquotes, horizontal rules, paragraphs, and inline
``code`` / **bold** / *italic* / [text](url).  Everything else is passed through verbatim.
This exists so the site's prose pages have one source of truth in Markdown and one consistent
HTML shell; it is not a general Markdown parser.
"""
from __future__ import annotations

import html
import os
import pathlib
import re
import sys

SHELL = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{css}">
</head><body>
<header>
  <span class="brand">62GEMSDOE</span>
  <nav>
{nav}
  </nav>
</header>
<main>
{body}
</main>
<footer>62GEMSDOE · datum-offset lane · every number on this site is labelled MEASURED,
OWNER-REPORTED, OFFICIAL or MODEL; a projection is never written as a score.</footer>
</body></html>
"""

NAV = [
    ("index.html", "Download &amp; verdict"),
    ("executive-summary.html", "How to submit"),
    ("results.html", "Results"),
    ("method.html", "Method"),
    ("hypotheses-2026-10-12.html", "Hypotheses"),
    ("run-card.html", "Run card"),
    ("irregularities.html", "Irregularities"),
    ("next-steps.html", "Next steps"),
]


def inline(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "`":
            j = s.find("`", i + 1)
            if j == -1:
                out.append(ch); i += 1; continue
            out.append("<code>" + html.escape(s[i + 1:j]) + "</code>")
            i = j + 1
        elif ch == "[":
            m = re.match(r"\[([^\]]+)\]\(([^)\s]+)\)", s[i:])
            if m:
                out.append(f'<a href="{html.escape(m.group(2))}">{inline(m.group(1))}</a>')
                i += m.end()
            else:
                out.append(ch); i += 1
        elif s.startswith("**", i):
            j = s.find("**", i + 2)
            if j == -1:
                out.append("**"); i += 2; continue
            out.append("<b>" + inline(s[i + 2:j]) + "</b>")
            i = j + 2
        elif ch == "*" or ch == "_":
            j = s.find(ch, i + 1)
            if j == -1:
                out.append(ch); i += 1; continue
            out.append("<i>" + inline(s[i + 1:j]) + "</i>")
            i = j + 1
        else:
            out.append(html.escape(ch)); i += 1
    return "".join(out)


def render(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    para: list[str] = []
    list_stack: list[str] = []
    li_buf: list[str] = []

    def flush_para() -> None:
        if para:
            out.append("<p>" + inline(" ".join(para).strip()) + "</p>")
            para.clear()

    def flush_li() -> None:
        if li_buf:
            out.append("<li>" + inline(" ".join(li_buf).strip()) + "</li>")
            li_buf.clear()

    def close_lists() -> None:
        flush_li()
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_para(); close_lists()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue
        if stripped.startswith("<"):
            # raw HTML pass-through (anchors, embedded tables, …)
            flush_para(); close_lists(); out.append(line.rstrip()); i += 1; continue
        if not stripped:
            flush_para(); close_lists(); i += 1; continue
        if stripped.startswith("---") and set(stripped) <= set("-"):
            flush_para(); close_lists(); out.append("<hr>"); i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            flush_para(); close_lists()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>" + inline(m.group(2)) + f"</h{lvl}>")
            i += 1; continue
        if stripped.startswith("|"):
            flush_para(); close_lists()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(row); i += 1
            sep = None
            body = rows
            if len(rows) > 1 and all(set(c) <= set(":- ") and "-" in c for c in rows[1]):
                sep, body = rows[0], rows[2:]
            out.append("<table>")
            if sep:
                out.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in sep) + "</tr>")
            for r in body:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            out.append("</table>")
            continue
        m = re.match(r"^([-*]|\d+\.)\s+(.*)$", stripped)
        if m:
            flush_para()
            tag = "ul" if m.group(1) in ("-", "*") else "ol"
            flush_li()
            if not list_stack or list_stack[-1] != tag:
                out.append(f"<{tag}>"); list_stack.append(tag)
            li_buf.append(m.group(2))
            i += 1; continue
        # lazy continuation of a hard-wrapped list item
        if li_buf and line[:1] in (" ", "\t") and not stripped.startswith("|"):
            li_buf.append(stripped); i += 1; continue
        if stripped.startswith(">"):
            flush_para(); close_lists()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip("> ").strip()); i += 1
            out.append("<blockquote>" + inline(" ".join(quote)) + "</blockquote>")
            continue
        para.append(stripped); i += 1
    flush_para(); close_lists()
    return "\n".join(out)


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2])
    title = sys.argv[3]
    css = sys.argv[4] if len(sys.argv) > 4 else "assets/site.css"
    cur = os.path.basename(dst)
    def navitem(h, label):
        cls = ' class="active"' if h == cur else ""
        return f'    <a{cls} href="{h}">{label}</a>'
    nav = "\n".join(navitem(href, label) for href, label in NAV)
    dst.write_text(SHELL.format(title=html.escape(title), css=css, nav=nav,
                                body=render(src.read_text())))
    print(f"{src} -> {dst} ({dst.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
