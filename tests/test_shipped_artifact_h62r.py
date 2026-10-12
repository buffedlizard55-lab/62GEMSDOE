"""Execute the H62-R artifact and the pages that describe it.

``evidence/h62r_artifact.json`` records which file **this lane** shipped; ``docs/index.html``
stacks sessions newest-first and gives each lane its own block, so the lane's block -- not the
page hero -- is what this module checks.  (An earlier revision of this file asserted that the
lane's file *was* the hero.  Merging with ``main`` showed why that was the wrong invariant: two
lanes had produced competing candidates with no measurement able to rank them, and pinning the
hero to one of them turned a decision into a test failure.)

Everything a reader of the lane's block on ``docs/index.html`` is told about this file is
re-derived here from the bytes on disk, and the numbers on the page are compared with the receipts.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import grid  # noqa: E402

CUR = json.loads((ROOT / "evidence" / "h62r_artifact.json").read_text())
TIF = ROOT / CUR["file"]
ZIP = ROOT / CUR["zip"]
EV = ROOT / "evidence" / "h62r"
HOLDOUT = ROOT / "evidence" / "h62r" / "e9_holdout.json"
UNIQ = ROOT / "evidence" / "h62r" / "e7_uniqueness.json"
STATS = ROOT / "evidence" / "h62r" / "e10_field_stats.json"
EMISSION = ROOT / "evidence" / "h62r" / "e5_emission.json"

pytestmark = pytest.mark.skipif(not TIF.exists(), reason="artifact not in this checkout")


# ---------------------------------------------------------------- the bytes
def test_receipt_matches_the_bytes_on_disk():
    receipt = grid.check_submission(TIF)
    assert receipt["sha256"] == CUR["sha256"], "the shipped file is not the receipted file"
    assert receipt["bytes"] == CUR["bytes"]
    assert hashlib.sha256(TIF.read_bytes()).hexdigest() == CUR["sha256"]
    assert receipt["legal"] is True
    assert receipt["nodata"] is None, "a nodata tag is one of the two mechanisms behind the " \
                                      "portal error 'Predicted values must be in range [0, 1]'"
    assert receipt["all_finite"] and receipt["nan_count"] == 0
    assert receipt["n_outside_0_1"] == 0
    assert receipt["crs_match"] and receipt["transform_match"] and receipt["width_height_match"]
    emitted = json.loads(EMISSION.read_text())["receipt"]
    assert emitted["sha256"] == receipt["sha256"], "emission and validation disagree on the file"


def test_the_zip_contains_exactly_that_file():
    """A .zip that ships a different raster than the one receipted is the classic trap."""
    import zipfile
    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        assert names == [f"{CUR['submission_name']}.tif"], names
        assert hashlib.sha256(z.read(names[0])).hexdigest() == CUR["sha256"]


def test_dot_count_and_zero_kernel_overlap():
    """At most one dot inside any 300 m disc, measured against the metric's own kernel.

    IR-62-H62R-03: the first version of this statistic counted the disc's *boundary*,
    which makes two dots exactly 300 m apart -- k(300 m) = 0 -- look like a collision,
    and it reported self-overlap for a single dot.  Both are asserted here directly.
    """
    import rasterio
    from scipy import ndimage as ndi
    with rasterio.open(TIF) as src:
        a = src.read(1)
    assert set(np.unique(a)).issubset({0.0, 1.0}), "dot field, not a probability surface"
    n = int((a > 0).sum())
    assert n == CUR["n_dots"]

    yy, xx = np.mgrid[-3:4, -3:4]
    r2 = yy * yy + xx * xx
    kern = np.zeros((7, 7))
    m = r2 < 9                                  # strictly inside the kernel radius
    kern[m] = 1.0 - np.sqrt(r2[m]) / 3.0
    kern[3, 3] = 0.0                            # a dot is not its own neighbour
    got = ndi.convolve(a, kern, mode="constant")
    assert got[a > 0].max() == 0.0, "some dot's kernel overlaps another dot's"
    assert (got[a > 0] > 0).sum() == 0

    # exact nearest-neighbour distance: the thinning distance itself, to the metre
    from scipy.spatial import cKDTree
    r, c = np.nonzero(a > 0)
    tree = cKDTree(np.column_stack([c * 100.0, r * 100.0]))
    d, _ = tree.query(np.column_stack([c * 100.0, r * 100.0]), k=2)
    assert d[:, 1].min() == pytest.approx(300.0, abs=1e-6), d[:, 1].min()


def test_no_dot_sits_on_the_mapped_catalogue_and_none_sits_in_front_of_it():
    import rasterio
    from scipy import ndimage as ndi
    with rasterio.open(TIF) as src:
        a = src.read(1)
    labels = grid.read_labels(ROOT / "data" / "labels.tif")
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as src:
        foot = np.isfinite(src.read(1))
    cat = (labels == 1) & foot
    r, c = np.nonzero(a > 0)
    dist = ndi.distance_transform_edt(~cat, sampling=(100.0, 100.0))
    dm = dist[r, c]
    assert dm.min() >= 300.0, f"a dot sits {dm.min():.0f} m from the mapped catalogue"
    assert bool(cat[r, c].any()) is False, "a dot landed on the catalogue"
    stats = json.loads(STATS.read_text())
    assert stats["n_dots"] == int((a > 0).sum())
    assert stats["dot_dist_to_catalogue_m"]["frac_within_300m"] == 0.0
    assert f"{stats['dot_dist_to_catalogue_m']['median']:,.0f}" in \
        (ROOT / "docs" / "index.html").read_text(), "the median distance is not on the page"


# ---------------------------------------------------------------- the gates
def test_uniqueness_receipt_is_a_pass_and_names_its_comparators():
    u = json.loads(UNIQ.read_text())
    assert u["raster_sha256"] == CUR["sha256"], "uniqueness was run against a different file"
    assert u["n_registry_files"] > 400, "the registry was not harvested"
    assert u["max_abs_rho"] < 0.10, u["max_abs_rho"]
    assert u["n_comparators_abs_rho_gt_0_90"] == 0
    assert u["worst_jaccard3px"]["value"] < 0.25, u["worst_jaccard3px"]
    assert u["n_comparators_over_overlap_limit_nonvacuous"] == 0
    assert u["n_skipped"] <= 2, f"unexpectedly many comparators skipped: {u['skipped'][:5]}"
    # every row carries its own hash, so the comparison is reproducible from the receipt
    assert all(len(row["sha256"]) == 64 for row in u["rows"])


def test_holdout_is_reported_as_structural_not_as_a_pass():
    """The honest-reporting test.

    The catalogue-based holdout MUST be 0 for this field, because the exclusion radius
    equals the kernel radius.  What must not happen is that the site calls that 0 a
    success, or hides it.  This test pins both halves: the number, and the fact that the
    page says *why* it is vacuous.
    """
    h = json.loads(HOLDOUT.read_text())
    assert h["pooled_dti"] == 0.0
    assert h["withheld_positives_total"] > 50_000
    ctrl = h["controls_mean"]
    assert ctrl["random_dots"] > 0.0, "the control scored zero too -- the scorer is broken"
    text = (ROOT / "docs" / "index.html").read_text()
    assert "structurally vacuous" in text, "index.html does not disclose the vacuous holdout"
    assert "0.000000" in text, "index.html does not print the holdout number it must explain"
    assert "IR-62-H62R-02" in text, "the vacuity is not logged as an irregularity"
    assert "Not claimed" in text, "index.html must not imply an expected score"


def test_the_three_figures_exist_and_are_not_blank():
    """IR-62-12: a figure step once 'succeeded' while writing nothing."""
    figdir = ROOT / "docs" / "h62r"
    names = ["h62r_level_spectrum.png", "h62r_shoreline_profiles.png", "h62r_field_map.png"]
    for name in names:
        p = figdir / name
        assert p.exists(), f"{name} is missing"
        assert p.stat().st_size > 20_000, f"{name} is suspiciously small ({p.stat().st_size} B)"
    assert (ROOT / "docs" / "downloads" / "h62r-shoreline-profiles.csv").stat().st_size > 100_000


# ---------------------------------------------------------------- the pages
def test_the_landing_page_offers_this_file_with_its_measured_numbers():
    """The lane's block on index.html is generated (scripts/update_h62r_section.py), so every
    number below is re-read here from the same receipts the generator used."""
    html = (ROOT / "docs" / "index.html").read_text()
    rel = CUR["file"].split("docs/", 1)[1]
    assert 'id="h62r"' in html, "the landing page has no H62-R section"
    block = html[html.index('id="h62r"'):html.index("/LANE H62-R")]
    assert f'href="{rel}"' in block, "the section does not link the file"
    assert CUR["sha256"] in block, "the section does not print the sha256"
    assert CUR["submission_name"] in block
    assert f"{CUR['bytes']:,}" in block, "the section does not print the byte count"
    note = CUR["submission_note"]
    assert len(note) <= 140 and len(note) == CUR["submission_note_chars"]
    import html as _html
    assert _html.escape(note, quote=False) in block, "the section does not show the note to paste"
    # the numbers a reader acts on must be the measured ones, not stale text
    uni = json.loads(UNIQ.read_text())
    assert f"{uni['max_abs_rho']:.4f}" in block
    assert f"{uni['worst_jaccard3px']['value']:.4f}" in block
    assert f"{uni['n_compared']}" in block


def test_the_section_is_reproducible_from_the_receipts():
    """Re-running the generator must not change the page: the block IS its receipts."""
    import subprocess
    before = (ROOT / "docs" / "index.html").read_text()
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "update_h62r_section.py")],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr[-800:]
    assert (ROOT / "docs" / "index.html").read_text() == before, (
        "docs/index.html changed when the H62-R generator re-ran -- the committed page is not "
        "what the receipts produce")


@pytest.mark.parametrize("page", ["docs/index.html", "docs/executive-summary-h62r.html",
                                  "docs/hypotheses-h62r.html"])
def test_no_page_offers_a_nan_encoded_twin_as_a_download_button(page):
    """NaN twins stay reachable as evidence, but never as a button that looks like the answer.

    The merge with main kept this repository's NaN-encoded twins in docs/downloads (they are
    labelled 'not legal' in the all-files table, and their verdicts say not to submit them).  The
    line this test holds is the one that matters to the owner: no page may present a NaN-encoded
    file as a primary button, and this lane's own pages must not link one at all.
    """
    text = (ROOT / page).read_text()
    for m in re.finditer(r'class="btn[^"]*" href="([^"]*\.tif)"', text):
        assert "-nan.tif" not in m.group(1), f"{page} offers a NaN twin as a button: {m.group(1)}"
    if page != "docs/index.html":
        for href in re.findall(r'href="([^"]*\.tif)"', text):
            assert "-nan.tif" not in href, f"{page} links the NaN file {href}"


def test_the_landing_page_explains_the_portal_error():
    """A reader who was rejected must be able to find out why, from the front page."""
    text = (ROOT / "docs" / "index.html").read_text()
    assert "Predicted values must be in range [0, 1]" in text
    assert "7,111,787" in text, "the measured NaN cell count is not on the page"


def test_every_h62r_evidence_file_is_committed():
    for rel in CUR["evidence"]:
        p = ROOT / rel
        assert p.exists(), f"{rel} is not committed (build/ is snapshot-excluded)"
        assert p.stat().st_size > 100, f"{rel} is empty"
