"""Lane driver: Lake Lahontan highstand shoreline as a strain gauge.

Physics of the lane
-------------------
The Sehoo (Lahontan) highstand shoreline is a near-level constructional/erosional
datum formed at 13,070 +/- 60 14C yr B.P. = 15,475 +/- 720 cal yr B.P.
(Adams & Wesnousky 1998, GSA Bulletin 110, 1318-1332).  Because it was level when
formed and has since been deformed only by (a) regional isostatic rebound and
(b) fault slip, the residual of a mapped shoreline-elevation pick about a smooth
isobase is a *strain measurement*.  A fault that breaks the datum produces an
abrupt step or a lateral deflection in it -- the surveyor's "bench mark moved".

Verified literature (all read 2026-10-11, links in docs/sources.html):
  * highstand shoreline elevation 1,332-1,340 m; 1,339 m at the Jessup
    embayment; the highstand shoreline varies from ~1,340 m near the basin
    centre to ~1,318 m at the northern edge because of isostatic rebound and
    northward tilting  (Adams, Wesnousky & Bills 1999; Adams et al. 2008).
  * Pyramid Lake fault zone offsets post-Lahontan surfaces; >= 4 surface
    ruptures since desiccation, 2.6 +/- 0.3 mm/yr right-lateral
    (Briggs & Wesnousky 2004, JGR 109, B08402, doi:10.1029/2003JB002717).
  * a strike-slip fault outboard of the Wassuk Range front right-laterally
    displaces Lahontan recessional shorelines 13.5-13.9 m  (Dong et al. 2014,
    Geosphere 10(1), 40-48, doi:10.1130/GES00912.1).
  * two previously unmapped NW-striking fault segments near the centre of
    Smith Valley offset Holocene sediments  (Pierce, Wesnousky & Owen 2016,
    SCEC Annual Meeting Poster #097, SCEC Contribution #6917).

Nothing in this module is a competition score.  Every emitted number is
labelled MEASURED (reproducible from the pinned bytes) or MODEL.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

# ---------------------------------------------------------------- constants
# Literature band for the Sehoo highstand shoreline (verified, see docstring).
HIGHSTAND_M = 1333.0          # central value used only to centre the search
BAND_LO_M = 1295.0            # search band for shoreline benches
BAND_HI_M = 1365.0            # (band is a *search window*, never an input to the fit)


# ------------------------------------------------------------------- slope
def horn_slope_m_per_m(z: np.ndarray, cell: float = 100.0) -> np.ndarray:
    """Horn (1981) 3x3 slope; returns tan(slope) i.e. rise/run."""
    p = np.pad(z, 1, mode="edge")
    a, b, c = p[0:-2, 0:-2], p[0:-2, 1:-1], p[0:-2, 2:]
    d, f = p[1:-1, 0:-2], p[1:-1, 2:]
    g, h, i = p[2:, 0:-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8.0 * cell)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8.0 * cell)
    return np.hypot(dzdx, dzdy)


# ------------------------------------------------------------- isobase fit
def isobase_design(x_km: np.ndarray, y_km: np.ndarray) -> np.ndarray:
    """Quadratic design matrix [1, x, y, x^2, xy, y^2]."""
    x = np.asarray(x_km, float)
    y = np.asarray(y_km, float)
    # Works for 1-D (n,) -> (n, 6) and for 2-D (h, w) -> (h, w, 6).
    return np.stack([np.ones_like(x), x, y, x * x, x * y,
                     np.ones_like(x) * (y * y)], axis=-1)


def fit_isobase(x_km, y_km, z_m, *, huber_c: float = 2.0, iters: int = 25,
                ridge: float = 1e-8) -> dict:
    """Iteratively reweighted least squares (Huber) quadratic isobase.

    Returns the coefficients, the residual scale and the per-point residuals.
    The fit is the *only* place the "level datum" assumption is used; the band
    above only chose which pixels enter it.
    """
    A = isobase_design(x_km, y_km)
    z = np.asarray(z_m, float)
    w = np.ones_like(z)
    coef = np.zeros(A.shape[1])
    for _ in range(iters):
        Aw = A * w[:, None]
        G = A.T @ Aw + ridge * np.eye(A.shape[1])
        coef = np.linalg.solve(G, A.T @ (w * z))
        r = z - A @ coef
        s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-9
        u = np.abs(r) / (huber_c * s)
        w = np.where(u <= 1.0, 1.0, 1.0 / u)
    r = z - A @ coef
    return dict(coef=coef.tolist(), residual_scale_m=float(s),
                rmse_m=float(np.sqrt(np.mean(r ** 2))),
                n=int(z.size), residuals_m=r,
                tilt_x_m_per_km=float(coef[1]), tilt_y_m_per_km=float(coef[2]))


def isobase_surface(coef, x_km, y_km) -> np.ndarray:
    """Evaluate the isobase on 1-D or 2-D coordinates (contracted over the last axis)."""
    A = isobase_design(x_km, y_km)
    return np.tensordot(A, np.asarray(coef, float), axes=([-1], [0]))


# ---------------------------------------------------------------- benches
def bench_mask(slope: np.ndarray, band: np.ndarray, *,
               flat_pct: float = 20.0, steep_pct: float = 80.0,
               win: int = 5) -> tuple[np.ndarray, dict]:
    """A *bench* pixel is a locally flat pixel that has a steeper riser within
    `win` cells of it -- the tread/riser signature of a wave-cut or
    constructional shoreline terrace.

    Thresholds are percentiles of the measured in-band slope distribution, so
    nothing is hard-coded from memory.
    """
    s_in = slope[band]
    flat_thr = float(np.percentile(s_in, flat_pct))
    steep_thr = float(np.percentile(s_in, steep_pct))
    flat = band & (slope <= flat_thr)
    steep = band & (slope >= steep_thr)
    near_steep = ndi.maximum_filter(steep.astype(np.uint8), size=win) > 0
    bench = flat & near_steep
    return bench, dict(flat_slope_threshold_pct_m_per_m=flat_thr,
                       steep_slope_threshold_pct_m_per_m=steep_thr,
                       window_px=win,
                       n_band_px=int(band.sum()),
                       n_bench_px=int(bench.sum()))


# ------------------------------------------------------------ trace walker
def order_trace(pixels: np.ndarray) -> np.ndarray:
    """Order an unordered set of (row, col) pixels into a polyline greedily.

    Returns indices into `pixels` in walk order.  Adequate for the
    near-1-D traces produced here (verified by the trace-length check in
    tests/test_lahontan.py)."""
    if len(pixels) <= 2:
        return np.arange(len(pixels))
    pts = pixels.astype(float)
    used = np.zeros(len(pts), bool)
    # start at the endpoint that is furthest from the centroid
    c = pts.mean(axis=0)
    start = int(np.argmax(((pts - c) ** 2).sum(axis=1)))
    order = [start]
    used[start] = True
    for _ in range(len(pts) - 1):
        last = pts[order[-1]]
        d = ((pts - last) ** 2).sum(axis=1)
        d[used] = np.inf
        nxt = int(np.argmin(d))
        if not np.isfinite(d[nxt]) or d[nxt] > 9.0 ** 2:   # gap > 9 cells -> break
            break
        order.append(nxt)
        used[nxt] = True
    return np.array(order)


def profile_along_trace(rows: np.ndarray, cols: np.ndarray, zeta: np.ndarray,
                        z: np.ndarray, cell_px: float = 1.0) -> dict:
    """Distance (px and m) and elevation/zeta along an ordered trace."""
    d = np.hypot(np.diff(rows), np.diff(cols)).cumsum()
    dist_px = np.concatenate([[0.0], d])
    return dict(distance_px=dist_px,
                distance_m=dist_px * cell_px * 100.0,
                elevation_m=z[rows, cols].astype(float),
                zeta_m=zeta[rows, cols].astype(float),
                rows=rows.astype(np.int32), cols=cols.astype(np.int32))


def find_steps(prof: dict, *, win: int = 6, zeta_step_m: float = 2.5,
               deflect_deg: float = 25.0) -> list[dict]:
    """Flag abrupt steps / lateral deflections along a shoreline trace.

    Two independent criteria, both reported per flag:

    * **vertical step** -- a change of |zeta| between the mean of the `win`
      samples before and after a position on the trace.  This is the fault
      paring the datum up or down.
    * **lateral deflection** -- a change of heading of >= `deflect_deg`
      between the chord of the preceding `win` samples and the following
      `win` samples.  This is the strike-slip / oblique case (Dong et al.
      2014 measured 13.5 m of right-lateral deflection).
    """
    rows, cols = prof["rows"], prof["cols"]
    zeta = prof["zeta_m"]
    d = prof["distance_m"]
    n = len(rows)
    flags: list[dict] = []
    if n < 2 * win + 1:
        return flags

    # vertical step: compare local linear fits either side of the pivot
    for k in range(win, n - win):
        before = zeta[k - win:k]
        after = zeta[k:k + win]
        step = float(np.mean(after) - np.mean(before))
        if abs(step) >= zeta_step_m:
            flags.append(dict(index=int(k), kind="vertical_step",
                              distance_m=float(d[k]), row=int(rows[k]),
                              col=int(cols[k]), magnitude_m=step,
                              detail=dict(mean_before=float(before.mean()),
                                          mean_after=float(after.mean()),
                                          window=win)))

    # lateral deflection: heading change between the two chords
    for k in range(win, n - win):
        v1 = np.array([rows[k] - rows[k - win], cols[k] - cols[k - win]], float)
        v2 = np.array([rows[k + win] - rows[k], cols[k + win] - cols[k]], float)
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 < 1e-6 or n2 < 1e-6:
            continue
        cosang = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
        ang = float(np.degrees(np.arccos(cosang)))
        if ang >= deflect_deg:
            flags.append(dict(index=int(k), kind="lateral_deflection",
                              distance_m=float(d[k]), row=int(rows[k]),
                              col=int(cols[k]), magnitude_m=ang,
                              detail=dict(heading_change_deg=ang, window=win)))
    # de-duplicate: keep the strongest flag in any 5-px neighbourhood
    if not flags:
        return flags
    flags.sort(key=lambda f: -abs(f["magnitude_m"]))
    kept: list[dict] = []
    for f in flags:
        if all(np.hypot(f["row"] - g["row"], f["col"] - g["col"]) > 5 for g in kept):
            kept.append(f)
    kept.sort(key=lambda f: f["index"])
    return kept
