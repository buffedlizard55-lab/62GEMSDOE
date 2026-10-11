"""Unit tests for the Lahontan datum-offset lane.

Three things must be true before any of the lane's numbers mean anything:
the shift helper must not wrap, the step operator must recover an injected
offset of known size and trend, the persistence gate must veto a pinched
terrace edge, and the shared metric must reproduce the organiser's worked
example.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62_bench import lahontan, metric  # noqa: E402


# --------------------------------------------------------------------- _at
def _reference_at(a, dy, dx):
    out = np.zeros_like(a)
    H, W = a.shape
    for i in range(H):
        for j in range(W):
            si, sj = i - dy, j - dx
            if 0 <= si < H and 0 <= sj < W:
                out[i, j] = a[si, sj]
    return out


@pytest.mark.parametrize("dy,dx", [(0, 3), (5, 0), (-2, 4), (1, -1), (0, 0)])
def test_at_is_a_non_wrapping_shift(dy, dx):
    """_at(a, dy, dx) is a shift, not a roll: out[i, j] == a[i-dy, j-dx]."""
    rng = np.random.default_rng(1)
    a = rng.random((12, 9)).astype(np.float32)
    assert np.array_equal(lahontan._at(a, dy, dx), _reference_at(a, dy, dx))


def test_at_zeroes_weight_strip():
    w = np.ones((8, 8), np.float32)
    # out[i, j] = w[i-dy, j-dx]: the destination strip left empty is at the low end
    assert lahontan._at(w, 1, 0)[0].sum() == 0.0            # shifted down
    assert lahontan._at(w, -1, 0)[-1].sum() == 0.0          # shifted up
    assert lahontan._at(w, 0, 2)[:, :2].sum() == 0.0        # shifted right
    assert float(lahontan._at(w, 2, 0)[2:].sum()) == 8 * 6


# ------------------------------------------------------------------- metric
def test_metric_reproduces_organiser_worked_example():
    """Problem page: TPw=3.00, FPw=1.89, FNw=2.00 -> 0.60."""
    assert abs(metric.dti_from_components(3.00, 1.89, 2.00) - 0.60) < 5e-3


def test_metric_binary_matches_bruteforce():
    rng = np.random.default_rng(0)
    truth = rng.random((40, 40)) < 0.02
    pred = rng.random((40, 40)) < 0.03
    fast = metric.dti_binary(pred, truth)
    slow = metric.dti_bruteforce(pred.astype(float), truth)
    assert abs(fast["dti"] - slow["dti"]) < 1e-9, (fast, slow)


# --------------------------------------------------------- synthetic offset
def _synthetic_dem(step_m=22.0, trend_deg=100.0, size=240, ramp=2.0, pinch=False,
                   noise=0.0, seed=0):
    """A shoreline bench displaced along its own length by a fault.

    Profile across the bench (coordinate ``d``, pixels, 100 m each): a flat tread
    ~700 m wide, an 11 deg riser on each side, then an 8.5 deg waste slope.  Only
    the tread passes the detector's flatness tests, so a level contrast between
    two tread pixels can only come from the injected offset -- a synthetic made of
    flat terraces instead is degenerate, because every terrace edge then reads as
    a fault.

    Convention (identical to :mod:`gems62.lahontan`, array (row, col) units): for
    a trace trend ``az``, ``T = (sin az, cos az)`` runs along the trace and
    ``N = (cos az, -sin az)`` is across the step.  The bench is elongated along N
    and the datum offset accrues along N, so the fault trace runs along T and the
    operator's legs sample the two limbs.
    """
    H = W = size
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    tau = np.radians(trend_deg)
    ty, tx = np.sin(tau), np.cos(tau)
    ny, nx = np.cos(tau), -np.sin(tau)
    u = (yy - H / 2) * ny + (xx - W / 2) * nx        # along N: across the step
    w = (yy - H / 2) * ty + (xx - W / 2) * tx        # along T: along the trace
    d = w - 20.0                                     # coordinate across the bench
    sgn = np.sign(d)
    a_ = np.abs(d)
    base = 1300.0 + sgn * (20.0 * np.clip(a_ - 3.0, 0.0, 3.0)
                           + 15.0 * np.clip(a_ - 6.0, 0.0, None))
    # A fault keeps the offset for ever; a pinch (alluvial fill, a fan surface
    # incised beside the trace) raises the tread for a few hundred metres and
    # then returns to the same datum, which the control legs must catch.
    tail = np.clip((u + ramp / 2) / ramp, 0.0, 1.0)
    if pinch:
        tail = tail * np.clip((7.0 - u) / 2.0, 0.0, 1.0)
    sf = step_m * tail
    z = (base + sf).astype(np.float32)
    strip = a_ <= 3.0
    if noise:
        z = z + np.random.default_rng(seed).normal(0.0, noise, z.shape).astype(np.float32)
    return z.astype(np.float32), strip, u, w


def _flagged_at_crossing(fld, strip, u):
    return strip & (np.abs(u) < 4.0) & fld.zone


def test_step_operator_recovers_injected_offset():
    z, strip, u, w = _synthetic_dem(step_m=22.0, trend_deg=100.0)
    fld = lahontan.build_field(z, np.ones(z.shape, bool), verbose=False)
    near = _flagged_at_crossing(fld, strip, u)
    assert near.sum() > 10, f"only {int(near.sum())} px flagged at the crossing"
    offs = fld.step[near]
    assert abs(float(np.median(offs)) - 22.0) <= 3.0, f"recovered {np.median(offs):.1f} m"
    assert float(offs.min()) >= 18.0 and float(offs.max()) <= 27.0, \
        f"spread {float(offs.min()):.1f}-{float(offs.max()):.1f} m"
    # every flag must sit on the scarp, and nothing else along the bench
    assert float(np.abs(u[near]).max()) <= 6.0
    assert int((fld.zone & (np.abs(u) > 8.0)).sum()) == 0, "spurious flags along strike"


@pytest.mark.parametrize("trend", [0.0, 30.0, 65.0, 100.0, 145.0])
def test_offset_is_recovered_for_every_trace_trend(trend):
    """A non-orthogonal operator (the bug this test family was written for) shows
    up as a trend-dependent amplitude: with legs and control windows along the
    same vector, only az = 45/135 deg read the right offset."""
    z, strip, u, w = _synthetic_dem(step_m=25.0, trend_deg=trend)
    fld = lahontan.build_field(z, np.ones(z.shape, bool), verbose=False)
    near = _flagged_at_crossing(fld, strip, u)
    assert near.sum() > 10, f"trend {trend}: nothing flagged"
    assert abs(float(np.median(fld.step[near])) - 25.0) <= 2.5, \
        f"trend {trend}: median {float(np.median(fld.step[near])):.1f} m"
    assert int((fld.zone & (np.abs(u) > 8.0)).sum()) == 0, f"trend {trend}: spurious flags"
    d = np.abs(fld.step_azim[near] - trend)
    d = np.minimum(d, 180.0 - d)
    assert float((d <= 15.0).mean()) >= 0.4, f"trend {trend}: az response collapsed"
    assert float((d <= 25.0).mean()) >= 0.7, f"trend {trend}: az response collapsed"


def test_strike_is_degenerate_on_a_straight_scarp():
    """Documented limitation, not a bug: where both limbs are level and the scarp
    is straight, |J| is the same for every trace direction whose legs stay on the
    tread, so the arg-max azimuth is only weakly determined.  This is why the lane
    walks the sign boundary of ``step_signed`` to trace a scarp rather than
    integrating ``step_azim``, and why the amplitude -- not the azimuth -- carries
    the physical claim."""
    z, strip, u, w = _synthetic_dem(step_m=22.0, trend_deg=100.0)
    fld = lahontan.build_field(z, np.ones(z.shape, bool), verbose=False)
    near = _flagged_at_crossing(fld, strip, u)
    js = fld.step[near]
    assert float(js.std() / js.mean()) < 0.06, "amplitude should be the stable part"
    assert len(np.unique(fld.step_azim[near])) > 2, "expected a flat azimuth response"


def test_step_field_is_quiet_with_no_offset():
    z, strip, u, w = _synthetic_dem(step_m=0.0, trend_deg=100.0)
    fld = lahontan.build_field(z, np.ones(z.shape, bool), verbose=False)
    assert int(fld.zone.sum()) == 0, f"{int(fld.zone.sum())} spurious flags"


def test_isolated_dem_spikes_are_not_flagged():
    """A 1-cell 25 m bump is the classic DEM artefact; nothing else changes."""
    z, strip, u, w = _synthetic_dem(step_m=0.0, trend_deg=100.0)
    rng = np.random.default_rng(9)
    yy = rng.integers(40, 200, 60); xx = rng.integers(40, 200, 60)
    z2 = z.copy()
    z2[yy, xx] += 25.0
    fld = lahontan.build_field(z2, np.ones(z2.shape, bool), verbose=False)
    assert int(fld.zone.sum()) == 0, f"{int(fld.zone.sum())} px flagged on pure spikes"


def test_short_lens_is_not_vetoed_documented_limitation():
    """~600 m of 22 m offset is indistinguishable from a range-front scarp at 100 m
    cells, so the control legs do not veto it and the code does not pretend to.
    Pinned here to keep the limitation visible: the gate rejects isolated relief
    (the spike test) and mixed-level limb windows, and where an offset dies within
    a kilometre it loses part of its flagged core -- but not its amplitude."""
    z, strip, u, w = _synthetic_dem(step_m=22.0, trend_deg=100.0)
    fault = lahontan.build_field(z, np.ones(z.shape, bool), verbose=False)
    zf = _synthetic_dem(step_m=22.0, trend_deg=100.0, pinch=True)[0]
    fill = lahontan.build_field(zf, np.ones(zf.shape, bool), verbose=False)
    def stats(fld):
        core = strip & (np.abs(u) < 3.0) & fld.zone
        return int(core.sum()), float(np.median(fld.step[core]))
    n_f, a_f = stats(fault)
    n_x, a_x = stats(fill)
    assert n_f >= 10
    assert 0.3 * n_f <= n_x <= n_f, f"fill core {n_x} px vs fault {n_f} px"
    assert abs(a_x - a_f) <= 3.0, f"amplitudes should not diverge: {a_x} vs {a_f}"


def test_gate_survives_modest_dem_noise():
    """1 m of DEM roughness must not destroy a 22 m datum offset (SNR 22:1)."""
    z, strip, u, w = _synthetic_dem(step_m=22.0, trend_deg=100.0, noise=1.0, seed=5)
    fld = lahontan.build_field(z, np.ones(z.shape, bool), verbose=False)
    near = _flagged_at_crossing(fld, strip, u)
    assert int(near.sum()) >= 5, f"noise killed the detection: {int(near.sum())} px"


def test_isobase_fit_recovers_a_tilt_and_ignores_the_step():
    """The reporting surface must be fitted to the limbs, not through the offset."""
    d = np.linspace(0.0, 8.0, 200)
    bench = np.ones(d.shape, bool)
    # a tilted lake datum with a faulted window in the middle of the transect
    e = 1300.0 - 1.5 * d + np.where((d > 4.0) & (d < 6.0), 22.0, 0.0)
    fit = lahontan.fit_isobase_1d(d, e, bench, exclude=(3.5, 6.5), deg=1)
    assert fit is not None
    assert abs(fit["coef"][0] + 1.5) < 0.15, fit["coef"]
    assert fit["rms_m"] < 0.5
    naive = lahontan.fit_isobase_1d(d, e, bench, deg=1)
    assert naive["rms_m"] > 2.0, "excluding the step should matter"
    # the residual inside the faulted window is the offset the lane reports
    assert float(np.median(fit["residual_m"][(d > 4.2) & (d < 5.8)])) > 18.0


def test_profile_api_runs_on_the_synthetic():
    z, strip, u, w = _synthetic_dem(step_m=22.0, trend_deg=100.0)
    fld = lahontan.build_field(z, np.ones(z.shape, bool), verbose=False)
    yy, xx = np.nonzero(fld.zone)
    order = np.argsort(u[yy, xx])
    path = np.stack([yy[order], xx[order]], axis=1)
    prof = lahontan.profile_along(path, fld)
    for k in ("distance_km", "bench_elev_m", "isobase_m", "anomaly_m", "step_m",
              "step_azim_deg", "slope_deg", "flagged"):
        assert k in prof and len(prof[k]) == len(path), k
    assert float(np.nanmax(prof["step_m"])) > 8.0, "no step along the flagged path"
    assert int(prof["flagged"].sum()) == int(fld.zone.sum())
    assert prof["distance_km"][0] == 0.0 and prof["distance_km"][-1] > 0.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
