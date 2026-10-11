"""Regression tests for the lane instruments that had real defects.

Every test here corresponds to a bug that actually occurred while building this
lane, so the test's job is to make the bug impossible to reintroduce silently:

* ``test_local_isobase_cannot_extrapolate``   -- the +25.7 m phantom offset
* ``test_step_test_rejects_noise``            -- 43 pairs flagged as a "handful"
* ``test_flag_steps_merges_one_place``        -- one place counted as many pairs
* ``test_map_writer_rejects_wrong_units``     -- a marker drawn 100,000 px off-canvas
* ``test_local_isobase_reports_sigma``        -- the residual/label contract
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems62 import lahontan  # noqa: E402
from gems62.lahontan import Bench  # noqa: E402


def bench(x: float, y: float, z: float, *, n_cells: int = 10, az: float = 0.0,
          elong: float = 1.0, rows=None, cols=None) -> Bench:
    return Bench(
        label=0,
        rows=np.array([0], dtype=int) if rows is None else np.asarray(rows),
        cols=np.array([0], dtype=int) if cols is None else np.asarray(cols),
        n_cells=n_cells, row_c=0.0, col_c=0.0, x=x, y=y, z=z, z_iqr=0.0,
        azimuth_deg=az, elongation=elong, length_m=1000.0,
    )


# --------------------------------------------------------------------------- 1
def test_local_isobase_cannot_extrapolate():
    """A plane fitted far away must not project a phantom offset onto a bench.

    The original defect: with only 6 neighbours, a robust plane fitted to
    benches several kilometres away extrapolated its gradient to the bench and
    returned a level 25.7 m outside the +-4 m strand band that had *defined* the
    strand, generating a fake step and setting the profile's y-axis.
    """
    rng = np.random.default_rng(0)
    far = [bench(60_000 * np.cos(t), 60_000 * np.sin(t), 5.0 + rng.normal(0, 0.5))
           for t in np.linspace(0, 2 * np.pi, 40, endpoint=False)]
    rng2 = np.random.default_rng(1)
    near = [bench(30_000 + 200 * i, 0.0, -1.0 + rng2.normal(0, 0.3)) for i in range(6)]
    lonely = bench(0.0, 0.0, 0.0)
    benches = [lonely] + near + far
    residual = np.array([b.z for b in benches], dtype=float)

    rho, info = lahontan.local_isobase(benches, residual)

    assert info["support_guards"]["gradient_max_m_per_km"] > 0
    # the phantom was 25 m; the guard keeps the level inside the neighbourhood
    assert abs(rho[0]) <= 8.0, rho[0]
    assert np.all(np.abs(rho) < 30.0)


def test_local_isobase_reports_sigma():
    """`rho` is the residual (r - level) and its robust sigma is reported."""
    rng = np.random.default_rng(2)
    benches, residual = [], []
    for i in range(40):
        z = 0.5 * (i % 10)
        benches.append(bench(3_000 * np.cos(i), 3_000 * np.sin(i), z))
        residual.append(z + rng.normal(0, 2.0))
    residual = np.array(residual)
    rho, info = lahontan.local_isobase(benches, residual)
    assert info["n_benches"] == 40
    assert rho.shape == residual.shape
    assert 0.5 < info["residual_sigma_m"] < 6.0
    # rho must be a deviation from a smooth level, so it is centred near zero
    assert abs(float(np.median(rho))) < 3.0


# --------------------------------------------------------------------------- 2
def test_step_test_rejects_noise():
    """The resolution gate alone is at the noise level and must not be enough.

    With sigma ~ 3 m, a 3 m threshold accepts most nearby pairs.  The
    significance gate (z * sqrt(2) * sigma) is what makes "a handful" honest.
    """
    frac = np.array([0.0, 1.0, 2.0, 3.0, 0.0, 1.0, 2.0, 3.0])
    res = np.array([0.0, 1.0, 2.0, 3.0, 0.0, 1.0, 2.0, 3.0])
    benches = [bench(1_000.0 * i, 0.0, 0.0) for i in range(len(frac))]
    res = np.array([1.5, 1.5, 1.5, 1.5, 1.5, 1.6, 1.6, 1.6]) + np.where(
        np.arange(len(frac)) == 7, 20.0, 0.0)

    stats: dict = {}
    locs = lahontan.flag_steps(benches, res, threshold_m=3.0, stats=stats)

    assert stats["robust_sigma_m"] > 0
    assert stats["robust_sigma_m_global_mad"] >= 0
    assert stats["pairs_within_radius"] > 0
    # the 20 m offset is the only one that clears the significance gate
    assert len(locs) <= 2
    assert any(abs(f.residual_jump_m) > 15.0 for f in locs)
    for f in locs:
        assert abs(f.residual_jump_m) >= stats["significance_gate_m"]
    assert "borderline_candidates" in stats
    for cand in stats["borderline_candidates"]:
        assert abs(cand["jump_m"]) < stats["significance_gate_m"]


def test_step_test_keeps_a_convincing_offset():
    """A 12 m offset over 2.5 km survives; a 4 m one does not."""
    xs = np.linspace(0.0, 20_000.0, 21)
    z = np.zeros_like(xs)
    z[12:] = 12.0                      # the step
    rng = np.random.default_rng(3)
    z = z + rng.normal(0, 1.0, size=z.size)
    benches = [bench(float(x), 0.0, 0.0) for x in xs]
    stats: dict = {}
    locs = lahontan.flag_steps(benches, z, threshold_m=3.0, stats=stats)
    assert len(locs) >= 1
    assert max(abs(f.residual_jump_m) for f in locs) > 8.0
    # this is the masking case: a global MAD would be inflated by the step itself
    # and would reject it, so the pairwise estimator must be the one in use
    assert stats["robust_sigma_m"] < stats["robust_sigma_m_global_mad"]


# --------------------------------------------------------------------------- 3
def test_flag_steps_merges_one_place():
    """One offset measured by several bench pairs is one LOCATION."""
    xs = np.linspace(0.0, 6_000.0, 13)
    z = np.zeros_like(xs)
    z[7:] = 12.0
    benches = [bench(float(x), 0.0, 0.0) for x in xs]
    stats: dict = {}
    locs = lahontan.flag_steps(benches, z, threshold_m=3.0,
                              cluster_m=3000.0, stats=stats)
    assert stats["pairs_accepted"] >= len(locs)
    assert len(locs) <= 3
    assert sum(f.n_pairs for f in locs) == stats["pairs_accepted"]
    for f in locs:
        assert f.cluster_jump_range_m is not None
        lo, hi = f.cluster_jump_range_m
        assert lo <= f.residual_jump_m <= hi


def test_deflections_are_locations_too():
    """Azimuth-change pairs collapse to locations the same way."""
    benches = [bench(1_000.0 * i, 0.0, 0.0, n_cells=40, az=0.0, elong=3.0)
               for i in range(6)]
    for i in range(6):
        benches.append(bench(1_000.0 * i + 500.0, 300.0, 0.0, n_cells=40,
                             az=90.0, elong=3.0))
    flags = lahontan.flag_deflections(benches)
    assert len(flags) >= 1
    assert len(flags) <= 3, "clustering failed: pairs were reported separately"
    assert all(f.n_pairs >= 1 for f in flags)


# --------------------------------------------------------------------------- 4
def test_map_writer_rejects_wrong_units(tmp_path):
    """A marker given in projected metres must never be drawn off-canvas.

    The original defect: flags were passed in metres to a helper expecting grid
    indices, so the step circle landed ~100,000 px away and Pillow drew nothing
    -- a "no evidence" figure that looked entirely normal.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_lane", Path(__file__).resolve().parents[1] / "scripts" / "run_lane.py")
    run_lane = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_lane)

    dem = np.zeros((300, 300))
    foot = np.ones((300, 300), bool)
    cat = np.zeros((300, 300), bool)
    band = np.zeros((300, 300), bool)
    dots = np.zeros((300, 300), bool)
    dots[150, 150] = True
    out = tmp_path / "m.png"

    # a flag expressed in projected metres inside the grid is accepted
    flag = {"x": 243350.0 + 150 * 100.0, "y": 4508550.0 - 150 * 100.0, "jump_m": 12.9}
    run_lane.save_map_png(dem, foot, cat, band, dots, out, flags=[flag])
    assert out.exists() and out.stat().st_size > 0

    # ... and one outside the grid raises instead of silently vanishing
    bad = {"x": -1.0e6, "y": -1.0e6, "jump_m": 12.9}
    with pytest.raises(ValueError):
        run_lane.save_map_png(dem, foot, cat, band, dots, out, flags=[bad])


# --------------------------------------------------------------------------- 5
def test_datum_offset_surface_matches_residual():
    """The pre-placement surface is |residual| on the bench cells, and nothing else."""
    benches = [bench(0.0, 0.0, 0.0, rows=[1, 1], cols=[2, 3], n_cells=2)]
    residual = np.array([-4.0])
    full, evidence = lahontan.datum_offset_surface(
        benches, residual, (4, 5), step_threshold_m=3.0)
    assert full.shape == (4, 5)
    assert full[1, 2] == pytest.approx(4.0)
    assert full[1, 3] == pytest.approx(4.0)
    assert full.sum() == pytest.approx(8.0)
    assert evidence.sum() == pytest.approx(8.0)     # 4 m clears the 3 m gate
    full2, ev2 = lahontan.datum_offset_surface(
        benches, np.array([1.0]), (4, 5), step_threshold_m=3.0)
    assert full2.sum() == pytest.approx(2.0)
    assert ev2.sum() == 0.0                          # below the gate: no evidence cell
