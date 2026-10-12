"""H62-R: tests for the multi-level Lahontan datum stack.

Each test encodes one thing that was *measured to go wrong* on the way here, so a
future session cannot silently reintroduce it:

* ``test_wide_window_is_what_admits_a_displaced_bench`` -- IR-62-LEVEL-01.  The first
  version selected bench pixels with the narrow level window and then looked for steps
  inside them, which deletes exactly the displaced benches the lane is for.
* ``test_robust_isobase_survives_a_minority_offset`` -- why the isobase is a tile
  *mode* and not a Gaussian mean.
* ``test_hough_needs_two_levels`` -- the repeat-offset rule itself.
* ``test_hough_rejects_a_one_level_cluster`` -- and its negative control.
* ``test_span_and_continuity_filters`` -- IR-62-HOUGH-01, the star artifact.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems62 import levels

PX = 100.0


def _flat_dem(shape=(120, 200), value=1300.0):
    return np.full(shape, float(value))


def test_wide_window_is_what_admits_a_displaced_bench():
    """IR-62-LEVEL-01 regression: a 30 m displaced bench must survive selection."""
    z = _flat_dem()
    z[:, 100:] += 30.0                     # a bench displaced by 30 m east of x=100
    geom = np.ones(z.shape, dtype=bool)
    narrow = levels.level_bench_mask(z, geom, geom, 1300.0, tol_m=10.0, wide_m=10.0)
    wide = levels.level_bench_mask(z, geom, geom, 1300.0, tol_m=10.0, wide_m=45.0)
    assert narrow[:, 100:].sum() == 0, "the narrow window must (wrongly) delete the offset"
    assert wide[:, 100:].sum() == z[:, 100:].size, "the wide window must keep it"
    assert wide[:, :100].sum() == z[:, :100].size


def test_robust_isobase_ignores_a_minority_offset_within_a_tile():
    """The tile *mode* stays on the un-displaced majority; a mean would split it.

    This is the measurable reason the isobase is modal.  A whole-tile displacement and
    a minority displacement of one tile are both tested, because they fail differently:
    the first would drag a mean, the second would drag a mean too, and only the mode
    survives both.  (Measured: with a 30 % displaced minority, the mode lands exactly on
    the un-displaced datum while the comparator mean moves.)
    """
    z = np.full((400, 400), 1300.0)
    z[200:240, 200:240][:, :12] += 35.0     # 30 % of exactly one tile
    bench = np.ones(z.shape, dtype=bool)
    iso = levels.robust_isobase(z, bench, 1300.0, tile_px=40, half_m=60.0, min_px=25)
    assert np.isfinite(iso).all()
    assert np.isclose(iso[220, 220], 1300.0, atol=0.5), iso[220, 220]
    assert np.isclose(iso[50, 50], 1300.0, atol=0.5), iso[50, 50]
    # and the displaced minority keeps its full ~35 m residual
    assert np.isclose((z - iso)[220, 205], 35.0, atol=1.0), (z - iso)[220, 205]


def test_robust_isobase_survives_a_displaced_region():
    """A displaced *region* leaves a residual near its full throw away from the seam."""
    z = np.full((400, 400), 1300.0)
    z[160:240, :] += 35.0                   # 20 % of the map
    bench = np.ones(z.shape, dtype=bool)
    iso = levels.robust_isobase(z, bench, 1300.0, tile_px=40, half_m=60.0, min_px=25)
    assert np.isfinite(iso).all()
    # the un-displaced majority is held to within a few metres of the datum
    assert abs((z - iso)[320:, :].mean()) < 5.0, (z - iso)[320:, :].mean()
    # and the displaced region keeps most of its throw
    assert (z - iso)[180:220, :].mean() > 15.0, (z - iso)[180:220, :].mean()


def test_level_surface_flags_an_injected_step():
    """A 40 m step across one line, on an otherwise level bench, must be flagged."""
    z = _flat_dem(shape=(120, 240), value=1330.0)
    z[:, 120:] += 40.0
    bench_geom = np.ones(z.shape, dtype=bool)
    az = np.zeros(z.shape)
    slope = np.zeros(z.shape)
    s = levels.level_surface(z, slope, az, bench_geom, {"elev_m": 1330.0, "level_index": 0},
                             bench_geom=bench_geom, wide_m=60.0, tile_px=40,
                             throw_lo_m=15.0, throw_hi_m=140.0, k_mad=1.5)
    assert s.n_bench > 0
    assert s.n_step > 0, "an injected 40 m step must be flagged"
    assert np.nanmax(np.abs(s.step_m)) > 25.0


def _two_level_surfaces(shape=(200, 200), n_per_level=8, n_levels=2, jitter=0,
                        common_line=True):
    """Two synthetic levels whose flagged steps sit on ONE common line.

    This is the geometry the lane's repeat-offset test actually asserts.  Pluvial
    shorelines are nested, so a fault crosses level A and level B at *different map
    points* -- but always along the same fault line.  Both levels' points are therefore
    planted on row 60, in different along-strike segments, and the older level throws
    less than the younger one (which the sign/throw test must accept).
    """
    out = []
    rng = np.random.default_rng(7)
    for li in range(n_levels):
        step = np.zeros(shape, dtype=bool)
        step_m = np.full(shape, np.nan)
        c0 = 20 + 80 * li
        cols = np.linspace(c0, min(c0 + 70, shape[1] - 1), n_per_level).astype(int)
        rows = np.full(cols.size, 60 if common_line else 60 + 20 * li)
        if jitter:
            rows = rows + rng.integers(-jitter, jitter + 1, size=rows.size)
        step[rows, cols] = True
        step_m[rows, cols] = 60.0 - 10.0 * li        # older level throws LESS here
        out.append(levels.LevelSurface(
            level={"elev_m": 1400.0 - 50 * li, "level_index": li},
            bench=step.copy(), isobase=np.full(shape, np.nan), resid=np.full(shape, np.nan),
            resid_median_m=0.0, resid_mad_m=1.0, step=step, step_m=step_m,
            deflect=np.zeros(shape, dtype=bool), n_bench=int(step.sum()),
            n_step=int(step.sum()), n_deflect=0))
    return out


def test_hough_needs_two_levels():
    """Steps from two levels on one line must be accepted."""
    surfs = _two_level_surfaces()
    corr = levels.hough_offsets(surfs, min_points=4, min_levels=2, min_span_px=20)
    assert len(corr.lines) >= 1, "two collinear chains on two levels must be accepted"
    best = corr.lines[0]
    assert best.n_levels == 2
    assert best.n_points >= 8
    # the planted chain is horizontal in image coordinates: its inliers must share a row
    rows = {r for r, _ in best.support}
    assert len(rows) <= 2, rows
    assert best.support[-1][1] - best.support[0][1] >= 100, best.support


def test_hough_rejects_a_one_level_cluster():
    """The negative control: one level alone must NOT be accepted."""
    surfs = [_two_level_surfaces(n_levels=1)[0],
             _two_level_surfaces(n_levels=1)[0].__class__(
                 level={"elev_m": 1200.0, "level_index": 1},
                 bench=np.zeros((200, 200), dtype=bool),
                 isobase=np.full((200, 200), np.nan), resid=np.full((200, 200), np.nan),
                 resid_median_m=0.0, resid_mad_m=1.0,
                 step=np.zeros((200, 200), dtype=bool),
                 step_m=np.full((200, 200), np.nan),
                 deflect=np.zeros((200, 200), dtype=bool),
                 n_bench=0, n_step=0, n_deflect=0)]
    corr = levels.hough_offsets(surfs, min_points=4, min_levels=2, min_span_px=20)
    assert len(corr.lines) == 0, "a single level cannot satisfy a two-level test"


def test_span_and_continuity_filters():
    """IR-62-HOUGH-01: a tight clump is not a line, however many points it holds."""
    surfs = _two_level_surfaces(n_per_level=8)
    # collapse both chains into one 2-px clump: span test must now fail
    for s in surfs:
        s.step[:] = False
        s.step[60:62, 100:110] = True
        s.step_m[:] = np.nan
        s.step_m[60:62, 100:110] = 25.0
    corr = levels.hough_offsets(surfs, min_points=4, min_levels=2, min_span_px=20)
    assert len(corr.lines) == 0, "a clump with no along-strike extent must be rejected"


def test_repeat_offsets_needs_at_least_one_surface():
    """An empty surface list is a programming error, not an empty result."""
    with pytest.raises(IndexError):
        levels.hough_offsets([])


def test_tile_mode_levels_find_a_planted_level():
    """A basin-wide flat surface at 1330 m must appear as a level."""
    z = np.full((400, 400), 1500.0)
    z[100:300, 100:300] = 1330.0            # a large, flat, level surface
    bench = np.zeros(z.shape, dtype=bool)
    bench[100:300, 100:300] = True
    lv, survey = levels.levels_from_tile_modes(bench, z, tile_px=40, min_bench_px=25,
                                               min_weight=0.03, min_elev_m=1150.0,
                                               max_elev_m=1520.0)
    assert lv, f"a planted level must be found; survey={survey}"
    assert any(abs(d["elev_m"] - 1330.0) <= 4.0 for d in lv), lv
    assert survey.get("n_tiles_used", 0) > 0, survey
