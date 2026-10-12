#!/usr/bin/env python3
"""Render `docs/*.md` into the sibling `docs/*.html` that GitHub Pages serves.

Why this exists: the site's prose lives in markdown, but Pages serves HTML, and
`scripts/make_site.py` -- which owns the *other* pages -- is a token-substitution generator that
rewrites `docs/index.html` from a stale template.  Importing it to reuse its markdown function
would therefore clobber the hand-maintained home page.  So this script reuses only what is safe:
it keeps each target page's existing `<head>` and back-link byte-for-byte and replaces the body
with a rendered version of the markdown file next to it.

The subset supported is the one these documents use: `#`-headings, paragraphs, `-`/`*` and
numbered lists, blockquotes, `---`, tables (`|`-rows), `` `code` ``, `**bold**`, `*italic*` and
`[text](url)`.  Nothing is invented and nothing is dropped.

    python3 scripts/render_doc_pages.py irregularities next-steps run-card hypotheses-2026-10-12
"""
from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", t)
    return t


def md_to_html(md: str) -> str:
    """Render the markdown subset these documents use.

    Written to reproduce, byte for byte, the HTML the previous sessions committed: a paragraph is
    one `<p>` whose source lines are joined with a space, a table is `<table>` with one `<tr>` per
    line and no `thead`/`tbody`, a fence is `<pre><code>`, a blockquote is one line. The byte
    identity is the point -- `--check` then fails on a stale page, and a re-render shows up in
    `git diff` only where the markdown actually changed.
    """
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.rstrip()
        if not s.strip():
            i += 1
            continue
        if s.strip().startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].rstrip().startswith("|"):
                cells = [x.strip() for x in lines[i].rstrip().strip("|").split("|")]
                i += 1
                if set("".join(cells)) <= set("-: "):
                    continue
                tag = "th" if not rows else "td"
                rows.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            out.append("<table>" + "\n".join(rows) + "</table>")
            continue
        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].rstrip().startswith(">"):
                buf.append(lines[i].rstrip().lstrip(">").strip()); i += 1
            out.append("<blockquote>" + inline(" ".join(x for x in buf if x)) + "</blockquote>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            i += 1
            continue
        if s.strip() == "---":
            out.append("<hr>")
            i += 1
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", s)
        if m:
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i].rstrip()))
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
                    items[-1] += " " + lines[i].strip(); i += 1
            out.append("<ul>\n" + "\n".join(f"<li>{inline(x)}</li>" for x in items) + "\n</ul>")
            continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", s)
        if m:
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i].rstrip()))
                i += 1
                while i < len(lines) and lines[i].startswith("   ") and lines[i].strip():
                    items[-1] += " " + lines[i].strip(); i += 1
            out.append("<ol>\n" + "\n".join(f"<li>{inline(x)}</li>" for x in items) + "\n</ol>")
            continue
        buf = [s]
        i += 1
        while i < len(lines):
            nxt = lines[i].rstrip()
            if (not nxt.strip() or nxt.startswith(("#", "|", ">", "```"))
                    or re.match(r"^\s*([-*]|\d+\.)\s+", nxt) or nxt.strip() == "---"):
                break
            buf.append(nxt)
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out)


def plain(t: str) -> list[str]:
    """Words only -- the lossless guard compares this on both sides of the render."""
    t = re.sub(r"<[^>]+>", " ", t)
    t = (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'"))
    return [w for w in re.split(r"[\s`*_|]+", t) if w]


def verify_lossless(md: str, body: str) -> None:
    """Refuse to write a page whose *words* are not the markdown's words.

    The markdown side is reduced to the same thing the renderer keeps: structural markers removed
    (rules, table separators, leading pipes, heading/list/blockquote markers), link labels kept and
    link targets dropped (they become an href, which `plain` strips), emphasis and code ticks gone.
    If the two word lists differ at any position the render is refused, so a page can never quietly
    lose a sentence to a parser gap.
    """
    md = re.sub(r"^```[^`\n]*$", " ", md, flags=re.M)     # fence lines, incl. ```json info strings
    md = re.sub(r"^ {0,3}(-{3,}|\*\*\*|_{3,}) *$", " ", md, flags=re.M)
    md = re.sub(r"^\s*[|\-: ]+$", " ", md, flags=re.M)
    md = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", r"\1", md)
    md = re.sub(r"^[ \t]*[-*] +", "", md, flags=re.M)
    md = re.sub(r"^[ \t]*\d+\. +", "", md, flags=re.M)
    md = re.sub(r"^ *>", "", md, flags=re.M)
    md = re.sub(r"^ {0,3}#{1,6} +", "", md, flags=re.M)
    md = re.sub(r"^\s*\|", " ", md, flags=re.M)
    md = re.sub(r"\\([*_`])", " ", md)
    md = md.replace("*", " ").replace("`", " ").replace("|", " ")
    src, got = plain(md), plain(body)
    if src != got:
        for i, (x, y) in enumerate(zip(src, got)):
            if x != y:
                raise SystemExit(f"render would LOSE or CHANGE text at word {i}: md has {x!r}, "
                                 f"html has {y!r} -- refusing to write")
        at = min(len(src), len(got))
        extra = (f"; md continues with {src[at:at + 4]!r}" if len(src) > at
                 else f"; html continues with {got[at:at + 4]!r}" if len(got) > at else "")
        raise SystemExit(f"render would LOSE or CHANGE text at word {at}: {len(src)} words in, "
                         f"{len(got)} out{extra} -- refusing to write")


def render(name: str, *, check_only: bool = False, docs: pathlib.Path = DOCS) -> int:
    md_path, html_path = docs / f"{name}.md", docs / f"{name}.html"
    if not md_path.exists():
        print(f"skip {name}: no {md_path.name}")
        return 0
    md_text = md_path.read_text()
    body = md_to_html(md_text)
    verify_lossless(md_text, body)
    if html_path.exists():
        cur = html_path.read_text()
        lines = cur.split("\n")
        k = next((i for i, ln in enumerate(lines) if "<body" in ln), None)
        if k is None or "</body>" in lines[k]:
            print(f"{name}: existing html is not in the expected shape; writing a full page")
        else:
            prefix = "\n".join(lines[:k + 1])
            tail = "</div></body></html>"
            new = prefix + "\n" + body + "\n" + tail
            if new == cur:
                print(f"ok {name}.html already matches {name}.md")
                return 0
            if check_only:
                print(f"STALE {name}.html -- re-render with scripts/render_doc_pages.py {name}")
                return 1
            html_path.write_text(new)
            print(f"rendered {name}.html from {name}.md ({len(new):,} B), head and back-link kept")
            return 0
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{name}</title></head><body><div class='wrap'>\n{body}\n</div></body></html>")
    if check_only:
        print(f"MISSING {name}.html")
        return 1
    html_path.write_text(page)
    print(f"wrote {name}.html")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="doc basenames without extension")
    ap.add_argument("--all", action="store_true", help="every docs/*.md with a sibling .html")
    ap.add_argument("--docs", default=str(DOCS), help="directory holding the md/html pairs "
                                                     "(the repository's docs/ by default)")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any page is stale, without writing (for CI)")
    args = ap.parse_args()
    names = list(args.names)
    if args.all:
        names = sorted(p.stem for p in DOCS.glob("*.md"))
    if not names:
        names = ["irregularities", "next-steps", "run-card"]
    docs = pathlib.Path(args.docs).resolve()
    rc = 0
    for n in names:
        rc |= render(n, check_only=args.check, docs=docs)
    return rc


if __name__ == "__main__":
    sys.exit(main())
