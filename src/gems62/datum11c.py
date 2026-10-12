"""Multi-datum corroborated step detection on Lake Lahontan shorelines.

This is the **datum-offset lane** (``PROMPT.md`` Part 1), rebuilt around one physical
idea that the earlier lane sessions in this repository did not use: *the Lahontan basin
does not have one level datum, it has several*, and a fault offsets all of them at the
same map location, while every non-tectonic confuser (delta, spit, landslide, eolian
dune, a single stillstand's wave-cut notch) offsets only one.

Verified published datums used here -- literature values, never fitted numbers:

===================  ============================   ==================================================
datum                published elevation (m)      source
===================  ============================   ==================================================
Sehoo highstand      1318.4 - 1340.8 (mean 1331.46) Adams, Wesnousky & Bills 1999, GSA Bull. 111;
                                                    Bills, Adams & Wesnousky 2007, JGR 112
  Jessup embayment    1338.5 - 1339.0               Adams & Wesnousky 1998, GSA Bull. 110, 1318-1332
Younger Dryas ~12 ka 1225 - 1235                    Benson et al. 1997; Briggs et al. 2005, Quat. Res. 64
post-highstand rise  1231                           Briggs, Wesnousky & Adams 2005, Quat. Res. 64
late Holocene        1198 - 1210 (1204)             Adams 2003, in Adams et al. 2008, Geoarchaeology 23
===================  ============================   ==================================================

The **detection floor is published, not assumed**: the elevation of the high shoreline is
resolved to about 3 m over a broad area, and "almost all of the post-Sehoo vertical
displacements ... are less than or equal to about 3 m" (Adams, Wesnousky & Bills 1999).
A single-strand detector therefore lives at the noise floor; requiring the *same* step on
two independent datums is what buys signal-to-noise back, and the amplitude bar here is
1.5 m -- *below* the literature floor -- precisely because corroboration, not amplitude,
is the discriminator.

Pipeline
--------
1. :func:`datum_residual` -- local isobase per datum by large-sigma masked smoothing of
   that datum's own cells.  Absorbs the rebound dome (~22 m, wavelength 100-200 km) and
   the regional tilt without a parametric model.
2. :func:`offset_map` -- oriented, multi-scale two-sample step field on the residual: for
   azimuth ``theta`` and offsets of 300/500/700 m, the residual ``r`` sampled at ``+n``
   minus ``r`` sampled at ``-n``, standardised by the local scatter.  ``theta`` is the
   *fault strike* (the normal is the offset direction).
3. :func:`loci_from_map` -- threshold and cluster into candidate loci.
4. :func:`corroborate_loci` -- keep a locus only if an independent datum carries a locus
   **collinear with it along the strike**.  A fault is a line, so collinearity -- not a
   flat radius -- is the right geometry, and it is simultaneously more sensitive and more
   specific.
5. :func:`extend_straight` -- march the trace from the seed with a bounded turn rate along
   DEM structure-tensor ridge evidence.

Emission reuses :mod:`gems62.emit` (unit dots, catalogue exclusion, minimum separation)
and the writer/validator are the shared ones.  Nothing here is a score: every emitted
number is MEASURED (reproducible from pinned bytes) or MODEL (algebra, labelled).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

from .grid import PIXEL_M

# --------------------------------------------------------------------------- constants
#: Published datum windows (m asl). SEARCH WINDOWS ONLY -- never an input to a fit.
DATUMS: dict[str, tuple[float, float]] = {
    "sehoo_highstand": (1313.0, 1348.0),
    "younger_dryas": (1222.0, 1242.0),
    "late_holocene": (1196.0, 1212.0),
}

#: Isobase (rebound + regional tilt) smoothing, in 100 m cells (~9 km half-width).
ISOBASE_SIGMA_PX = 90.0

#: Oriented step field.
STEP_ANGLES_DEG: tuple[int, ...] = tuple(range(0, 180, 15))
STEP_OFFSETS_PX: tuple[int, ...] = (3, 5, 7)
STEP_LOCAL_SIGMA_PX = 15

#: Cross-datum corroboration geometry.
CORROB_MAX_SEP_M = 12000.0
CORROB_MIN_SEP_M = 400.0
CORROB_ALONG_STRIKE_DEG = 30.0
CORROB_AMP_RATIO_MAX = 3.0

#: Trace extension.
EXT_MAX_LENGTH_M = 12000.0
EXT_STEP_M = 300.0
EXT_MAX_TURN_DEG = 12.0
EXT_COH_MIN = 0.10
EXT_RELIEF_MIN_M = 2.0


# --------------------------------------------------------------------------- helpers
def _axis_delta(a: float, b: float) -> float:
    """Smallest angle between two axial (180 deg ambiguous) directions, in degrees."""
    return abs(((a - b) + 90.0) % 180.0 - 90.0)


def horn_slope(z: np.ndarray, cell: float = PIXEL_M) -> np.ndarray:
    """Horn (1981) 3x3 slope as tan(slope)."""
    p = np.pad(z, 1, mode="edge")
    a, b, c = p[0:-2, 0:-2], p[0:-2, 1:-1], p[0:-2, 2:]
    d, f = p[1:-1, 0:-2], p[1:-1, 2:]
    g, h, i = p[2:, 0:-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8.0 * cell)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8.0 * cell)
    return np.hypot(dzdx, dzdy)


# --------------------------------------------------------------------------- isobase
def datum_residual(z: np.ndarray, footprint: np.ndarray, datum_cells: np.ndarray,
                   *, sigma_px: float = ISOBASE_SIGMA_PX) -> np.ndarray:
    """``r = z - isobase``, isobase = masked large-sigma smooth of this datum's cells.

    The smooth absorbs isostatic rebound (a dome, amplitude up to ~22 m, wavelength
    100-200 km) and the regional tilt.  What is left is the departure of the datum from
    its own regional trend -- the strain measurement.  NaN where the datum is absent.
    """
    m = datum_cells & footprint & np.isfinite(z)
    if not m.any():
        return np.full(z.shape, np.nan, dtype=np.float32)
    zf = np.where(m, z, 0.0)
    w = ndi.gaussian_filter(m.astype(np.float64), sigma_px)
    num = ndi.gaussian_filter(zf, sigma_px)
    with np.errstate(invalid="ignore", divide="ignore"):
        isobase = np.where(w > 1e-6, num / np.maximum(w, 1e-12), np.nan)
    return np.where(m, z - isobase, np.nan).astype(np.float32)


# --------------------------------------------------------------------------- step field
def _shift2d(arr: np.ndarray, dr: int, dc: int) -> np.ndarray:
    """``arr[y + dr, x + dc]`` sampled at ``(y, x)``; NaN outside the grid."""
    out = np.full(arr.shape, np.nan, dtype=np.float32)
    h, w = arr.shape
    r0, r1 = max(0, -dr), min(h, h - dr)
    c0, c1 = max(0, -dc), min(w, w - dc)
    if r0 < r1 and c0 < c1:
        out[r0:r1, c0:c1] = arr[r0 + dr:r1 + dr, c0 + dc:c1 + dc]
    return out


def offset_map(
    residual: np.ndarray,
    active: np.ndarray,
    *,
    angles_deg: tuple[int, ...] = STEP_ANGLES_DEG,
    offsets_px: tuple[int, ...] = STEP_OFFSETS_PX,
    local_sigma_px: int = STEP_LOCAL_SIGMA_PX,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Oriented multi-scale step field on the datum residual.

    For azimuth ``theta`` and offset ``L`` the raw step is ``r(p + L*n) - r(p - L*n)``
    where ``n = (cos theta, -sin theta)`` is the **normal** to the fault, so ``theta`` is
    the fault's own strike.  Averaging the three offsets is the multi-scale part: a fault
    displaces the datum on both sides, so the difference is large and nearly constant
    across scales, whereas the rebound trend and surface roughness average down.

    Returns ``(best_z, best_abs_m, best_theta_deg, signed_m)``; the first three are NaN
    where the datum is absent or the local scatter is undefined.
    """
    r = np.asarray(residual, dtype=np.float32)
    act = np.asarray(active, bool)
    m = np.isfinite(r) & act
    num = ndi.uniform_filter(np.where(m, r, 0.0), size=local_sigma_px)
    cnt = ndi.uniform_filter(m.astype(np.float32), size=local_sigma_px)
    sq = ndi.uniform_filter(np.where(m, r * r, 0.0), size=local_sigma_px)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = np.where(cnt > 0.05, num / np.maximum(cnt, 1e-6), np.nan)
        var = np.where(cnt > 0.05, sq / np.maximum(cnt, 1e-6) - mu * mu, np.nan)
    sigma = np.sqrt(np.maximum(var, 0.0)).astype(np.float32)

    shape = r.shape
    best_z = np.full(shape, np.nan, dtype=np.float32)
    best_a = np.full(shape, np.nan, dtype=np.float32)
    best_t = np.full(shape, np.nan, dtype=np.float32)
    best_s = np.full(shape, np.nan, dtype=np.float32)
    for theta in angles_deg:
        t = np.radians(float(theta))
        nx, ny = np.cos(t), -np.sin(t)
        acc = np.zeros(shape, dtype=np.float32)
        good = np.zeros(shape, dtype=np.float32)
        for L in offsets_px:
            dr = int(round(-ny * L))          # image rows increase southwards
            dc = int(round(nx * L))
            if dr == 0 and dc == 0:
                continue
            d = _shift2d(r, dr, dc) - _shift2d(r, -dr, -dc)
            fin = np.isfinite(d)
            acc = acc + np.where(fin, d, np.float32(0.0))
            good = good + fin.astype(np.float32)
        with np.errstate(invalid="ignore", divide="ignore"):
            s = np.where(good > 0, acc / np.maximum(good, 1.0), np.nan)
        se = sigma * np.sqrt(2.0 / np.maximum(good, 1.0))
        z = np.where(m & (good > 0), np.abs(s) / np.maximum(se, 1e-6), np.nan)
        upd = np.isfinite(z) & (~np.isfinite(best_z) | (z > best_z))
        best_z = np.where(upd, z, best_z)
        best_a = np.where(upd, np.abs(s).astype(np.float32), best_a)
        best_s = np.where(upd, s.astype(np.float32), best_s)
        best_t = np.where(upd, np.float32(theta), best_t)
    return best_z, best_a, best_t, best_s


# --------------------------------------------------------------------------- loci
@dataclass
class Locus:
    """One clustered candidate datum-offset location, from one datum."""

    datum: str
    x: float
    y: float
    strike_deg: float
    step_m: float
    signed_m: float
    z_stat: float
    n_cells: int
    corroborated_by: list[str] = field(default_factory=list)

    @property
    def strength(self) -> float:
        """Ranking key: how significant, how large, and how many cells agree."""
        return float(self.z_stat) * float(self.step_m) ** 0.5 * float(self.n_cells) ** 0.5


def loci_from_map(
    name: str,
    z: np.ndarray,
    amp: np.ndarray,
    theta: np.ndarray,
    signed: np.ndarray,
    *,
    transform: tuple[float, float, float, float, float, float] = (100.0, 0.0, 243350.0,
                                                                 0.0, -100.0, 4508550.0),
    z_min: float = 3.6,
    amp_min: float = 1.5,
    min_cells: int = 2,
    merge_radius_px: int = 5,
) -> list[Locus]:
    """Threshold the step field and reduce each cluster to one candidate locus."""
    good = np.isfinite(z) & (z >= z_min) & (amp >= amp_min)
    if not good.any():
        return []
    grown = ndi.binary_dilation(
        good, structure=np.ones((2 * merge_radius_px + 1, 2 * merge_radius_px + 1), bool))
    lab, _ = ndi.label(grown, structure=ndi.generate_binary_structure(2, 2))
    a, b, c, d, e, f = transform
    out: list[Locus] = []
    for sl in ndi.find_objects(lab):
        if sl is None:
            continue
        sub = good[sl]
        n = int(sub.sum())
        if n < min_cells:
            continue
        rr, cc = np.nonzero(sub)
        rr = rr + sl[0].start
        cc = cc + sl[1].start
        ang = np.radians(2.0 * theta[rr, cc])
        mean2 = float(np.arctan2(np.sin(ang).mean(), np.cos(ang).mean()))
        strike = float((0.5 * np.degrees(mean2)) % 180.0)
        out.append(Locus(datum=name,
                         x=a * float(cc.mean()) + c,
                         y=f + e * float(rr.mean()),
                         strike_deg=strike,
                         step_m=float(np.mean(amp[rr, cc])),
                         signed_m=float(np.mean(signed[rr, cc])),
                         z_stat=float(np.mean(z[rr, cc])),
                         n_cells=n))
    return out


def corroborate_loci(
    loci: list[Locus],
    *,
    max_separation_m: float = CORROB_MAX_SEP_M,
    min_separation_m: float = CORROB_MIN_SEP_M,
    along_strike_tol_deg: float = CORROB_ALONG_STRIKE_DEG,
    amp_ratio_max: float = CORROB_AMP_RATIO_MAX,
) -> list[Locus]:
    """Keep loci that an independent datum reproduces **on the same line**.

    A fault is a *line*, so two step loci produced by one fault are separated *along the
    strike*.  The test is therefore collinearity, not proximity: the bearing from this
    locus to the candidate corroborator must lie within ``along_strike_tol_deg`` of the
    strike, and the corroborator's own strike must agree with it too.  Collinearity is
    more sensitive than a flat radius (it survives a wide ribbon offset between two
    datums 100 m apart in elevation) and more specific (an unrelated second-datum locus
    rarely sits along the strike).
    """
    kept: list[Locus] = []
    for s in loci:
        hits: list[str] = []
        for t in loci:
            if t is s or t.datum == s.datum:
                continue
            dx, dy = t.x - s.x, t.y - s.y
            sep = float(np.hypot(dx, dy))
            if not (min_separation_m <= sep <= max_separation_m):
                continue
            bearing = float(np.degrees(np.arctan2(dx, dy)) % 180.0)
            if _axis_delta(bearing, s.strike_deg) > along_strike_tol_deg:
                continue
            if _axis_delta(t.strike_deg, s.strike_deg) > along_strike_tol_deg:
                continue
            ratio = max(t.step_m, s.step_m) / max(1e-6, min(t.step_m, s.step_m))
            if ratio > amp_ratio_max:
                continue
            hits.append(t.datum)
        if hits:
            s.corroborated_by = sorted(set(hits))
            kept.append(s)
    return kept


# --------------------------------------------------------------------------- extension
def _bilinear(field: np.ndarray, x: float, y: float,
              transform: tuple[float, float, float, float, float, float]) -> float:
    a, b, c, d, e, f = transform
    col = (x - c) / a
    row = (y - f) / e
    if row < 0 or col < 0 or row >= field.shape[0] - 1 or col >= field.shape[1] - 1:
        return float("nan")
    r0, c0 = int(np.floor(row)), int(np.floor(col))
    dr, dc = row - r0, col - c0
    v = (field[r0, c0] * (1 - dr) * (1 - dc) + field[r0 + 1, c0] * dr * (1 - dc)
         + field[r0, c0 + 1] * (1 - dr) * dc + field[r0 + 1, c0 + 1] * dr * dc)
    return float(v)


def extend_straight(
    x0: float,
    y0: float,
    strike_deg: float,
    coherence: np.ndarray,
    relief: np.ndarray,
    footprint: np.ndarray,
    transform: tuple[float, float, float, float, float, float],
    *,
    max_length_m: float = EXT_MAX_LENGTH_M,
    step_m: float = EXT_STEP_M,
    max_turn_deg: float = EXT_MAX_TURN_DEG,
    coh_min: float = EXT_COH_MIN,
    relief_min: float = EXT_RELIEF_MIN_M,
) -> tuple[np.ndarray, np.ndarray, float]:
    """March a trace from a seed along strike, bounded turn rate, DEM-supported.

    Deliberately different from :func:`gems62.emit.extend_trace`: that routine hands the
    running azimuth to the local structure tensor whenever the tensor is inside a fan,
    which at a shoreline seed locks the trace onto the shoreline.  Here the running
    direction is owned by this function and only *nudged* towards the tensor at a bounded
    rate, and only in the direction that maximises DEM ridge evidence.  A bounded turn
    rate is also the correct geological prior: Basin and Range normal faults hold their
    strike for many kilometres.

    Returns ``(xs, ys, evidence_min_coherence)``.
    """

    def inside(x: float, y: float) -> bool:
        a, b, c, d, e, f = transform
        col = int((x - c) / a)
        row = int((y - f) / e)
        return (0 <= row < footprint.shape[0] and 0 <= col < footprint.shape[1]
                and bool(footprint[row, col]))

    def march(direction: float) -> tuple[list[tuple[float, float]], float]:
        pts: list[tuple[float, float]] = []
        x, y = x0, y0
        az = strike_deg
        ev_min = np.inf
        travelled = 0.0
        while travelled < max_length_m:
            best = None
            for daz in np.arange(-max_turn_deg, max_turn_deg + 1e-9, 3.0):
                cand = (az + daz) % 180.0
                nx = x + direction * step_m * np.sin(np.radians(cand))
                ny = y + direction * step_m * np.cos(np.radians(cand))
                if not inside(nx, ny):
                    continue
                coh = _bilinear(coherence, nx, ny, transform)
                rel = _bilinear(relief, nx, ny, transform)
                if not np.isfinite(coh) or not np.isfinite(rel):
                    continue
                score = coh + 0.02 * min(rel, 20.0)
                if best is None or score > best[0]:
                    best = (score, cand, nx, ny, coh, rel)
            if best is None:
                break
            _, cand, nx, ny, coh, rel = best
            if coh < coh_min or rel < relief_min:
                break
            ev_min = min(ev_min, coh)
            az = cand
            pts.append((nx, ny))
            x, y = nx, ny
            travelled += step_m
        return pts, (float(ev_min) if np.isfinite(ev_min) else float("nan"))

    fwd, ev_f = march(1.0)
    bwd, ev_b = march(-1.0)
    pts = list(reversed(bwd)) + [(x0, y0)] + fwd
    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    fin = [v for v in (ev_f, ev_b) if np.isfinite(v)]
    return xs, ys, (float(min(fin)) if fin else 0.0)
