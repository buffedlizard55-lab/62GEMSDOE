"""The 2026-10-12 site must not drift from the 2026-10-12 evidence.

Every assertion here greps a published page back out of the run card that generated it, so a
regenerated page with a stale number fails.  The companion session tests
(`test_docs_20261011b.py`, `test_shipped_artifact_20261011b.py`) follow the preserved page
`docs/index-2026-10-11b-superseded.html`.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD = json.loads((ROOT / "evidence/run_card_20261012.json").read_text())
INDEX = DOCS / "index.html"
EXEC = DOCS / "executive-summary-2026-10-12.html"
TIF = DOCS / "downloads" / f"{CARD['slug']}.tif"


def test_the_shipped_bytes_are_the_bytes_the_card_describes():
    assert TIF.exists(), TIF
    import hashlib
    h = hashlib.sha256()
    with open(TIF, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    assert h.hexdigest() == CARD["raster_sha256"]
    assert TIF.stat().st_size == CARD["raster_bytes"]
    assert CARD["format_receipt_from_disk"]["legal"] is True
    assert CARD["validator_output"]["passed"] is True
    assert CARD["validator_output"]["values_min"] >= 0.0
    assert CARD["validator_output"]["values_max"] <= 1.0
    # the regression the portal rejected a previous upload for: no nodata tag, nothing out of range
    assert CARD["format_receipt_from_disk"]["nodata"] is None


def test_the_note_fits_the_portal_limit_and_is_on_both_pages():
    note = CARD["submission_note"]
    assert 20 <= len(note) <= 140, len(note)
    assert CARD["submission_note_chars"] == len(note)
    assert note in INDEX.read_text(), "the front page does not show the note to paste"
    assert note in EXEC.read_text(), "the executive summary does not show the note to paste"


def test_the_verdict_is_obvious_and_is_the_verdict_in_the_card():
    text = INDEX.read_text()
    assert "DO NOT SUBMIT THIS FILE" in text
    assert CARD["verdict_label"].split(":")[0] in text          # "DUPLICATE - STOP"
    assert CARD["verdict"] == "negative"
    # the trip numbers quoted on the page are the trip numbers in the evidence
    cmp_ = CARD["duplicate_trip"]["comparator"]
    assert f"{100*cmp_['my_frac3px']:.2f} %" in text
    assert f"{cmp_['exact_shared_dots']:,}" in text
    assert cmp_["alias"] in text


def test_the_download_button_points_at_the_current_artifact():
    m = re.search(r'class="btn" href="(downloads/[^"]+\.tif)"', INDEX.read_text())
    assert m, "the hero has no download button"
    assert pathlib.Path(m.group(1)).name == f"{CARD['slug']}.tif"
    assert (DOCS / m.group(1)).exists()


def test_the_profile_table_quotes_the_measured_numbers():
    text = INDEX.read_text()
    prof = CARD["emission"]["measured_profile"]
    assert f"{prof['M']:,}" in text
    assert f"{prof['dens21']:.2f}" in text
    assert f"{prof['lidar_scarp_mean']:.1f}" in text
    assert f"{CARD['emission']['min_separation_m']:.0f} m" in text
    assert CARD["emission"]["dots_with_another_dot_inside_300m"] == 0
    assert CARD["emission"]["deterministic_rebuild_identical"] is True


def test_no_number_on_the_page_is_presented_as_a_score():
    """The protocol: a projection is never written as a score."""
    text = INDEX.read_text()
    assert "never a score" in text.lower() or "NEVER a score" in text
    assert "ORGANIZER-CONFIRMED" in text
    assert "No file in this repository has an organizer-confirmed score." in text
    model = CARD["model_projection"]
    assert f"{model['dti_at_K12000']:.4f}" in text
    assert model["label"].startswith("MODEL")


def test_every_internal_link_resolves():
    for page in (INDEX, EXEC, DOCS / "irregularities.html", DOCS / "next-steps.html"):
        for href in re.findall(r'href="([^"]+)"', page.read_text()):
            if href.startswith(("http", "mailto:", "#")):
                continue
            target = (page.parent / href.split("#")[0]).resolve()
            assert target.exists(), f"{page.name} -> {href}"


def test_published_pages_have_balanced_tags():
    for page in (INDEX, EXEC):
        text = page.read_text()
        assert text.count("<table") == text.count("</table>")
        assert text.count("<div") == text.count("</div>")
        assert text.count("<tr>") == text.count("</tr>")
        assert text.startswith("<!doctype html>") and text.rstrip().endswith("</html>")
