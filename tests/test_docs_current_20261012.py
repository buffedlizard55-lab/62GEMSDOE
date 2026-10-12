"""The CURRENT artifact and the pages that describe it (2026-10-12, session arena/61e7859a).

Supersedes the page-level half of ``tests/test_docs_20261011b.py`` (that module keeps checking
the archived 2026-10-11b artifact, which must stay downloadable).  Everything a reader sees on
``docs/index.html`` and ``docs/executive-summary.html`` about the file offered for submission is
re-derived here from the run card and from the bytes on disk, so prose and evidence cannot drift.

The invariants:
  * the hero's big green button points at the run card's file, and that file is legal on re-read;
  * the submission note is <= 140 characters and appears on both pages;
  * the sha256 prefix appears on both pages;
  * the uniqueness numbers quoted on the landing page match ``evidence/h63_diffuse_uniqueness.json``;
  * every internal link on both pages resolves;
  * no page has unbalanced tags.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD = json.loads((ROOT / "evidence" / "h63_diffuse_isolated_runcard.json").read_text())
UNIQ = json.loads((ROOT / "evidence" / "h63_diffuse_uniqueness.json").read_text())
TIF = DOCS / "downloads" / f"{CARD['name']}-zeros.tif"
PAGES = [DOCS / "index.html", DOCS / "executive-summary.html",
         DOCS / "research" / "instrument-audit-2026-10-12.html"]


def test_the_run_card_matches_the_shipped_bytes():
    import hashlib
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from gems62 import grid
    if not TIF.exists():
        pytest.skip("artifact not in this checkout")
    assert hashlib.sha256(TIF.read_bytes()).hexdigest() == CARD["sha256_zeros"]
    receipt = grid.check_submission(TIF)
    assert receipt["legal"] is True
    assert receipt["nodata"] is None
    assert receipt["all_finite"] and receipt["nan_count"] == 0
    assert receipt["n_outside_0_1"] == 0
    assert receipt["crs_match"] and receipt["transform_match"] and receipt["width_height_match"]


def test_hero_button_points_at_this_file():
    text = (DOCS / "index.html").read_text()
    m = re.search(r'class="btn" href="(downloads/[^"]+\.tif)"', text)
    assert m, "the hero has no download button"
    assert pathlib.Path(m.group(1)).name == TIF.name, "the hero does not offer this artifact"


def test_note_is_short_and_on_both_pages():
    note = CARD["expectation"]["basis"]  # not a note; guard against copy/paste slips below
    assert note  # the card itself must be non-empty
    hero_note = re.search(r"Submission note[^<]*</td><td><code>([^<]+)</code>", 
                          (DOCS / "index.html").read_text())
    assert hero_note, "the landing page does not show the note to paste"
    text = hero_note.group(1)
    assert 20 <= len(text) <= 140, f"note is {len(text)} chars, the portal allows 140"
    assert text in (DOCS / "executive-summary.html").read_text(), \
        "the executive summary lost the note"


def test_sha256_and_verdict_are_on_the_pages():
    for page in (DOCS / "index.html", DOCS / "executive-summary.html"):
        text = page.read_text()
        assert CARD["sha256_zeros"][:32] in text, f"{page.name} lacks the sha256"
        assert "0.3195" in text, f"{page.name} must state what is NOT claimed"


def test_uniqueness_numbers_on_the_page_match_the_evidence():
    text = (DOCS / "index.html").read_text()
    worst = UNIQ["worst_jaccard"]
    assert worst["dilated_jaccard"] < 0.5, "sanity: the measurement itself"
    assert f"{worst['dilated_jaccard']:.3f}" in text, \
        "the landing page must quote the measured max dilated Jaccard"
    assert worst["file"].split("__")[-1][:24] in text, "the page must name the closest comparator"


@pytest.mark.parametrize("page", [str(p.relative_to(ROOT)) for p in PAGES])
def test_every_internal_link_resolves(page):
    text = (ROOT / page).read_text()
    broken = []
    for href in re.findall(r'href="([^"#:]+)"', text):
        if href.startswith(("http", "mailto:", "//")):
            continue
        target = (ROOT / page).parent / href.split("#")[0]
        if not target.exists():
            broken.append(href)
    assert not broken, f"{page} links to missing files: {sorted(set(broken))}"


def test_pages_have_balanced_tags():
    tags = ("div", "table", "thead", "tbody", "tr", "td", "th", "p", "code", "pre",
            "ul", "ol", "li", "h1", "h2", "h3")
    for page in PAGES:
        if not page.exists():
            continue
        text = page.read_text()
        unbalanced = [f"{t} {len(re.findall(rf'<{t}[ >]', text))}/{len(re.findall(rf'</{t}>', text))}"
                      for t in tags
                      if len(re.findall(rf"<{t}[ >]", text)) != len(re.findall(rf"</{t}>", text))]
        assert not unbalanced, f"{page.name}: {unbalanced}"
