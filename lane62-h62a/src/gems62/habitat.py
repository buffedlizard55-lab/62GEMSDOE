"""Habitat weighting derived only from the *visible* catalogue.

The lane detector itself uses no catalogue information.  The emission
*prioritisation* does: dots are ranked by how fault-rich their topographic
habitat is.  Under the hide-and-recover holdout that ranking must be rebuilt
from the visible faults only, or the withheld segments leak in through the
weights.  This module is that rebuild, and it is the same function used at
final emission time (with the full visible catalogue = all mapped faults), so
there is no train/serve skew.

Habitat = 2-D binning of (topographic position index, detrended-elevation
slope).  The measured enrichment in the full catalogue, which is what makes
this the right habitat for the lane, is

    tpi < -200 m   x slope 10-15 deg   ->  3.16x footprint mean
    tpi < -200 m   x slope 15-25 deg   ->  3.21x
    tpi < -200 m   x slope  6-10 deg   ->  2.33x
    tpi -200..-120 x slope  6-10 deg   ->  2.31x
    tpi -200..-120 x slope 10-15 deg   ->  2.32x
    tpi -200..-120 x slope 15-25 deg   ->  2.33x
    tpi >  +120 m  x any slope         ->  0.28-0.34x  (range crests: depleted)

(see ``evidence/lane_enrichment.json``).  Negative topographic position with a
scarp-scale slope *is* the pluvial-lake margin: the basin-side toe of a range
front, which is precisely where a Lake Lahontan shoreline bench is cut and
where a fault that offsets it will show.
"""

from __future__ import annotations

import numpy as np

TPI_EDGES = np.array([-1e9, -300, -200, -120, -60, -20, 20, 60, 120, 1e9])
SLOPE_EDGES = np.array([-1e9, 1.0, 3.0, 6.0, 10.0, 15.0, 25.0, 35.0, 1e9])
PRIOR_COUNT = 40.0          # Laplace smoothing: pseudo-counts per bin


def bin_index(x: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.digitize(x, edges[1:-1]), 0, len(edges) - 2)


def habitat_enrichment(tpi: np.ndarray, slope: np.ndarray, positives: np.ndarray,
                       support: np.ndarray, prior_count: float = PRIOR_COUNT) -> np.ndarray:
    """Per-pixel multiplicative enrichment weight from a visible-fault catalogue.

    Returns a float field >= 0 whose value at a pixel is the smoothed fault
    rate of that pixel's (TPI, slope) habitat divided by the smoothed global
    rate.  Bins with no support get weight 0 rather than a fabricated value.
    """
    out = np.zeros(tpi.shape, np.float64)
    ib = bin_index(tpi, TPI_EDGES)
    js = bin_index(slope, SLOPE_EDGES)
    valid = support & np.isfinite(tpi) & np.isfinite(slope)
    if not valid.any() or not positives.any():
        return out
    nb, ns = len(TPI_EDGES) - 1, len(SLOPE_EDGES) - 1
    flat = (ib * ns + js)
    fv = flat[valid]
    pv = (positives & valid).astype(np.float64)
    cnt = np.bincount(fv, minlength=nb * ns).astype(np.float64)
    pos_cnt = np.bincount(fv, weights=pv[valid], minlength=nb * ns)
    base = pos_cnt.sum() / max(cnt.sum(), 1.0)
    rate = (pos_cnt + prior_count * base) / (cnt + prior_count)
    w = rate / base if base > 0 else np.zeros_like(rate)
    out[valid] = w[flat[valid]]
    return out


def enrichment_table(tpi: np.ndarray, slope: np.ndarray, positives: np.ndarray,
                     footprint: np.ndarray) -> dict:
    """The diagnostic table quoted in this module's docstring, recomputed live."""
    ib = bin_index(tpi, TPI_EDGES)
    js = bin_index(slope, SLOPE_EDGES)
    valid = footprint & np.isfinite(tpi) & np.isfinite(slope)
    base = float((positives & footprint).sum()) / max(int(footprint.sum()), 1)
    rows = []
    nb, ns = len(TPI_EDGES) - 1, len(SLOPE_EDGES) - 1
    for i in range(nb):
        for j in range(ns):
            m = valid & (ib == i) & (js == j)
            n = int(m.sum())
            if n == 0:
                continue
            k = int((positives & m).sum())
            rows.append(dict(tpi_lo=float(TPI_EDGES[i]), tpi_hi=float(TPI_EDGES[i + 1]),
                             slope_lo=float(SLOPE_EDGES[j]), slope_hi=float(SLOPE_EDGES[j + 1]),
                             px=n, positives=k, rate=k / n,
                             enrichment=(k / n) / base if base > 0 else None))
    rows.sort(key=lambda r: -(r["enrichment"] or 0))
    return dict(base_rate=base, n_footprint=int(footprint.sum()),
                n_positives=int((positives & footprint).sum()), cells=rows)
