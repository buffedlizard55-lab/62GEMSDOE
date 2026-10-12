"""H62-R — multi-level Lahontan datum stack: a repeat-offset strain gauge.

Why this module exists (and how it differs from every earlier lane here)
-----------------------------------------------------------------------
Every earlier session in this repository treated the Lahontan datum as **one**
surface: a single "pluvial-lake-margin band" (H62-A), a single fitted isobase of
detrended elevation, a single 1308-1360 m datum window (H62-G/H62-I).  That is a
real loss of information, because a pluvial lake does not leave one shoreline --
it leaves a **stack of nested shorelines**, one per stillstand/highstand, at
different elevations and therefore of different ages.  Each level is an
independent near-level datum formed at a known *relative* time.

That stack is the strain gauge.  A fault that has been active since the oldest
level offsets **every** level it crosses.  A non-tectonic step -- a delta top-set
break, a fan toe, a landslide edge, a wave-cut notch cut into a resistant bed at a
promontory -- is a property of *one* level at *one* place and does not repeat
coherently at the same map position on an older datum metres higher.

So the discriminative rule added here is a **repeat-offset test**:

    A datum step is promoted only if a step of the *same sign* is independently
    flagged at the *same map location* (within a tolerance radius) on at least
    two different shoreline levels.

The magnitude contrast between the levels carries a second, purely geometric
prediction.  For constant slip rate ``s`` and level ages ``t_i > t_j``, the
cumulative throws satisfy ``throw_i / throw_j = t_i / t_j > 1``.  The test is
therefore not only "same place, same sign" but "**older level throws more**",
which is a statement no landscape process other than cumulative tectonic
displacement is required to satisfy.

What is *not* claimed
---------------------
* The individual level elevations are **detected from the DEM hypsometry**, not
  taken from the literature (the literature values are quoted only as a sanity
  cross-check and are labelled as such).  Detected levels are reported with their
  own evidence so a reviewer can reject any of them.
* The ages of the levels are **not** measured here.  The ordering "higher ==
  older" is used, which is the standard reading of nested shorelines and is the
  only ordering the test needs.
* This module reads **no** fault catalogue.  The catalogue is used downstream, in
  the driver, only (a) to measure enrichment, (b) as the holdout truth, and
  (c) to delete dots sitting on already-mapped faults.

References for the physical premise (quoted, not used to place any dot)
-----------------------------------------------------------------------
* Reheis, M.C. (1999) *Highest pluvial-lake shorelines and Pleistocene climate of
  the western Great Basin.* Quaternary Research 51, 196-205.
* Adams, K.D. & Wesnousky, S.G. (1998) *Shoreline processes and the age of the
  Lake Lahontan highstand in the Jessup embayment, Nevada.* GSA Bulletin 110,
  1318-1332.
* Briggs, R.W. & Wesnousky, S.G. (2004) JGR 109, B08405 -- displaced Lahontan
  features used to constrain slip on the Pyramid Lake fault zone.  (The lane
  paragraph names this paper as JGR 2004; the article number B08405 is quoted
  from that repository's own citation of it and is flagged for manual check in
  ``docs/irregularities.md``.)
* Pierce & Wesnousky (SCEC poster, 2016) -- two unmapped NW-striking segments in
  Smith Valley's basin centre offsetting Holocene sediments.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

PIXEL_M = 100.0


# =====================================================================================
# 1.  Shoreline levels from the DEM hypsometry
# =====================================================================================
@dataclass
class Survey:
    """The hypsometric survey a level list is drawn from, kept for audit."""

    bins_m: np.ndarray            # bin centres (m)
    count: np.ndarray             # bench-like pixels per bin
    prominence: np.ndarray        # count / local median count (peak prominence)
    domain_cells: int
    floor_m: float                # lowest elevation inside the pluvial domain
    ceil_m: float                 # highest


def hypsometric_survey(dem: np.ndarray, slope_deg: np.ndarray, domain: np.ndarray,
                       *, floor_m: float = 1100.0, ceil_m: float = 1600.0,
                       bin_m: float = 1.0, slope_max_deg: float = 6.0,
                       smooth_bins: float = 4.0) -> Survey:
    """Count bench-like pixels per elevation bin inside the pluvial domain.

    A wave-cut shoreline bench is a **flat, contour-parallel** surface, so it
    shows up as an excess of low-slope pixels at one elevation.  The count is
    smoothed (``smooth_bins``) only to make the peak-finding robust; the returned
    ``prominence`` is the ratio of the smoothed count to a wide-window median of
    itself, i.e. a local background estimate, so a broad hillslope contribution
    is divided out.
    """
    z = np.asarray(dem, float)
    ok = domain & np.isfinite(z) & (z >= floor_m) & (z <= ceil_m)
    if ok.sum() == 0:
        raise ValueError("hypsometric_survey: no pixels inside domain/floor/ceil")
    flat = ok & np.isfinite(slope_deg) & (slope_deg <= slope_max_deg)
    zz = z[ok]
    floor = float(np.min(zz))
    ceil = float(np.max(zz))
    edges = np.arange(np.floor(floor), np.ceil(ceil) + bin_m, bin_m)
    centres = 0.5 * (edges[:-1] + edges[1:])
    count, _ = np.histogram(z[flat], bins=edges)
    count = count.astype(float)
    smooth = ndi.gaussian_filter1d(count, smooth_bins, mode="nearest")
    bg = ndi.median_filter(smooth, size=max(9, int(round(120.0 / bin_m))), mode="nearest")
    bg = np.maximum(bg, 1.0)
    return Survey(bins_m=centres, count=smooth, prominence=smooth / bg,
                  domain_cells=int(ok.sum()), floor_m=floor, ceil_m=ceil)


def bench_components(bench_mask: np.ndarray, dem: np.ndarray, *, min_px: int = 120,
                     max_sd_m: float = 12.0, min_major_axis_km: float = 2.0) -> list[dict]:
    """Measured bench patches, each with its own median elevation.

    A shoreline bench is a **large, level, contour-parallel patch**.  At 100 m the
    global hypsometric histogram is dominated by the playa floors (measured: the
    strongest global peaks are at the basin floors, prominence 2.9-3.1, while the
    shoreline elevations sit at prominence ~1.2), so the level list is built from
    *patches* instead: 8-connected components of the bench mask, kept when they
    are big enough (``min_px``), level enough (elevation standard deviation below
    ``max_sd_m``) and elongated enough (major axis above ``min_major_axis_km``).

    Returns one dict per kept patch: median elevation, size, levelness, major-axis
    length and the component centroid.
    """
    lab, n = ndi.label(bench_mask, structure=np.ones((3, 3), dtype=bool))
    if n == 0:
        return []
    idx = np.arange(1, n + 1)
    sizes = np.bincount(lab.ravel(), minlength=n + 1)[1:]
    keep = idx[sizes >= min_px]
    out: list[dict] = []
    z = np.asarray(dem, float)
    for k in keep:
        rr, cc = np.nonzero(lab == k)
        zz = z[rr, cc]
        good = np.isfinite(zz)
        if good.sum() < min_px:
            continue
        zz = zz[good]
        rr, cc = rr[good], cc[good]
        sd = float(np.std(zz))
        if not np.isfinite(sd) or sd > max_sd_m:
            continue
        # major axis from the second moments of the patch (km)
        r0, c0 = float(rr.mean()), float(cc.mean())
        dr = (rr - r0) * PIXEL_M / 1000.0
        dc = (cc - c0) * PIXEL_M / 1000.0
        cov = np.cov(np.vstack([dc, dr]))
        ev = np.linalg.eigvalsh(cov)
        major = float(4.0 * np.sqrt(max(ev[-1], 0.0)))     # ~ +/-2 sigma along the axis
        if major < min_major_axis_km:
            continue
        out.append(dict(elev_m=float(np.median(zz)), sd_m=sd, n_px=int(zz.size),
                        major_axis_km=major, row=r0, col=c0))
    return out


def levels_from_bench_patches(patches: list[dict], *, bin_m: float = 2.0,
                              min_weight: float = 0.04, min_separation_m: float = 15.0,
                              max_levels: int = 6, min_elev_m: float = 1150.0,
                              max_elev_m: float = 1520.0) -> list[dict]:
    """Cluster measured bench patches by elevation into a level list.

    Patches are weighted by area, binned at ``bin_m``, smoothed lightly and peak
    picked; a level is kept when it carries at least ``min_weight`` of the total
    patch area, which is the operational meaning of "this elevation is a surface
    the lake really stood at across a large part of the basin".
    """
    if not patches:
        return []
    e = np.array([p["elev_m"] for p in patches], float)
    w = np.array([p["n_px"] for p in patches], float)
    sel = (e >= min_elev_m) & (e <= max_elev_m)
    if not sel.any():
        return []
    e, w = e[sel], w[sel]
    edges = np.arange(min_elev_m, max_elev_m + bin_m, bin_m)
    hist, _ = np.histogram(e, bins=edges, weights=w)
    centres = 0.5 * (edges[:-1] + edges[1:])
    hist = ndi.gaussian_filter1d(hist, 1.5, mode="nearest")
    tot = hist.sum()
    if tot <= 0:
        return []
    cands = []
    for i in range(1, hist.size - 1):
        if hist[i] >= min_weight * tot and hist[i] >= hist[i - 1] and hist[i] > hist[i + 1]:
            cands.append(dict(elev_m=float(centres[i]), weight=float(hist[i] / tot)))
    cands.sort(key=lambda d: -d["weight"])
    kept: list[dict] = []
    for d in cands:
        if any(abs(d["elev_m"] - k["elev_m"]) < min_separation_m for k in kept):
            continue
        kept.append(d)
        if len(kept) >= max_levels:
            break
    kept.sort(key=lambda d: -d["elev_m"])                # highest (oldest) first
    for i, d in enumerate(kept):
        d["level_index"] = i
    return kept


def levels_from_tile_modes(bench_mask: np.ndarray, dem: np.ndarray, *,
                           tile_px: int = 40, bin_m: float = 2.0,
                           min_bench_px: int = 25, smooth_bins: float = 2.0,
                           min_weight: float = 0.03, min_separation_m: float = 15.0,
                           max_levels: int = 5, min_elev_m: float = 1150.0,
                           max_elev_m: float = 1520.0) -> tuple[list[dict], dict]:
    """Level list from the **modal bench elevation per 4 km tile**.

    This is the detector that survives measurement on this DEM.  The global
    hypsometric histogram is a playa-floor detector (prominence 2.9-3.1 at the
    basin floors, ~1.2 at the shoreline elevations), and 8-connected bench
    *patches* fragment into 9-26 pieces, which is too few to weight a histogram.
    The tile mode asks the local question instead -- "at what elevation does this
    4 x 4 km neighbourhood hold a bench?" -- which is the question a shoreline
    level actually answers, and is immune to the floor's much larger area.

    Returns ``(levels, survey)``; ``survey`` carries the raw tile-mode histogram
    so the peak chooser can be re-run and audited without recomputing the DEM.
    """
    z = np.asarray(dem, float)
    h, w = z.shape
    t = int(tile_px)
    bins = np.arange(min_elev_m, max_elev_m + bin_m, bin_m)
    centres = 0.5 * (bins[:-1] + bins[1:])
    accum = np.zeros(centres.size)
    n_tiles = n_used = 0
    modes: list[float] = []
    weights: list[float] = []
    for i in range(0, h, t):
        for j in range(0, w, t):
            sub_m = bench_mask[i:i + t, j:j + t]
            n_tiles += 1
            npx = int(sub_m.sum())
            if npx < min_bench_px:
                continue
            v = z[i:i + t, j:j + t][sub_m]
            v = v[np.isfinite(v)]
            if v.size < min_bench_px:
                continue
            hist, _ = np.histogram(v, bins=bins)
            k = int(np.argmax(hist))
            if hist[k] < 5:
                continue
            lo, hi = bins[k], bins[k + 1]
            inb = v[(v >= lo) & (v <= hi)]
            if inb.size == 0:
                continue
            mode = float(np.median(inb))
            modes.append(mode)
            weights.append(float(npx))
            n_used += 1
            accum += np.histogram([mode], bins=bins, weights=[float(npx)])[0]
    if not modes:
        return [], dict(bins_m=centres, weight=accum, n_tiles=n_tiles, n_tiles_used=0)
    accum = ndi.gaussian_filter1d(accum, smooth_bins, mode="nearest")
    tot = accum.sum()
    cands = []
    if tot > 0:
        for i in range(1, accum.size - 1):
            if (accum[i] >= min_weight * tot
                    and accum[i] >= accum[i - 1] and accum[i] > accum[i + 1]):
                cands.append(dict(elev_m=float(centres[i]), weight=float(accum[i] / tot),
                                  support_tiles=int(sum(1 for m in modes
                                                        if abs(m - centres[i]) < bin_m))))
    cands.sort(key=lambda d: -d["weight"])
    kept: list[dict] = []
    for d in cands:
        if any(abs(d["elev_m"] - k["elev_m"]) < min_separation_m for k in kept):
            continue
        kept.append(d)
        if len(kept) >= max_levels:
            break
    kept.sort(key=lambda d: -d["elev_m"])
    for i, d in enumerate(kept):
        d["level_index"] = i
    survey = dict(bins_m=centres, weight=accum, n_tiles=n_tiles, n_tiles_used=n_used,
                  tile_modes=modes, tile_weights=weights)
    return kept, survey


def detect_levels(survey: Survey, *, min_elev_m: float = 1150.0, max_elev_m: float = 1550.0,
                  min_prominence: float = 1.25, min_separation_m: float = 12.0,
                  max_levels: int = 6) -> list[dict]:
    """Local maxima of the hypsometric prominence curve = candidate shorelines.

    Returns a list of dicts, **highest first** (i.e. oldest first under the
    nested-shoreline reading), each with its detected elevation, the prominence
    that flagged it and the pixel count supporting it.
    """
    p = survey.prominence.copy()
    e = survey.bins_m
    sel = (e >= min_elev_m) & (e <= max_elev_m)
    p = np.where(sel, p, 0.0)
    out: list[dict] = []
    n = p.size
    for i in range(1, n - 1):
        if p[i] < min_prominence:
            continue
        if p[i] >= p[i - 1] and p[i] > p[i + 1]:
            out.append(dict(elev_m=float(e[i]), prominence=float(p[i]),
                            support_px=float(survey.count[i])))
    out.sort(key=lambda d: -d["elev_m"])
    kept: list[dict] = []
    for d in out:
        if d["prominence"] <= 0.0:
            continue
        if any(abs(d["elev_m"] - k["elev_m"]) < min_separation_m for k in kept):
            continue
        kept.append(d)
        if len(kept) >= max_levels:
            break
    for i, d in enumerate(kept):
        d["level_index"] = i
    return kept


# =====================================================================================
# 2.  Per-level bench mask, isobase and residual
# =====================================================================================
def level_bench_mask(dem: np.ndarray, bench_geom: np.ndarray, domain: np.ndarray,
                     level_m: float, *, tol_m: float = 10.0,
                     wide_m: float = 45.0) -> np.ndarray:
    """Bench pixels belonging to one shoreline level.

    ``tol_m`` is used **only to enumerate levels in the spectrum** (E1), where a
    narrow window is correct: the question there is "how many blocks hold a bench
    at exactly this elevation".

    ``wide_m`` is used for the **detector**.  This distinction is a defect fix and
    is worth stating plainly (IR-62-LEVEL-01): the first version of this module
    selected bench pixels with the *narrow* window and then looked for steps inside
    them.  Measured: 0 to 6 flagged step pixels per level, and an empty artifact.
    The reason is a blind spot, not a physical null -- a bench displaced by 30 m
    falls outside a +/-10 m window, so the selection had already deleted exactly
    the pixels the lane is looking for.  Widening to +/-45 m admits benches
    displaced by up to 45 m while the *robust* isobase below stays anchored on the
    un-displaced majority.
    """
    z = np.asarray(dem, float)
    return (domain & bench_geom & np.isfinite(z)
            & (np.abs(z - level_m) <= wide_m))


def nan_smooth(a: np.ndarray, sigma_px: float) -> np.ndarray:
    """Gaussian smoothing that ignores NaN (normalised convolution)."""
    m = np.isfinite(a)
    z = np.where(m, a, 0.0)
    w = m.astype(np.float64)
    num = ndi.gaussian_filter(z, sigma_px, mode="constant", cval=0.0)
    den = ndi.gaussian_filter(w, sigma_px, mode="constant", cval=0.0)
    out = np.full(np.shape(a), np.nan)
    ok = den > 1e-9
    out[ok] = num[ok] / den[ok]
    return out


def robust_isobase(dem: np.ndarray, bench: np.ndarray, level_m: float, *,
                   tile_px: int = 40, bin_m: float = 2.0, half_m: float = 60.0,
                   min_px: int = 25, smooth_tiles: float = 1.5) -> np.ndarray:
    """Per-tile **modal** bench elevation, then smoothed -- the fitted datum surface.

    The mode is what makes the fit robust to the signal: where a fault has pushed a
    minority of the level's bench up or down, the Gaussian fit used previously
    would split the difference and halve the measured step, whereas the mode stays
    on the un-displaced majority.  The surface is then free to warp, which is the
    licence the lane paragraph gives it ("allowing for post-pluvial isostatic
    rebound"): rebound is a smooth regional warp, so only smoothness is imposed and
    a rebound dome survives into the residual instead of being called a fault.
    """
    h, w = dem.shape
    tr = int(np.ceil(h / tile_px))
    tc = int(np.ceil(w / tile_px))
    bins = np.arange(level_m - half_m, level_m + half_m + bin_m, bin_m)
    surf = np.full((tr, tc), np.nan)
    for i in range(tr):
        for j in range(tc):
            sl_r = slice(i * tile_px, (i + 1) * tile_px)
            sl_c = slice(j * tile_px, (j + 1) * tile_px)
            v = dem[sl_r, sl_c][bench[sl_r, sl_c]]
            v = v[np.isfinite(v)]
            if v.size < min_px:
                continue
            hist, edges = np.histogram(v, bins=bins)
            k = int(np.argmax(hist))
            if hist[k] < 8:
                continue
            inb = v[(v >= edges[k]) & (v <= edges[k + 1])]
            if inb.size == 0:
                continue
            surf[i, j] = float(np.median(inb))
    if np.isnan(surf).all():
        return np.full(dem.shape, np.nan, dtype=np.float64)
    idx = ndi.distance_transform_edt(np.isnan(surf), return_distances=False,
                                     return_indices=True)
    filled = surf[tuple(idx)]
    sm = ndi.gaussian_filter(filled, smooth_tiles)
    yi = np.clip(np.arange(h) / tile_px, 0, tr - 1)
    xi = np.clip(np.arange(w) / tile_px, 0, tc - 1)
    y0 = np.floor(yi).astype(int); x0 = np.floor(xi).astype(int)
    y1 = np.clip(y0 + 1, 0, tr - 1); x1 = np.clip(x0 + 1, 0, tc - 1)
    fy = (yi - y0)[:, None]; fx = (xi - x0)[None, :]
    out = (sm[np.ix_(y0, x0)] * (1 - fy) * (1 - fx) + sm[np.ix_(y1, x0)] * fy * (1 - fx)
           + sm[np.ix_(y0, x1)] * (1 - fy) * fx + sm[np.ix_(y1, x1)] * fy * fx)
    return out.astype(np.float64)


@dataclass
class LevelSurface:
    """Everything computed for one detected shoreline level."""

    level: dict
    bench: np.ndarray              # bool
    isobase: np.ndarray            # metres, NaN where unfit
    resid: np.ndarray              # dem - isobase, metres, NaN off-bench
    resid_median_m: float
    resid_mad_m: float
    step: np.ndarray               # bool: elevation-step flag
    step_m: np.ndarray             # signed residual jump magnitude (m)
    deflect: np.ndarray            # bool: along-strike azimuth kink flag
    n_bench: int
    n_step: int
    n_deflect: int


def level_surface(dem: np.ndarray, slope_deg: np.ndarray, az_field: np.ndarray,
                  domain: np.ndarray, level: dict, *, bench_geom: np.ndarray | None = None,
                  tol_m: float = 10.0, wide_m: float = 45.0, tile_px: int = 40,
                  throw_lo_m: float = 15.0, throw_hi_m: float = 140.0,
                  k_mad: float = 1.5, deflect_win_px: int = 12,
                  deflect_deg: float = 25.0) -> LevelSurface:
    """Bench mask -> robust isobase -> residual -> step and deflection flags.

    The residual is ``dem - robust_isobase`` **at the bench pixels of this level**.
    Because the datum was level when it formed, the residual is a direct measure of
    the cumulative post-pluvial vertical displacement of that surface, minus only
    the smooth rebound warp the isobase already carries.
    """
    z = np.asarray(dem, float)
    if bench_geom is None:
        bench_geom = np.ones(z.shape, dtype=bool)
    bench = level_bench_mask(z, bench_geom, domain, level["elev_m"], tol_m=tol_m,
                             wide_m=wide_m)
    iso = robust_isobase(z, bench, level["elev_m"], tile_px=tile_px)
    resid = np.where(bench & np.isfinite(iso), z - iso, np.nan)
    vals = resid[np.isfinite(resid)]
    if vals.size < 100:
        empty = np.zeros_like(bench)
        return LevelSurface(level=level, bench=bench, isobase=iso, resid=resid,
                            resid_median_m=float("nan"), resid_mad_m=float("nan"),
                            step=empty, step_m=np.zeros_like(iso, dtype=float),
                            deflect=empty, n_bench=int(bench.sum()), n_step=0, n_deflect=0)
    med = float(np.median(vals))
    mad = float(1.4826 * np.median(np.abs(vals - med)))
    mad = mad if mad > 0.0 else float(np.std(vals) + 1e-6)
    d = np.abs(resid - med)
    step = (bench & np.isfinite(resid) & (d >= throw_lo_m)
            & (d < throw_hi_m) & (d > k_mad * mad))
    step_m = np.where(step, resid - med, np.nan)

    # Along-strike deflection: azimuth kink of the contour at a ~1 km lever arm.
    # IR-62-DEFL-01 measured a NULL for the 3-px (300 m) version of this test;
    # the kink of a shoreline displaced by a strike-slip fault is a kilometre-scale
    # rotation, so the lever arm here is 12 px (1.2 km), not 3 px.
    s = np.where(bench & np.isfinite(az_field), np.radians(az_field), np.nan)
    u, v = np.cos(2.0 * s), np.sin(2.0 * s)
    ang = np.zeros(np.shape(bench))
    win = int(deflect_win_px)
    for dy in (0, win, -win):
        for dx in (0, win, -win):
            if dy == 0 and dx == 0:
                continue
            us = np.roll(u, (dy, dx), axis=(0, 1))
            vs = np.roll(v, (dy, dx), axis=(0, 1))
            dot = np.clip(u * us + v * vs, -1.0, 1.0)
            ang = np.maximum(ang, np.degrees(0.5 * np.arccos(dot)))
    deflect = bench & np.isfinite(ang) & (ang >= deflect_deg)

    return LevelSurface(level=level, bench=bench, isobase=iso, resid=resid,
                        resid_median_m=med, resid_mad_m=mad, step=step, step_m=step_m,
                        deflect=deflect, n_bench=int(bench.sum()),
                        n_step=int(step.sum()), n_deflect=int(deflect.sum()))


# =====================================================================================
# 3.  The repeat-offset test
# =====================================================================================
# =====================================================================================
# 3.  The repeat-offset test
# =====================================================================================
#
# IMPORTANT GEOMETRY, stated because the naive form of this test is wrong.  Pluvial
# shorelines are **nested**: the highest (oldest) level has the largest lake and
# therefore lies *outside* the lower levels.  A fault is a **line**; it crosses level
# L at whatever map point that line intersects L's shoreline, and those intersection
# points are at *different* map positions for different levels.  So the correct
# repeat-offset test is NOT "the same place on two levels" -- it is
#
#     "the flagged points of two or more levels lie on ONE common line"
#
# which is exactly a Hough vote.  The linear form also carries the throw prediction:
# along one fault, cumulative throw grows with the age of the datum it crosses.

@dataclass
class FaultLine:
    """One Hough-accepted line supported by flagged offsets on >= 2 levels."""

    azimuth_deg: float          # strike, degrees clockwise from north, [0, 180)
    rho_px: float               # line offset in the (theta, rho) parametrisation
    n_points: int
    n_levels: int
    levels: list[int]
    signs: list[int]
    mean_throw_m: float
    support: list[tuple[int, int]]   # (row, col) of the inlier flagged points
    score: float


@dataclass
class Corroboration:
    """The promoted lines and the surfaces a trace is extended from."""

    support: np.ndarray            # bool: pixel lies on an accepted line
    n_levels: np.ndarray           # int16: distinct levels inlier on that line
    score: np.ndarray              # float: line score, broadcast to its inlier pixels
    lines: list[FaultLine]
    n_flagged_total: int
    per_level_px: list[int] = field(default_factory=list)
    per_level_points: list[int] = field(default_factory=list)
    azimuths_deg: list[float] = field(default_factory=list)
    min_span_px: int = 20


def hough_offsets(surfaces: list["LevelSurface"], *, rho_bin_px: float = 2.0,
                  min_points: int = 6, min_levels: int = 2, min_span_px: int = 20,
                  max_gap_px: float = 1e9, max_median_gap_px: float = 1e9,
                  nms_jaccard: float = 0.4,
                  max_lines: int = 20000, neighbor_px: int = 1) -> Corroboration:
    """Hough vote over the flagged step pixels of every level.

    ``surfaces`` may be in any order; each contributes its ``step`` mask and its
    signed ``step_m``.  The accumulator is over azimuth (5 degree steps in
    ``[0, 180)``) and perpendicular offset ``rho = c*cos(theta) + r*sin(theta)``
    (the pixel axes are treated as an orthogonal pair; the 100 m scale is uniform,
    so the Hough parametrisation is geometrically exact here and no metric
    correction is needed).

    A line is accepted when its accumulator bin holds at least ``min_points``
    flagged pixels drawn from at least ``min_levels`` **distinct** levels **and**
    those inliers span at least ``min_span_px`` along the line.  The span test is
    what makes the vote meaningful: a fault trace is a *long* object, so a bin that
    collects its points in one 200 m cluster is a chance coincidence (a single
    ragged bench edge straddling a rho bin), not a line.  Measured on this DEM with
    the span test off, all 400 available line slots fill within seconds; with a
    20 px (2 km) span requirement the accepted set is two orders of magnitude
    smaller and every survivor is a genuinely elongate object.  Sign
    agreement and the "older level throws at least as much as the younger" test
    are then applied within the inliers, and lines failing either are dropped.

    ``neighbor_px = 1`` means the three adjacent rho bins are pooled, which
    absorbs the +/-1 px scatter of a hand-drawn-equivalent digital line.
    """
    shape = surfaces[0].step.shape
    pts_r: list[np.ndarray] = []
    pts_c: list[np.ndarray] = []
    pts_v: list[np.ndarray] = []
    pts_l: list[np.ndarray] = []
    per_level_points: list[int] = []
    for li, s in enumerate(surfaces):
        rr, cc = np.nonzero(s.step & np.isfinite(s.step_m))
        per_level_points.append(int(rr.size))
        if rr.size == 0:
            continue
        pts_r.append(rr)
        pts_c.append(cc)
        pts_v.append(s.step_m[rr, cc])
        pts_l.append(np.full(rr.size, li, dtype=np.int16))
    if not pts_r:
        z = np.zeros(shape, dtype=bool)
        return Corroboration(support=z, n_levels=np.zeros(shape, np.int16),
                             score=np.zeros(shape), lines=[],
                             n_flagged_total=0, min_span_px=min_span_px,
                             per_level_px=[int(s.step.sum()) for s in surfaces],
                             per_level_points=per_level_points,
                             azimuths_deg=list(np.arange(0, 180, 5.0)))
    R = np.concatenate(pts_r).astype(np.float64)
    C = np.concatenate(pts_c).astype(np.float64)
    V = np.concatenate(pts_v).astype(np.float64)
    L = np.concatenate(pts_l)
    n_total = R.size

    azimuths = np.arange(0.0, 180.0, 5.0)
    diagonal = float(np.hypot(*shape))
    lines: list[FaultLine] = []
    for az in azimuths:
        th = np.radians(az)
        # direction along the line and its perpendicular (row, col axes)
        dr, dc = np.cos(th), np.sin(th)
        pr, pc = -np.sin(th), np.cos(th)
        rho = R * pr + C * pc
        lo, hi = float(rho.min()), float(rho.max())
        nbin = max(2, int(np.ceil((hi - lo) / rho_bin_px)) + 1)
        idx = np.clip(((rho - lo) / rho_bin_px).astype(int), 0, nbin - 1)
        while nbin * len(azimuths) > 400_000 and rho_bin_px < 8.0:
            rho_bin_px *= 2.0
            nbin = max(2, int(np.ceil((hi - lo) / rho_bin_px)) + 1)
            idx = np.clip(((rho - lo) / rho_bin_px).astype(int), 0, nbin - 1)
        order = np.argsort(idx, kind="stable")
        idx_s = idx[order]
        bounds = np.searchsorted(idx_s, np.arange(nbin + 1))
        for b in range(nbin):
            i0, i1 = bounds[b], bounds[b + 1]
            if i1 - i0 < min_points:
                continue
            sel = order[i0:i1]
            lv = np.unique(L[sel])
            if lv.size < min_levels:
                continue
            v = V[sel]
            if (v > 0).any() and (v < 0).any():
                continue                      # sign disagreement -> not one fault
            mags = np.abs(v)
            # older level (smaller index == higher == older) must not throw less
            # than a younger one on the same line, within a 40 % tolerance
            bad = False
            for a in range(lv.size):
                for bb in range(a + 1, lv.size):
                    la, lb = int(lv[a]), int(lv[bb])
                    ma = mags[L[sel] == la].mean()
                    mb = mags[L[sel] == lb].mean()
                    if not np.isfinite(ma) or not np.isfinite(mb):
                        continue
                    older, younger = (ma, mb) if la < lb else (mb, ma)
                    if older < 0.6 * younger:
                        bad = True
                        break
                if bad:
                    break
            # Along-strike span AND continuity of the inliers, in pixels.
            #
            # IR-62-HOUGH-01 FIX (2026-10-12).  A span test alone is not enough: a
            # loose clump of flagged pixels a few pixels across satisfies a line at
            # *every* azimuth through the clump, so the accepted set fills with
            # radiating "stars" (visible immediately in the first field map).  The
            # measured cure is continuity -- sort the inliers along strike and
            # require the chain to have no big holes and a sane median spacing, so
            # only genuine along-strike chains survive.
            along = np.sort(R[sel] * dr + C[sel] * dc)
            span = float(along[-1] - along[0])
            if span < min_span_px:
                continue
            gaps = np.diff(along)
            if gaps.size and (float(gaps.max()) > max_gap_px
                              or float(np.median(gaps)) > max_median_gap_px):
                continue
            score = float(np.log1p(i1 - i0) * (1.0 + 0.5 * (lv.size - 1))
                          * np.log1p(span / min_span_px))
            lines.append(FaultLine(azimuth_deg=float(az), rho_px=float(lo + (b + 0.5) * rho_bin_px),
                                   n_points=int(i1 - i0), n_levels=int(lv.size),
                                   levels=[int(x) for x in lv],
                                   signs=[int(np.sign(v.mean())) or 1],
                                   mean_throw_m=float(mags.mean()),
                                   support=[(int(R[k]), int(C[k]))
                                            for k in sel[np.argsort(along)]],
                                   score=score))
    lines.sort(key=lambda f: (-f.n_levels, -f.score))
    # Non-maximum suppression.  Suppressing only by (theta, rho) leaves two lines
    # through the same clump of pixels at different azimuths, which is what produced
    # the star artifacts (IR-62-HOUGH-01).  Suppression is therefore on the INLIER
    # SET: a new line is dropped when it shares more than ``nms_jaccard`` of its
    # inliers with an already-kept line.
    kept: list[FaultLine] = []
    kept_sets: list[set] = []
    for f in lines:
        fs = set(f.support)
        dup = False
        for ks in kept_sets:
            inter = len(fs & ks)
            if inter and inter / len(fs | ks) > nms_jaccard:
                dup = True
                break
        if dup:
            continue
        kept.append(f)
        kept_sets.append(fs)
        if len(kept) >= max_lines:
            break

    support = np.zeros(shape, dtype=bool)
    nl = np.zeros(shape, dtype=np.int16)
    sc = np.zeros(shape, dtype=np.float64)
    hi = float(np.percentile([f.score for f in kept], 99)) if kept else 1.0
    hi = hi if hi > 0 else 1.0
    for f in kept:
        s = min(f.score / hi, 1.0)
        for (r, c) in f.support:
            support[r, c] = True
            nl[r, c] = max(nl[r, c], f.n_levels)
            sc[r, c] = max(sc[r, c], s)
    return Corroboration(support=support, n_levels=nl, score=sc, lines=kept,
                         n_flagged_total=int(n_total), min_span_px=min_span_px,
                         per_level_px=[int(s.step.sum()) for s in surfaces],
                         per_level_points=per_level_points,
                         azimuths_deg=[float(a) for a in azimuths])


# =====================================================================================
# 4.  Seeds and the emitted locus field
# =====================================================================================
def seed_points(corr: Corroboration, *, min_score: float = 0.25,
                min_levels: int = 2, min_separation_px: int = 8) -> np.ndarray:
    """Greedy strongest-first thinning of the corroborated loci into seeds.

    ``min_separation_px = 8`` (800 m) is deliberately coarser than the 300 m dot
    kernel: two corroborated loci 800 m apart are two different structures, not
    two samples of one.
    """
    sel = corr.support & (corr.n_levels >= min_levels) & (corr.score >= min_score)
    rr, cc = np.nonzero(sel)
    if rr.size == 0:
        return np.empty((0, 2), dtype=int)
    order = np.argsort(-corr.score[rr, cc], kind="stable")
    kept: list[tuple[int, int]] = []
    used = np.zeros(corr.support.shape, dtype=bool)

    def clear(r0: int, c0: int) -> bool:
        r1, r2 = max(0, r0 - min_separation_px), min(used.shape[0], r0 + min_separation_px + 1)
        c1, c2 = max(0, c0 - min_separation_px), min(used.shape[1], c0 + min_separation_px + 1)
        sub = used[r1:r2, c1:c2]
        if not sub.any():
            return True
        sr, sc = np.nonzero(sub)
        d = np.hypot((sr + r1 - r0) * PIXEL_M, (sc + c1 - c0) * PIXEL_M)
        return bool(np.all(d >= min_separation_px * PIXEL_M))

    for k in order:
        r, c = int(rr[k]), int(cc[k])
        if clear(r, c):
            used[r, c] = True
            kept.append((r, c))
    return np.array(kept, dtype=int) if kept else np.empty((0, 2), dtype=int)
