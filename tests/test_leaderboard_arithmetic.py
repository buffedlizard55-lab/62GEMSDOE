"""Regression tests for the leaderboard-anchored arithmetic and the shipped rasters.

These are not smoke tests.  Each one executes a code path or an artifact that a claim on
the site depends on:

* ``test_closed_form_matches_the_exact_metric``  -- the ``DTI = cM/(0.2M+0.8N)`` identity
  quoted all over ``docs/research/leaderboard-arithmetic.md`` is checked against
  ``gems62.metric.dti_components``, the exact published index, on a synthetic field.
* ``test_marginal_rule_is_where_the_closed_form_turns_over`` -- the design rule used to pick
  the dot budget.
* ``test_truth_mass_bound_is_reproduced`` -- the ``N <= 13,688`` bound is re-derived from the
  two owner-reported thinning rows, so a typo in the document cannot survive.
* ``test_isolation_claim_is_supported_by_the_committed_registry`` -- the headline claim that
  isolated fields beat clustered fields is re-tested against the committed measurements.
* ``test_shipped_rasters_satisfy_the_submission_contract`` -- both GeoTIFFs are re-read from
  disk and re-counted; this is the test that would have caught the portal error
  "Predicted values must be in range [0, 1]".
* ``test_run_card_agrees_with_the_bytes`` -- the sha256 / dot count published in the run card
  and on the site must match the file that is actually downloadable.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import grid as G                                   # noqa: E402
from gems62 import metric as MT                                # noqa: E402


def test_official_worked_example_still_holds():
    assert MT.dti_from_components(3.00, 1.89, 2.00) == pytest.approx(0.6026517, abs=1e-6)


def test_closed_form_matches_the_exact_metric():
    """``c*M/(0.2M+0.8N)`` must reproduce the published index for isolated unit dots."""
    rng = np.random.default_rng(3)
    truth = np.zeros((400, 400), bool)
    for _ in range(600):                                    # hidden "new faults"
        truth[rng.integers(5, 395), rng.integers(5, 395)] = True
    dots = np.zeros((400, 400))
    ys = rng.choice(np.arange(6, 394), size=120, replace=False)
    xs = rng.choice(np.arange(6, 394), size=120, replace=False)
    dots[ys, xs] = 1.0
    assert MT.credit_audit(dots > 0)["redundancy_fraction"] < 0.05, "dots must be isolated"
    c = MT.dti_components(dots, truth)
    M = float(dots.sum())
    N = float(truth.sum())
    mean_credit = c.tp_w / M
    closed = mean_credit / (MT.ALPHA + MT.BETA * N / M)
    assert closed == pytest.approx(c.dti, rel=0.02)


def test_marginal_rule_is_where_the_closed_form_turns_over():
    """Adding a dot pays iff its credit exceeds ``alpha*DTI``."""
    N, M = 12000.0, 40000.0
    c = 0.12
    s = MT.unit_dot_dti(int(M), c, N)
    # A dot with realised credit p raises DTI iff p > alpha*DTI:
    #   (cM+p)/(alpha(M+1)+beta N) > cM/(alpha M + beta N)  <=>  p > alpha*DTI.
    bar = MT.ALPHA * s
    better = MT.unit_dot_dti(int(M) + 1, (c * M + bar + 1e-6) / (M + 1), N)
    worse = MT.unit_dot_dti(int(M) + 1, (c * M + bar - 1e-3) / (M + 1), N)
    assert better > s > worse
    assert MT.maximum_useful_distance_m(0.2778) == pytest.approx(283.32, abs=0.05)


def _truth_mass_bound(s1, M1, r1, s2, M2, r2):
    """Thinning cannot add credit: solve the inequality for the hidden truth mass N."""
    a1, a2 = M1 * (1 - r1), M2 * (1 - r2)
    return (s1 * 0.2 * a1 - s2 * 0.2 * a2) / (0.8 * (s2 - s1))


def test_truth_mass_bound_is_reproduced():
    doc = json.loads((ROOT / "research/leaderboard_arithmetic.json").read_text())
    got = _truth_mass_bound(0.2600, 44090, 0.018, 0.2778, 37654, 0.017)
    assert doc["truth_mass_bound"]["N_upper"] == pytest.approx(got, abs=1.0)
    assert got < 14100, "must stay inside the sibling repository's independent range"
    assert got > 9000


def test_isolation_claim_is_supported_by_the_committed_registry():
    m = json.loads((ROOT / "research/registry_measurements.json").read_text())
    assert len(m) >= 80, "the score-anchored registry must stay large"
    iso = [r["score"] for r in m if r["redun_mean"] < 0.05]
    clu = [r["score"] for r in m if r["redun_mean"] >= 0.23]
    assert max(iso) == pytest.approx(0.2778), "the best raster in the registry is isolated"
    assert max(clu) <= 0.2477, "no clustered raster reaches the isolated best"
    assert float(np.median(iso)) > float(np.median(clu))


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


SHIPPED = [
    ("docs/downloads/gems62-h62g-benchcrosscut-hardcore-zeros.tif",
     "79eb0a7ddc2dcfb4667bff41bbc237f8d5663dd63e025eed79af8c8f984ed500", 10000),
    ("docs/downloads/gems62-h62i-scarpcrosscut-hardcore-zeros.tif",
     "aaadb736f1b6037919c66983049a8deafab66e986ddba08c2c76083f233568cb", 60000),
]


@pytest.mark.parametrize("rel,want_sha,want_dots", SHIPPED)
def test_shipped_rasters_satisfy_the_submission_contract(rel, want_sha, want_dots):
    p = ROOT / rel
    assert p.exists(), f"{rel} must be downloadable from the site"
    assert _sha(p) == want_sha, "the bytes changed without the receipt being updated"
    rec = G.check_submission(p)
    assert rec["count"] == 1 and rec["dtype"] == "float32"
    assert rec["crs"] == G.CRS and rec["transform_match"] and rec["width_height_match"]
    assert rec["nodata"] is None, "a nodata tag is one of the two portal-error mechanisms"
    assert rec["all_finite"] and rec["nan_count"] == 0
    assert rec["n_outside_0_1"] == 0, 'the portal rejects this with "values must be in [0, 1]"'
    assert rec["n_positive"] == want_dots
    assert rec["legal"] is True


def test_emitted_dots_are_isolated_and_off_catalogue():
    """Design rules R1 (isolation) and the organiser masking rule, re-measured."""
    labels = G.read_labels(ROOT / "data/labels.tif")
    cat = labels == 1
    import rasterio
    for rel, _, _ in SHIPPED:
        with rasterio.open(ROOT / rel) as d:
            a = d.read(1).astype(float)
        pos = a > 0
        audit = MT.credit_audit(pos)
        assert audit["redundancy_fraction"] == pytest.approx(0.0, abs=0.02), \
            f"{rel} violates R1: dots are clustered"
        assert int(cat[pos].sum()) == 0, f"{rel} wastes mass on masked catalogue pixels"


def test_run_card_agrees_with_the_bytes():
    card = json.loads((ROOT / "evidence/h62g/run_card.json").read_text())
    by_name = {r["file"]: r for r in card["rasters"]}
    prim = "gems62-h62g-benchcrosscut-hardcore-zeros.tif"
    assert by_name[prim]["sha256"] == SHIPPED[0][1]
    assert by_name[prim]["n_dots"] == SHIPPED[0][2]
    assert card["verdict"] == "negative"
    assert card["organizer_score"] is None
    assert len(card["submission_note"]) <= 140
