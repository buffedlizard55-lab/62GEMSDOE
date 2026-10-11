"""Lahontan bench-detection lane: the geomorphic offset of a pluvial-lake
shoreline datum as a primary fault-signal source.

Why this exists
---------------
The task is a segmentation problem whose positive class is a *linear* feature
whose only reliable expression in a 100 m DEM is topography, and the published
catalogue is the very thing the labels were extended from.  Any model trained on
catalogue-derived shape therefore maximises its score by re-deriving the
catalogue, which is exactly where the family's earlier lane plateaued
(raster/GBM 0.2181, feature-stack GEMSDOE60 0.2759, trace graph 0.2708).  The
score that is actually being sought is the *residual* signal, so this lane
builds an independent primary measurement instead of a classifier:

    Pluvial Lake Lahontan stood at the Sehoo highstand 15.5 +- 0.7 cal ka BP
    and left benches, relict shorelines and spillways that were later cut by the
    same range-front faults the contest asks for.  Published offsets measured
    across individual fault strands are ~2.6 +- 0.3 mm/yr (12-15 m on channels
    and 35-43 m on side canyons across (39 +- 4) kyr of incision, Briggs &
    Wesnousky 2004, JGR 109:B08402), ~0.9 mm/yr on shorelines near the Wassuk
    Range (~14 m since 15.1 ka, Dong et al. 2014, Geosphere), and 15 +- 10 m of
    vertical separation on a Sehoo-age ridge south of Black Rock Desert (Angster
    et al. 2016, BSSA).  The expected signal is therefore ~10-45 m of vertical
    offset of a continuous near-level surface, and it should be *parallel* to
    the shoreline where the fault is oblique and *perpendicular* to the
    shoreline where the fault cuts across it.

Design decisions that matter
----------------------------
* The signal is the *jump in the datum across a candidate trace*, measured on
  pixels the flat-tread test accepts -- not the elevation anomaly relative to a
  fitted regional surface.  A whole-lake version of the latter was built and
  rejected: the basin contains nested still-stands and playa floors, so the
  block median settles between levels and the residual measures which surface a
  pixel belongs to rather than whether it is faulted (tread |anomaly| median 45 m
  on the full grid).
* Bench identification is direction-free: a tread is a cell flanked within a few
  pixels by ground both higher and lower (a riser on both sides), with modest
  local relief in both directions.  An isotropic |z - median| test was tried and
  abandoned, because a 500-700 m wide tread is mostly riser pixels inside a 7x7
  window and the real benches fail it for the wrong reason.
* Offset estimation uses a discrete matched filter over 12 trace trends.  For a
  trend ``az``, ``T = (sin az, cos az)`` walks *along* the trace and
  ``N = (cos az, -sin az)`` is *across* the step; the datum is compared between
  +/- legs along N, and the control windows are offset along T.
* A step is only kept when each limb keeps one level over four independent
  sub-windows and the sign of the offset continues along the trace.  Those two
  tests are what separate a through-going fault from a DEM spike or an
  artefact.  Known limitation, tested for rather than glossed over: an alluvial
  lens that carries the tread ~600 m past the trace and then returns to the
  datum is NOT vetoed, because at 100 m cells that is what a short range-front
  scarp looks like; the flagged core shrinks by about a third and the amplitude
  is unchanged.
* Regional uplift/subsidence is O(1 m/km) across the basin (isostatic rebound
  after Lahontan), which over the 0.2-1 km lever arm of the operator is <1 m: it
  cannot manufacture a 10-45 m step, so no isobase needs to be removed before
  gating.  A smooth regional datum is still computed for the maps and profiles.
* Discretisation: on a 100 m grid the leg offsets are integers, so a scarp whose
  face is 1-2 cells wide is measured with a bias of a few metres and the arg-max
  trend is weakly determined where both limbs are level.  The amplitude carries
  the physical claim; the trace is followed through the sign boundary of
  ``step_signed``, not by integrating ``step_azim``.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

# ------------------------------------------------------------------ constants
PIXEL_M = 100.0                                 # training-grid cell size
AZIMUTHS = np.arange(0.0, 180.0, 15.0)           # candidate trace trends, deg
J_LEGS = (2, 3, 4, 5)                             # px, datum lever arms
OUT_LEGS = (7, 8, 9, 10)                          # px, persistence control legs
J_HALVES = ((2, 3), (4, 5))                       # sub-windows for limb stability
W_HALVES = ((7, 8), (9, 10))
CROSS = (-1, 0, 1)                                # px, averaging across the tread
LEG_LEN_PX = max(OUT_LEGS)                        # px, outer lever arm
FLANK_PX = 4                                      # px, tread must be flanked within
MIN_RELIEF_M = 6.0                                # m, riser relief on both sides
MAX_SLOPE_DEG = 7.0                               # deg, tread must be near-level
MAX_PLANARITY_M = 3.0                             # m, 5x5 departure from the median
MAX_ANCHOR_SLOPE_DEG = 12.0                       # deg, reject scarps and valley sides
MIN_SUBWIN_CELLS = 0.9        # bench cells needed for a sub-window mean to count
MIN_SIDE_CELLS = 3.0          # bench cells needed per limb, pooled over sub-windows
MIN_VALID_SUBWINS = 2         # sub-windows per limb that must be usable
LIMB_TOLERANCE_M = 10.0                           # m, spread allowed within one limb
ISO_BLOCK = 50                                    # px, regional datum block size
ISO_SMOOTH_BLOCKS = 4.0                           # blocks, smoothing of that surface
PLUVIAL_WINDOW_M = (1120.0, 1520.0)               # lake-level window for this grid
MIN_STEP_M = 8.0                                  # m, >= 2 DEM s.u. and ~3x the
#    smallest published Lahontan offset (9 m at the Walker Lane sils)
MAX_STEP_M = 90.0                                 # m, beyond this it is a range front
BENCH_HABITAT_DILATE = 4                           # px, tread-to-habitat buffer


class DatumField(dict):
    """Container for the lane's fields (attribute and key access both work)."""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as e:                 # pragma: no cover
            raise AttributeError(k) from e

    def __setattr__(self, k, v):
        self[k] = v


# ------------------------------------------------------------------ small helpers
def _at(arr: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Shift an array by whole pixels, zero-filled (no wrap-around).

    ``out[i, j] == arr[i - dy, j - dx]`` for indices inside the array; the strip
    left at the edge is *zeroed* rather than copied, so a roll can never leak a
    far-side value across the map.  Verified pixel-for-pixel against an explicit
    index loop by tests/test_lahontan.py.
    """
    out = np.zeros_like(arr)
    H, W = arr.shape
    ys, xs = slice(max(dy, 0), min(H + dy, H)), slice(max(dx, 0), min(W + dx, W))
    yd, xd = slice(max(-dy, 0), min(H - dy, H)), slice(max(-dx, 0), min(W - dx, W))
    if ys.start < ys.stop and xs.start < xs.stop:
        out[ys, xs] = arr[yd, xd]
    return out


def _block_reduce(vals: np.ndarray, mask: np.ndarray, block: int, stat: str) -> tuple:
    """Block-reduce float data and a boolean mask onto one coarse grid."""
    H, W = vals.shape
    nby, nbx = int(np.ceil(H / block)), int(np.ceil(W / block))
    padH, padW = nby * block, nbx * block
    v = np.full((padH, padW), np.nan, np.float64)
    v[:H, :W] = np.where(mask, vals, np.nan)
    m = np.zeros((padH, padW), bool)
    m[:H, :W] = mask
    vb = v.reshape(nby, block, nbx, block).transpose(0, 2, 1, 3).reshape(nby, nbx, -1)
    mb = m.reshape(nby, block, nbx, block).transpose(0, 2, 1, 3).reshape(nby, nbx, -1)
    cnt = mb.sum(2)
    with np.errstate(invalid="ignore"):
        if stat == "mean":
            out = np.where(cnt > 0, np.nanmean(vb, axis=2), np.nan)
        elif stat == "frac":
            out = np.where(cnt > 0, mb.mean(2), np.nan)
        elif stat == "median":
            out = np.where(cnt > 0, np.nanmedian(vb, axis=2), np.nan)
        else:                               # pragma: no cover
            raise ValueError(stat)
    return out.astype(np.float32), cnt


def _zoom_to(small: np.ndarray, shape) -> np.ndarray:
    """Nearest-zoom a coarse map back to full grid, staying on cell centres."""
    return np.asarray(ndi.zoom(small, (shape[0] / small.shape[0],
                                        shape[1] / small.shape[1]), order=0,
                               mode="nearest"), np.float32)


def _slope_aspect(z: np.ndarray) -> tuple:
    """Slope in degrees and dip direction in degrees from north, from a 2-point
    central difference.  np.gradient returns m per *pixel* here, hence PIXEL_M."""
    gy, gx = np.gradient(z.astype(np.float64))
    g = np.hypot(gy, gx) / PIXEL_M
    return np.degrees(np.arctan(g)).astype(np.float32), \
        np.degrees(np.arctan2(gx, -gy)).astype(np.float32)


# ------------------------------------------------------------------ the field
def build_field(z: np.ndarray, footprint: np.ndarray, *,
                min_step: float = MIN_STEP_M, max_step: float = MAX_STEP_M,
                iso_block: int = ISO_BLOCK,
                window=PLUVIAL_WINDOW_M, verbose: bool = True) -> DatumField:
    """Compute the bench mask, the offset-corrected datum and the step fields.

    Parameters
    ----------
    z : float array (H, W)
        DEM in metres above sea level; NaN where the tile did not cover.
    footprint : bool array (H, W)
        Cells inside the contest grid.
    min_step, max_step : float
        Accepted vertical offset of the bench datum across the trace, metres.
    """
    z = np.asarray(z, np.float32)
    fin = np.isfinite(z) & np.asarray(footprint, bool)
    zf = np.where(fin, z, np.float32(np.nan)).astype(np.float32)
    zfmed = ndi.median_filter(np.nan_to_num(zf, nan=0.0), size=5)
    zf = np.where(fin, zf, zfmed).astype(np.float32)

    slope, aspect = _slope_aspect(zf)
    in_band = fin & (zf >= window[0]) & (zf <= window[1])

    # ---- tread test (direction-free) ------------------------------------
    # A tread cell is flanked within FLANK_PX by ground both clearly above and
    # clearly below it (a riser on both sides) and is itself near-level, with
    # little relief in a small window.
    hi = ndi.maximum_filter(np.where(in_band, zf, np.float32(-1e9)),
                            size=2 * FLANK_PX + 1)
    lo = ndi.minimum_filter(np.where(in_band, zf, np.float32(1e9)),
                            size=2 * FLANK_PX + 1)
    flanked = (hi - zf >= MIN_RELIEF_M) & (zf - lo >= MIN_RELIEF_M)
    planar = np.abs(zf - ndi.median_filter(zf, size=5)) <= MAX_PLANARITY_M
    bench = in_band & (slope <= MAX_SLOPE_DEG) & flanked & planar
    if verbose:
        print(f"[field] pluvial-band px {int(in_band.sum())}, bench px {int(bench.sum())}",
              flush=True)

    # ---- matched-filter step operator ----------------------------------
    # The datum is measured on tread pixels and nowhere else, and the SAME mask
    # weights numerator and denominator so sv/cv is a true mean elevation.  A
    # softened weight was tried and is wrong: it lets the riser, whose elevation
    # differs by exactly the bench relief, leak into a limb mean and fabricate a
    # step of the bench height at every tread margin.
    wgt = bench.astype(np.float32)
    zf0 = np.nan_to_num(zf, nan=0.0).astype(np.float32)
    zq = (zf0 * wgt).astype(np.float32)
    step = np.zeros(z.shape, np.float32)
    step_signed = np.zeros(z.shape, np.float32)
    step_azim = np.zeros(z.shape, np.float32)
    gated = np.zeros(z.shape, np.float32)
    best = np.full(z.shape, -1.0, np.float32)

    def limb(legs, sign, ny, nx, ty, tx):
        """Sum and count of bench elevation on one limb over these legs.

        Each leg is averaged over ``CROSS`` pixels across the tread as well, so a
        tread only one or two cells wide still yields a continuous field along its
        strike.  Returns sums so the caller can pool legs however it likes.
        """
        sv = np.zeros(z.shape, np.float32)
        cv = np.zeros(z.shape, np.float32)
        for leg in legs:
            for m in CROSS:
                py = int(round(sign * leg * ny + m * ty))
                px = int(round(sign * leg * nx + m * tx))
                if py == 0 and px == 0:
                    continue
                sv = sv + _at(zq, -py, -px)      # sample at (i+py, j+px)
                cv = cv + _at(wgt, -py, -px)
        return sv, cv

    for az in AZIMUTHS:                # trend of the trace, deg from north
        th = np.radians(float(az))
        ty, tx = np.sin(th), np.cos(th)          # along the trace (the walk)
        ny, nx = np.cos(th), -np.sin(th)          # across the step (the legs)
        mus, svs, cvs = [], [], []
        for sign in (+1, -1):
            for legs in J_HALVES + W_HALVES:
                sv, cv = limb(legs, sign, ny, nx, ty, tx)
                svs.append(sv); cvs.append(cv)
                with np.errstate(invalid="ignore", divide="ignore"):
                    mu = np.where(cv >= MIN_SUBWIN_CELLS,
                                  sv / np.maximum(cv, 1e-6), np.float32(np.nan))
                mus.append(np.asarray(mu, np.float32))
        spread = np.zeros(z.shape, np.float32)
        nvalid = np.zeros(z.shape, np.int16)
        ok = np.ones(z.shape, bool)
        for side in (0, 4):                       # one level test per limb
            stack = np.stack(mus[side:side + 4])
            nv = np.isfinite(stack).sum(0).astype(np.int16)
            nvalid = nvalid + nv
            with np.errstate(invalid="ignore"):
                sp = np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)
            sp = np.where(nv >= 2, sp, np.float32(1e6))
            spread = np.maximum(spread, np.nan_to_num(sp, nan=1e6).astype(np.float32))
            tot = np.stack(cvs[side:side + 4]).sum(0)
            ok &= tot >= MIN_SIDE_CELLS
        ok &= nvalid >= 2 * MIN_VALID_SUBWINS
        with np.errstate(invalid="ignore", divide="ignore"):
            svp = np.stack(svs[0:4]).sum(0)
            cvp = np.stack(cvs[0:4]).sum(0)
            svm = np.stack(svs[4:8]).sum(0)
            cvm = np.stack(cvs[4:8]).sum(0)
            dS = np.where(ok, svp / np.maximum(cvp, 1e-6)
                          - svm / np.maximum(cvm, 1e-6), np.float32(0.0))
        dS = np.nan_to_num(dS, nan=0.0).astype(np.float32)
        J = np.abs(dS).astype(np.float32)
        # the offset must keep its sign for a couple of pixels along the trace:
        # a real scarp continues, a lone bump or a pixel-scale artefact oscillates
        signs_ok = np.ones(z.shape, bool)
        for leg in (1, 2):
            py, px = int(round(leg * ty)), int(round(leg * tx))
            if py == 0 and px == 0:
                continue
            sp_ = _at(dS, py, px)
            sm_ = _at(dS, -py, -px)
            signs_ok &= ((sp_ * dS >= 0) | (sp_ == 0)) & ((sm_ * dS >= 0) | (sm_ == 0))
        score = J * ok * (spread <= LIMB_TOLERANCE_M) * signs_ok \
            * (J >= min_step) * (J <= max_step)
        upd = score > best
        step = np.where(upd, J, step).astype(np.float32)
        step_signed = np.where(upd, dS, step_signed).astype(np.float32)
        step_azim = np.where(upd, np.float32(az), step_azim).astype(np.float32)
        gated = np.where(upd, score, gated).astype(np.float32)
        best = np.where(upd, score, best).astype(np.float32)
        del mus, svs, cvs, ok, spread, nvalid, dS, J, signs_ok, score, upd

    # coarse regional datum surface, for maps/profiles only (never used to gate)
    regional, rcnt = _block_reduce(zf, bench, iso_block, "median")
    regional = np.where(np.isfinite(regional), regional, np.nanmedian(regional))
    isobase = _zoom_to(ndi.gaussian_filter(regional, sigma=ISO_SMOOTH_BLOCKS), z.shape)
    anomaly = (zf - isobase).astype(np.float32)

    ev = np.clip(gated / max(max_step, 1e-6), 0.0, 1.0).astype(np.float32)
    ev = ndi.gaussian_filter(ev, sigma=0.8).astype(np.float32)
    mx = float(ev.max()) if ev.size else 0.0
    if mx > 0:
        ev = (ev / mx).astype(np.float32)

    # The anchor pixel of a step is the riser itself, which the flat-tread test
    # rejects, so the flag also lives on the tread beside the step.  Anchors on
    # steep ground are rejected outright: a smooth range-front slope concentrates
    # the same bench level change into 2-3 cells and reads 3-4x the true offset.
    zone = ((gated >= min_step) & ndi.binary_dilation(bench, iterations=2)
            & (slope <= MAX_ANCHOR_SLOPE_DEG))
    habitat = (ndi.binary_dilation(bench & (slope <= MAX_ANCHOR_SLOPE_DEG),
                                  iterations=BENCH_HABITAT_DILATE) & footprint)
    n_flag = int(zone.sum())
    if verbose:
        print(f"[field] gated persistent-step px >= {min_step} m: {n_flag}; "
              f"habitat px {int(habitat.sum())}", flush=True)
    return DatumField(z=z, slope=slope, aspect=aspect, bench=bench, isobase=isobase,
                      anomaly=anomaly, step=step, step_signed=step_signed,
                      step_azim=step_azim, gated=gated, zone=zone, evidence=ev,
                      habitat=np.asarray(habitat, bool),
                      meta=dict(pluvial_window=[float(window[0]), float(window[1])],
                                iso_block=int(iso_block), min_step_m=float(min_step),
                                max_step_m=float(max_step),
                                limb_tolerance_m=LIMB_TOLERANCE_M,
                                min_side_cells=MIN_SIDE_CELLS, xcross=list(CROSS),
                                n_band=int(in_band.sum()), n_bench=int(bench.sum()),
                                n_step_flagged=n_flag, n_habitat=int(habitat.sum()),
                                azimuths=AZIMUTHS.tolist(), legs_j=list(J_LEGS),
                                legs_out=list(OUT_LEGS), flank_px=FLANK_PX,
                                min_relief_m=MIN_RELIEF_M, max_slope_deg=MAX_SLOPE_DEG,
                                max_planarity_m=MAX_PLANARITY_M))


# --------------------------------------------------------------- isobase / profiles
def fit_isobase_1d(dist_km: np.ndarray, elev_m: np.ndarray, bench_m: np.ndarray,
                  exclude: tuple[float, float] | None = None, deg: int = 3):
    """Robust polynomial isobase fit along a shoreline transect (km, m asl).

    ``exclude`` masks a along-strike window (km) around a flagged step so the
    smooth rebound/tilt surface is fitted to the limbs only and the step height
    is a genuine datum offset rather than a fitting artefact.  Two robust IRLS
    passes clip the displaced limb.
    """
    d = np.asarray(dist_km, float)
    e = np.asarray(elev_m, float)
    m = np.asarray(bench_m, bool) & np.isfinite(d) & np.isfinite(e)
    if exclude is not None:
        m &= ~((d >= exclude[0]) & (d <= exclude[1]))
    if m.sum() < deg + 3:
        return None
    w = np.ones(m.sum(), float)
    dd, ee = d[m], e[m]
    coef = np.polyfit(dd, ee, deg, w=w)
    for _ in range(2):
        r = ee - np.polyval(coef, dd)
        s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-6
        w = 1.0 / (1.0 + (r / (2.5 * s)) ** 2)
        coef = np.polyfit(dd, ee, deg, w=w)
    iso = np.polyval(coef, d)
    resid = e - iso
    return dict(deg=deg, coef=coef.tolist(), isobase_m=iso, residual_m=resid,
                rms_m=float(np.sqrt(np.mean(r ** 2))), n_fit=int(m.sum()))


# --------------------------------------------------------------- profiles
def profile_along(path_yx: np.ndarray, fld: DatumField) -> dict:
    """Elevation-versus-distance profile along a bench path: measured bench
    elevation, the regional datum, and the detected steps."""
    yy = np.clip(path_yx[:, 0].astype(int), 0, fld.z.shape[0] - 1)
    xx = np.clip(path_yx[:, 1].astype(int), 0, fld.z.shape[1] - 1)
    d = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(yy), np.diff(xx)))])
    st = fld.step[yy, xx].astype(np.float64)
    return dict(distance_km=(d * PIXEL_M / 1000.0),
                bench_elev_m=fld.z[yy, xx].astype(np.float64),
                isobase_m=fld.isobase[yy, xx].astype(np.float64),
                anomaly_m=fld.anomaly[yy, xx].astype(np.float64),
                step_m=st,
                step_azim_deg=fld.step_azim[yy, xx].astype(np.float64),
                slope_deg=fld.slope[yy, xx].astype(np.float64),
                flagged=st >= float(fld.meta["min_step_m"]))
