"""Datum-offset lane: Lake Lahontan shorelines as a strain gauge.

The physics being exploited
---------------------------
The Lake Lahontan highstand shoreline is a near-level datum formed at ~15 ka: a wave-cut
bench/terrace whose tread is nearly horizontal and whose lakeward edge is a riser (a slope
break).  Because the surface was level when it formed, any *post-pluvial* deformation is
legible as a departure from a smooth isobase:

* **vertical separation** of the shoreline across a fault -> a step in the bench's
  elevation-versus-along-strike-distance profile (the classic shoreline-angle scarp);
* **lateral deflection** of the shoreline trace where a strike-slip / oblique fault crosses it;
* **warping** of the bench inside a fault's deformation field (a smooth isobase bend).

Method (`DatumLane`), matching the assigned lane paragraph one clause at a time:

1. "map shoreline benches in the DEM"            -> `bench_response`
2. "fit a smooth isobase, allowing for post-pluvial isostatic rebound"
                                                 -> `isobase_surface` (robust local mode of the
                                                    bench elevations, then Gaussian smoothing;
                                                    no assumption of a planar datum)
3. "flag abrupt steps or lateral deflections along strike" -> `flag_steps`, `flag_deflections`
4. "seed a trace at each, extend it while DEM-ridge evidence supports it"
                                                 -> `ScarpField` + `trace_from_seed`
5. "emit dotted lines"                           -> `emit_dots`

Nothing in this module reads the fault catalogue except the optional, explicit
`catalogue_exclusion_px` guard in `emit_dots`, which *deletes* dots near already-known faults
(they are masked/excluded from scoring -- DrivenData forum thread 11516, chrisk-dd, 2026-09-16)
and can be set to 0 to disable.  That makes the detector catalogue-free by construction, which
is what the hide-and-recover instrument (`scripts/run_holdout.py`) tests.

Published anchors for the target datum (used only to set *windows*, never to place dots):
  Reheis, M.C. (1999) Highest pluvial-lake shorelines and Pleistocene climate of the western
    Great Basin. Quaternary Research 51, 196-205.  (Lahontan highstand shoreline above ~1330 m;
    shorelines in the western Lahontan subbasins lie in a few-metre band.)
  Adams, K.D. & Wesnousky, S.G. (1998) Shoreline processes and the age of the Lake Lahontan
    highstand in the Jessup embayment, Nevada. GSA Bulletin 110, 1318-1332.
  Briggs, R.W. & Wesnousky, S.G. (2004) JGR 109, B08405 -- displaced Lahontan features used to
    constrain slip on the Pyramid Lake fault zone.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------------------------------------
# terrain derivatives
# ---------------------------------------------------------------------------------------------
def horn_slope(z: np.ndarray, res: float) -> np.ndarray:
    p = np.pad(z, 1, mode="edge")
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * res)
    return np.hypot(dzdx, dzdy)


def gradient(z: np.ndarray, res: float) -> tuple[np.ndarray, np.ndarray]:
    p = np.pad(z, 1, mode="edge")
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * res)
    return dzdx, dzdy


# ---------------------------------------------------------------------------------------------
# 1. shoreline benches
# ---------------------------------------------------------------------------------------------
def bench_response(z: np.ndarray, res: float, *, flat_slope=0.035, riser_slope=0.10,
                   riser_min_m=100.0, riser_max_m=500.0, above_floor_m=12.0,
                   floor_window_m=3000.0) -> dict:
    """Grade the terrain for "wave-cut bench": flat tread, riser nearby, above the lake floor.

    flat  = slope < `flat_slope`
    riser = slope > `riser_slope`
    score = flat  x  [ there is a riser 100-500 m away ]  x  [>= `above_floor_m` above the
            local minimum elevation in a 3 km window, which removes the playa floors that are
            otherwise the flattest, most confusing surfaces in the basin]
    """
    slope = horn_slope(z, res)
    flat = slope < flat_slope
    riser = slope > riser_slope
    d_riser = ndimage.distance_transform_edt(~riser) * res
    near = np.exp(-((d_riser - 250.0) / 200.0) ** 2)
    win = int(round(floor_window_m / res))
    local_min = ndimage.minimum_filter(z, size=win)
    above = z - local_min
    floor_ok = above > above_floor_m
    score = np.where(flat & floor_ok, near, 0.0).astype(np.float32)
    return dict(slope=slope.astype(np.float32), flat=flat, riser=riser,
                d_riser=d_riser.astype(np.float32), score=score, above_floor=above.astype(np.float32))


def isobase_surface(z: np.ndarray, bench_mask: np.ndarray, res: float, *,
                    tile_m: float = 4000.0, smooth_tiles: float = 1.5,
                    z_lo: float = 1150.0, z_hi: float = 1450.0, dz: float = 2.0) -> np.ndarray:
    """Smooth isobase: per-tile robust mode of bench elevations, then Gaussian-smoothed.

    The mode answers "at what elevation does this neighbourhood keep a bench?", which is the
    observed datum.  Post-pluvial isostatic rebound is allowed for *by construction*: the
    surface is free to warp, and only its smoothness is imposed, so a rebound dome survives
    into the residual instead of being mistaken for a fault step.
    """
    h, w = z.shape
    t = int(round(tile_m / res))
    bins = np.arange(z_lo, z_hi + dz, dz)
    tr = int(np.ceil(h / t))
    tc = int(np.ceil(w / t))
    surf = np.full((tr, tc), np.nan)
    for i in range(tr):
        for j in range(tc):
            sub = z[i * t:(i + 1) * t, j * t:(j + 1) * t]
            m = bench_mask[i * t:(i + 1) * t, j * t:(j + 1) * t]
            v = sub[m & np.isfinite(sub)]
            if v.size < 25:
                continue
            hist, edges = np.histogram(v, bins=bins)
            k = int(np.argmax(hist))
            if hist[k] < 10:
                continue
            lo, hi = edges[k], edges[k + 1]
            inb = v[(v >= lo) & (v <= hi)]
            surf[i, j] = float(np.median(inb))
    # fill holes with nearest valid tile, then smooth
    if np.isnan(surf).all():
        return np.full_like(z, np.nan, dtype=np.float32)
    idx = ndimage.distance_transform_edt(np.isnan(surf), return_distances=False,
                                         return_indices=True)
    filled = surf[tuple(idx)]
    sm = ndimage.gaussian_filter(filled, sigma=smooth_tiles)
    # upsample tile surface to the DEM grid (bilinear via zoom)
    out = np.empty_like(z, dtype=np.float32)
    yi = np.clip((np.arange(h) / t), 0, tr - 1)
    xi = np.clip((np.arange(w) / t), 0, tc - 1)
    y0 = np.floor(yi).astype(int); x0 = np.floor(xi).astype(int)
    y1 = np.clip(y0 + 1, 0, tr - 1); x1 = np.clip(x0 + 1, 0, tc - 1)
    fy = (yi - y0)[:, None]; fx = (xi - x0)[None, :]
    out = (sm[np.ix_(y0, x0)] * (1 - fy) * (1 - fx) + sm[np.ix_(y1, x0)] * fy * (1 - fx)
           + sm[np.ix_(y0, x1)] * (1 - fy) * fx + sm[np.ix_(y1, x1)] * fy * fx)
    return out.astype(np.float32)


def shoreline_mask(z: np.ndarray, bench: dict, isobase: np.ndarray, *, tol_m: float = 8.0,
                   min_score: float = 0.25) -> np.ndarray:
    r = z - isobase
    return (bench["score"] >= min_score) & np.isfinite(isobase) & (np.abs(r) <= tol_m)


# ---------------------------------------------------------------------------------------------
# 2. ordering a bench into an along-strike chain + profile statistics
# ---------------------------------------------------------------------------------------------
def order_chain(points: np.ndarray, res: float) -> np.ndarray:
    """Order scattered bench pixels into a polyline by greedy nearest-neighbour walking.

    points: (N,2) array of (row, col).  Returns the visiting order.  For the thin, elongated
    components the shoreline detector produces this recovers the along-strike direction; the
    walk is restarted at the most extreme point (max PCA projection) so it does not begin in the
    middle of a strand.  Use `chains_from_component` instead when a component may contain more
    than one strand.
    """
    n = len(points)
    if n < 2:
        return np.arange(n)
    xy = points.astype(np.float64)
    centred = xy - xy.mean(0)
    u, s, vt = np.linalg.svd(centred, full_matrices=False)
    proj = centred @ vt[0]
    start = int(np.argmax(proj))
    remaining = np.ones(n, bool)
    order = [start]
    remaining[start] = False
    cur = start
    for _ in range(n - 1):
        rem_idx = np.nonzero(remaining)[0]
        d = np.hypot(points[rem_idx, 0] - points[cur, 0], points[rem_idx, 1] - points[cur, 1])
        nxt = int(rem_idx[int(np.argmin(d))])
        order.append(nxt)
        remaining[nxt] = False
        cur = nxt
    return np.array(order)


def chains_from_component(points: np.ndarray, res: float, *, max_jump_m: float = 150.0,
                          min_chain_px: int = 40) -> list[np.ndarray]:
    """Split a connected bench component into *strands* by capping the chaining jump.

    Why this exists: a connected component of the shoreline mask is a "flat and near the local
    isobase" region, and such a region can contain several parallel strands (two stands of the
    same lake, plus the odd alluvial-flat patch).  The plain nearest-neighbour walk then leaps
    between strands, which manufactures a fake 10 m "step" out of a 2 km jump along the chain --
    exactly the artefact that made the first version of this pipeline emit zero traces (every
    flagged station sat on a leap, where there is no scarp in the DEM to extend along).

    Strands longer than `min_chain_px` are returned as ordered index arrays; shorter leftovers
    are discarded as noise.
    """
    n = len(points)
    if n < min_chain_px:
        return []
    order = order_chain(points, res)
    p = points[order]
    jumps = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1])) * res
    breaks = np.nonzero(jumps > max_jump_m)[0]
    chains = []
    starts = np.concatenate([[0], breaks + 1])
    ends = np.concatenate([breaks + 1, [n]])
    for a, b in zip(starts, ends):
        if b - a >= min_chain_px:
            chains.append(order[a:b])
    return chains


def profile(points_rowcol: np.ndarray, z: np.ndarray, isobase: np.ndarray, res: float) -> dict:
    """Along-strike profile: cumulative distance s, bench elevation, isobase, residual r, azimuth."""
    order = order_chain(points_rowcol, res)
    pf = points_rowcol[order].astype(np.float64)
    pi = np.rint(pf).astype(int)
    y = pf[:, 0] * res
    x = pf[:, 1] * res
    ds = np.hypot(np.diff(y), np.diff(x))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    zb = z[pi[:, 0], pi[:, 1]].astype(np.float64)
    zib = isobase[pi[:, 0], pi[:, 1]].astype(np.float64)
    idx = np.arange(len(pf))
    # azimuth over a moving window of +-250 m (robust to pixel-scale jitter)
    half = max(2, int(250.0 / res))
    az = np.full(len(pf), np.nan)
    for i in range(len(pf)):
        a = max(0, i - half); b = min(len(pf) - 1, i + half)
        dy = y[b] - y[a]; dx = x[b] - x[a]
        if abs(dy) + abs(dx) > 0:
            az[i] = np.degrees(np.arctan2(dy, dx)) % 180.0
    return dict(s=s, z=zb, isobase=zib, r=zb - zib, azimuth=az, idx=idx)


# ---------------------------------------------------------------------------------------------
# 3. flag abrupt steps and lateral deflections along strike
# ---------------------------------------------------------------------------------------------
def smooth_profile(v: np.ndarray, res: float, window_m: float = 300.0) -> np.ndarray:
    k = max(1, int(round(window_m / res)))
    if k < 2 or v.size < 3:
        return v
    return ndimage.median_filter(v, size=k, mode="nearest")


def flag_steps(prof: dict, *, window_m: float = 500.0, res: float = 25.0,
               min_step_m: float = 2.0, smooth_m: float = 250.0) -> list[dict]:
    """Vertical separation: |r(s+w) - r(s-w)| above threshold, at a local extremum of the
    along-strike difference.  `min_step_m` is the *observed* offset of the bench surface across
    the station; 2 m is the smallest offset a 25 m DEM + wave-cut bench can support honestly."""
    r = smooth_profile(prof["r"], res, smooth_m)
    s = prof["s"]
    w = int(round(window_m / res))
    if len(r) < 2 * w + 3:
        return []
    d = np.full(len(r), np.nan)
    d[w:-w] = r[2 * w:] - r[:-2 * w]
    out = []
    for i in range(w + 1, len(r) - w - 1):
        if not np.isfinite(d[i]):
            continue
        if abs(d[i]) < min_step_m:
            continue
        if abs(d[i]) >= abs(d[i - 1]) and abs(d[i]) >= abs(d[i + 1]):
            out.append(dict(kind="step", i=int(i), s_m=float(s[i]), step_m=float(d[i]),
                            sign=int(np.sign(d[i]))))
    # keep the strongest station per 1 km of along-strike distance
    out.sort(key=lambda e: -abs(e["step_m"]))
    kept = []
    for e in out:
        if all(abs(e["s_m"] - k["s_m"]) > 1000.0 for k in kept):
            kept.append(e)
    kept.sort(key=lambda e: e["s_m"])
    return kept


def flag_deflections(prof: dict, *, res: float = 25.0, window_m: float = 500.0,
                     min_delta_deg: float = 12.0) -> list[dict]:
    """Lateral deflection: an abrupt change of the along-strike azimuth, the signature a
    strike-slip / oblique fault leaves on a shoreline trace."""
    az = prof["azimuth"]
    s = prof["s"]
    w = int(round(window_m / res))
    if len(az) < 2 * w + 3 or not np.isfinite(az).any():
        return []
    daz = np.full(len(az), np.nan)
    for i in range(w, len(az) - w):
        a0, a1 = az[i - w], az[i + w]
        if np.isfinite(a0) and np.isfinite(a1):
            dd = (a1 - a0 + 90.0) % 180.0 - 90.0
            daz[i] = dd
    out = []
    for i in range(w + 1, len(az) - w - 1):
        if not np.isfinite(daz[i]) or abs(daz[i]) < min_delta_deg:
            continue
        if abs(daz[i]) >= abs(np.nan_to_num(daz[i - 1])) and abs(daz[i]) >= abs(np.nan_to_num(daz[i + 1])):
            out.append(dict(kind="deflection", i=int(i), s_m=float(s[i]),
                            delta_deg=float(daz[i]), sign=int(np.sign(daz[i]))))
    out.sort(key=lambda e: -abs(e["delta_deg"]))
    kept = []
    for e in out:
        if all(abs(e["s_m"] - k["s_m"]) > 1000.0 for k in kept):
            kept.append(e)
    kept.sort(key=lambda e: e["s_m"])
    return kept


# ---------------------------------------------------------------------------------------------
# 4. DEM-ridge evidence + trace extension
# ---------------------------------------------------------------------------------------------
@dataclass
class ScarpField:
    """Scarp/lineament evidence from the DEM alone.

    A fault scarp is a *step* in the elevation field, i.e. a ridge of the gradient magnitude.
    We build |grad z| (smoothed at `sigma_m`), take its Hessian, and score cells by the standard
    ridge (Frangi) criterion -- the largest-*magnitude* Hessian eigenvalue must be negative
    (convex across the ridge) and the along-ridge curvature must be smaller:

        evid = |lambda_big| * (1 - |lambda_small| / |lambda_big|)   if lambda_big < 0 else 0

    Two defects this replaces are worth naming, because the first version shipped them:
    (1) the criterion was applied to the algebraically larger eigenvalue instead of the
    largest-magnitude one, so a bright ridge scored zero whenever the along-strike curvature
    happened to be positive -- the field came back all zeros on real shorelines;
    (2) the strike was read from the Hessian eigenvector, which is noisy on a 25 m DEM.

    The strike is instead taken from the smoothed elevation gradient: at a scarp the gradient
    points down the step, so the strike is perpendicular to it -- the geomorphic definition,
    and far more stable than the eigenvector.
    """
    evidence: np.ndarray
    strike_deg: np.ndarray
    res: float

    @classmethod
    def from_dem(cls, z: np.ndarray, res: float, *, sigma_m: float = 75.0,
                 sigma_strike_m: float = 150.0):
        dzdx, dzdy = gradient(z, res)
        gn = ndimage.gaussian_filter(np.hypot(dzdx, dzdy), sigma_m / res)
        s = sigma_m / res
        hxx = ndimage.gaussian_filter(gn, s, order=(2, 0), mode="nearest")
        hyy = ndimage.gaussian_filter(gn, s, order=(0, 2), mode="nearest")
        hxy = ndimage.gaussian_filter(gn, s, order=(1, 1), mode="nearest")
        tmp = np.hypot(hxx - hyy, 2 * hxy)
        l_max = 0.5 * (hxx + hyy + tmp)      # algebraically larger eigenvalue
        l_min = 0.5 * (hxx + hyy - tmp)      # algebraically smaller eigenvalue
        use_max = np.abs(l_max) >= np.abs(l_min)
        big = np.where(use_max, l_max, l_min)
        small = np.where(use_max, l_min, l_max)
        ridge = np.where(big < 0.0,
                         np.abs(big) * (1.0 - np.minimum(np.abs(small) / (np.abs(big) + 1e-9), 1.0)),
                         0.0)
        scale = np.percentile(ridge, 99.5)
        ev = np.clip(ridge / (scale if scale > 0 else 1.0), 0.0, 1.0).astype(np.float32)
        gx = ndimage.gaussian_filter(dzdx, sigma_strike_m / res)
        gy = ndimage.gaussian_filter(dzdy, sigma_strike_m / res)
        mag = np.hypot(gx, gy)
        # IR-62-J-02 FIX (2026-10-12): `gy` from ``gradient`` is -dz/dy, so the ascent is
        # (gx, -gy) and the along-strike perpendicular is (gy, gx).  The shipped version used
        # (-gy, gx), which reflects the strike about the E-W axis (azimuth -> 180 - azimuth):
        # a NW-striking trace was walked at its NE mirror image.  Regression test:
        # tests/test_geom_axes.py::test_scarpfield_strike_matches_the_true_line.
        te = np.where(mag > 0, gy / np.maximum(mag, 1e-9), 0.0)    # along-strike (east component)
        tn = np.where(mag > 0, gx / np.maximum(mag, 1e-9), 1.0)    # along-strike (north component)
        strike = np.degrees(np.arctan2(te, tn)) % 180.0
        return cls(evidence=ev, strike_deg=strike.astype(np.float32), res=res)

    def sample(self, row: float, col: float, field: np.ndarray) -> float:
        r = np.clip(row, 0, field.shape[0] - 1.001); c = np.clip(col, 0, field.shape[1] - 1.001)
        r0, c0 = int(np.floor(r)), int(np.floor(c))
        fr, fc = r - r0, c - c0
        v = (field[r0, c0] * (1 - fr) * (1 - fc) + field[r0 + 1, c0] * fr * (1 - fc)
             + field[r0, c0 + 1] * (1 - fr) * fc + field[r0 + 1, c0 + 1] * fr * fc)
        return float(v)


def step_rc(azimuth_deg: float, step_px: float) -> tuple[float, float]:
    """Convert a compass azimuth (deg from north, clockwise) into a (drow, dcol) step.

    This mapping is where the first version of this tracker was wrong: it used
    (row += step*sin, col += step*cos), which is neither the compass convention nor the
    row/col convention -- it rotated the heading by 90 deg and flipped the north sign, so the
    walk ran *across* the scarp instead of along it and every trace died at the first step.
    """
    th = np.radians(azimuth_deg)
    return -step_px * np.cos(th), step_px * np.sin(th)


def trace_from_seed(scarp: ScarpField, seed_rowcol: tuple[float, float], *,
                    step_m: float = 200.0, max_len_m: float = 15000.0,
                    min_evidence: float = 0.22, max_turn_deg: float = 25.0,
                    min_mean_evidence: float = 0.15) -> list[tuple[float, float]]:
    """Walk a trace outward from a seed while oriented DEM ridge evidence supports it.

    The walk keeps a heading, tries small heading changes, and accepts the one whose path has
    the highest mean scarp evidence; it stops as soon as the best available continuation falls
    below `min_evidence`.  This is the "extend it while DEM-ridge evidence supports it" clause
    of the lane, made explicit and reproducible.
    """
    res = scarp.res
    step_px = step_m / res
    out: dict[int, list[tuple[float, float]]] = {+1: [], -1: []}
    for sgn in (+1, -1):
        r, c = seed_rowcol
        base = float(scarp.sample(r, c, scarp.strike_deg))
        heading = base if sgn > 0 else (base + 180.0) % 360.0
        path: list[tuple[float, float]] = []
        for _ in range(int(max_len_m / step_m)):
            best = None
            for ddeg in (-max_turn_deg, -0.5 * max_turn_deg, 0.0, 0.5 * max_turn_deg, max_turn_deg):
                h = heading + ddeg
                rr, cc = step_rc(h, step_px)
                nr, nc = r + rr, c + cc
                if not (0 <= nr < scarp.evidence.shape[0] and 0 <= nc < scarp.evidence.shape[1]):
                    continue
                # sample the whole candidate segment: a real scarp is continuous, and this is
                # what stops the walk hopping between parallel lineaments
                vals = [scarp.sample(r + t * rr, c + t * cc, scarp.evidence)
                        for t in (0.25, 0.5, 0.75, 1.0)]
                score = float(np.mean(vals))
                if best is None or score > best[0]:
                    best = (score, h, nr, nc)
            if best is None or best[0] < min_evidence:
                break
            _, heading, r, c = best
            path.append((float(r), float(c)))
        if path and float(np.mean([scarp.sample(*q, scarp.evidence) for q in path])) < min_mean_evidence:
            path = []
        out[sgn] = path
    return out[-1][::-1] + [tuple(seed_rowcol)] + out[+1]


# ---------------------------------------------------------------------------------------------
# 5. dotted emission on the 100 m competition grid
# ---------------------------------------------------------------------------------------------
def emit_dots(traces_rc: list[dict], dem_transform, *, catalogue: np.ndarray,
              footprint: np.ndarray, spacing_px: float = 2.8, value: float = 1.0,
              min_catalogue_px: float = 1.0, max_dots: int = 12000):
    """Rasterise traces as a dotted line on the official 100 m grid.

    Spacing default 2.8 px = 280 m: every point of a continuous trace is then within 1.4 px
    (140 m) of an emitted dot, i.e. inside the triangular kernel's support (3 px), while the
    emitted mass stays low -- the metric charges 0.2 per unit of mass, so a dot pays for itself
    only if its realised kernel weight exceeds 0.2*DTI (derivation in metric.marginal_bar).

    Dots are deleted within `min_catalogue_px` cells of the already-known catalogue, because
    known USGS/INGENIOUS pixels are masked out of scoring (organizer clarification, forum
    thread 11516) and mass spent there earns nothing.  Set to 0 to keep them.

    `traces_rc` is a list of dicts with keys rowcol (list of (row, col) in the DEM grid),
    seed_rc, evidence (mean scarp evidence), loci (list of flagged stations).
    """
    H, W = catalogue.shape
    grid = np.zeros((H, W), dtype=np.float32)
    cat_dist_px = ndimage.distance_transform_edt(~catalogue) if min_catalogue_px > 0 else None
    summary: list[dict] = []
    total = 0
    for ti, tr in enumerate(traces_rc):
        pts = np.array(tr["rowcol"], dtype=np.float64)
        if len(pts) < 2:
            continue
        xs = dem_transform.c + (pts[:, 1] + 0.5) * dem_transform.a
        ys = dem_transform.f + (pts[:, 0] + 0.5) * dem_transform.e
        seg = np.hypot(np.diff(xs), np.diff(ys))
        s = np.concatenate([[0.0], np.cumsum(seg)])
        if s[-1] < 400.0:
            continue
        spacing_m = spacing_px * 100.0
        ss = np.arange(0.0, s[-1] + 1e-9, spacing_m)
        if ss.size < 2:
            continue
        xi = np.interp(ss, s, xs); yi = np.interp(ss, s, ys)
        # competition grid: origin (243350, 4508550), 100 m, north-up.  Computed directly rather
        # than through rasterio.transform.rowcol, whose signature expects an Affine object (a
        # plain tuple silently selects the GCP transformer and raises).
        cc = np.floor((xi - 243350.0) / 100.0).astype(int)
        rr = np.floor((4508550.0 - yi) / 100.0).astype(int)
        placed = 0
        dropped_cat = 0
        dropped_off = 0
        for r, c in zip(np.atleast_1d(rr), np.atleast_1d(cc)):
            if not (0 <= r < H and 0 <= c < W):
                dropped_off += 1
                continue
            if not footprint[r, c]:
                dropped_off += 1
                continue
            if cat_dist_px is not None and cat_dist_px[r, c] < min_catalogue_px:
                dropped_cat += 1
                continue
            if grid[r, c] > 0:
                continue
            grid[r, c] = value
            placed += 1
            total += 1
            if total >= max_dots:
                break
        summary.append(dict(trace=int(ti), dots=int(placed), length_m=float(s[-1]),
                            dropped_catalogue=int(dropped_cat), dropped_off_footprint=int(dropped_off),
                            evidence=float(tr.get("evidence", float("nan"))),
                            n_loci=len(tr.get("loci", []))))
        if total >= max_dots:
            break
    return grid, summary


# ---------------------------------------------------------------------------------------------
# 2b. datum-step loci: the lane's core signal, computed on the isobase residual
# ---------------------------------------------------------------------------------------------
def frangi_ridge(field: np.ndarray, res: float, *, sigma_m: float = 75.0):
    """Bright-ridge score + local strike for an arbitrary scalar field (Frangi criterion).

    Used twice in this repository, on purpose: once on |grad z| (a *DEM* step, i.e. any scarp)
    and once on |grad r| where r = z - isobase (a *datum* step, i.e. specifically a shoreline
    that is no longer level).  The difference between those two fields is the scientific content
    of the lane: the first is "there is a scarp here", the second is "the pluvial datum is
    offset here", and the second is what a fault cutting a 15 ka shoreline produces.
    """
    s = sigma_m / res
    hxx = ndimage.gaussian_filter(field, s, order=(2, 0), mode="nearest")
    hyy = ndimage.gaussian_filter(field, s, order=(0, 2), mode="nearest")
    hxy = ndimage.gaussian_filter(field, s, order=(1, 1), mode="nearest")
    tmp = np.hypot(hxx - hyy, 2 * hxy)
    l_max = 0.5 * (hxx + hyy + tmp)
    l_min = 0.5 * (hxx + hyy - tmp)
    use_max = np.abs(l_max) >= np.abs(l_min)
    big = np.where(use_max, l_max, l_min)
    small = np.where(use_max, l_min, l_max)
    ridge = np.where(big < 0.0,
                     np.abs(big) * (1.0 - np.minimum(np.abs(small) / (np.abs(big) + 1e-9), 1.0)),
                     0.0)
    scale = np.percentile(ridge, 99.5)
    return (np.clip(ridge / (scale if scale > 0 else 1.0), 0.0, 1.0).astype(np.float32),
            (big / (np.abs(big) + 1e-12)).astype(np.float32))


# ---------------------------------------------------------------------------------------------
# 2c. the datum-doublet surfaces -- the lane's measurement, in one shared, axis-tested place
# ---------------------------------------------------------------------------------------------
def doublet_surfaces(z: np.ndarray, isobase: np.ndarray, bench_score: np.ndarray, res: float, *,
                     smooth_m: float = 120.0, scarp_sigma_m: float = 100.0,
                     offset_half_m: float = 250.0, min_step_m: float = 2.0,
                     flank_tol_m: float = 6.0, corr_sigma_m: float = 300.0,
                     min_corr: float = 0.0, max_shore_distance_m: float = 1500.0,
                     min_cross_angle_deg: float = 30.0, excess_step: bool = True,
                     legacy_axis_swap: bool = False) -> dict:
    """Per-pixel fields for "the pluvial datum is offset here", on any array (block-callable).

    ``r = z - isobase`` is the datum residual; a fault that displaces the shoreline steps ``r``
    across its own trace.  Everything measured is a property of ``|grad r|``:

    ``evid``        Frangi bright-ridge score of ``|grad r|`` (a *line*, not a blob);
    ``step``        ``|r| +h along the ascent  -  r| -h``  with h = ``offset_half_m``;
    ``doublet_ok``  BOTH flanks sit on the datum (``|r| <= flank_tol_m``) -- the paired-bench
                    test: a step *between two benches of the same isobase height* is a displaced
                    shoreline, a step into empty air is a scarp of any origin;
    ``corr``        local shape agreement of the two flanks over a ``corr_sigma_m`` window:
                    ``corr(A, B)`` of the two sampled residual fields.  A fault leaves the bench
                    tread intact on both sides (high corr); a landslide headwall or an erosional
                    riser does not;
    ``cross_deg``   angle between the step trace and the local isobase CONTOUR: >= 30 deg
                    rejects the level-feature family (berms, bluffs, fan-head risers);
    ``shore_dist``  distance to the nearest bench pixel, i.e. the lane's honest coverage mask.

    Axis conventions live in ``gems62.geom`` (IR-62-J-01).  ``legacy_axis_swap=True`` reproduces
    the pre-fix mapping, which measured the offset ALONG the scarp for N-S and E-W structures;
    it exists only so the shipped v8 receipt stays reproducible.
    """
    from . import geom

    z = np.asarray(z, np.float32)
    finite = np.isfinite(z) & np.isfinite(isobase)
    r = np.where(finite, z - isobase, np.float32(np.nan)).astype(np.float32)
    r0 = np.nan_to_num(r, nan=0.0)
    r_s = ndimage.gaussian_filter(r0, smooth_m / res, mode="nearest")
    if legacy_axis_swap:
        gx, gy = gradient(r_s, res)
        m = np.hypot(gx, gy) + 1e-12
        u_row, u_col = (gx / m).astype(np.float32), (gy / m).astype(np.float32)
    else:
        dzdr, dzdc = geom.grad_arr(r_s, res)
        u_row, u_col = geom.unit_ascent(dzdr, dzdc)
    mag = np.hypot(dzdr if not legacy_axis_swap else gx,
                   dzdc if not legacy_axis_swap else gy).astype(np.float32)
    evid, _ = frangi_ridge(mag, res, sigma_m=scarp_sigma_m)
    a_f, b_f = geom.offset_pair(r0, u_row, u_col, offset_half_m, res)
    step_raw = np.abs(a_f - b_f).astype(np.float32)
    # Excess-step refinement: `step` also picks up whatever the ISOBASE itself changes across the
    # 2h sampling baseline.  In a warped datum -- up to ~22 m over 300 km for the Lahontan
    # highstand (Adams, Wesnousky & Bills 1999) -- a steep local isobase gradient can manufacture
    # a "step" of several metres on terrain that is perfectly level relative to its own datum.
    # So the step is measured against the isobase's own jump over the same baseline, and only the
    # EXCESS is a datum offset.  Without this, `min_step_m` is a function of the fit's slope.
    ia_f, ib_f = geom.offset_pair(np.nan_to_num(np.asarray(isobase, np.float32), nan=0.0),
                                 u_row, u_col, offset_half_m, res)
    iso_step = np.abs(ia_f - ib_f).astype(np.float32)
    step = (np.maximum(step_raw - iso_step, 0.0) if excess_step else step_raw).astype(np.float32)
    doublet_ok = (np.abs(a_f) <= flank_tol_m) & (np.abs(b_f) <= flank_tol_m) & finite
    if min_corr > 0.0:
        sa = ndimage.gaussian_filter(a_f, corr_sigma_m / res, mode="nearest")
        sb = ndimage.gaussian_filter(b_f, corr_sigma_m / res, mode="nearest")
        cov = (ndimage.gaussian_filter(a_f * b_f, corr_sigma_m / res, mode="nearest") - sa * sb)
        va = (ndimage.gaussian_filter(a_f * a_f, corr_sigma_m / res, mode="nearest") - sa * sa)
        vb = (ndimage.gaussian_filter(b_f * b_f, corr_sigma_m / res, mode="nearest") - sb * sb)
        corr = (cov / np.sqrt(np.maximum(va, 0) * np.maximum(vb, 0) + 1e-12)).astype(np.float32)
    else:
        corr = np.ones_like(step)
    # strike of the step trace = perpendicular to the ascent direction, in compass degrees
    az_step = geom.strike_azimuth_from_ascent(geom.azimuth_from_drc(u_row, u_col)).astype(np.float32)
    ib = np.nan_to_num(np.asarray(isobase, np.float32), nan=0.0)
    ibr = ndimage.gaussian_filter(ib, scarp_sigma_m / res, mode="nearest")
    if legacy_axis_swap:
        igx, igy = gradient(ibr, res)
        az_cont = ((np.degrees(np.arctan2(igx, igy)) % 180.0)).astype(np.float32)
    else:
        ihr, ihc = geom.grad_arr(ibr, res)
        az_cont = geom.azimuth_from_drc(ihr, ihc).astype(np.float32)
        az_cont = (az_cont + 90.0) % 180.0                  # contour = perpendicular to its ascent
    d_az = np.abs(az_step - az_cont) % 180.0
    cross_deg = np.where(d_az > 90.0, 180.0 - d_az, d_az).astype(np.float32)
    bench = np.asarray(bench_score) >= 0.25
    if bench.any():
        d_shore = (ndimage.distance_transform_edt(~bench) * res).astype(np.float32)
    else:
        d_shore = np.full(z.shape, np.inf, np.float32)
    gates = ((step >= min_step_m) & doublet_ok & (corr >= min_corr)
             & (d_shore <= max_shore_distance_m) & (cross_deg >= min_cross_angle_deg) & finite)
    return dict(residual=r, evid=evid, step=step, step_raw=step_raw, iso_step=iso_step,
                flank_plus=a_f, flank_minus=b_f,
                doublet_ok=doublet_ok, corr=corr, az_step=az_step, cross_deg=cross_deg,
                shore_distance=d_shore, gates=gates,
                score=(evid * np.clip(step / (2.0 * min_step_m), 0.0, 1.0)
                       * np.clip(corr, 0.0, 1.0)).astype(np.float32))


def datum_step_loci(z: np.ndarray, isobase: np.ndarray, bench_score: np.ndarray, res: float, *,
                    smooth_m: float = 120.0, scarp_sigma_m: float = 100.0,
                    offset_half_m: float = 250.0, min_step_m: float = 2.0,
                    min_datum_evidence: float = 0.10, max_shore_distance_m: float = 1500.0,
                    suppression_m: float = 2000.0, max_loci: int = 300,
                    stride_m: float = 50.0, min_cross_angle_deg: float = 30.0,
                    flank_tol_m: float = 1e9, min_corr: float = 0.0, excess_step: bool = True,
                    legacy_axis_swap: bool = True) -> dict:
    """Find places where the *pluvial datum* steps, using the isobase residual.

    r(x) = z(x) - isobase(x) is how far the local bench sits above/below the smooth datum.  A
    fault that displaces a shoreline makes r jump across its trace, i.e. |grad r| has a ridge
    there -- so we score the Frangi ridge of |grad r|, measure the actual offset by differencing
    r half a kernel either side of that ridge, and keep only loci that are (a) strongly ridged,
    (b) offset by at least `min_step_m`, and (c) inside the pluvial margin, i.e. within
    `max_shore_distance_m` of a shoreline bench pixel.

    Gates (c) is what keeps this lane honest about its coverage: the detector is not allowed to
    wander into terrain where there is no pluvial datum to be offset.

    Gate (d) is the *geomorphological* discriminator, and it is the reason the first version of
    this detector lit up every range front in the basin.  A step whose trace runs parallel to the
    local isobase contours is a *level* feature -- a fan-head riser, a wave-cut bluff, a beach
    berm, the edge of a terrace -- because "contour-parallel" is exactly what "constant
    elevation" means.  A tectonic scarp is a step in *height across its own trace*: it cuts
    across the topography and therefore crosses contours.  So we keep steps that cross contours
    at more than `min_cross_angle_deg` and drop the contour-parallel family.
    """
    # IR-62-J-01 (2026-10-12): the measurement below used to be written inline with the east
    # gradient component driving the ROW shift and the (sign-flipped) north component driving
    # the COLUMN shift, i.e. an axis swap that reflects the sampling direction about the NE-SW
    # diagonal.  For a scarp striking N-S or E-W the sampled direction was ALONG the scarp, so
    # the measured offset collapsed to ~0 and the detector was structurally blind to those
    # strikes.  The geometry now lives in ``doublet_surfaces``/``gems62.geom`` (one convention,
    # unit-tested).  ``legacy_axis_swap=True`` reproduces the pre-fix mapping so the shipped v8
    # receipt stays reproducible; new runs should pass False.
    su = doublet_surfaces(z, isobase, bench_score, res, smooth_m=smooth_m,
                          scarp_sigma_m=scarp_sigma_m, offset_half_m=offset_half_m,
                          min_step_m=min_step_m, flank_tol_m=flank_tol_m, min_corr=min_corr,
                          max_shore_distance_m=max_shore_distance_m,
                          min_cross_angle_deg=min_cross_angle_deg,
                          excess_step=excess_step, legacy_axis_swap=legacy_axis_swap)
    r = su["residual"]
    if not np.isfinite(r).any():
        return dict(loci=[], evidence=np.zeros_like(z, np.float32))
    evid = su["evid"]
    step = su["step"]
    cross_deg = su["cross_deg"]
    d_shore = su["shore_distance"]
    if legacy_axis_swap:                      # v8 gate: ridge evidence + step + shore proximity
        cand = ((evid >= min_datum_evidence) & (step >= min_step_m)
                & (d_shore <= max_shore_distance_m) & (cross_deg >= min_cross_angle_deg)
                & np.isfinite(r))
    else:
        cand = su["gates"] & (evid >= min_datum_evidence)
    az_step = su["az_step"]
    score = np.where(cand, evid * np.clip(step / (2.0 * min_step_m), 0.0, 3.0), 0.0)
    sup = int(round(suppression_m / res))
    work = np.where(cand, score, 0.0).copy()
    loci = []
    for _ in range(max_loci):
        k = int(np.argmax(work))
        if work.flat[k] <= 0:
            break
        i, j = np.unravel_index(k, work.shape)
        loci.append(dict(row=float(i), col=float(j), score=float(score[i, j]),
                         datum_evidence=float(evid[i, j]), step_m=float(step[i, j]),
                         shore_distance_m=float(d_shore[i, j]),
                         cross_angle_deg=float(cross_deg[i, j]),
                         strike_deg=float(az_step[i, j])))
        i0 = max(0, i - sup); i1 = min(work.shape[0], i + sup + 1)
        j0 = max(0, j - sup); j1 = min(work.shape[1], j + sup + 1)
        work[i0:i1, j0:j1] = 0.0
    return dict(loci=loci, evidence=evid, step=step.astype(np.float32),
                shore_distance=d_shore.astype(np.float32))


def isobase_quadratic(x: np.ndarray, y: np.ndarray, z: np.ndarray, *, iters: int = 12,
                      huber_k: float = 2.0, bounds_km: float = 200.0) -> dict:
    """Robust low-order isobase fit -- the "smooth isobase, allowing for isostatic rebound".

    Post-pluvial rebound in the Lahontan basin is a long-wavelength warp (tens of metres over
    a hundred kilometres).  A 6-term quadratic in (x, y) is therefore the physically right
    order: it can absorb the rebound dome and the regional tilt, but it *cannot* follow the
    local slope of an alluvial-fan apron, a debris-flow lobe or a fault scarp.  That selectivity
    is the entire point -- an isobase re-fitted on a short length scale is free to chase whatever
    surface it is shown, which is why the first version of this pipeline fired on every range
    front in the basin (flat piedmont + riser = "bench" to a local detector).

    IRLS with Huber weights keeps a minority of true bench pixels from being dragged by the
    (much more numerous) fan-apron and playa-margin pixels.

    Returns dict(coeffs, predict(x, y), rmad) where rmad is the robust spread of the residual.
    """
    x = np.asarray(x, float) / 1000.0        # km
    y = np.asarray(y, float) / 1000.0
    xc = x - float(np.median(x)); yc = y - float(np.median(y))
    if float(np.nanmax(np.hypot(xc, yc))) > bounds_km:
        pass                                  # no hard clamp; the caller decides on extent
    A = np.stack([np.ones_like(xc), xc, yc, xc * xc, xc * yc, yc * yc], axis=1)
    w = np.ones_like(x)
    coef = np.zeros(6)
    for _ in range(iters):
        Aw = A * w[:, None]
        coef, *_ = np.linalg.lstsq(Aw, z * w, rcond=None)
        resid = z - A @ coef
        sigma = 1.4826 * float(np.median(np.abs(resid - np.median(resid)))) + 1e-6
        w = np.where(np.abs(resid) <= huber_k * sigma, 1.0, (huber_k * sigma) / np.abs(resid))
    resid = z - A @ coef
    return dict(coeffs=coef, x_centre=float(np.median(x)) * 1000.0,
                y_centre=float(np.median(y)) * 1000.0,
                rmad=1.4826 * float(np.median(np.abs(resid - np.median(resid)))),
                n=int(z.size), resid=resid)

def isobase_eval(fit: dict, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Evaluate a fit from `isobase_quadratic` at UTM coordinates (metres)."""
    xc = (np.asarray(x, float) - fit["x_centre"]) / 1000.0
    yc = (np.asarray(y, float) - fit["y_centre"]) / 1000.0
    c = fit["coeffs"]
    return c[0] + c[1] * xc + c[2] * yc + c[3] * xc * xc + c[4] * xc * yc + c[5] * yc * yc
