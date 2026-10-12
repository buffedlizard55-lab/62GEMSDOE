"""Regression tests for the array/world axis conventions (IR-62-J-01, IR-62-J-02).

Two shipped helpers of this lane mixed up the row/col axes.  Each test states the geometry,
asserts the CORRECT value, and -- where the point is that the old code was blind -- asserts the
failure through the legacy switch, so the defect is documented by an executable rather than by
prose.  Ramps (not hard steps) are used where a constant gradient is wanted, because a
staircased hard step has a spatially wild gradient magnitude.

Conventions under test: north-up grid, ``res`` metres; column index increases east, row index
increases south.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import geom  # noqa: E402

RES = 25.0
H, W = 241, 241


def _xy():
    """World coordinates of every pixel centre, with the array centre at (0, 0)."""
    r = np.arange(H, dtype=np.float64)
    c = np.arange(W, dtype=np.float64)
    x = np.broadcast_to((c[None, :] - W / 2.0) * RES, (H, W))
    y = np.broadcast_to(-(r[:, None] - H / 2.0) * RES, (H, W))
    return x, y


def ramp_field(strike_deg: float, amp: float = 5.0, width_m: float = 200.0) -> np.ndarray:
    """A plane that rises by `amp` across a zone of width `width_m`, centred on the array.

    The zone's boundary line strikes `strike_deg` (deg from north, clockwise); the gradient is
    constant and perpendicular to it.
    """
    th = np.radians(strike_deg)
    nx, ny = np.cos(th), -np.sin(th)          # unit normal to a line of that strike
    x, y = _xy()
    d = x * nx + y * ny
    return (amp * np.clip(d / width_m + 0.5, 0.0, 1.0)).astype(np.float32)


def step_field(strike_deg: float, amp: float = 5.0) -> np.ndarray:
    th = np.radians(strike_deg)
    nx, ny = np.cos(th), -np.sin(th)
    x, y = _xy()
    return np.where(x * nx + y * ny > 0.0, amp, 0.0).astype(np.float32)


def fault_on_a_dipping_datum(throw_m: float = 6.0, tilt_m_per_m: float = 0.02,
                             fault_strike_deg: float = 0.0):
    """Synthetic lane geometry: a flat bench, one vertical fault of `throw_m`, an isobase that
    dips in the direction perpendicular to the fault.  Returns (z, isobase, bench_score).

    The isobase is set halfway between the two bench panels, so both flanks sit on the datum
    within `throw/2` -- which is exactly the paired-bench ("doublet") condition.
    """
    th = np.radians(fault_strike_deg)
    nx, ny = np.cos(th), -np.sin(th)                 # across-fault direction
    x, y = _xy()
    d = x * nx + y * ny
    along = x * -ny + y * nx                          # along-fault direction
    # The datum (isobase) is a tilted plane; the two bench panels are PARALLEL to it and offset
    # by +-throw/2, which is what "the shoreline is displaced by a fault" means.  r = z - iso is
    # then piecewise constant, and the only structure in |grad r| is the fault itself.
    iso = (tilt_m_per_m * along).astype(np.float32)
    z = (iso + np.where(d > 0.0, throw_m / 2.0, -throw_m / 2.0)).astype(np.float32)
    return z, iso, np.ones_like(z, np.float32)


# ---------------------------------------------------------------------------------------------
# 1. the gradient helper and the azimuth mapping
# ---------------------------------------------------------------------------------------------
def test_grad_arr_signs_and_units():
    x, y = _xy()
    z = (0.1 * x).astype(np.float32)                  # rises eastward at 0.1 m/m
    dzdr, dzdc = geom.grad_arr(z, RES)
    assert abs(float(np.median(dzdc)) - 0.1) < 1e-4
    assert abs(float(np.median(dzdr))) < 1e-4
    z2 = (0.1 * y).astype(np.float32)                 # rises northward
    dzdr2, dzdc2 = geom.grad_arr(z2, RES)
    assert float(np.median(dzdr2)) < 0.0               # north is -row, so dz/drow < 0
    assert abs(float(np.median(dzdc2))) < 1e-4


@pytest.mark.parametrize("strike", [0.0, 30.0, 45.0, 90.0, 135.0, 160.0])
def test_ascent_and_strike_azimuths(strike: float):
    """Strike of a ramp line is recovered from the ascent direction, for any strike."""
    z = ramp_field(strike, amp=5.0)
    dzdr, dzdc = geom.grad_arr(z, RES)
    mag = np.hypot(dzdr, dzdc)
    inner = (slice(60, 181), slice(60, 181))
    on = (mag > 0.9 * mag.max()) & (mag > 0)
    on &= np.zeros_like(on)
    on[inner] = (mag[inner] > 0.9 * mag.max())
    assert on.sum() > 200, strike
    ur, uc = geom.unit_ascent(dzdr, dzdc)
    az = geom.strike_azimuth_from_ascent(geom.azimuth_from_drc(ur, uc))[on]
    got = float(np.median(az))
    d = abs(got - strike) % 180.0
    assert min(d, 180.0 - d) < 3.0, (strike, got)


# ---------------------------------------------------------------------------------------------
# 2. IR-62-J-01: measuring the offset ACROSS a structure vs ALONG it
# ---------------------------------------------------------------------------------------------
def test_offset_across_a_ns_ramp_and_legacy_blindness():
    z = ramp_field(0.0, amp=5.0)                       # N-S striking ramp, 5 m total
    dzdr, dzdc = geom.grad_arr(z, RES)
    ur, uc = geom.unit_ascent(dzdr, dzdc)
    plus, minus = geom.offset_pair(z, ur, uc, 250.0, RES)
    assert float(np.nanmax(np.abs(plus - minus))) > 4.5
    lr, lc = dzdc / (np.hypot(dzdr, dzdc) + 1e-12), dzdr / (np.hypot(dzdr, dzdc) + 1e-12)
    p2, m2 = geom.offset_pair(z, lr, lc, 250.0, RES)
    assert float(np.nanmax(np.abs(p2 - m2))) < 0.2      # sampled ALONG the line -> blind


def test_shift_by_unit_moves_in_world_directions():
    x, y = _xy()
    z = (1.0 * x).astype(np.float32)                   # 1 m per metre eastward
    zero_r = np.zeros_like(z); one_c = np.ones_like(z)
    inner = (slice(40, 200), slice(60, 180))
    p = geom.shift_by_unit(z, zero_r, one_c, 100.0, RES)
    assert abs(float(np.median(p[inner] - z[inner])) - 100.0) < 1.0
    m = geom.shift_by_unit(z, zero_r, one_c, -100.0, RES)
    assert abs(float(np.median(m[inner] - z[inner])) + 100.0) < 1.0


def test_legacy_blindness_through_the_shipped_helper():
    """Same statement as above, through ``datum.doublet_surfaces`` -- the code path the lane
    actually used, not a copy of it."""
    from gems62 import datum
    z = ramp_field(0.0, amp=6.0)
    iso = np.zeros_like(z)
    bench = np.ones_like(z, np.float32)
    kw = dict(min_step_m=0.5, flank_tol_m=1e9, max_shore_distance_m=1e9, min_cross_angle_deg=0.0)
    good = datum.doublet_surfaces(z, iso, bench, RES, **kw)
    bad = datum.doublet_surfaces(z, iso, bench, RES, legacy_axis_swap=True, **kw)
    assert float(np.nanmax(good["step"])) > 5.4
    assert float(np.nanmax(bad["step"])) < 0.6


def test_doublet_surfaces_measure_a_fault_on_the_dipping_datum():
    from gems62 import datum
    z, iso, bench = fault_on_a_dipping_datum(throw_m=6.0)
    su = datum.doublet_surfaces(z, iso, bench, RES, min_step_m=1.0, flank_tol_m=3.5,
                               max_shore_distance_m=1e9, min_cross_angle_deg=30.0,
                               corr_sigma_m=200.0)
    prof = su["step"].max(axis=0)                      # collapse along the (N-S) fault
    assert prof.max() > 5.0, float(prof.max())
    # LOCALISATION comes from the ridge field: the raw offset measurement is plateued over
    # +-offset_half_m by construction (any pixel whose +-250 m sample straddles the fault sees
    # the full jump), so evid -- not step -- is what puts the dot on the structure.
    assert int(np.argmax(su["evid"].max(axis=0))) in range(W // 2 - 2, W // 2 + 3), \
        int(np.argmax(su["evid"].max(axis=0)))
    on = su["gates"]
    assert on.sum() > 200, "the doublet gate should stay open along a real datum offset"
    d = float(np.median(su["cross_deg"][on]))
    assert d > 60.0, d                                  # the fault crosses the datum contours
    st = su["az_step"][on]
    ds = float(np.median(st)) % 180.0
    assert min(ds, 180.0 - ds) < 5.0, ds                # ... and its measured strike is N-S


def test_doublet_gate_rejects_a_step_that_is_not_a_datum_offset():
    """A 6 m riser whose flanks are 60 m off the datum is a level feature, not an offset bench."""
    from gems62 import datum
    z, iso, bench = fault_on_a_dipping_datum(throw_m=6.0)
    iso = iso - 60.0                                    # push the datum far below both panels
    su = datum.doublet_surfaces(z, iso, bench, RES, min_step_m=1.0, flank_tol_m=3.5,
                               max_shore_distance_m=1e9, min_cross_angle_deg=0.0)
    assert float(np.nanmax(su["step"])) > 5.0           # the step is real...
    assert not su["doublet_ok"].any()                    # ...but neither flank is on the datum


def test_datum_step_loci_finds_a_ns_datum_step():
    from gems62 import datum
    z, iso, bench = fault_on_a_dipping_datum(throw_m=6.0)
    kw = dict(max_loci=5, suppression_m=500.0, min_datum_evidence=0.0, min_step_m=1.0,
              max_shore_distance_m=1e9, min_cross_angle_deg=30.0)
    out = datum.datum_step_loci(z, iso, bench, RES, legacy_axis_swap=False,
                                flank_tol_m=3.5, **kw)
    assert out["loci"], "no loci found on a 6 m step in the datum residual"
    st = float(out["loci"][0]["strike_deg"]) % 180.0
    assert min(st, 180.0 - st) < 10.0, out["loci"][0]
    legacy = datum.datum_step_loci(z, iso, bench, RES, legacy_axis_swap=True, **kw)
    assert not legacy["loci"], "the legacy mapping should be blind to this structure"


# ---------------------------------------------------------------------------------------------
# 3. IR-62-J-02: the along-strike sign in ScarpField.from_dem
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("strike", [0.0, 45.0, 90.0, 135.0])
def test_scarpfield_strike_matches_the_true_line(strike: float):
    """The east component of the along-strike vector used to carry the wrong sign, mirroring
    every non-orthogonal strike (135 deg came back as 45 deg)."""
    from gems62 import datum
    z = ramp_field(strike, amp=6.0, width_m=150.0)
    sc = datum.ScarpField.from_dem(z, RES, sigma_m=25.0, sigma_strike_m=25.0)
    mag = np.hypot(*geom.grad_arr(z, RES))
    on = mag > 0.9 * mag.max()
    got = float(np.median(sc.strike_deg[on]))
    d = abs(got - strike) % 180.0
    assert min(d, 180.0 - d) < 6.0, (strike, got)
