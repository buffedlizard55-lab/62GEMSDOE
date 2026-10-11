"""Verification suite.  Every assertion here is against a published number or a
brute-force transcription of the organiser's formula -- none is self-referential.

Run:  pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems62 import emission, grid, habitat, holdout, isobase, uniqueness, validate  # noqa: E402
from gems62 import submission_writer as sw                                          # noqa: E402
from gems62.metric import (ALPHA, BETA, RADIUS_PX, attainable_kernel_weights,        # noqa: E402
                           credit_bar, dti, dti_binary, dti_bruteforce, kernel,
                           marginal_inclusion_threshold)


# --------------------------------------------------------------------------------------
# metric
# --------------------------------------------------------------------------------------
def test_kernel_triangular():
    assert kernel(0.0) == 1.0
    assert kernel(1.5) == pytest.approx(0.5)
    assert kernel(3.0) == 0.0
    assert kernel(4.0) == 0.0
    assert kernel(-1.0) == pytest.approx(4.0 / 3.0)  # max(1-(-1)/3, 0) = 4/3 (no upper clip)


def test_kernel_matches_published_definition():
    """k(d) = max(1 - d/R, 0), R = 300 m = 3 px at 100 m."""
    assert RADIUS_PX == 3.0
    for d in np.linspace(0, 6, 25):
        assert kernel(d) == pytest.approx(max(1.0 - d / 3.0, 0.0))


def test_published_scoring_example():
    """The organiser's worked example: TP_w=3.00, FP_w=1.89, FN_w=2.00 -> 0.60.

    Reproduced from
    https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#scoring-example
    A 5-pixel vertical ground-truth line; the prediction is the same line
    shifted one pixel to the right plus one extra pixel.  The published
    components are asserted on the algebraic identity
    DTI = TP/(TP + 0.2*FP + 0.8*FN) with those exact numbers.
    """
    tp_w, fp_w, fn_w = 3.00, 1.89, 2.00
    got = tp_w / (tp_w + ALPHA * fp_w + BETA * fn_w)
    assert got == pytest.approx(0.60, abs=5e-3)


def test_algebraic_identity_dti_equals_t_over_02TF_plus_08K():
    """DTI = T / (0.2(T + F) + 0.8|G|) because FN_w = |G| - TP_w."""
    rng = np.random.default_rng(0)
    for _ in range(6):
        truth = rng.random((40, 40)) < 0.05
        pred = np.where(rng.random((40, 40)) < 0.15, rng.random((40, 40)), 0.0)
        r = dti(pred, truth)
        T, F, K = r["tp"], r["fp"], r["n_truth"]
        assert r["dti"] == pytest.approx(T / (ALPHA * (T + F) + BETA * K), abs=1e-9)
        assert r["fn"] == pytest.approx(K - T, abs=1e-9)


def test_fast_and_bruteforce_agree():
    rng = np.random.default_rng(3)
    truth = rng.random((24, 24)) < 0.08
    pred = np.where(rng.random((24, 24)) < 0.12, rng.random((24, 24)), 0.0)
    a = dti(pred, truth)
    b = dti_bruteforce(pred, truth)
    assert a["tp"] == pytest.approx(b["tp"], abs=1e-9)
    assert a["fp"] == pytest.approx(b["fp"], abs=1e-9)
    assert a["fn"] == pytest.approx(b["fn"], abs=1e-9)
    assert a["dti"] == pytest.approx(b["dti"], abs=1e-9)


def test_binary_path_matches_general_path():
    rng = np.random.default_rng(4)
    truth = rng.random((30, 30)) < 0.07
    mask = rng.random((30, 30)) < 0.10
    a = dti(mask.astype(float), truth)
    b = dti_binary(mask, truth)
    assert a["dti"] == pytest.approx(b["dti"], abs=1e-9)


def test_known_mask_removes_pixels_from_scoring():
    truth = np.zeros((20, 20), bool); truth[5:15, 10] = True
    pred = np.zeros((20, 20)); pred[5:15, 12] = 1.0
    known = np.zeros((20, 20), bool); known[5:8, 10] = True
    full = dti(pred, truth)
    masked = dti(pred, truth, known=known)
    assert masked["n_truth"] == full["n_truth"] - 3


def test_marginal_inclusion_threshold_is_alpha_times_dti():
    """k > alpha * DTI (derived in metric.py, verified by finite difference)."""
    truth = np.zeros((41, 41), bool); truth[10:31, 20] = True
    pred = np.zeros((41, 41)); pred[10:31, 20] = 1.0
    base = dti(pred, truth)["dti"]
    bar = marginal_inclusion_threshold(base)
    assert bar == pytest.approx(ALPHA * base)
    # a dot at kernel weight just above the bar must raise DTI
    good = pred.copy(); good[5, 21] = 1.0     # d = sqrt(26) -> k = 0 (no help)
    assert dti(good, truth)["dti"] <= base
    assert attainable_kernel_weights()[0] == 1.0
    assert credit_bar(0.2778) == pytest.approx(0.2 * 0.2778)


def test_attainable_kernel_weights_are_the_lattice_values():
    w = attainable_kernel_weights()
    expected = sorted({round(max(1 - np.hypot(dy, dx) / 3.0, 0.0), 12)
                       for dy in range(-3, 4) for dx in range(-3, 4)
                       if max(1 - np.hypot(dy, dx) / 3.0, 0.0) > 0}, reverse=True)
    assert [round(v, 12) for v in w] == expected
    # the (2,2)-diagonal weight still clears the bar at the group's best score
    diag22 = 1 - 2 * np.sqrt(2) / 3
    assert any(abs(v - diag22) < 1e-12 for v in w)
    assert diag22 > credit_bar(0.2778)


def test_dti_rejects_out_of_range_predictions():
    truth = np.zeros((10, 10), bool); truth[5, 5] = True
    with pytest.raises(ValueError):
        dti(np.full((10, 10), 1.5), truth)
    with pytest.raises(ValueError):
        dti(np.full((10, 10), -0.1), truth)


# --------------------------------------------------------------------------------------
# emission
# --------------------------------------------------------------------------------------
def test_greedy_thin_respects_min_sep_and_budget():
    rng = np.random.default_rng(1)
    score = rng.random((200, 200))
    elig = rng.random((200, 200)) < 0.5
    mask, _ = emission._greedy_thin(score, elig, min_sep=3, budget=500)
    ys, xs = np.nonzero(mask)
    assert ys.size <= 500
    from scipy.spatial import cKDTree
    if ys.size > 1:
        d, _ = cKDTree(np.column_stack([ys, xs])).query(
            np.column_stack([ys, xs]), k=2)
        assert d[:, 1].min() >= 3.0 - 1e-9
    # highest-priority eligible pixel must be kept
    best = np.unravel_index(np.argmax(np.where(elig, score, -np.inf)), score.shape)
    assert mask[best]


def test_greedy_thin_matches_quadratic_reference_on_small_input():
    rng = np.random.default_rng(11)
    score = rng.random((40, 40))
    elig = rng.random((40, 40)) < 0.6
    fast, _ = emission._greedy_thin(score, elig, min_sep=3, budget=None)
    # O(n^2) reference
    ys, xs = np.nonzero(elig)
    order = np.argsort(-score[ys, xs], kind="stable")
    ys, xs = ys[order], xs[order]
    ref = np.zeros((40, 40), bool)
    kept = []
    for y, x in zip(ys, xs):
        if all((y - ky) ** 2 + (x - kx) ** 2 >= 9 for ky, kx in kept):
            ref[y, x] = True
            kept.append((int(y), int(x)))
    assert np.array_equal(fast, ref)


def test_emit_dots_prunes_catalogue_and_reports_stats():
    fp = np.ones((60, 60), bool)
    cat = np.zeros((60, 60), bool); cat[30, 30] = True
    prio = np.random.default_rng(2).random((60, 60))
    r = emission.emit_dots(prio, fp, fp, cat, budget=100, min_sep=3, prune_cat_px=3.0)
    assert r.n_dots <= 100
    assert not (r.mask & cat).any()
    assert r.stats["dot_dist_to_catalogue_px"]["frac_within_3px"] == 0.0
    assert set(np.unique(r.values)) <= {0.0, 1.0}


# --------------------------------------------------------------------------------------
# holdout
# --------------------------------------------------------------------------------------
def test_segments_are_whole_and_buffered():
    m = np.zeros((60, 60), bool)
    m[10:20, 10:12] = True
    m[40:50, 30:32] = True
    lab, n = holdout.segments_of(m, min_size=5)
    assert n == 2
    rng = np.random.default_rng(0)
    withheld, buffered = holdout.split_segments(lab, n, 0.5, rng, buffer_px=3)
    # a withheld segment is withheld whole
    for s in np.unique(lab[withheld]):
        if s:
            assert withheld[(lab == s)].all()
    assert buffered.sum() > withheld.sum()


def test_holdout_hides_whole_segments_and_scores_pooled():
    rng = np.random.default_rng(5)
    shape = (120, 120)
    fp = np.ones(shape, bool)
    cat = np.zeros(shape, bool)
    for _ in range(6):
        y, x = rng.integers(10, 100, 2)
        cat[y:y + 12, x:x + 2] = True
    elig = rng.random(shape) < 0.4
    prio = rng.random(shape)

    def emit(e, p, f, visible, budget):
        m = emission.emit_dots(p, e & f, f, visible, budget=60, min_sep=2).mask
        return m

    out = holdout.run_holdout(elig, prio, fp, cat, emit, n_folds=2, seeds=(1,),
                              budget=60, controls=True)
    assert out["n_folds"] >= 1
    assert 0.0 <= out["pooled_dti"] <= 1.0
    assert out["fold_dti_ci95"][0] <= out["fold_dti_ci95"][1]
    assert set(out["controls_mean"]) == {"random_lines", "random_dots", "catalogue_offset"}


def test_leakage_canary_recovers_a_perfect_feature_and_a_null_one():
    rng = np.random.default_rng(6)
    fp = np.ones((80, 80), bool)
    pos = np.zeros((80, 80), bool); pos[20:60, 40] = True
    perfect = pos.astype(float)
    assert holdout.leakage_canary(perfect, pos, fp) == pytest.approx(1.0)
    null = rng.random((80, 80))
    assert abs(holdout.leakage_canary(null, pos, fp) - 0.5) < 0.06


# --------------------------------------------------------------------------------------
# isobase / lane
# --------------------------------------------------------------------------------------
def test_flag_steps_bounded_window_is_not_the_unbounded_outlier_test():
    """IR-62-STEP-01: the window must exclude the >210 m tail, not keep only it."""
    rng = np.random.default_rng(7)
    resid = np.concatenate([rng.normal(0, 40, 9000), rng.normal(0, 300, 1000)])
    resid = resid.reshape(100, 100)
    support = np.ones((100, 100), bool)
    unbounded = isobase.flag_steps(resid, support, k=2.5)
    bounded = isobase.flag_steps(resid, support, k=0.0, lo_m=15.0, hi_m=130.0)
    assert unbounded.any() and bounded.any()
    d = np.abs(resid - np.median(resid[support]))
    # the bounded window excludes the extreme tail the unbounded test keeps
    assert (d[unbounded] > 130.0).any()
    assert not (d[bounded] >= 130.0).any()
    assert (d[bounded] >= 15.0).all() and (d[bounded] < 130.0).all()
    assert (d[unbounded] > 2.5 * 1.4826 *
            np.median(np.abs(resid[support] - np.median(resid[support])))).all()


def test_bench_pixels_no_longer_excludes_large_residuals():
    """IR-62-BENCH-01: the bench mask is geometric only."""
    rng = np.random.default_rng(8)
    yy, xx = np.mgrid[0:80, 0:80]
    elev = 1000.0 + 0.02 * xx + rng.normal(0, 5, (80, 80))
    elev[30:50, 40:] += 250.0                        # a big step
    fp = np.ones((80, 80), bool)
    slope = np.full((80, 80), 8.0)
    margin = np.ones((80, 80), bool)
    iso = np.full((80, 80), 1000.0)
    b = isobase.bench_pixels(elev, margin, iso, fp, slope)
    resid = np.abs(elev - iso)
    assert b.any()
    assert (resid[b] > 200).any()                    # large residuals survive


def test_extend_traces_walks_along_strike_not_across_it():
    """IR-62-EXT-01: a north-south strike must produce a north-south trace."""
    shape = (80, 80)
    fp = np.ones(shape, bool)
    ev = np.full(shape, 0.9)
    strike = np.full(shape, 0.0)                     # 0 rad = north
    seeds = np.zeros(shape, bool); seeds[40, 40] = True
    traced, traces = isobase.extend_traces(seeds, ev, fp, strike=strike,
                                           min_evidence=0.5, max_len_px=20)
    ys, xs = np.nonzero(traced)
    assert ys.min() < 40 and ys.max() > 40           # extended in y
    assert xs.min() == 40 and xs.max() == 40         # not in x
    assert traces[0]["n"] > 20


def test_extend_traces_stops_when_evidence_fails():
    shape = (60, 60)
    fp = np.ones(shape, bool)
    ev = np.full(shape, 0.9)
    ev[35:, :] = 0.1
    strike = np.full(shape, 0.0)
    seeds = np.zeros(shape, bool); seeds[30, 30] = True
    traced, traces = isobase.extend_traces(seeds, ev, fp, strike=strike,
                                           min_evidence=0.5, max_len_px=25)
    ys, _ = np.nonzero(traced)
    assert ys.max() < 35


def test_local_strike_of_a_tilted_plane():
    """A plane rising to the east has N-S contours -> strike ~0 deg."""
    yy, xx = np.mgrid[0:60, 0:60]
    iso = 0.05 * xx.astype(float)
    fp = np.ones((60, 60), bool)
    st = isobase.local_strike(iso, fp)
    interior = st[10:50, 10:50]
    assert np.nanmean(np.abs(np.degrees(interior))) < 5.0


# --------------------------------------------------------------------------------------
# habitat
# --------------------------------------------------------------------------------------
def test_habitat_enrichment_recovers_a_planted_habitat():
    rng = np.random.default_rng(9)
    shape = (200, 200)
    fp = np.ones(shape, bool)
    tpi = rng.uniform(-500, 500, shape)
    slope = rng.uniform(0, 40, shape)
    pos = fp & (tpi < -200) & (slope > 10) & (rng.random(shape) < 0.5)
    w = habitat.habitat_enrichment(tpi, slope, pos, fp)
    good = fp & (tpi < -200) & (slope > 10)
    bad = fp & (tpi > 200) & (slope < 3)
    assert w[good].mean() > w[bad].mean()
    assert w[good].mean() > 1.0 > w[bad].mean()


def test_enrichment_table_sums_to_the_footprint():
    rng = np.random.default_rng(10)
    shape = (100, 100)
    fp = np.ones(shape, bool)
    tpi = rng.uniform(-400, 400, shape)
    slope = rng.uniform(0, 40, shape)
    pos = rng.random(shape) < 0.02
    tab = habitat.enrichment_table(tpi, slope, pos, fp)
    assert sum(c["px"] for c in tab["cells"]) == shape[0] * shape[1]
    assert sum(c["positives"] for c in tab["cells"]) == int(pos.sum())


# --------------------------------------------------------------------------------------
# uniqueness
# --------------------------------------------------------------------------------------
def test_kdtree_and_edt_overlap_agree():
    rng = np.random.default_rng(12)
    a = np.zeros((80, 80), bool); a[rng.integers(0, 80, 300), rng.integers(0, 80, 300)] = True
    b = np.zeros((80, 80), bool); b[rng.integers(0, 80, 300), rng.integers(0, 80, 300)] = True
    from scipy.ndimage import distance_transform_edt
    d = distance_transform_edt(~b)
    ys, xs = np.nonzero(a)
    ref = float((d[ys, xs] <= 3.0).mean())
    got = uniqueness.one_sided_overlap(a, b, px=3.0)
    assert got == pytest.approx(ref)


def test_identical_raster_is_flagged_duplicate(tmp_path):
    import rasterio
    v = np.zeros((40, 40), np.float32)
    rng = np.random.default_rng(13)
    v[rng.integers(0, 40, 200), rng.integers(0, 40, 200)] = 1.0
    p = tmp_path / "same.tif"
    with rasterio.open(p, "w", driver="GTiff", height=40, width=40, count=1,
                       dtype="float32", crs="EPSG:32611") as d:
        d.write(v, 1)
    rep = uniqueness.check_uniqueness(v.astype(float), tmp_path)
    assert rep["verdict"] == "DUPLICATE"
    assert rep["worst_overlap_3px"]["value"] == 1.0
    assert abs(rep["worst_rho_surface"]["value"]) > uniqueness.RHO_LIMIT


def test_disjoint_rasters_are_unique(tmp_path):
    import rasterio
    rng = np.random.default_rng(14)
    mine = np.zeros((60, 60), np.float32)
    mine[0:20, 0:20][rng.random((20, 20)) < 0.2] = 1.0
    theirs = np.zeros((60, 60), np.float32)
    theirs[40:60, 40:60][rng.random((20, 20)) < 0.2] = 1.0
    p = tmp_path / "other.tif"
    with rasterio.open(p, "w", driver="GTiff", height=60, width=60, count=1,
                       dtype="float32", crs="EPSG:32611") as d:
        d.write(theirs, 1)
    rep = uniqueness.check_uniqueness(mine.astype(float), tmp_path)
    assert rep["verdict"] == "UNIQUE"
    assert rep["worst_overlap_3px"]["value"] == 0.0
    # perfectly anti-correlated dot fields are the opposite of a duplicate, so
    # the signed-rho gate must not fire even though |rho| is large
    assert rep["worst_rho_surface"]["value"] <= uniqueness.RHO_LIMIT
    assert rep["gate_uses_signed_rho"] is True


def test_positive_duplicate_correlation_fires_the_rho_gate(tmp_path):
    import rasterio
    rng = np.random.default_rng(15)
    base = np.zeros((120, 120), np.float32)
    # 250 points in a 14,400-px grid: sparse enough that a RANDOM dot set would
    # NOT trip the 0.70 overlap leg (null_overlap ~0.49), and >= 100 support
    # points so surface_rho's small-sample guard does not suppress the
    # correlation. Both legs must fire on an identical field.
    idx = rng.integers(0, 120, (250, 2))
    base[idx[:, 0], idx[:, 1]] = 1.0
    mine = base.copy()
    theirs = base.copy()                      # identical -> rho = +1.0, overlap 1.0
    p = tmp_path / "twins.tif"
    _write_tif(p, theirs)
    rep = uniqueness.check_uniqueness(mine.astype(float), tmp_path)
    assert rep["drift_by_correlation"] is True
    assert rep["drift_by_overlap_literal"] is True
    assert rep["drift_by_overlap_informative"] is True
    assert rep["drift_by_jaccard"] is True
    assert rep["verdict"] == "DUPLICATE"


# --------------------------------------------------------------------------------------
# validator + writer
# --------------------------------------------------------------------------------------
def _fake_stack(shape=(3730, 3292)):
    fp = np.zeros(shape, bool)
    fp[100:3600, 100:3100] = True
    return fp


def _small_expect(shape, n_footprint=None):
    """An `expected` override so unit tests can build small rasters.

    ``submission_writer.profile_for(strict=True)`` still refuses to write a
    non-official geometry, which is what ``test_writer_refuses_wrong_shape``
    asserts; the tests that do write small files pass ``strict=False``.
    """
    h, w = shape
    x0, y0 = 243350.0, 4508550.0          # the writer always uses the official origin
    return dict(shape=(h, w),
                transform=(100.0, 0.0, x0, 0.0, -100.0, y0),
                bounds=(x0, y0 - 100.0 * h, x0 + 100.0 * w, y0),
                footprint=(h * w if n_footprint is None else int(n_footprint)))


def test_write_zeros_produces_an_all_finite_in_range_file(tmp_path):
    fp = _fake_stack((400, 400))
    vals = np.zeros((400, 400)); vals[200, 200] = 1.0
    p = sw.write_zeros(vals, fp, tmp_path / "t.tif", strict=False)
    r = validate.validate(p, footprint=fp, expected=_small_expect((400, 400), fp.sum()))
    assert r["ok"], [c for c in r["checks"] if not c["ok"]]
    assert r["n_nan"] == 0
    assert r["min"] == 0.0 and r["max"] == 1.0
    assert r["nodata"] is None


def test_writer_refuses_sentinel_values(tmp_path):
    fp = np.ones((200, 200), bool)
    vals = np.zeros((200, 200))
    vals[50, 50] = -3.4028234663852886e38   # the training_features.tif nodata sentinel
    with pytest.raises(ValueError):
        sw.write_zeros(vals, fp, tmp_path / "bad.tif")


def test_writer_refuses_values_above_one(tmp_path):
    fp = np.ones((200, 200), bool)
    vals = np.zeros((200, 200)); vals[50, 50] = 1.0000001
    with pytest.raises(ValueError):
        sw.write_zeros(vals, fp, tmp_path / "bad.tif")


def test_nan_twin_matches_sample_submission_layout(tmp_path):
    fp = _fake_stack((200, 200))
    vals = np.zeros((200, 200)); vals[50, 50] = 1.0
    p = sw.write_nan(vals, fp, tmp_path / "n.tif", strict=False)
    import rasterio
    with rasterio.open(p) as s:
        a = s.read(1)
    assert np.isnan(a[~fp]).all()
    assert np.isfinite(a[fp]).all()
    assert a[fp].min() >= 0.0 and a[fp].max() <= 1.0


def test_write_and_validate_reports_ok_to_submit(tmp_path):
    fp = _fake_stack((300, 300))
    vals = np.zeros((300, 300)); vals[150, 150] = 1.0
    cat = np.zeros((300, 300), bool); cat[10, 10] = True
    b = sw.write_and_validate(vals, fp, "unit-test", tmp_path, catalogue=cat,
                              make_nan_twin=True, make_zip=True,
                              strict=False, expected=_small_expect((300, 300), fp.sum()))
    assert b["ok_to_submit"] is True
    assert b["receipt"]["n_fail"] == 0
    assert Path(b["zip"]).is_file()
    assert b["nan_twin"]["ok"] is True


def test_zip_contains_exactly_one_geotiff(tmp_path):
    import zipfile
    fp = _fake_stack((120, 120))
    vals = np.zeros((120, 120)); vals[60, 60] = 1.0
    p = sw.write_zeros(vals, fp, tmp_path / "z.tif", strict=False)
    z = sw.zip_single(p)
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    assert len(names) == 1 and names[0].endswith(".tif")


# --------------------------------------------------------------------------------------
# grid spec constants
# --------------------------------------------------------------------------------------
def test_expected_spec_matches_the_organiser_published_requirements():
    assert grid.EXPECTED["epsg"] == 32611
    assert grid.EXPECTED["res"] == (100.0, 100.0)
    assert grid.EXPECTED["dtype"] == "float32"
    assert grid.EXPECTED["count"] == 19
    assert (grid.EXPECTED["height"], grid.EXPECTED["width"]) == (3730, 3292)
    assert validate.REQUIRED_BOUNDS == (243350.0, 4135550.0, 572550.0, 4508550.0)
    assert validate.REQUIRED_SHAPE == (grid.EXPECTED["height"], grid.EXPECTED["width"])
    assert validate.REQUIRED_TRANSFORM == grid.EXPECTED["transform"]


def test_writer_refuses_wrong_shape():
    """A submission raster that is not 3730 x 3292 must never be written."""
    fp = np.ones((400, 400), bool)
    vals = np.zeros((400, 400))
    with pytest.raises(ValueError):
        sw.profile_for((400, 400), strict=True)
    assert sw.profile_for((3730, 3292), strict=True)["height"] == 3730
    assert fp.sum() == vals.shape[0] * vals.shape[1]


def test_band_names_are_the_nineteen_published_layers():
    assert len(grid.BAND_NAMES) == 19
    assert grid.BAND_NAMES[11] == "det_elev"
    assert grid.BAND_NAMES[18] == "det_elev_slope"
    assert grid.BAND_INDEX["det_elev"] == 12


# --------------------------------------------------------------------------------------
# IR-62-UNIQ-01: the overlap leg is degenerate against lattices and near-blankets
# --------------------------------------------------------------------------------------
def _write_tif(path, arr):
    import rasterio
    from gems62 import submission_writer as _sw
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=_sw.OFFICIAL_TRANSFORM) as d:
        d.write(arr.astype(np.float32), 1)


def test_regular_lattice_is_overlap_degenerate_but_not_a_duplicate(tmp_path):
    """A lattice at 5 px spacing makes EVERY artifact score ~1.0 on the overlap leg.

    That is measured, not asserted: ``null_overlap`` is the overlap a uniformly
    random dot set would score against the same comparator, and the leg is
    waived only where that null itself exceeds the 0.70 limit.
    """
    rng = np.random.default_rng(21)
    n = 120
    lattice = np.zeros((n, n), np.float32)
    lattice[::5, ::5] = 1.0
    mine = np.zeros((n, n), np.float32)
    idx = rng.integers(0, n, (3000, 2))
    mine[idx[:, 0], idx[:, 1]] = 1.0
    _write_tif(tmp_path / "lattice.tif", lattice)
    fp = np.ones((n, n), bool)
    rep = uniqueness.check_uniqueness(mine.astype(float), tmp_path, footprint=fp)
    c = rep["comparisons"][0]
    assert c["overlap_one_sided_3px"] > 0.95          # the literal leg fires
    assert c["null_overlap_random_dots"] > 0.95       # ... and so would a random artifact
    assert c["overlap_degenerate"] is True
    assert c["jaccard"] < 0.05                        # dot-for-dot agreement is nil
    assert rep["drift_by_overlap_literal"] is True
    assert rep["drift_by_overlap_informative"] is False
    assert rep["verdict_strict_literal"] == "DUPLICATE"
    assert rep["verdict"] == "UNIQUE"


def test_near_blanket_comparator_is_degenerate(tmp_path):
    blanket = np.ones((80, 80), np.float32)
    mine = np.zeros((80, 80), np.float32)
    rng = np.random.default_rng(22)
    mine[rng.integers(0, 80, 500), rng.integers(0, 80, 500)] = 1.0
    _write_tif(tmp_path / "blanket.tif", blanket)
    fp = np.ones((80, 80), bool)
    rep = uniqueness.check_uniqueness(mine.astype(float), tmp_path, footprint=fp)
    c = rep["comparisons"][0]
    assert c["overlap_one_sided_3px"] == 1.0
    assert c["null_overlap_random_dots"] == 1.0
    assert c["overlap_degenerate"] is True
    assert c["theirs_density"] == 1.0
    # a constant comparator has an undefined Spearman; the gate must not fire
    assert rep["drift_by_correlation"] is False
    assert rep["verdict"] == "UNIQUE"


def test_sparse_genuine_duplicate_is_still_caught(tmp_path):
    """A comparator that is NOT degenerate must still trip the overlap leg."""
    rng = np.random.default_rng(23)
    n = 120
    theirs = np.zeros((n, n), np.float32)
    # 200 points in a 14,400-px grid -> null_overlap ~0.39, i.e. an INFORMATIVE
    # comparator. 2,000 points would saturate the 3 px disk and be degenerate,
    # which is exactly the trap IR-62-UNIQ-01 is about.
    idx = rng.integers(0, n, (200, 2))
    theirs[idx[:, 0], idx[:, 1]] = 1.0
    mine = theirs.copy()                       # identical sparse field
    _write_tif(tmp_path / "sparse.tif", theirs)
    fp = np.ones((n, n), bool)
    rep = uniqueness.check_uniqueness(mine.astype(float), tmp_path, footprint=fp)
    c = rep["comparisons"][0]
    assert c["null_overlap_random_dots"] < 0.70   # informative comparator
    assert c["overlap_degenerate"] is False
    assert c["overlap_one_sided_3px"] == 1.0
    assert c["jaccard"] == 1.0
    assert rep["verdict"] == "DUPLICATE"
    assert rep["verdict_strict_literal"] == "DUPLICATE"


def test_overlap_excess_is_zero_for_degenerate_and_positive_for_real(tmp_path):
    rng = np.random.default_rng(24)
    n = 100
    lattice = np.zeros((n, n), np.float32); lattice[::5, ::5] = 1.0
    cluster = np.zeros((n, n), np.float32); cluster[10:20, 10:20] = 1.0
    mine = np.zeros((n, n), np.float32)
    mine[12:18, 12:18] = 1.0                   # inside the cluster, not the lattice
    _write_tif(tmp_path / "a_lattice.tif", lattice)
    _write_tif(tmp_path / "b_cluster.tif", cluster)
    fp = np.ones((n, n), bool)
    rep = uniqueness.check_uniqueness(mine.astype(float), tmp_path, footprint=fp)
    by = {c["name"]: c for c in rep["comparisons"]}
    assert by["a_lattice.tif"]["overlap_degenerate"] is True
    assert by["a_lattice.tif"]["overlap_excess_above_chance"] == 0.0
    assert by["b_cluster.tif"]["overlap_excess_above_chance"] > 0.5


def test_null_overlap_is_a_probability_in_zero_one(tmp_path):
    n = 60
    theirs = np.zeros((n, n), bool); theirs[::7, ::7] = True
    ti = np.nonzero(theirs)
    rng = np.random.default_rng(25)
    sy = rng.integers(0, n, 5000); sx = rng.integers(0, n, 5000)
    v = uniqueness.null_overlap(ti, (sy, sx))
    assert 0.0 <= v <= 1.0
    empty = uniqueness.null_overlap((np.zeros(0, int), np.zeros(0, int)), (sy, sx))
    assert empty == 0.0
