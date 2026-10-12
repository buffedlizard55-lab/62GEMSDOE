"""Tests for the docs renderer and its lossless guard.

`scripts/render_doc_pages.py` is the tool that lets `docs/*.md` be the source of truth while GitHub
Pages serves `docs/*.html`.  It is only trustworthy if (a) it reproduces the HTML conventions the
committed pages already use, (b) CI can prove a page is not stale, and (c) a page can never quietly
lose a sentence to a markdown gap -- which is what `verify_lossless` is for.  These tests exercise the
renderer directly; the repository's own pages are checked by the CI step, not re-parsed here.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_doc_pages", ROOT / "scripts/render_doc_pages.py")
rd = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rd)


def test_headings_paragraphs_and_inline_marks():
    md = "# Title\n\nSome **bold** and `code` and [a link](x.html).\n"
    html = rd.md_to_html(md)
    assert "<h1>Title</h1>" in html
    assert "<b>bold</b>" in html and "<code>code</code>" in html
    assert '<a href="x.html">a link</a>' in html
    assert html.count("<p>") == 1, "a wrapped markdown paragraph is ONE <p>"


def test_tables_lists_and_fences():
    md = ("| a | b |\n| --- | --- |\n| 1 | 2 |\n\n"
          "- one\n- two\n\n1. first\n2. second\n\n```json\n{\"k\": 1}\n```\n")
    html = rd.md_to_html(md)
    assert "<table><tr><th>a</th><th>b</th></tr>" in html
    assert "<tr><td>1</td><td>2</td></tr>" in html
    assert "<ul>\n<li>one</li>\n<li>two</li>\n</ul>" in html
    assert "<ol>\n<li>first</li>\n<li>second</li>\n</ol>" in html
    assert "<pre><code>{\"k\": 1}</code></pre>" in html
    assert "json" not in html.split("<pre>")[0], "the fence info string must not leak into text"


def test_list_continuations_join_into_the_item():
    md = "- a line that wraps\n  and continues\n- next item\n"
    html = rd.md_to_html(md)
    assert "<li>a line that wraps and continues</li>" in html
    assert "<p>" not in html, "the old renderer leaked continuations into stray paragraphs"


def test_lossless_guard_rejects_a_dropped_sentence():
    md = "## H\n\nA complete sentence here.\n\n## Two\n\nAnother sentence that must survive.\n"
    body = rd.md_to_html(md)
    rd.verify_lossless(md, body)                     # no exception
    broken = body.replace("Another sentence that must survive.", "")
    with pytest.raises(SystemExit) as e:
        rd.verify_lossless(md, broken)
    assert "LOSE or CHANGE" in str(e.value)


def test_html_special_characters_are_escaped_not_injected():
    html = rd.md_to_html("Compare a < b && c > d in prose.\n")
    assert "< b" not in html and "&amp;&amp;" in html and "&gt;" in html


RENDERED = rd.RENDERED          # the script owns the list; CI runs `--check` with no arguments
# Pages whose committed HTML is NOT generated from their markdown, and why. A hand-written pair is a
# standing exception only when it is named: `docs/hypotheses-2026-10-12.{md,html}` came in from session
# arena/778884cc with a styled, hand-built HTML page and a separate markdown draft, so rendering the
# markdown would destroy their layout -- and leaving it undeclared would let the next drift go unnoticed.
# Register entry IR-62-J-07 is the case this list exists to prevent.
HAND_WRITTEN = set(rd.HAND_WRITTEN)


@pytest.mark.parametrize("name", RENDERED)
def test_committed_pages_match_their_markdown(name):
    """The site's pages are rendered, not hand-edited -- so CI and this test agree with each other."""
    md = ROOT / "docs" / f"{name}.md"
    html = ROOT / "docs" / f"{name}.html"
    assert md.exists() and html.exists(), f"docs/{name}.md/.html must both be committed"
    body = rd.md_to_html(md.read_text())
    rd.verify_lossless(md.read_text(), body)
    lines = html.read_text().split("\n")
    k = next(i for i, ln in enumerate(lines) if "<body" in ln)
    existing = "\n".join(lines[k + 1:]).rsplit("\n</div></body></html>")[0]
    assert existing == body, (f"docs/{name}.html is stale: run "
                              f"`python3 scripts/render_doc_pages.py {name}`")


def test_check_flag_reports_staleness_in_ci(tmp_path):
    doc = tmp_path / "docs"
    doc.mkdir()
    (doc / "a.md").write_text("# A\n\ntext\n")
    (doc / "a.html").write_text("<html><body><div class='wrap'>\n<h1>A</h1>\n</div></body></html>")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/render_doc_pages.py"),
                        "--check", "--docs", str(doc), "a"], capture_output=True, text=True)
    assert r.returncode == 1 and "STALE" in r.stdout + r.stderr, r.stdout + r.stderr
    r2 = subprocess.run([sys.executable, str(ROOT / "scripts/render_doc_pages.py"),
                         "--docs", str(doc), "a"], capture_output=True, text=True)
    assert r2.returncode == 0 and "rendered a.html" in r2.stdout
    assert "<h1>A</h1>" in (doc / "a.html").read_text()


def test_undeclared_markdown_html_pairs_at_least_agree_on_being_present():
    """Any other `docs/*.md` with a sibling `.html` must be in one of the two lists above.

    Deliberately weak -- it only checks the HTML page still carries the markdown's title -- because the
    repository contains hand-written pages this lane does not own. What it prevents is the cheap failure:
    a page renamed on one side only (2026-10-12: two lanes both created `hypotheses-2026-10-12`, and this
    lane's was renamed with a lane suffix), or a `.md` whose `.html` was deleted and never noticed.
    """
    docs = ROOT / "docs"
    for md in sorted(docs.glob("*.md")):
        html = md.with_suffix(".html")
        if not html.exists() or md.stem in RENDERED or md.stem in HAND_WRITTEN:
            continue
        title = next((ln.lstrip("#").strip() for ln in md.read_text().split("\n")
                      if ln.startswith("# ")), "")
        assert title, f"{md.name} has no top-level heading"
        key = re.sub(r"<[^>]+>", "", title).split("—")[0].strip()
        assert key[:24] in html.read_text(), (
            f"{md.name} and {html.name} disagree on what the page is; either render it "
            f"(scripts/render_doc_pages.py {md.stem}) or declare it hand-written in this test")


def test_the_declared_lists_stay_disjoint_and_honest():
    """A page cannot be both rendered and exempt, and every exempt page must still be a real pair.

    CI checks `RENDERED`, so anything in it must render losslessly; anything in `HAND_WRITTEN` must be a
    page this repository genuinely does not own. An entry left in `HAND_WRITTEN` after its page was
    regenerated would silently exempt it from the guard forever, which is the drift `IR-62-J-07` records.
    """
    assert not (set(rd.RENDERED) & set(rd.HAND_WRITTEN)), "a page is both rendered and exempt"
    for name in rd.RENDERED:
        assert (ROOT / "docs" / f"{name}.md").exists(), f"RENDERED lists {name}, which has no markdown"
        assert (ROOT / "docs" / f"{name}.html").exists(), f"{name}.md has no committed page to check"
    for name, why in rd.HAND_WRITTEN.items():
        assert (ROOT / "docs" / f"{name}.html").exists(), f"exempt page {name} is gone; unlist it"
        assert why.strip(), f"exempt page {name} has no reason recorded"
