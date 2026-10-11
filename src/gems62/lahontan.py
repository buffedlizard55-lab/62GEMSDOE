"""Datum-offset lane: Lake Lahontan shorelines as a strain gauge.

Scientific basis (all sources fetched and quoted in ``docs/research/sources.md``):

* The late-Pleistocene (Sehoo) highstand of Lake Lahontan is an **isochronous,
  near-horizontal datum** formed in a period of years to decades immediately
  prior to 13.07 +/- 0.06 ka (Adams & Wesnousky 1998, GSA Bulletin 110, 1318-1332;
  Briggs, Wesnousky & Adams 2005).
* Used as a **passive strain marker**, its elevation now ranges from 1318.4 m at
  the basin periphery to 1340.8 m in the basin centre -- ~22 m of vertical
  deflection, most of it isostatic rebound (domal) plus a down-to-the-north
  regional tilt (Adams, Wesnousky & Bills 1999, JGR).
* "**Active faults locally offset the high shoreline**, but cannot explain the
  regional upwarping" (Adams, Wesnousky & Bills 1999, abstract) -- so the datum
  carries a tectonic residual on top of a smooth rebound field.
* Shorelines of this lake have been used to measure **strike-slip displacement**
  where they are displaced across faults outboard of the Wassuk Range front
  (Dong et al., Geosphere).
* Resolution of the *elevation* method is ~3 m, limited by the natural scatter in
  how high constructional beach features build above still water (Adams,
  Wesnousky & Bills 1999).  The *map-view* signal -- a lateral deflection of the
  shoreline trace -- is not limited by that 3 m and is the primary detector here.

Method implemented below, in order:

1. Select cells on the highstand datum: inside the published deformed-elevation
   window, low local slope (a wave-planed bench or a constructional bar top).
2. Reduce each connected bench to one datum observation (area, centroid,
   median elevation, elongation, azimuth).
3. Fit a smooth **isobase** (robust 2-D polynomial) to those observations.  The
   isobase is the sum of the rebound dome and the regional tilt -- exactly the
   two terms the literature attributes the regional signal to.
4. Residual ``r = z_obs - isobase``.  A **step** is a residual jump between two
   benches that are close in plan view.
5. A **lateral deflection** is a sharp change of the bench-trace azimuth, or a
   gap where a bench trace resumes with a map-view offset.
6. Seed a fault trace at every flagged step and extend it along the local
   structural grain while DEM evidence supports it (``emit.py``).

Every threshold is a module constant so the run card can quote it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

from .grid import PIXEL_M

# --- Published constants ------------------------------------------------------
#: Deformed highstand elevation window (m).  Adams, Wesnousky & Bills (1999)
#: report 1318.4 m (northern periphery) to 1340.8 m (basin centre); the window is
#: widened by 5 m on each side so that the datum is never clipped.
HIGHSTAND_LO_M = 1313.5
HIGHSTAND_HI_M = 1345.8

#: Elevation resolution of the *elevation* method: 3 m (natural scatter of
#: constructional beach crests above still water).  A residual step must exceed
#: this to be reported as a datum offset rather than beach-crest scatter.
ELEVATION_RESOLUTION_M = 3.0

#: A bench is wave-planed: its slope is well below the regional hillslope median.
BENCH_SLOPE_MAX_DEG = 3.0
#: Minimum connected-bench area, in cells (1 cell = 1 ha at 100 m).
BENCH_MIN_CELLS = 8

#: Two benches closer than this in plan view can be contrasted for a step.
STEP_PAIR_RADIUS_M = 5000.0
#: An azimuth change of this size or more is a lateral deflection.
DEFLECTION_MIN_DEG = 35.0


@dataclass
class Bench:
    """One connected set of highstand-datum cells, reduced to a datum observation."""

    label: int
    rows: np.ndarray
    cols: np.ndarray
    n_cells: int
    row_c: float
    col_c: float
    x: float
    y: float
    z: float                # median elevation of the bench (m)
    z_iqr: float
    azimuth_deg: float      # principal axis of the bench footprint, [0, 180)
    elongation: float       # sqrt(lambda1 / lambda2) of the cell covariance
    length_m: float

    @property
    def is_elongated(self) -> bool:
        return self.elongation >= 2.0 and self.n_cells >= BENCH_MIN_CELLS


def slope_degrees(dem: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Terrain slope in degrees from a 100 m DEM (Horn's 3x3 operator, central form)."""
    z = np.where(footprint & np.isfinite(dem), dem, np.nan)
    fill = np.nanmedian(z) if np.isfinite(z).any() else 0.0
    zf = np.where(np.isfinite(z), z, fill)
    gy, gx = np.gradient(zf, PIXEL_M, PIXEL_M)
    out = np.degrees(np.arctan(np.hypot(gx, gy)))
    out[~footprint] = np.nan
    return out


def highstand_mask(dem: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Cells whose elevation lies in the published deformed highstand window."""
    with np.errstate(invalid="ignore"):
        return (
            footprint
            & np.isfinite(dem)
            & (dem >= HIGHSTAND_LO_M)
            & (dem <= HIGHSTAND_HI_M)
        )


def bench_cells(
    dem: np.ndarray,
    footprint: np.ndarray,
    *,
    slope_max_deg: float = BENCH_SLOPE_MAX_DEG,
    min_cells: int = BENCH_MIN_CELLS,
) -> np.ndarray:
    """Wave-planed cells on the highstand datum, small patches removed.

    A cell qualifies when it is inside the highstand window, its slope is below
    ``slope_max_deg``, and it belongs to a connected patch of at least
    ``min_cells`` such cells (8-connected).
    """
    slope = slope_degrees(dem, footprint)
    cand = highstand_mask(dem, footprint) & np.isfinite(slope) & (slope <= slope_max_deg)
    lab, n = ndi.label(cand, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return np.zeros_like(cand)
    sizes = np.bincount(lab.ravel())
    keep = sizes >= min_cells
    keep[0] = False
    return keep[lab]


def _principal_axis(rows: np.ndarray, cols: np.ndarray) -> tuple[float, float]:
    """Azimuth (deg, [0,180)) and elongation of a cell footprint."""
    if rows.size < 3:
        return 0.0, 1.0
    # x = east (col), y = north (-row)
    x = cols.astype(float)
    y = -rows.astype(float)
    x = x - x.mean()
    y = y - y.mean()
    cov = np.cov(np.vstack([x, y]))
    w, v = np.linalg.eigh(cov)
    order = np.argsort(w)[::-1]
    w = w[order]
    v = v[:, order]
    dx, dy = v[0, 0], v[1, 0]
    az = np.degrees(np.arctan2(dx, dy)) % 180.0   # azimuth measured clockwise from north
    elong = float(np.sqrt(max(w[0], 1e-9) / max(w[1], 1e-9)))
    return float(az), elong


def describe_benches(
    dem: np.ndarray,
    footprint: np.ndarray,
    transform: tuple[float, float, float, float, float, float],
    *,
    slope_max_deg: float = BENCH_SLOPE_MAX_DEG,
    min_cells: int = BENCH_MIN_CELLS,
    max_cells: int = 4000,
) -> list[Bench]:
    """Label the wave-planed datum patches and reduce each to one observation.

    Patches larger than ``max_cells`` are split by a conservative watershed on the
    filled patch mask so that one observation never averages the datum across
    more than ~40 km^2 of shoreline.
    """
    mask = bench_cells(dem, footprint, slope_max_deg=slope_max_deg, min_cells=min_cells)
    lab, n = ndi.label(mask, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return []

    a, _, c0, _, e, f = transform
    out: list[Bench] = []
    objs = ndi.find_objects(lab)
    for i, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        rr, cc = np.nonzero(lab[sl] == i)
        rr = rr + sl[0].start
        cc = cc + sl[1].start
        if rr.size < min_cells:
            continue
        zz = dem[rr, cc]
        ok = np.isfinite(zz)
        if ok.sum() < min_cells:
            continue
        rr, cc, zz = rr[ok], cc[ok], zz[ok]
        if rr.size > max_cells:
            sub = np.zeros(lab.shape, dtype=bool)
            sub[rr, cc] = True
            k = int(np.ceil(rr.size / max_cells))
            k = max(2, min(k, 64))
            # Split along the principal axis into k equal-area bins.
            x = cc.astype(float)
            y = -rr.astype(float)
            az, _ = _principal_axis(rr, cc)
            th = np.radians(az)
            proj = x * np.sin(th) + y * np.cos(th)
            edges = np.quantile(proj, np.linspace(0, 1, k + 1))
            idx = np.clip(np.searchsorted(edges, proj, side="right") - 1, 0, k - 1)
            for j in range(k):
                sel = idx == j
                if sel.sum() >= min_cells:
                    out.append(_bench_from_cells(i * 1000 + j, rr[sel], cc[sel], zz[sel], (a, c0, e, f)))
            continue
        out.append(_bench_from_cells(i, rr, cc, zz, (a, c0, e, f)))
    return out


def _bench_from_cells(label: int, rr: np.ndarray, cc: np.ndarray, zz: np.ndarray,
                      params: tuple[float, float, float, float]) -> Bench:
    a, c0, e, f = params
    row_c = float(rr.mean())
    col_c = float(cc.mean())
    x = c0 + (col_c + 0.5) * a
    y = f + (row_c + 0.5) * e
    az, elong = _principal_axis(rr, cc)
    q25, q75 = np.percentile(zz, [25, 75])
    # Along-axis length from the principal-axis projection range.
    th = np.radians(az)
    proj = (cc - col_c) * np.sin(th) + (-(rr - row_c)) * np.cos(th)
    length_m = float(proj.max() - proj.min()) * PIXEL_M
    return Bench(
        label=label, rows=rr, cols=cc, n_cells=int(rr.size),
        row_c=row_c, col_c=col_c, x=float(x), y=float(y),
        z=float(np.median(zz)), z_iqr=float(q75 - q25),
        azimuth_deg=az, elongation=elong, length_m=length_m,
    )


def fit_isobase(
    benches: list[Bench],
    *,
    order: int = 2,
    irls_iters: int = 12,
    huber_k: float = 1.345,
) -> tuple[np.ndarray, dict]:
    """Robust 2-D polynomial isobase fitted to the bench datum elevations.

    The polynomial absorbs the two regional terms the literature names -- the
    domal isostatic rebound and the down-to-the-north tilt.  Fitting is done by
    iteratively reweighted least squares with a Huber weight, so that a handful
    of genuinely faulted benches cannot drag the regional surface.

    Returns ``(coef, info)`` where ``info`` records the design and the residual
    scale of the inlier population.
    """
    if len(benches) < (order + 1) * (order + 2) // 2:
        raise ValueError("not enough benches to fit an isobase of this order")

    x = np.array([b.x for b in benches], dtype=float)
    y = np.array([b.y for b in benches], dtype=float)
    z = np.array([b.z for b in benches], dtype=float)
    # Work in km about the centroid for conditioning.
    x0, y0 = x.mean(), y.mean()
    xs = (x - x0) / 1000.0
    ys = (y - y0) / 1000.0

    terms: list[tuple[int, int]] = [
        (i, j) for i in range(order + 1) for j in range(order + 1 - i)
    ]
    A = np.column_stack([xs ** i * ys ** j for i, j in terms])

    w = np.ones_like(z)
    coef = np.zeros(A.shape[1])
    for _ in range(irls_iters):
        Aw = A * np.sqrt(w)[:, None]
        zw = z * np.sqrt(w)
        coef, *_ = np.linalg.lstsq(Aw, zw, rcond=None)
        r = z - A @ coef
        s = 1.4826 * np.median(np.abs(r - np.median(r)))
        s = max(s, 1e-6)
        u = np.abs(r) / (s * huber_k)
        w = np.where(u <= 1.0, 1.0, 1.0 / np.maximum(u, 1e-9))

    resid = z - A @ coef
    sigma = float(1.4826 * np.median(np.abs(resid - np.median(resid))))
    info = {
        "n_benches": int(len(benches)),
        "order": int(order),
        "x0": float(x0),
        "y0": float(y0),
        "terms": terms,
        "coef": [float(v) for v in coef],
        "residual_sigma_m": sigma,
        "residual_p16_m": float(np.percentile(resid, 16)),
        "residual_p84_m": float(np.percentile(resid, 84)),
        "residual_median_m": float(np.median(resid)),
        "irls_iters": int(irls_iters),
        "huber_k": float(huber_k),
    }
    return coef, info


def isobase_at(coef: np.ndarray, terms: list[tuple[int, int]], x0: float, y0: float,
               x: np.ndarray, y: np.ndarray) -> np.ndarray:
    xs = (np.asarray(x, dtype=float) - x0) / 1000.0
    ys = (np.asarray(y, dtype=float) - y0) / 1000.0
    out = np.zeros_like(xs)
    for c, (i, j) in zip(coef, terms):
        out += c * xs ** i * ys ** j
    return out


@dataclass
class StepFlag:
    """A flagged abrupt step of the datum along strike."""

    x: float
    y: float
    residual_jump_m: float
    pair_distance_m: float
    az_deg: float            # azimuth of the line joining the two benches
    bench_a: int
    bench_b: int
    kind: str = "elevation_step"


@dataclass
class DeflectionFlag:
    """A flagged lateral deflection of the datum trace."""

    x: float
    y: float
    az_change_deg: float
    gap_m: float
    az_in_deg: float
    az_out_deg: float
    bench_a: int
    bench_b: int
    kind: str = "lateral_deflection"


def level_structure(residual: np.ndarray, weights: np.ndarray,
                    *, bin_m: float = 1.0) -> dict:
    """Describe the discrete level structure of the datum residuals.

    A pluvial basin hosts several stacked shorelines (Lake Lahontan preserves the
    late-Pleistocene Sehoo highstand plus older Eetza/Wyemaha strands, and a
    staircase of recessional bars).  All of them plot inside the published
    deformed-elevation window, so the residual distribution is *multi-modal*.
    Two benches on different strands differ in elevation by construction and would
    be a false "step"; this function reports the modes so the caller can restrict
    the step test to one strand.

    Returns the mode locations (cell-weighted), their mass, and the dominant mode.
    """
    r = np.asarray(residual, dtype=float)
    w = np.asarray(weights, dtype=float)
    if r.size == 0:
        return {"modes": [], "dominant_m": float("nan"), "n_modes": 0}
    lo, hi = float(r.min()), float(r.max())
    edges = np.arange(lo - bin_m, hi + bin_m * 2, bin_m)
    hist, _ = np.histogram(r, bins=edges, weights=w)
    # Light smoothing so single-bin gaps do not split one mode.
    k = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    k = k / k.sum()
    hist_s = np.convolve(hist, k, mode="same")
    centres = 0.5 * (edges[:-1] + edges[1:])
    # Mode seeking with a minimum separation.
    order = np.argsort(hist_s)[::-1]
    modes: list[dict] = []
    min_sep = 3.0
    for idx in order:
        if hist_s[idx] <= 0:
            continue
        if any(abs(centres[idx] - m["value_m"]) < min_sep for m in modes):
            continue
        modes.append({"value_m": float(centres[idx]), "mass_cells": float(hist_s[idx])})
        if len(modes) >= 6:
            break
    modes.sort(key=lambda m: m["value_m"])
    dominant = max(modes, key=lambda m: m["mass_cells"]) if modes else {"value_m": float("nan")}
    total = float(sum(m["mass_cells"] for m in modes)) or 1.0
    for m in modes:
        m["fraction"] = m["mass_cells"] / total
    return {
        "modes": modes,
        "n_modes": len(modes),
        "dominant_m": float(dominant["value_m"]),
        "bin_m": bin_m,
    }


def dominant_strand_mask(
    residual: np.ndarray,
    weights: np.ndarray,
    *,
    tolerance_m: float = 4.0,
    mode: float | None = None,
) -> tuple[np.ndarray, dict]:
    """Select the benches belonging to the dominant (most massive) datum strand.

    ``tolerance_m`` is how far a bench may sit from the strand's level and still be
    treated as part of it.  It is deliberately a little wider than the published
    3 m elevation resolution so that faulted-but-still-picked benches are retained
    for the step test rather than silently dropped.
    """
    struct = level_structure(residual, weights)
    target = float(struct["dominant_m"]) if mode is None else float(mode)
    r = np.asarray(residual, dtype=float)
    keep = np.isfinite(r) & (np.abs(r - target) <= tolerance_m)
    struct["strand_tolerance_m"] = tolerance_m
    struct["strand_benches"] = int(keep.sum())
    struct["strand_cells"] = int(np.asarray(weights, dtype=float)[keep].sum()) if keep.any() else 0
    return keep, struct


def local_isobase(
    benches: list[Bench],
    residual: np.ndarray,
    *,
    radius_m: float = 12_000.0,
    min_neighbours: int = 6,
    huber_k: float = 1.345,
    iters: int = 8,
) -> tuple[np.ndarray, dict]:
    """Locally robust isobase fitted to *one* isochronous strand.

    The literature supplies the physical form of the regional signal: a domal
    isostatic rebound plus a northward tilt, both of which vary on the 100 km
    scale (22 m of total deflection across the basin).  Over the 12 km fitting
    radius used here that signal is a smooth, near-planar surface.  For every bench
    a robust plane is therefore fitted to its neighbours' *residuals*, and the
    local level is the plane's value at the bench.  Doing this on residuals (rather
    than raw elevations) also lets the caller restrict the fit to a single strand,
    which removes the stacked-shoreline mimic.
    """
    n = len(benches)
    x = np.array([b.x for b in benches], dtype=float)
    y = np.array([b.y for b in benches], dtype=float)
    r = np.asarray(residual, dtype=float)
    level = np.full(n, np.nan)
    n_used = np.zeros(n, dtype=int)

    for i in range(n):
        d = np.hypot(x - x[i], y - y[i])
        sel = np.nonzero((d <= radius_m) & (d > 0))[0]
        if sel.size < min_neighbours:
            sel = np.argsort(d)[1 : min_neighbours + 1]
        if sel.size == 0:
            level[i] = r[i]
            continue
        xr = (x[sel] - x[i]) / 1000.0
        yr = (y[sel] - y[i]) / 1000.0
        A = np.column_stack([np.ones_like(xr), xr, yr])
        zz = r[sel]
        w = np.ones_like(zz)
        coef = np.zeros(3)
        for _ in range(iters):
            Aw = A * np.sqrt(w)[:, None]
            coef, *_ = np.linalg.lstsq(Aw, zz * np.sqrt(w), rcond=None)
            rr = zz - A @ coef
            s = 1.4826 * np.median(np.abs(rr - np.median(rr)))
            s = max(s, 1e-6)
            u = np.abs(rr) / (s * huber_k)
            w = np.where(u <= 1.0, 1.0, 1.0 / np.maximum(u, 1e-9))
        level[i] = float(coef[0])
        n_used[i] = int(sel.size)

    rho = r - level
    sigma = float(1.4826 * np.median(np.abs(rho - np.median(rho))))
    info = {
        "radius_m": radius_m,
        "min_neighbours": min_neighbours,
        "huber_k": huber_k,
        "residual_sigma_m": sigma,
        "n_benches": n,
        "median_neighbours": int(np.median(n_used)) if n else 0,
    }
    return rho, info


def flag_steps(
    benches: list[Bench],
    residual: np.ndarray,
    *,
    threshold_m: float = ELEVATION_RESOLUTION_M,
    radius_m: float = STEP_PAIR_RADIUS_M,
) -> list[StepFlag]:
    """Flag bench pairs that are close in plan view but differ in residual.

    The threshold defaults to the published 3 m elevation resolution: a smaller
    difference is not separable from the natural scatter of beach-crest heights.
    """
    flags: list[StepFlag] = []
    for i, bi in enumerate(benches):
        for j in range(i + 1, len(benches)):
            bj = benches[j]
            d = float(np.hypot(bi.x - bj.x, bi.y - bj.y))
            if d > radius_m:
                continue
            jump = float(residual[i] - residual[j])
            if abs(jump) < threshold_m:
                continue
            az = float(np.degrees(np.arctan2(bj.x - bi.x, bj.y - bi.y)) % 180.0)
            flags.append(
                StepFlag(
                    x=0.5 * (bi.x + bj.x), y=0.5 * (bi.y + bj.y),
                    residual_jump_m=jump, pair_distance_m=d, az_deg=az,
                    bench_a=i, bench_b=j,
                )
            )
    return flags


def flag_deflections(
    benches: list[Bench],
    *,
    min_change_deg: float = DEFLECTION_MIN_DEG,
    max_gap_m: float = 5000.0,
) -> list[DeflectionFlag]:
    """Flag azimuth changes between nearby, well-elongated datum traces."""
    flags: list[DeflectionFlag] = []
    elongated = [b for b in benches if b.is_elongated]
    for i, bi in enumerate(elongated):
        for j in range(i + 1, len(elongated)):
            bj = elongated[j]
            d = float(np.hypot(bi.x - bj.x, bi.y - bj.y))
            if d > max_gap_m:
                continue
            da = abs(((bi.azimuth_deg - bj.azimuth_deg) + 90.0) % 180.0 - 90.0)
            if da < min_change_deg:
                continue
            az = float(np.degrees(np.arctan2(bj.x - bi.x, bj.y - bi.y)) % 180.0)
            flags.append(
                DeflectionFlag(
                    x=0.5 * (bi.x + bj.x), y=0.5 * (bi.y + bj.y),
                    az_change_deg=float(da), gap_m=d,
                    az_in_deg=bi.azimuth_deg, az_out_deg=bj.azimuth_deg,
                    bench_a=i, bench_b=j,
                )
            )
    return flags


def datum_offset_surface(
    benches: list[Bench],
    residual: np.ndarray,
    shape: tuple[int, int],
    *,
    step_threshold_m: float = ELEVATION_RESOLUTION_M,
) -> tuple[np.ndarray, np.ndarray]:
    """The two rasters the lane rule means by "the surface before placement".

    ``full``
        |local-isobase residual| in metres on every dominant-strand datum cell.
        This is the field the seeding and extension steps read.
    ``evidence``
        the same field restricted to benches flagged as anomalous
        (|residual| >= ``step_threshold_m``); the analogue of a dot set when the
        3-px overlap half of the rule is applied before placement.

    Both are zero away from their cells and therefore comparable, by
    ``gems62.uniqueness.compare``, against any registry raster without further
    masking.
    """
    full = np.zeros(shape, np.float32)
    evidence = np.zeros(shape, np.float32)
    for b, r in zip(benches, residual):
        mag = np.abs(float(r)).astype(np.float32)
        full[b.rows, b.cols] = mag
        if abs(float(r)) >= step_threshold_m:
            evidence[b.rows, b.cols] = mag
    return full, evidence


def shoreline_profile(benches: list[Bench], residual: np.ndarray, *,
                      track_deg: float) -> list[dict]:
    """Order benches along a published shoreline track and return a profile.

    ``track_deg`` is the azimuth of the track (degrees clockwise from north).
    The returned list is the first deliverable of the lane: an
    elevation-versus-distance profile of the datum with the flagged steps.
    """
    if not benches:
        return []
    th = np.radians(track_deg)
    rows = []
    for i, b in enumerate(benches):
        s = (b.x * np.sin(th) + b.y * np.cos(th))
        rows.append({
            "bench": i,
            "x": b.x, "y": b.y,
            "along_track_m": float(s),
            "elevation_m": b.z,
            "isobase_m": float(b.z - residual[i]),
            "residual_m": float(residual[i]),
            "n_cells": b.n_cells,
            "azimuth_deg": b.azimuth_deg,
            "length_m": b.length_m,
        })
    rows.sort(key=lambda r: r["along_track_m"])
    s0 = rows[0]["along_track_m"]
    for r in rows:
        r["distance_track_m"] = r["along_track_m"] - s0
    return rows
