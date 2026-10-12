"""Contract tests for the 2026-10-12 session's pages and artifact.

Same contract the 2026-10-11b module enforces, re-pointed at the current run card:
the note fits the portal and appears on the hero and the executive summary, the sha256
on the pages is the sha of the shipped bytes, the download button points at the current
artifact, and every internal link on the pages this session generated resolves.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD = json.loads((ROOT / "evidence" / "run_card_20261012.json").read_text())
E7 = json.loads((ROOT / "evidence" / "e7_emit_20261012.json").read_text())

TIF = DOCS / "downloads" / f"{CARD['submission_name']}.tif"
PAGES = [DOCS / "index.html", DOCS / "executive-summary-2026-10-12.html",
         DOCS / "hypotheses-2026-10-12.html", DOCS / "run-card-2026-10-12.html"]


def test_note_fits_the_portal_limit_and_is_on_the_hero():
    note = CARD["submission_note"]
    assert len(note) <= 140, f"note is {len(note)} chars, the portal allows 140"
    assert len(note) >= 20
    hero = (DOCS / "index.html").read_text()
    import html as _html
    assert note in hero or _html.escape(note, quote=False) in hero, \
        "the hero does not show the note to paste"
    md = (DOCS / "executive-summary-2026-10-12.md").read_text()
    assert note in md, "the executive summary does not show the note to paste"


def test_card_sha256_is_the_sha256_of_the_shipped_file():
    if not TIF.exists():
        pytest.skip("artifact not in this checkout")
    h = hashlib.sha256(TIF.read_bytes()).hexdigest()
    assert h == CARD["raster"]["sha256"]
    assert h == E7["artifact"]["sha256"]
    assert len(CARD["raster"]["sha256"]) == 64
    for page in (DOCS / "index.html", DOCS / "executive-summary-2026-10-12.md"):
        assert CARD["raster"]["sha256"][:16] in page.read_text(), f"{page.name} lacks the sha256"


def test_download_button_points_at_the_current_artifact():
    text = (DOCS / "index.html").read_text()
    m = re.search(r'class="btn" href="(downloads/[^"]+\.tif)"', text)
    assert m, "the hero has no download button"
    assert pathlib.Path(m.group(1)).name == f"{CARD['submission_name']}.tif"


def test_verdict_is_labelled_and_consistent():
    """The hero must say plainly whether it is OK to submit."""
    hero = (DOCS / "index.html").read_text()
    assert "OK TO SUBMIT" in hero or "DO NOT SUBMIT" in hero
    rc = json.loads((ROOT / "evidence" / "run_card_20261012.json").read_text())
    if rc["verdict"] == "promote":
        assert "OK TO SUBMIT" in hero
    else:
        assert "DO NOT SUBMIT" in hero
    assert rc["verdict"] in ("promote", "negative")
    assert rc["organizer_confirmed_scores"] == 0, "no receipt exists; nothing is ORGANIZER-CONFIRMED"


def test_numbers_are_labelled_not_projected_as_scores():
    """The run card must never contain a projection written as a score."""
    rc = json.loads((ROOT / "evidence" / "run_card_20261012.json").read_text())
    assert rc["numbers_are_projections"] is True
    assert "label" in rc["holdout_dti"] and "HOLDOUT" in rc["holdout_dti"]["label"].upper()
    assert "label" in rc["sstar_v2_cv"]
    hero = (DOCS / "index.html").read_text()
    assert "Not claimed" in hero or "not a score" in hero.lower()


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


def test_uniqueness_numbers_match_the_evidence():
    ev = E7["uniqueness"]
    hero = (DOCS / "index.html").read_text()
    assert f"{ev['max_frac3px_nonvacuous']:.3f}" in hero
    assert f"{ev['max_rho']:.3f}" in hero
    # the tripwire verdict in the card must agree with the evidence
    rc = json.loads((ROOT / "evidence" / "run_card_20261012.json").read_text())
    assert rc["correlation_overlap_vs_registry"]["tripped"] == ev["tripped"]
    if ev["tripped"]:
        assert rc["verdict"] == "negative"
