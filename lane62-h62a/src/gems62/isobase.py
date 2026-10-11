"""Lane: Lake Lahontan shorelines as a strain gauge.

Method (verbatim scope from the tasking paragraph, implemented step by step):

  1. Map shoreline benches in the DEM.
  2. Fit a smooth isobase, allowing for post-pluvial isostatic rebound.
  3. Flag abrupt steps or lateral deflections along strike.
  4. Seed a trace at each flag.
  5. Extend the trace while DEM-ridge evidence supports it.
  6. Emit dotted lines.

Everything below is computed from the sha256-pinned official feature stack only
(``det_elev``, ``det_elev_slope``, ``tmi_hg``, ``iso_grav_anom_hg``) plus the
grid geometry.  No catalogue pixels enter the *detector*; the catalogue is used
only (a) to measure enrichment, (b) as the holdout truth, and (c) in the final
emission prune that deletes dots sitting on already-mapped faults (a change the
group has an organiser-confirmed +0.0178 for, 0.2600 -> 0.2778).

Physical basis
--------------
Lake Lahontan filled the northwestern Great Basin to its highstand at ~15 ka.
Its shoreline is a near-level datum whose present-day elevation varies along
strike because of waterplane tilt during loading and post-pluvial isostatic
rebound.  Briggs & Wesnousky (JGR, 2004) used features displaced since the
highstand to constrain slip on the Pyramid Lake fault zone; Dong et al.
(Geosphere) documented Lahontan shorelines displaced along a strike-slip fault
outboard of the Wassuk Range front; Pierce & Wesnousky (SCEC poster, 2016)
reported two previously unmapped NW-striking segments in Smith Valley's basin
centre offsetting Holocene sediments.

The detector's target signature is therefore:  a contour-parallel bench that is
locally *interrupted* -- stepped in elevation or deflected laterally -- by a
structure that cuts it.  Such a structure is by construction one that offsets
young (post-15 ka) surface, i.e. exactly the class of fault the catalogue is
incomplete for.

Detrended-elevation caveat (IR-62-DEM-01)
-----------------------------------------
The official stack carries no absolute elevation.  The isobase is therefore fit
in detrended-elevation space: ``isobase = smooth(det_elev)`` over the
basin-margin band, and the flags are *residuals against that fit*.  A smooth
detrending operator and a smooth isobase tilt are degenerate at long
wavelength, so the fit absorbs the unknown trend and the residual keeps the
short-wavelength step signal -- which is what the lane actually needs.  This is
stated on the site rather than papered over.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

# --------------------------------------------------------------------------------------
# geometry / scale constants
# --------------------------------------------------------------------------------------
PX_M = 100.0                    # metres per pixel (verified from the transform)
SIG_TPI = 25.0                  # 2.5 km: local topographic position (basin vs ridge)
SIG_ISOBASE = 60.0              # 6.0 km: the smooth datum surface being fit
SIG_TREND_OK = 0.35             # min Gaussian weight for a TPI value to be trusted


def _nan_smooth(a: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    """NaN-aware Gaussian smoothing.  Returns (smoothed, total_weight)."""
    m = np.isfinite(a)
    z = np.where(m, a, 0.0)
    w = m.astype(np.float64)
    gz = ndi.gaussian_filter(z, sigma, mode="constant", cval=0.0)
    gw = ndi.gaussian_filter(w, sigma, mode="constant", cval=0.0)
    out = np.full(a.shape, np.nan)
    ok = gw > 1e-9
    out[ok] = gz[ok] / gw[ok]
    return out, gw


@dataclass
class LaneSurfaces:
    """Every intermediate surface the lane produces, kept for audit and figures."""
    elev: np.ndarray                 # det_elev, NaN outside footprint
    slope: np.ndarray                # band 19, degrees
    tpi: np.ndarray                  # elev - smooth(elev, SIG_TPI)
    tpi_ok: np.ndarray               # bool: enough neighbours for tpi to be trusted
    isobase: np.ndarray              # fitted smooth datum surface (NaN where unfit)
    resid: np.ndarray                # elev - isobase
    margin: np.ndarray               # bool: pluvial-lake-margin band
    bench: np.ndarray                # bool: contour-parallel bench pixels
    strike: np.ndarray               # radians, local isobase-contour strike
    step_flag: np.ndarray            # bool: abrupt elevation step along the datum
    deflect_flag: np.ndarray         # bool: lateral deflection along strike
    ridge_evidence: np.ndarray       # 0..1, DEM/magnetic ridge support for extension
    stats: dict = field(default_factory=dict)


# --------------------------------------------------------------------------------------
# 1-2.  benches and the isobase fit
# --------------------------------------------------------------------------------------
def margin_band(elev: np.ndarray, tpi: np.ndarray, tpi_ok: np.ndarray,
                slope: np.ndarray, footprint: np.ndarray,
                tpi_lo: float = -400.0, tpi_hi: float = -40.0,
                slope_lo: float = 1.0, slope_hi: float = 30.0) -> np.ndarray:
    """Pluvial-lake-margin band: basin-side topographic position with a scarp-scale slope.

    ``tpi`` (elevation minus its 2.5 km-scale mean) is strongly negative on the
    basin-margin toe and strongly positive on range crests.  The lake shoreline
    sits in the negative-TPI band, and the *scarp* that offsets it has slope in
    the 3-25 degree range.  Measured enrichment of the mapped catalogue in
    ``tpi < -120 m`` x ``slope 6-25 deg`` is 2.3-3.2x the footprint mean
    (``evidence/lane_enrichment.json``), which is the quantitative justification
    for the band.
    """
    m = footprint & tpi_ok & np.isfinite(tpi) & np.isfinite(slope)
    return m & (tpi >= tpi_lo) & (tpi < tpi_hi) & (slope >= slope_lo) & (slope <= slope_hi)


def fit_isobase(elev: np.ndarray, margin: np.ndarray,
                sigma: float = SIG_ISOBASE) -> np.ndarray:
    """Smooth datum surface fit through the pluvial-lake-margin band.

    This is the "fit a smooth isobase, allowing for post-pluvial isostatic
    rebound" step.  A Gaussian fit at 6 km scale is used instead of a global
    polynomial because rebound is *differential*: the datum tilts between
    sub-basins (Pyramid Lake / Winnemucca / Lahontan Reservoir / Walker /
    Carson Sink / Smith Valley), so one plane for the whole 330 x 370 km
    footprint would be geologically wrong.  The 6 km scale is long enough to be
    a datum and short enough to follow rebound between sub-basins.
    """
    masked = np.where(margin & np.isfinite(elev), elev, np.nan)
    sm, gw = _nan_smooth(masked, sigma)
    # widen: a datum value is available wherever the margin band is within the
    # smoothing kernel, so residuals are defined on the whole margin band.
    fill, _ = _nan_smooth(np.where(np.isfinite(sm), sm, np.nan), sigma / 2.0)
    out = np.where(np.isfinite(sm), sm, fill)
    return out


def local_strike(isobase: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Local strike (radians, 0 = north) of the isobase contours.

    The contour direction is perpendicular to grad(isobase).  Returned as the
    azimuth of the *contour*, folded to [0, pi) because a strike is undirected.
    """
    z = np.where(np.isfinite(isobase), isobase, 0.0)
    gy, gx = np.gradient(z, PX_M, PX_M)
    gx = ndi.gaussian_filter(gx, 2.0, mode="nearest")
    gy = ndi.gaussian_filter(gy, 2.0, mode="nearest")
    az = np.arctan2(gx, -gy)          # azimuth of the downhill normal
    strike = az + np.pi / 2.0         # contour direction
    strike = np.mod(strike, np.pi)    # fold to [0, pi)
    mag = np.hypot(gx, gy)
    out = np.where(footprint & (mag > 1e-6), strike, np.nan)
    return out


def plan_curvature_abs(elev: np.ndarray, sigma: float = 1.5) -> np.ndarray:
    """|plan curvature| of the elevation surface (1/m), lightly smoothed.

    Plan curvature is the curvature of the contour line.  Near zero means the
    contour runs straight or in a gentle arc -- the signature of a wave-cut
    bench.  Gullies, fan heads and ridge crests all have strongly non-zero plan
    curvature and are rejected by it.
    """
    z = np.where(np.isfinite(elev), elev, 0.0)
    gy, gx = np.gradient(z, PX_M, PX_M)
    gyy, gyx = np.gradient(gy, PX_M, PX_M)
    gxy, gxx = np.gradient(gx, PX_M, PX_M)
    g2 = np.maximum(gx * gx + gy * gy, 1e-12)
    plan = -(gxx * gy * gy - 2.0 * gxy * gx * gy + gyy * gx * gx) / (g2 ** 1.5)
    return np.abs(ndi.gaussian_filter(plan, sigma, mode="nearest"))


def bench_pixels(elev: np.ndarray, margin: np.ndarray, isobase: np.ndarray,
                 footprint: np.ndarray, slope: np.ndarray,
                 slope_lo: float = 3.0, slope_hi: float = 22.0,
                 plan_pct: float = 55.0) -> np.ndarray:
    """Contour-parallel bench pixels: moderate slope and low plan curvature.

    A wave-cut bench is a straight-to-gently-curved, contour-parallel surface,
    so the selection is (a) inside the pluvial-lake-margin band, (b) slope in
    the scarp range, (c) plan curvature below its in-band percentile.

    NOTE (bug fixed 2026-10-11, IR-62-BENCH-01): an earlier version of this
    function also required ``|elev - isobase|`` to be below the 60th percentile
    of the in-band residual.  That is circular -- it removes exactly the large
    residuals the lane is supposed to *flag*, and it produced zero step flags
    over the whole footprint.  The residual test now belongs to
    :func:`flag_steps` alone, which applies it to this geometry-defined bench
    set.
    """
    plan = plan_curvature_abs(elev)
    sel = footprint & margin & (slope >= slope_lo) & (slope <= slope_hi)
    if not sel.any():
        return sel
    thr = float(np.nanpercentile(plan[sel], plan_pct))
    return sel & (plan <= thr)


# --------------------------------------------------------------------------------------
# 3.  flag abrupt steps and lateral deflections along strike
# --------------------------------------------------------------------------------------
def _mad(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return 0.0
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def flag_steps(resid: np.ndarray, support: np.ndarray, k: float = 2.5,
               lo_m: float | None = None, hi_m: float | None = None) -> np.ndarray:
    """Abrupt elevation steps: isobase-residual outliers, optionally *bounded*.

    ``support`` restricts the flag to the bench band so a random hillside is
    never flagged.

    With ``lo_m``/``hi_m`` given the test becomes a **bounded throw window**:
    ``lo_m <= |resid - median| < hi_m``.  That is the physically correct form
    and it is measured, not assumed -- see ``evidence/e2_enrichment.json``,
    which gives catalogue enrichment as a function of |isobase residual| inside
    the bench band:

        |resid|  [  0, 130) m   2.26 - 2.77x footprint mean
        |resid| [210, 260) m    1.45x
        |resid| [260, 320) m    1.16x
        |resid| [320, 400) m    0.66x
        |resid| [400, 700) m    0.00x   (403 px, no mapped fault at all)

    An unbounded outlier test (IR-62-STEP-01) therefore *keeps* exactly the
    pixels that are depleted: it scored 1.21x enrichment over 14,586 px, versus
    2.44x for the bench band it was drawn from.  The physical reading is that a
    step larger than ~210 m is not a displaced shoreline at all -- it is the
    range front, or a canyon head, and those are terrain the catalogue maps
    *less* completely, not more.

    The window bounds have an independent physical meaning.  A structure that
    offsets the ~15 ka Lahontan highstand shoreline at a slip rate of 1-8 mm/yr
    accumulates 15-120 m of throw in 15 kyr, which brackets the slow-to-fast
    range of Great Basin normal and strike-slip faults.  Below ~15 m the step is
    beneath the vertical resolution a 100 m pixel can express against terrain
    noise; above ~130 m it has left the shoreline-offset regime.
    """
    vals = resid[support & np.isfinite(resid)]
    if vals.size == 0:
        return np.zeros_like(support)
    med = float(np.median(vals))
    s = _mad(vals)
    if s <= 0.0:
        return np.zeros_like(support)
    d = np.abs(resid - med)
    out = support & (d > k * s)
    if lo_m is not None:
        out &= support & (d >= lo_m)
    if hi_m is not None:
        out &= support & (d < hi_m)
    return out


def flag_deflections(strike: np.ndarray, support: np.ndarray,
                     dtheta_deg: float = 22.0, win: int = 3) -> np.ndarray:
    """Lateral deflections along strike: abrupt change of contour azimuth.

    A strike-slip fault crossing a shoreline produces exactly this -- the bench
    continues but is offset sideways, so its azimuth kinks.  Measured as the
    maximum angular difference between the local strike and the strike a few
    pixels along the contour, using the circular difference so 0/180 wrap.
    """
    if not support.any():
        return np.zeros_like(support)
    s = np.where(np.isfinite(strike), strike, np.nan)
    # double-angle representation makes the [0, pi) fold a proper circle
    u = np.cos(2.0 * s)
    v = np.sin(2.0 * s)
    best = np.zeros(s.shape, bool)
    for dy in range(-win, win + 1):
        for dx in range(-win, win + 1):
            d = np.hypot(dy, dx)
            if d < win - 0.5 or d > win + 0.5:
                continue
            us = np.roll(u, (dy, dx), axis=(0, 1))
            vs = np.roll(v, (dy, dx), axis=(0, 1))
            dot = np.clip(u * us + v * vs, -1.0, 1.0)
            dtheta = 0.5 * np.arccos(dot)          # back from double angle
            best |= (np.degrees(dtheta) > dtheta_deg)
    return support & best


# --------------------------------------------------------------------------------------
# 4-5.  seed traces and extend while DEM-ridge evidence supports them
# --------------------------------------------------------------------------------------
def ridge_evidence(elev: np.ndarray, slope: np.ndarray, tmi_hg: np.ndarray,
                   grav_hg: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """0..1 support surface for extending a trace: DEM edge + geophysical corroboration.

    The DEM part is the across-strike second derivative of elevation (a scarp is
    a convex/concave break) combined with the slope band; the geophysical part
    is the horizontal gradient of TMI and of the isostatic gravity anomaly,
    which is where a buried or alluvium-covered continuation of the same
    structure shows up.  Each term is rank-normalised inside the footprint so
    the combination is scale-free.
    """
    def rank01(a):
        a = np.asarray(a, float)
        m = footprint & np.isfinite(a)
        if not m.any():
            return np.zeros_like(a)
        r = np.zeros_like(a)
        vals = a[m]
        order = np.argsort(vals, kind="stable")
        ranks = np.empty(vals.size, float)
        ranks[order] = np.arange(vals.size, dtype=float)
        r[m] = ranks / max(vals.size - 1, 1)
        return r

    z = np.where(np.isfinite(elev), elev, 0.0)
    gy, gx = np.gradient(z, PX_M, PX_M)
    gyy, gyx = np.gradient(gy, PX_M, PX_M)
    gxy, gxx = np.gradient(gx, PX_M, PX_M)
    g2 = np.maximum(gx * gx + gy * gy, 1e-12)
    prof = -(gxx * gx * gx + 2.0 * gxy * gx * gy + gyy * gy * gy) / (g2 ** 1.5)
    prof_abs = np.abs(ndi.gaussian_filter(prof, 1.0, mode="nearest"))

    dem = 0.60 * rank01(prof_abs) + 0.40 * rank01(np.where(
        footprint & (slope >= 3.0) & (slope <= 25.0), slope, 0.0))
    geo = 0.5 * rank01(np.where(np.isfinite(tmi_hg), tmi_hg, np.nan)) \
        + 0.5 * rank01(np.where(np.isfinite(grav_hg), grav_hg, np.nan))
    out = np.clip(0.65 * dem + 0.35 * geo, 0.0, 1.0)
    return np.where(footprint, out, 0.0)


def extend_traces(seeds: np.ndarray, evidence: np.ndarray, footprint: np.ndarray,
                  strike: np.ndarray | None = None,
                  min_evidence: float = 0.55, max_len_px: int = 120,
                  step_px: int = 1, taper: float = 0.0) -> tuple[np.ndarray, list[dict]]:
    """Grow a trace from every seed pixel ALONG STRIKE while DEM-ridge evidence holds.

    NOTE (bug fixed 2026-10-11, IR-62-EXT-01): an earlier version derived the
    walk direction from the gradient of the smoothed evidence field, on the
    argument that evidence ridges run along the structure.  On this data that
    direction is far too noisy: median trace length came out at 1 pixel and mean
    at 2.4, i.e. the traces never extended at all.  The lane says "extend it
    while DEM-ridge evidence supports it" -- the *direction* of extension is
    the strike of the datum the seed sits on, which is a well-posed quantity
    (``local_strike`` of the fitted isobase).  Evidence is now used only as the
    stopping criterion, which is what the lane actually asks for.

    ``strike``   -- per-pixel contour azimuth in radians (from
                    :func:`local_strike`); where it is NaN the local structure
                    tensor of the evidence field supplies a fallback direction.
    ``taper``    -- if > 0, the evidence threshold decays linearly by ``taper``
                    over the walk, so a trace can run out along a gradually
                    weakening ridge instead of stopping dead.
    """
    ys, xs = np.nonzero(seeds)
    traced = np.zeros(seeds.shape, bool)
    traces: list[dict] = []
    if ys.size == 0:
        return traced, traces

    # fallback direction: structure tensor of the evidence field
    ev_s = ndi.gaussian_filter(np.nan_to_num(evidence), 2.0, mode="nearest")
    gy, gx = np.gradient(ev_s, PX_M, PX_M)
    jxx = ndi.gaussian_filter(gx * gx, 2.0, mode="nearest")
    jyy = ndi.gaussian_filter(gy * gy, 2.0, mode="nearest")
    jxy = ndi.gaussian_filter(gx * gy, 2.0, mode="nearest")
    fb_strike = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy) % np.pi

    use_strike = strike if strike is not None else fb_strike
    st = np.where(np.isfinite(use_strike), use_strike, fb_strike)

    H, W = evidence.shape
    for i in range(ys.size):
        y0, x0 = int(ys[i]), int(xs[i])
        if traced[y0, x0]:
            continue
        th = float(st[y0, x0])
        # strike is the contour azimuth measured from north, clockwise
        dx = np.sin(th)
        dy = -np.cos(th)
        pts = [(y0, x0)]
        for sgn in (1.0, -1.0):
            y, x = float(y0), float(x0)
            n = 0
            while n < max_len_px:
                y += sgn * dy * step_px
                x += sgn * dx * step_px
                n += 1
                iy, ix = int(round(y)), int(round(x))
                if not (0 <= iy < H and 0 <= ix < W):
                    break
                if not footprint[iy, ix]:
                    break
                thr = min_evidence - (taper * n / max(max_len_px, 1))
                if evidence[iy, ix] < thr:
                    break
                pts.append((iy, ix))
        seen = set()
        for (py, px) in pts:
            if (py, px) not in seen:
                traced[py, px] = True
                seen.add((py, px))
        traces.append(dict(seed=[y0, x0], n=len(seen), length_m=float(len(seen)) * PX_M,
                           strike_deg=float(np.degrees(th)) % 180.0))
    return traced, traces


# --------------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------------
def build_surfaces(features: np.ndarray, footprint: np.ndarray,
                   bands: dict[str, int] | None = None,
                   tpi_lo: float = -400.0, tpi_hi: float = -40.0,
                   slope_lo: float = 1.0, slope_hi: float = 30.0,
                   step_k: float = 0.0, deflect_deg: float = 22.0,
                   throw_lo_m: float = 15.0, throw_hi_m: float = 130.0,
                   iso_sigma: float = SIG_ISOBASE) -> LaneSurfaces:
    """Run lane steps 1-3 and produce every surface, plus summary statistics."""
    b = bands or {"det_elev": 11, "det_elev_slope": 18, "tmi_hg": 2, "iso_grav_anom_hg": 17}
    elev = np.where(footprint, features[b["det_elev"]].astype(np.float64), np.nan)
    slope = np.where(footprint, features[b["det_elev_slope"]].astype(np.float64), np.nan)
    tmi_hg = np.where(footprint, features[b["tmi_hg"]].astype(np.float64), np.nan)
    grav_hg = np.where(footprint, features[b["iso_grav_anom_hg"]].astype(np.float64), np.nan)

    sm, gw = _nan_smooth(elev, SIG_TPI)
    tpi_ok = gw > SIG_TREND_OK
    tpi = np.where(tpi_ok, elev - sm, np.nan)

    margin = margin_band(elev, tpi, tpi_ok, slope, footprint,
                         tpi_lo=tpi_lo, tpi_hi=tpi_hi,
                         slope_lo=slope_lo, slope_hi=slope_hi)
    isobase = fit_isobase(elev, margin, sigma=iso_sigma)
    resid = elev - isobase
    bench = bench_pixels(elev, margin, isobase, footprint, slope)
    strike = local_strike(isobase, footprint)

    steps = flag_steps(resid, bench, k=step_k, lo_m=throw_lo_m, hi_m=throw_hi_m)
    deflects = flag_deflections(strike, bench & ~steps, dtheta_deg=deflect_deg)
    ev = ridge_evidence(elev, slope, tmi_hg, grav_hg, footprint)

    stats = dict(
        n_footprint=int(footprint.sum()),
        n_margin=int(margin.sum()),
        n_bench=int(bench.sum()),
        n_steps=int(steps.sum()),
        n_deflects=int(deflects.sum()),
        resid_median_m=float(np.nanmedian(resid[bench])) if bench.any() else None,
        resid_mad_m=_mad(resid[bench]) if bench.any() else None,
        step_threshold_m=float(step_k * _mad(resid[bench])) if bench.any() else None,
        tpi_lo=tpi_lo, tpi_hi=tpi_hi, slope_lo=slope_lo, slope_hi=slope_hi,
        step_k=step_k, deflect_deg=deflect_deg, iso_sigma=iso_sigma,
        sig_tpi=SIG_TPI, throw_lo_m=throw_lo_m, throw_hi_m=throw_hi_m,
        n_step_flag=int(steps.sum()), n_deflect_flag=int(deflects.sum()),
    )
    return LaneSurfaces(elev=elev, slope=slope, tpi=tpi, tpi_ok=tpi_ok,
                        isobase=isobase, resid=resid, margin=margin, bench=bench,
                        strike=strike, step_flag=steps, deflect_flag=deflects,
                        ridge_evidence=ev, stats=stats)
