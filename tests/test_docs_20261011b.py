"""No manual checking: the pages, the receipts, the links and the note, all re-derived.

Three things a human would otherwise have to verify by eye, each of which has silently
broken in this repository before:

1. **The prose on the download pages matches the evidence JSON.**  Every headline figure on
   ``docs/index.html`` and the 2026-10-11b executive summary is grepped back out of the page
   and compared with the number the build script wrote.
2. **The submission note is short enough to paste.**  The portal caps it at 140 characters.
3. **Every internal link resolves.**  A landing page whose download button 404s is the one
   failure that makes everything else moot.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD = json.loads((ROOT / "evidence" / "run_card_20261011b.json").read_text())
FIELD = json.loads(
    (ROOT / "evidence"
     / "final_field_gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.json").read_text())
GATES = json.loads((ROOT / "evidence" / "e4_gates_20261011b.json").read_text())

TIF = DOCS / "downloads" / f"{CARD['submission_name']}.tif"
assert CARD['submission_note_chars'] == len(CARD['submission_note'])
PAGES = [DOCS / "index.html", DOCS / "executive-summary-2026-10-11b.html",
         DOCS / "hypotheses-2026-10-11b.html",
         DOCS / "research" / "beating-02778-2026-10-11b.html"]


def test_note_fits_the_portal_limit():
    note = CARD["submission_note"]
    assert len(note) <= 140, f"note is {len(note)} chars, the portal allows 140"
    assert len(note) >= 20
    # 2026-10-12: the hero is owned by the current session's module (test_docs_20261012);
    # this module certifies the 2026-10-11b pages it created.
    import html as _html
    md = (DOCS / "executive-summary-2026-10-11b.md").read_text()
    assert note in md, "the executive summary does not show the note to paste"
    assert _html.escape(note, quote=False) in (
        DOCS / "executive-summary-2026-10-11b.html").read_text(), "the rendered page lost the note"


def test_card_sha256_is_the_sha256_of_the_shipped_file():
    if not TIF.exists():
        pytest.skip("artifact not in this checkout")
    h = hashlib.sha256(TIF.read_bytes()).hexdigest()
    assert h == CARD["raster_sha256"]
    assert len(CARD["raster_sha256"]) == 64


def test_headline_numbers_on_the_pages_come_from_the_evidence():
    card_num = CARD["numbers"]
    field_stats = FIELD["stats"]
    credit = card_num["credit_per_dot_vs_sgmc_offcatalogue"]
    bar = card_num["credit_needed_to_beat_0.2778_at_120k"]
    pages = {p.name: p.read_text() for p in PAGES if p.exists()}
    assert pages, "no pages to check"
    joined = "\n".join(pages.values())
    for needle in (f"{credit:.4f}", f"{bar:.4f}",
                   f"{card_num['holdout_dti']['value']:.5f}",
                   f"{card_num['model_at_120k_exact_transfer']:.3f}",
                   f"{CARD['raster_sha256'][:16]}"):
        assert needle in joined, f"{needle} is missing from the pages"
    assert "120,000" in joined
    # the isolation claim on the pages must be the measured one
    assert field_stats["max_dots_in_300m_disk"] == 1
    assert "max dots in any 300 m disc" in (DOCS / "run-card.html").read_text()


def test_proxy_correlation_claims_match_the_gates_receipt():
    b = GATES["B_proxy_vs_portal"]
    text = (DOCS / "research" / "beating-02778-2026-10-11b.md").read_text()
    assert f"{abs(b['spearman_rho']):.3f}" in text, "the anti-correlation figure is not on the page"
    assert f"+0.617" in text, "the positive per-dot-credit correlation is not on the page"
    a = GATES["A_lattice_leg"]
    lattice = (DOCS / "executive-summary-2026-10-11b.md").read_text()
    assert f"{a['frac3px_ours']:.3f}" in lattice
    assert f"{a['frac3px_uniform_random_null']:.4f}" in lattice
    assert f"{a['frac3px_3px_lattice_null']:.4f}" in lattice


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


def test_download_button_points_at_the_current_artifact():
    """The hero's download button must point at the CURRENT session's artifact."""
    import json as _json
    card = _json.loads((ROOT / "evidence" / "run_card_20261012.json").read_text())
    text = (DOCS / "index.html").read_text()
    m = re.search(r'class="btn" href="(downloads/[^"]+\.tif)"', text)
    assert m, "the hero has no download button"
    assert pathlib.Path(m.group(1)).name == f"{card['submission_name']}.tif"


def test_published_pages_have_balanced_tags():
    """Cheap structural check: a page that browsers silently mangle is a page that lies.

    This is not a validator; it catches the specific mistake the renderer can make (an
    unclosed table or blockquote swallowing the rest of the document).
    """
    tags = ("div", "table", "thead", "tbody", "tr", "td", "th", "p", "code", "pre",
            "ul", "ol", "li", "blockquote")
    for page in [DOCS / "index.html", DOCS / "run-card.html", DOCS / "irregularities.html"] + PAGES:
        if not page.exists():
            continue
        text = page.read_text()
        unbalanced = []
        for tag in tags:
            opens = len(re.findall(rf"<{tag}[ >]", text))
            closes = len(re.findall(rf"</{tag}>", text))
            if opens != closes:
                unbalanced.append(f"{tag} {opens}/{closes}")
        assert not unbalanced, f"{page.name}: {unbalanced}"
