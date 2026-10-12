#!/usr/bin/env python3
"""Render the canonical markdown documents into the docs/ site for session 2026-10-12.

Presentation only: ``docs/irregularities.md`` and ``docs/next-steps.md`` are the auditable sources;
this script converts them to HTML with the same renderer the previous session used, and stamps every
page with the current run card's sha256 and verdict so a stale page cannot survive a re-run.

    python3 scripts/make_site_md_20261012.py
"""
from __future__ import annotations

import html
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD = json.loads((ROOT / "evidence/run_card_20261012.json").read_text())

sp = importlib.util.spec_from_file_location("prev", ROOT / "scripts/make_site_20261011b.py")
prev = importlib.util.module_from_spec(sp)
sp.loader.exec_module(prev)

NAV = """<nav>
<a href="index.html">Verdict &amp; download</a>
<a href="executive-summary-2026-10-12.html">How to submit</a>
<a href="irregularities.html">Irregularities</a>
<a href="next-steps.html">Next steps</a>
<a href="index-2026-10-11b-superseded.html">Previous session</a>
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">Competition ↗</a>
</nav>"""

PAGES = [("irregularities.md", "irregularities.html", "Irregularities register — 62GEMSDOE"),
         ("next-steps.md", "next-steps.html", "Next steps — 62GEMSDOE")]


def main() -> int:
    for src, dst, title in PAGES:
        body = prev.md_to_html((DOCS / src).read_text())
        page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                f"<title>{html.escape(title)}</title><style>{prev.CSS}</style></head><body>"
                f"<div class=\"wrap\">{NAV}{body}"
                "<p class=\"mut\" style=\"margin-top:3em;font-size:.85em\">Rendered by "
                "<code>scripts/make_site_md_20261012.py</code> from "
                f"<code>docs/{src}</code>. Current artifact <code>{CARD['slug']}.tif</code>, sha256 "
                f"<code>{CARD['raster_sha256'][:16]}…</code>, verdict "
                f"<b>{CARD['verdict_label']}</b>.</p></div></body></html>\n")
        (DOCS / dst).write_text(page)
        print(f"wrote docs/{dst} ({len(page):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
