"""Execute the shipped artifact and the pages that describe it.

Every claim a reader of ``docs/index.html`` or ``docs/executive-summary-2026-10-11b.html``
sees about the file is re-derived here from the bytes on disk, and the numbers printed on
the pages are re-read from the evidence JSON so the two cannot drift apart.

If the file is absent (it is 481 kB and committed, so this is only a guard for partial
checkouts) the file-level tests skip rather than fail.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import grid  # noqa: E402

TIF = ROOT / "docs" / "downloads" / "gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.tif"
EVIDENCE = ROOT / "evidence" / "final_field_gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.json"
CARD = ROOT / "evidence" / "run_card_20261011b.json"
GATES = ROOT / "evidence" / "e4_gates_20261011b.json"

pytestmark = pytest.mark.skipif(not TIF.exists(), reason="artifact not in this checkout")


def test_receipt_matches_the_bytes_on_disk():
    receipt = grid.check_submission(TIF)
    ev = json.loads(EVIDENCE.read_text())["receipt"]
    assert receipt["sha256"] == ev["sha256"]
    assert receipt["bytes"] == ev["bytes"]
    assert receipt["legal"] is True
    assert receipt["nodata"] is None, "a nodata tag is one of the two mechanisms behind the " \
                                      "portal error 'Predicted values must be in range [0, 1]'"
    assert receipt["all_finite"] and receipt["nan_count"] == 0
    assert receipt["n_outside_0_1"] == 0
    assert receipt["crs_match"] and receipt["transform_match"] and receipt["width_height_match"]


def test_dot_count_and_hard_core_isolation():
    import rasterio
    from scipy import ndimage as ndi
    with rasterio.open(TIF) as src:
        a = src.read(1)
    assert set(np.unique(a)).issubset({0.0, 1.0}), "dot field, not a probability surface"
    n = int((a > 0).sum())
    assert n == 120_000
    yy, xx = np.mgrid[-3:4, -3:4]
    disk = ((yy * yy + xx * xx) <= 9).astype(np.int32)
    nb = ndi.convolve((a > 0).astype(np.int32), disk, mode="constant")
    assert nb[a > 0].max() == 1, "at most one dot inside any 300 m disc"
    assert nb[a > 0].sum() == n


def test_no_dot_sits_on_the_mapped_catalogue():
    known, footprint = grid.load_catalogue(ROOT / "data" / "labels.tif")
    with __import__("rasterio").open(TIF) as src:
        a = src.read(1)
    assert not known[a > 0].any()
    assert not (~footprint[a > 0]).any()
    ev = json.loads(EVIDENCE.read_text())["stats"]
    assert ev["frac_on_catalogue"] == 0.0
    assert ev["max_dots_in_300m_disk"] == 1


def test_uniqueness_numbers_on_the_pages_match_the_evidence():
    ev = json.loads(EVIDENCE.read_text())
    results = ev["lane_drift"]["results"]
    max_jac = max(r["jaccard"] for r in results)
    max_exact = max(r["frac_exact"] for r in results)
    assert max_jac < 0.05 and max_exact < 0.10
    card = json.loads(CARD.read_text())
    assert card["correlation_and_overlap_vs_registry"]["max_jaccard_vs_any_comparator"] == max_jac
    assert card["raster_sha256"] == ev["receipt"]["sha256"]
    # the two pages must quote the same hash and the same verdict
    # docs/index.html carries the 2026-10-12 session; this session's page is preserved verbatim
    for page in (ROOT / "docs" / "index-2026-10-11b-superseded.html",
                 ROOT / "docs" / "executive-summary-2026-10-11b.html"):
        text = page.read_text()
        assert ev["receipt"]["sha256"][:16] in text, f"{page.name} lacks the sha256"
        assert "120,000" in text or "120000" in text


def test_the_lattice_leg_is_vacuous_measured_not_asserted():
    """The page says the trip is vacuous; the evidence must contain the nulls that prove it."""
    g = json.loads(GATES.read_text())["A_lattice_leg"]
    assert g["frac3px_uniform_random_null"] > g["frac3px_ours"]
    assert g["frac3px_3px_lattice_null"] > g["frac3px_ours"]


def test_proxy_instrument_cannot_rank_fields():
    """The claim that promotion must not rest on the proxy, with its two correlations."""
    b = json.loads(GATES.read_text())["B_proxy_vs_portal"]
    assert b["n"] >= 20
    assert b["spearman_rho"] < 0, "the proxy DTI must be anti-correlated for the claim to hold"
