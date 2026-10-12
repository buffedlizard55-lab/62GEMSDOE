"""One place where ARRAY axes and WORLD axes are related -- with signs, once, and tested.

Why this module exists
----------------------
Every raster in this repository is a north-up GeoTIFF: **column index increases east (+x)**
and **row index increases south (-y)**.  Two separate defects in the datum lane came from
mixing those axes rather than stating them once:

* ``IR-62-J-01`` -- ``datum.datum_step_loci`` measured the datum offset by sampling the
  residual field at ``row +- h*u_x`` and ``col +- h*u_y``, i.e. the *east* component drove the
  north-south shift and vice versa (an axis swap = reflection about the NE-SW diagonal).  On a
  scarp striking N-S or E-W the sampled direction is exactly **along** the scarp, so the
  measured offset is ~0 and the detector is structurally blind to those strikes.
* ``IR-62-J-02`` -- ``datum.ScarpField.from_dem`` built the along-strike vector as
  ``(-g_y, g_x)`` from a ``g_y`` that is itself ``-dz/dy``, i.e. the east component carried the
  wrong sign: a reflection of the strike about the E-W axis, ``azimuth -> 180 - azimuth``.
  A NW-striking (135 deg) trace was therefore walked at 45 deg (NE) -- up to 90 deg off --
  which is why seeded traces died immediately and the shipped v8 emission carries only
  1,660 dots.

The rule used throughout: do the arithmetic in **array coordinates**, where
``dzdr = dz/d(row)`` and ``dzdc = dz/d(col)`` are unambiguous, and convert to a compass azimuth
only at the end with :func:`azimuth_from_drc`.

Compass convention: azimuth in degrees clockwise from north, in [0, 180) for a line (strike).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

__all__ = ["grad_arr", "unit_ascent", "azimuth_from_drc", "strike_azimuth_from_ascent",
           "shift_by_unit", "offset_pair", "linearity"]


def grad_arr(f: np.ndarray, res: float) -> tuple[np.ndarray, np.ndarray]:
    """Horn 3x3 gradient in ARRAY axes: returns (dz/dr, dz/dc), in units of f per metre.

    ``dz/dr`` is positive where the field *rises toward the south*; ``dz/dc`` is positive where
    it rises toward the east.  No world-axis sign is introduced here -- that is the point.
    """
    p = np.pad(np.asarray(f, np.float32), 1, mode="edge")
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, _ = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    # rows: a,b,c = north row; g,h,i = south row.  columns: a,d,g = west; c,f,i = east.
    dzdc = ((c + 2 * p[1:-1, 2:] + i) - (a + 2 * d + g)) / (8.0 * res)
    dzdr = ((g + 2 * h + i) - (a + 2 * b + c)) / (8.0 * res)
    return dzdr.astype(np.float32), dzdc.astype(np.float32)


def unit_ascent(dzdr: np.ndarray, dzdc: np.ndarray, *, eps: float = 1e-12
                ) -> tuple[np.ndarray, np.ndarray]:
    """Unit vector of steepest *ascent* in array axes, as (u_row, u_col)."""
    m = np.hypot(dzdr, dzdc) + eps
    return dzdr / m, dzdc / m


def azimuth_from_drc(drow: np.ndarray | float, dcol: np.ndarray | float) -> np.ndarray | float:
    """Compass azimuth (deg from north, clockwise, unnormalised) of an array-space vector.

    North is -row, east is +col, so ``az = atan2(dcol, -drow)``.
    """
    return np.degrees(np.arctan2(dcol, -drow))


def strike_azimuth_from_ascent(az_ascent: np.ndarray | float) -> np.ndarray | float:
    """Strike of the contour/line crossing the ascent direction, folded to [0, 180)."""
    return (az_ascent + 90.0) % 180.0


def shift_by_unit(f: np.ndarray, u_row: np.ndarray, u_col: np.ndarray,
                  metres: float, res: float, *, order: int = 1,
                  mode: str = "nearest") -> np.ndarray:
    """Bilinear sample of ``f`` displaced by ``metres`` along the unit field ``(u_row, u_col)``.

    Positive ``metres`` walks *with* the unit field, negative walks against it; because the
    displacement is supplied in ARRAY axes there is no sign convention left to get wrong.
    """
    rows, cols = np.indices(f.shape, dtype=np.float32)
    k = np.float32(metres / res)
    return ndimage.map_coordinates(f, [rows + k * u_row, cols + k * u_col], order=order,
                                   mode=mode, cval=0.0).astype(np.float32)


def offset_pair(f: np.ndarray, u_row: np.ndarray, u_col: np.ndarray, half_m: float, res: float
                ) -> tuple[np.ndarray, np.ndarray]:
    """``f`` sampled at +-``half_m`` along the unit field: returns (plus, minus)."""
    return (shift_by_unit(f, u_row, u_col, +abs(half_m), res),
            shift_by_unit(f, u_row, u_col, -abs(half_m), res))


def linearity(field: np.ndarray, res: float, *, sigma_m: float,
               anisotropy: tuple[float, float] | None = None) -> np.ndarray:
    """Isotropic evidence that a *linear* feature exists: magnitude of the smoothed field's
    ridge, normalised by its 99.5th percentile, in [0, 1].

    ``anisotropy`` optionally multiplies in the second-order orientation order parameter
    ``R = |<w e^{2 i theta}>| / <w>`` over a window of the given size in metres, which is the
    repository's standing test for "several samples agree there is a line *and* on its strike".
    """
    g = ndimage.gaussian_filter(field, sigma_m / res)
    if anisotropy is None:
        out = g
    else:
        win = max(1, int(round(anisotropy[0] / res)))
        out = g * (ndimage.uniform_filter(np.abs(g), size=win) > 0)
    s = float(np.percentile(out, 99.5)) if out.size else 0.0
    return np.clip(out / (s if s > 0 else 1.0), 0.0, 1.0).astype(np.float32)


# ---- legacy (WRONG) mappings, kept so that shipped artifacts stay reproducible -------------
def legacy_swap_ascent(dzdx: np.ndarray, dzdy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """IR-62-J-01 as shipped: (row, col) components built from (east, north) without swapping.

    Given the ``(g_x, g_y)`` pair returned by ``datum.gradient`` -- where ``g_y`` is
    ``-dz/dy`` -- the v8 detector used ``u_row = g_x/|g|`` and ``u_col = g_y/|g|``.
    """
    m = np.hypot(dzdx, dzdy) + 1e-12
    return dzdx / m, dzdy / m
