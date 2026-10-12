"""H62-M — the pluvial depositional datum and its base-level isobase.

This module is the one genuinely new piece of physics in the 2026-10-12 session, and it exists
to close a defect the repository has been carrying since it was written:

    IR-62-DEM-01 — the official 19-band feature stack contains **no absolute elevation**.
    Every previous lane therefore fit its isobase on band 12, ``det_elev`` ("topography with
    regional trends removed").  A Lahontan isobase is an absolute-elevation datum: the whole
    measurement is "this shoreline, which formed level, now sits at 1337 m here and 1312 m
    there".  Detrending removes part of the signal the lane is defined by, and — worse — the
    detrending operator is unknown, so the residual cannot be interpreted in metres.

The absolute DEM is now available (`data/geodawn_dem_a2_100m.tif`, sha256 ``d32762a3…``,
5,165,644 valid cells inside the footprint, 1027.9–3138.6 m), so the datum can be treated
properly.

What "the datum" is, precisely
--------------------------------
Not the DEM itself.  The DEM's elevation at a point on a pluvial-lake margin is the sum of

    z = (regional datum: lake floor / depositional plain)
      + (height above that plain: the shoreline bench, fan, or bedrock spur)
      + (noise)

The lane's observable is the *first* term.  It is estimated here by a **base-level surface**:
a running minimum of the DEM (the lowest ground within a neighbourhood) followed by a smooth,
i.e. the level of the local depositional plain / lake floor.  This is the standard
"base level / drainage-bullseye" construction in geomorphometry, and in a pluvial basin it is
the lake floor and its bench system.

    base = smooth( min_filter(z, W) )        W ~ 1.7 km, smooth ~ 0.9 km
    HAB  = z - base                          height above base level (geomorphic position)
    isobase = smooth(base, 6 km)             the *regional* datum, absorbing rebound
    resid   = base - isobase                 metres of local departure from the datum

Two flags are then taken, exactly as the lane's tasking paragraph specifies:

* **step** — |resid| exceeds k robust (MAD) standard deviations inside the pluvial band;
* **deflection** — the azimuth of the base-level contour turns by more than a threshold over
  300 m along strike.

Both are measured on the 100 m grid.  Nothing here reads the fault catalogue: the catalogue is
used only to mask the final emission, which is what makes the leakage canary meaningful.

Every function is NaN-safe: the footprint is an irregular subset of the 3730x3292 raster.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

PX_M = 100.0


# ---------------------------------------------------------------------------------------
# NaN-safe primitives
# ---------------------------------------------------------------------------------------
def nan_smooth(a: np.ndarray, sigma_px: float) -> np.ndarray:
    """Gaussian smoothing that ignores NaN and renormalises by the observed weight."""
    m = np.isfinite(a)
    z = np.where(m, a, 0.0)
    w = m.astype(np.float64)
    gz = ndi.gaussian_filter(z, sigma_px, mode="constant", cval=0.0)
    gw = ndi.gaussian_filter(w, sigma_px, mode="constant", cval=0.0)
    out = np.full(a.shape, np.nan, dtype=np.float64)
    ok = gw > 1e-9
    out[ok] = gz[ok] / gw[ok]
    return out


def base_level(z: np.ndarray, *, min_win_m: float = 1700.0,
               smooth_m: float = 900.0) -> np.ndarray:
    """The local depositional base level: a running minimum, then smoothed.

    ``min_win_m`` sets what counts as "the lowest ground nearby" (1.7 km is wide enough to
    reach a basin floor from a toe-of-fan position, narrow enough that a range front does not
    borrow the floor of the next basin).  The following smoothing removes the blocky artefact
    a min-filter leaves behind.
    """
    w = max(3, int(round(min_win_m / PX_M)) | 1)
    big = np.nanmax(z) + 1000.0 if np.isfinite(z).any() else 1e6
    filled = np.where(np.isfinite(z), z, big)
    mn = ndi.minimum_filter(filled, size=w, mode="nearest")
    mn = np.where(np.isfinite(z), mn, np.nan)
    return nan_smooth(mn, smooth_m / PX_M)


def height_above_base(z: np.ndarray, base: np.ndarray) -> np.ndarray:
    """Height above the local base level, in metres."""
    return z - base


def horn_slope(z: np.ndarray) -> np.ndarray:
    """Slope magnitude in degrees (Horn 1981), NaN-safe on the 100 m grid."""
    zf = np.where(np.isfinite(z), z, np.nan)
    gy, gx = np.gradient(np.where(np.isfinite(zf), zf, 0.0), PX_M, PX_M)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def local_relief(z: np.ndarray, *, win_m: float = 900.0) -> np.ndarray:
    """max - min elevation in a square window, a robust relief proxy."""
    w = max(3, int(round(win_m / PX_M)) | 1)
    zf = np.where(np.isfinite(z), z, np.nan)
    finite = np.isfinite(zf)
    lo = np.where(finite, zf, np.nanmax(zf) + 1e3)
    hi = np.where(finite, zf, np.nanmin(zf) - 1e3)
    return ndi.maximum_filter(hi, size=w, mode="nearest") - \
        ndi.minimum_filter(lo, size=w, mode="nearest")


def pluvial_band(hab: np.ndarray, slope: np.ndarray, relief: np.ndarray, *,
                 hab_max_m: float = 120.0, slope_max_deg: float = 6.0,
                 relief_max_m: float = 60.0) -> np.ndarray:
    """The pluvial-lake-margin band: on the depositional plain, low on its flanks, smooth.

    ``HAB <= 120 m`` is the Lahontan scale: the lake was ~120 m deep over the Pyramid Lake
    sub-basin at the Sehoo highstand, so every shoreline bench ever cut by it lies within
    ~120 m of the local basin floor.  Slope and relief gates remove bedrock spurs and fan
    surfaces that happen to sit at the right height.
    """
    return (np.isfinite(hab) & (hab >= 0.0) & (hab <= hab_max_m)
            & (slope <= slope_max_deg) & (relief <= relief_max_m))


def isobase(base: np.ndarray, band: np.ndarray, *, sigma_m: float = 6000.0) -> np.ndarray:
    """The regional datum: a sigma-wide smooth of the base level over the pluvial band.

    sigma = 6 km is the compromise the lane needs.  It is long enough that differential
    post-pluvial isostatic rebound between sub-basins (Adams, Wesnousky & Bills, 1999,
    attribute ~22 m of post-highstand deflection to rebound) is *absorbed into the datum*
    rather than being reported as a step, and short enough that a fault step, which is
    localised, survives in the residual.
    """
    b = np.where(band & np.isfinite(base), base, np.nan)
    return nan_smooth(b, sigma_m / PX_M)


# ---------------------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------------------
def robust_step(resid: np.ndarray, band: np.ndarray, *, k: float = 2.5,
                tile_m: float = 50000.0) -> tuple[np.ndarray, np.ndarray]:
    """Robust (MAD) standardised residual, computed per tile so scale cannot drift.

    Returns ``(z_score, step_flag)``.  The MAD is evaluated on 50 km tiles inside the band;
    a tile with too few band pixels is filled by the global value rather than left undefined,
    and the count is reported by the caller.
    """
    r = np.where(band & np.isfinite(resid), resid, np.nan)
    good = np.isfinite(r)
    med_all = float(np.median(r[good])) if good.any() else 0.0
    mad_all = float(np.median(np.abs(r[good] - med_all))) if good.any() else 1.0
    zs = np.full(r.shape, np.nan)
    t = max(1, int(round(tile_m / PX_M)))
    H, W = r.shape
    for i0 in range(0, H, t):
        for j0 in range(0, W, t):
            sub = r[i0:i0 + t, j0:j0 + t]
            g = np.isfinite(sub)
            if g.sum() < 50:
                med, mad = med_all, mad_all
            else:
                med = float(np.median(sub[g]))
                mad = float(np.median(np.abs(sub[g] - med)))
            sd = 1.4826 * max(mad, 1e-6)
            zs[i0:i0 + t, j0:j0 + t] = (sub - med) / sd
    step = np.isfinite(zs) & (np.abs(zs) >= k) & band
    return zs, step


def contour_azimuth(base: np.ndarray) -> np.ndarray:
    """Local azimuth of the base-level contour, degrees clockwise from north, in [0, 180)."""
    zf = np.where(np.isfinite(base), base, np.nan)
    med = float(np.nanmedian(zf)) if np.isfinite(zf).any() else 0.0
    zz = np.where(np.isfinite(zf), zf, med)
    gy, gx = np.gradient(nan_smooth(zz, 2.0), PX_M, PX_M)
    # contour direction is perpendicular to the gradient
    return np.degrees(np.arctan2(gx, -gy)) % 180.0


def deflection(azimuth: np.ndarray, band: np.ndarray, *,
               min_delta_deg: float = 25.0, step_px: int = 3) -> np.ndarray:
    """Lateral deflection: the contour azimuth turns by >= min_delta_deg over 300 m."""
    a = np.where(band, azimuth, np.nan)
    out = np.zeros(a.shape, bool)
    # four strike directions; shifts are explicit because np.roll would wrap the raster edge
    for dy, dx in ((0, step_px), (step_px, 0), (step_px, step_px), (step_px, -step_px)):
        b = np.full(a.shape, np.nan)
        ys0, ys1 = max(0, -dy), a.shape[0] - max(0, dy)
        xs0, xs1 = max(0, -dx), a.shape[1] - max(0, dx)
        b[ys0:ys1, xs0:xs1] = a[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
        d = _axis_diff(a, b)
        out |= np.isfinite(d) & (d >= min_delta_deg)
    return out & band


def _axis_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Smallest angular difference between two axial (mod 180 deg) direction fields."""
    d = np.abs(a - b) % 180.0
    return np.minimum(d, 180.0 - d)


# ---------------------------------------------------------------------------------------
# the lane's first deliverable: shoreline elevation-vs-distance profiles
# ---------------------------------------------------------------------------------------
@dataclass
class Profile:
    """A shoreline elevation-versus-distance profile through one flagged locus."""
    index: int
    rows: np.ndarray
    cols: np.ndarray
    dist_m: np.ndarray
    base_m: np.ndarray          # measured base level along the profile
    isobase_m: np.ndarray       # fitted datum along the profile
    resid_m: np.ndarray         # base - isobase
    step_index: int | None      # where the flagged step sits
    step_m: float | None        # its size in metres
    azimuth_deg: float


def profile_through(row: int, col: int, azimuth_deg: float, *,
                    base: np.ndarray, isobarm: np.ndarray,
                    half_len_px: int = 40) -> Profile | None:
    """Sample the datum along the local contour strike through (row, col)."""
    H, W = base.shape
    th = np.radians(azimuth_deg)
    dr, dc = np.sin(th), np.cos(th)
    t = np.arange(-half_len_px, half_len_px + 1, dtype=float)
    rows = np.clip(np.round(row + t * dr), 0, H - 1).astype(int)
    cols = np.clip(np.round(col + t * dc), 0, W - 1).astype(int)
    b = base[rows, cols]
    i = isobarm[rows, cols]
    if not np.isfinite(b).any():
        return None
    resid = b - i
    mid = half_len_px
    lo = max(0, mid - 10)
    hi = min(len(t), mid + 11)
    seg = resid[lo:hi]
    if not np.isfinite(seg).any():
        step_index, step_m = None, None
    else:
        # the step is the largest robust jump of the residual across the locus
        left = np.nanmedian(resid[max(0, mid - 10):mid + 1]) if mid >= 1 else np.nan
        right = np.nanmedian(resid[mid:min(len(t), mid + 11)])
        step_index = mid
        step_m = float(right - left) if np.isfinite(left) and np.isfinite(right) else None
    return Profile(index=-1, rows=rows, cols=cols, dist_m=t * PX_M, base_m=b,
                   isobase_m=i, resid_m=resid, step_index=step_index,
                   step_m=step_m, azimuth_deg=float(azimuth_deg))
