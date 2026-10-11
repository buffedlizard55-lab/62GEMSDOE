"""Turn flagged datum offsets into a submission raster.

Emission design is dictated by the published metric, not by taste:

* Unit-valued dots are optimal.  For a fixed support, writing value ``v`` on every
  dot gives ``DTI(v) = v*sum(k) / (0.2*v*N + 0.8*|G|)``, which is strictly
  increasing in ``v``; the limit is ``v = 1``.  (``tests/test_metric.py``
  checks the monotonicity; all 21 collected family artifacts from the sibling
  repositories indeed use ``1.0``.)
* Dot spacing is kernel-matched at ~300 m.  The best-scoring prior family used a
  nearest-neighbour spacing of 3.0 px = 300 m; at that spacing the triangular
  kernels just touch, so no emitted mass is wasted on shared coverage.
* A dot inside ~200 m of the mapped catalogue earns no credit: the organizer
  confirmed that known USGS/INGENIOUS fault pixels are masked out of the
  evaluation (DrivenData community thread 11516, staff, 2026-09-16), and the
  empirically best-scoring prior artifact is exactly the one produced by
  deleting the 100-200 m catalogue flank (its owner reports 0.2600 -> 0.2778 for
  that single edit).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from .grid import PIXEL_M
from .lahontan import (
    DEFLECTION_MIN_DEG,
    ELEVATION_RESOLUTION_M,
    DeflectionFlag,
    StepFlag,
)

#: Dot spacing along a trace: 3 px = 300 m, the kernel-matched value.
DOT_SPACING_M = 300.0
#: Catalogue exclusion radius (m).  See module docstring.
CATALOGUE_EXCLUSION_M = 200.0
#: Traces are extended while DEM lineament evidence exceeds these bars.
COHERENCE_MIN = 0.15
RELIEF_MIN_M = 4.0
#: Longest single trace extension from a seed, each way (m).
MAX_TRACE_LENGTH_M = 6000.0
#: Extension step (m).
TRACE_STEP_M = 200.0
#: Extensions are tried in this azimuth fan (deg clockwise from north).
AZIMUTH_FAN_DEG = 15.0


@dataclass
class Trace:
    """A single emitted fault trace, in map coordinates (m, EPSG:32611)."""

    seed_x: float
    seed_y: float
    azimuth_deg: float
    xs: np.ndarray
    ys: np.ndarray
    provenance: str
    evidence_min: float

    @property
    def length_m(self) -> float:
        if self.xs.size < 2:
            return 0.0
        return float(np.sum(np.hypot(np.diff(self.xs), np.diff(self.ys))))

    def sample(self, spacing_m: float = DOT_SPACING_M) -> tuple[np.ndarray, np.ndarray]:
        """Resample the polyline at roughly ``spacing_m`` intervals."""
        if self.xs.size == 0:
            return np.array([]), np.array([])
        seg = np.hypot(np.diff(self.xs), np.diff(self.ys))
        s = np.concatenate([[0.0], np.cumsum(seg)])
        if s[-1] <= 0:
            return self.xs[:1].copy(), self.ys[:1].copy()
        n = max(1, int(round(s[-1] / spacing_m)) + 1)
        targets = np.linspace(0.0, s[-1], n)
        return np.interp(targets, s, self.xs), np.interp(targets, s, self.ys)


def structure_tensor(dem: np.ndarray, footprint: np.ndarray, *,
                     sigma_px: float = 5.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Gradient-covariance (structure) tensor of the terrain.

    Returns ``(azimuth_deg, coherence, relief_m)`` on the full grid:

    * ``azimuth_deg`` -- dominant lineament azimuth, degrees clockwise from north,
      in ``[0, 180)``.  It is the direction *along* which the terrain gradient is
      smallest, i.e. the ridge/escarpment trend.
    * ``coherence`` -- ``(l1 - l2) / (l1 + l2)`` of the tensor, in ``[0, 1]``; a
      measure of how lineament-like the local terrain is.
    * ``relief_m`` -- the cross-strike elevation contrast over the smoothing
      window, a proxy for scarp height.
    """
    z = np.where(footprint & np.isfinite(dem), dem, np.nan)
    fill = np.nanmedian(z) if np.isfinite(z).any() else 0.0
    zf = np.where(np.isfinite(z), z, fill)
    gy, gx = np.gradient(zf, PIXEL_M, PIXEL_M)
    valid = footprint.astype(float)

    def smooth(a):
        num = ndi.gaussian_filter(a * valid, sigma_px)
        den = ndi.gaussian_filter(valid, sigma_px)
        return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-9)

    gxx = smooth(gx * gx)
    gyy = smooth(gy * gy)
    gxy = smooth(gx * gy)
    tr = gxx + gyy
    det = gxx * gyy - gxy * gxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    denom = np.maximum(l1 + l2, 1e-12)
    coherence = np.where(tr > 0, (l1 - l2) / denom, 0.0)

    # Eigenvector of l2 is the lineament direction.
    vx = np.where(np.abs(gxy) > 1e-12, l2 - gyy, 1.0)
    vy = np.where(np.abs(gxy) > 1e-12, gxy, 0.0)
    norms = np.hypot(vx, vy)
    norms = np.where(norms > 1e-12, norms, 1.0)
    vx, vy = vx / norms, vy / norms
    azimuth = np.degrees(np.arctan2(vx, vy)) % 180.0

    relief = np.sqrt(np.maximum(l1, 0.0)) * (2.0 * sigma_px * PIXEL_M)
    return azimuth.astype(np.float64), np.clip(coherence, 0.0, 1.0), relief


def _bilinear(field: np.ndarray, x: float, y: float,
              transform: tuple[float, float, float, float, float, float]) -> float:
    a, b, c, d, e, f = transform
    col = (x - c) / a - 0.5
    row = (y - f) / e - 0.5
    h, w = field.shape
    if row < 0 or col < 0 or row > h - 1.001 or col > w - 1.001:
        return float("nan")
    r0, c0 = int(np.floor(row)), int(np.floor(col))
    dr, dc = row - r0, col - c0
    v = (
        field[r0, c0] * (1 - dr) * (1 - dc)
        + field[r0 + 1, c0] * dr * (1 - dc)
        + field[r0, c0 + 1] * (1 - dr) * dc
        + field[r0 + 1, c0 + 1] * dr * dc
    )
    return float(v)


def extend_trace(
    seed_x: float,
    seed_y: float,
    seed_azimuth_deg: float,
    azimuth_field: np.ndarray,
    coherence: np.ndarray,
    relief: np.ndarray,
    footprint: np.ndarray,
    transform: tuple[float, float, float, float, float, float],
    *,
    both_ways: bool = True,
    max_length_m: float = MAX_TRACE_LENGTH_M,
    step_m: float = TRACE_STEP_M,
    coherence_min: float = COHERENCE_MIN,
    relief_min: float = RELIEF_MIN_M,
    fan_deg: float = AZIMUTH_FAN_DEG,
) -> Trace | None:
    """March outward from a seed while lineament evidence supports the trace.

    At each step the local structure-tensor azimuth is consulted; the trace
    direction is allowed to deviate from the running azimuth by at most
    ``fan_deg`` per step, and the step is accepted only if both the lineament
    coherence and the cross-strike relief clear their bars.  Marching stops at
    the first unsupported point.
    """
    h, w = coherence.shape

    def inside(x: float, y: float) -> bool:
        a, b, c, d, e, f = transform
        col = int((x - c) / a)
        row = int((y - f) / e)
        return 0 <= row < h and 0 <= col < w and footprint[row, col]

    def march(direction: float) -> tuple[list[tuple[float, float]], float]:
        pts: list[tuple[float, float]] = []
        x, y = seed_x, seed_y
        az = seed_azimuth_deg
        evidence_min = np.inf
        travelled = 0.0
        while travelled < max_length_m:
            # Candidate next azimuths inside the fan about the running azimuth.
            local = _bilinear(azimuth_field, x, y, transform)
            coh = _bilinear(coherence, x, y, transform)
            rel = _bilinear(relief, x, y, transform)
            if not np.isfinite(coh) or not np.isfinite(rel):
                break
            if coh < coherence_min or rel < relief_min:
                break
            evidence_min = min(evidence_min, coh)
            if np.isfinite(local):
                tol = fan_deg
                cands = [local % 180.0, (local + 180.0) % 180.0]
                # Choose the branch closest to the running azimuth.
                best = min(cands, key=lambda c: _axis_diff(c, az))
                if _axis_diff(best, az) <= tol:
                    az = best
            # Advance along the running azimuth, signed by `direction`.
            nx = x + direction * step_m * np.sin(np.radians(az))
            ny = y + direction * step_m * np.cos(np.radians(az))
            if not inside(nx, ny):
                break
            pts.append((nx, ny))
            x, y = nx, ny
            travelled += step_m
        return pts, (float(evidence_min) if np.isfinite(evidence_min) else float("nan"))

    forward, ev_fwd = march(1.0)
    backward, ev_bwd = march(-1.0) if both_ways else ([], float("nan"))
    back = list(reversed(backward))
    pts = back + [(seed_x, seed_y)] + forward
    if len(pts) < 3:
        return None
    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    finite = [v for v in (ev_fwd, ev_bwd) if np.isfinite(v)]
    ev = float(min(finite)) if finite else 0.0
    return Trace(seed_x=seed_x, seed_y=seed_y, azimuth_deg=seed_azimuth_deg,
                 xs=xs, ys=ys, provenance="datum_offset", evidence_min=ev)


def _axis_diff(a: float, b: float) -> float:
    """Smallest angle between two axial directions in degrees."""
    return abs(((a - b) + 90.0) % 180.0 - 90.0)


@dataclass
class Seed:
    """A fault trace seed derived from one flagged datum offset.

    ``azimuth_deg`` is the fault's own strike, which is *not* the local DEM
    lineament azimuth at the seed: at a datum-offset seed the dominant DEM
    lineament is the shorelines own edge.  The two offset classes therefore take
    opposite constructions, both of them geometric:

    * vertical step -- the shoreline drops as one walks along it, so the fault
      that does the dropping must cross the shoreline: ``az = datum_az + 90``.
    * lateral deflection -- the shoreline is displaced along its own length
      (the Pyramid Lake fault-zone case of Briggs & Wesnousky and of Dong et al.),
      so the fault runs roughly parallel to the datum: ``az = datum_az``.
    """

    x: float
    y: float
    kind: str
    strength: float
    azimuth_deg: float
    az_tol_deg: float = AZIMUTH_FAN_DEG


def seeds_from_flags(
    step_flags: list[StepFlag],
    deflection_flags: list[DeflectionFlag],
    benches: list["Bench"],  # noqa: F821
    *,
    min_abs_jump_m: float = ELEVATION_RESOLUTION_M,
    min_az_change_deg: float = DEFLECTION_MIN_DEG,
    dedupe_radius_m: float = 600.0,
) -> list[Seed]:
    """Build fault seeds from the flagged datum offsets, strongest evidence first.

    The fault azimuth is the mean of the two contrasted benches' principal-axis
    azimuths, rotated by 90 degrees for a vertical step (fault crosses the datum)
    and left unrotated for a lateral deflection (fault runs along the datum).
    """
    raw: list[Seed] = []
    for f in step_flags:
        if abs(f.residual_jump_m) < min_abs_jump_m:
            continue
        a = 0.5 * (benches[f.bench_a].azimuth_deg + benches[f.bench_b].azimuth_deg)
        raw.append(Seed(x=f.x, y=f.y, kind="elevation_step",
                        strength=abs(f.residual_jump_m), azimuth_deg=(a + 90.0) % 180.0))
    for d in deflection_flags:
        if d.az_change_deg < min_az_change_deg:
            continue
        a = 0.5 * (d.az_in_deg + d.az_out_deg)
        raw.append(Seed(x=d.x, y=d.y, kind="lateral_deflection",
                        strength=d.az_change_deg / 10.0, azimuth_deg=a % 180.0))

    raw.sort(key=lambda s: -s.strength)
    kept: list[Seed] = []
    for s in raw:
        if any(np.hypot(s.x - k.x, s.y - k.y) < dedupe_radius_m for k in kept):
            continue
        kept.append(s)
    return kept


def traces_from_flags(
    seeds: list[Seed],
    azimuth_field: np.ndarray,
    coherence: np.ndarray,
    relief: np.ndarray,
    footprint: np.ndarray,
    transform: tuple[float, float, float, float, float, float],
    *,
    min_evidence_coherence: float = COHERENCE_MIN,
    min_length_m: float = 400.0,
) -> list[Trace]:
    """Extend one trace per seed while DEM evidence supports it."""
    traces: list[Trace] = []
    for s in seeds:
        coh_at_seed = _bilinear(coherence, s.x, s.y, transform)
        if not np.isfinite(coh_at_seed) or coh_at_seed < min_evidence_coherence:
            continue
        t = extend_trace(s.x, s.y, s.azimuth_deg, azimuth_field, coherence, relief,
                         footprint, transform, fan_deg=s.az_tol_deg)
        if t is None or t.length_m < min_length_m:
            continue
        t.provenance = s.kind
        t.azimuth_deg = s.azimuth_deg
        traces.append(t)
    return traces


def dots_from_traces(
    traces: list[Trace],
    catalogue: np.ndarray,
    footprint: np.ndarray,
    transform: tuple[float, float, float, float, float, float],
    *,
    spacing_m: float = DOT_SPACING_M,
    exclusion_m: float = CATALOGUE_EXCLUSION_M,
    min_separation_m: float = 0.9 * DOT_SPACING_M,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Rasterise traces as unit-valued dots.

    Three filters, in order:

    1. drop samples inside the scored footprint but within ``exclusion_m`` of the
       mapped catalogue (they cannot earn credit -- see module docstring);
    2. drop samples outside the survey footprint (the contract asks for null
       outside the data bounds);
    3. greedy minimum-separation thinning at ``min_separation_m`` so that no two
       kept dots waste mass on the same kernel.

    Returns ``(rows, cols, stats)``.
    """
    a, b, c, d, e, f = transform
    dist_cat = ndi.distance_transform_edt(~catalogue, sampling=(PIXEL_M, PIXEL_M))

    cand: list[tuple[int, int]] = []
    n_sampled = n_cat_excluded = n_outside = 0
    for t in traces:
        xs, ys = t.sample(spacing_m)
        for x, y in zip(xs, ys):
            n_sampled += 1
            col = int((x - c) / a)
            row = int((y - f) / e)
            if not (0 <= row < footprint.shape[0] and 0 <= col < footprint.shape[1]):
                n_outside += 1
                continue
            if not footprint[row, col]:
                n_outside += 1
                continue
            if dist_cat[row, col] < exclusion_m:
                n_cat_excluded += 1
                continue
            cand.append((row, col))

    # Greedy thinning in map space.
    kept: list[tuple[int, int]] = []
    used = np.zeros(footprint.shape, dtype=bool)
    step_cells = max(1, int(round(min_separation_m / PIXEL_M)))

    def clear(r0: int, c0: int) -> bool:
        r1, r2 = max(0, r0 - step_cells), min(used.shape[0], r0 + step_cells + 1)
        c1, c2 = max(0, c0 - step_cells), min(used.shape[1], c0 + step_cells + 1)
        sub = used[r1:r2, c1:c2]
        if not sub.any():
            return True
        rr, cc = np.nonzero(sub)
        dy = (rr + r1 - r0) * PIXEL_M
        dx = (cc + c1 - c0) * PIXEL_M
        return bool(np.all(np.hypot(dx, dy) >= min_separation_m))

    for r, c0 in cand:
        if clear(r, c0):
            used[r, c0] = True
            kept.append((r, c0))

    rows = np.array([k[0] for k in kept], dtype=int)
    cols = np.array([k[1] for k in kept], dtype=int)
    stats = {
        "n_traces": len(traces),
        "n_sampled": n_sampled,
        "n_dropped_outside_footprint": n_outside,
        "n_dropped_catalogue_exclusion": n_cat_excluded,
        "n_dots": int(rows.size),
        "spacing_m": spacing_m,
        "exclusion_m": exclusion_m,
        "min_separation_m": min_separation_m,
    }
    return rows, cols, stats


def raster_from_dots(rows: np.ndarray, cols: np.ndarray, shape: tuple[int, int],
                     *, value: float = 1.0) -> np.ndarray:
    """Unit-valued raster on the competition grid, zero everywhere else."""
    out = np.zeros(shape, dtype=np.float32)
    out[rows, cols] = np.float32(value)
    return out


def to_nan_outside(raster: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Return a copy with NaN outside the survey footprint (the page's wording)."""
    out = raster.astype(np.float32).copy()
    out[~footprint] = np.nan
    return out
