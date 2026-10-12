"""Execute the new shipped artifact for session 2026-10-12 and the pages that describe it."""

from __future__ import annotations

import json
import pathlib
import sys
import re

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import grid, validate

TIF = ROOT / "docs" / "downloads" / "gems62-datum-lahontan-strain-gauge-defensible-440dots-zeros.tif"
CARD = ROOT / "evidence" / "run_card_20261012.json"

pytestmark = pytest.mark.skipif(not TIF.exists(), reason="artifact not in this checkout")


def test_receipt_matches_the_bytes_on_disk_20261012():
    receipt = grid.check_submission(TIF)
    card = json.loads(CARD.read_text())
    assert receipt["sha256"] == card["raster_sha256"]
    assert receipt["bytes"] == card["raster_bytes"]
    assert receipt["legal"] is True
    assert receipt["nodata"] is None, "nodata must be null to avoid portal error"
    assert receipt["all_finite"] and receipt["nan_count"] == 0
    assert receipt["n_outside_0_1"] == 0
    assert receipt["crs_match"] and receipt["transform_match"] and receipt["width_height_match"]


def test_dot_count_and_isolation_20261012():
    import rasterio
    with rasterio.open(TIF) as src:
        a = src.read(1)
    assert set(np.unique(a)).issubset({0.0, 1.0}), "must be binary dots"
    n = int((a > 0).sum())
    assert n == 440


def test_off_catalogue_20261012():
    known, footprint = grid.load_catalogue(ROOT / "data" / "labels.tif")
    with __import__("rasterio").open(TIF) as src:
        a = src.read(1)
    # Zero dots on the mapped catalogue
    assert not known[a > 0].any(), "dots must not touch mapped catalogue"
    # All dots inside the footprint
    assert footprint[a > 0].all(), "all dots must be inside survey footprint"


def test_pages_describe_artifact_20261012():
    card = json.loads(CARD.read_text())
    sha16 = card["raster_sha256"][:16]
    name = card["submission_name"]
    note = card["submission_note"]

    assert len(note) <= 140, "submission note exceeds 140 chars"

    for page in (ROOT / "docs" / "index.html", ROOT / "docs" / "executive-summary.html"):
        text = page.read_text()
        assert name in text, f"{page.name} missing submission name"
        assert sha16 in text, f"{page.name} missing sha256 prefix"
        assert f"{name}.tif" in text, f"{page.name} missing tif download link"


def test_uniqueness_bounds_20261012():
    card = json.loads(CARD.read_text())
    dots_uniq = card["correlation_and_overlap_vs_registry"]["final_dots"]
    assert dots_uniq["passed"] is True
    assert abs(dots_uniq["max_abs_rho"]) <= 0.90
    assert dots_uniq["max_frac3px_non_vacuous"] <= 0.70


def test_internal_links_resolve_20261012():
    for page_path in (ROOT / "docs" / "index.html", ROOT / "docs" / "executive-summary.html"):
        text = page_path.read_text()
        for href in re.findall(r'href="([^"#:]+)"', text):
            if href.startswith(("http", "mailto:", "//")):
                continue
            target = page_path.parent / href.split("#")[0]
            assert target.exists(), f"{page_path.name} links to missing file: {href}"
