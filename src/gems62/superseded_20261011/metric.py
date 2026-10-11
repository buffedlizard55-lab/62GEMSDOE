"""Exact implementation of the GEMS distance-weighted Tversky index (DTI).

Transcribed from the competition problem description
(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/),
section "# Performance metric":

    k(d)          = max(1 - d / 300 m, 0)                      triangular kernel
    TI(a, b)      = S_TP / (S_TP + a*S_FP + b*S_FN)            plain Tversky form
    TP_w          = sum_{g in G} max_{x: d(x,g) <= R} p(x) * k(d(x,g))
    FP_w          = sum_{x: p(x) > 0} p(x) * [1 - max_{g in G} k(d(x,g))]
    FN_w          = sum_{g in G} [1 - max_{x: d(x,g) <= R} p(x) * k(d(x,g))]
    DTI(a, b)     = TP_w / (TP_w + a*FP_w + b*FN_w + eps),   a = 0.2, b = 0.8

Two identity checks are enforced by ``tests/test_metric.py``:

1. The official worked example: TP_w = 3.00, FP_w = 1.89, FN_w = 2.00 gives
   ``3.00 / (3.00 + 0.2*1.89 + 0.8*2.00) = 0.60266...`` (the page rounds to 0.60).
2. The 1x5 counterexample from the sibling repository's metric-erratum: truth at
   columns 1 and 2, one binary prediction at column 1, 1 m pixels, R = 3 m. Then
   TP_w = 1 + 2/3 = 5/3, FP_w = 0, FN_w = 1/3 and DTI = 25/29 = 0.8620689...

Note on the two axes: ``TP_w`` is *truth-centred* (a maximum over predictions for
each truth pixel) while ``FP_w`` is *prediction-centred* (a maximum over truth for
each prediction pixel).  They are not the same quantity and must never be
substituted for one another.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, hypot

import numpy as np
from scipy.ndimage import distance_transform_edt

RADIUS_M = 300.0
ALPHA = 0.2
BETA = 0.8
EPS = 1e-12


@dataclass(frozen=True)
class Components:
    tp_w: float
    fp_w: float
    fn_w: float
    dti: float

    def as_dict(self) -> dict:
        return {"TPw": self.tp_w, "FPw": self.fp_w, "FNw": self.fn_w, "DTI": self.dti}


def _offsets(radius_m: float, pixel_m: float) -> tuple[tuple[int, int, float], ...]:
    reach = int(ceil(radius_m / pixel_m))
    out = []
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            d = hypot(dy * pixel_m, dx * pixel_m)
            w = max(1.0 - d / radius_m, 0.0)
            if w > 0.0:
                out.append((dy, dx, float(w)))
    return tuple(out)


def _shift(values: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Return ``values[y+dy, x+dx]`` sampled at ``(y, x)``; zero outside the grid.

    The sampled offset set is symmetric under ``(dy, dx) -> (-dy, -dx)`` with equal
    weights, so the *maximum* over the set is invariant under a sign convention
    flip; the sign is nevertheless pinned here because the same helper is used by
    the diagnostic line-sampling code, where it is not symmetric.
    """
    arr = np.asarray(values)
    h, w = arr.shape
    out = np.zeros(arr.shape, dtype=np.float64)
    y0, y1 = max(0, -dy), min(h, h - dy)
    x0, x1 = max(0, -dx), min(w, w - dx)
    if y0 < y1 and x0 < x1:
        out[y0:y1, x0:x1] = arr[y0 + dy : y1 + dy, x0 + dx : x1 + dx]
    return out


def kernel(distance_m: np.ndarray | float, radius_m: float = RADIUS_M) -> np.ndarray:
    """Triangular credit ``max(1 - d/radius, 0)``."""
    return np.maximum(1.0 - np.asarray(distance_m, dtype=np.float64) / radius_m, 0.0)


def dti_components(
    prediction: np.ndarray,
    truth: np.ndarray | None = None,
    *,
    valid: np.ndarray | None = None,
    pixel_size_m: float | tuple[float, float] = 100.0,
    radius_m: float = RADIUS_M,
    alpha: float = ALPHA,
    beta: float = BETA,
    epsilon: float = EPS,
    precomputed: "Precomputed | None" = None,
) -> Components:
    """Exact DTI and its three weighted components.

    ``truth`` is a boolean/0-1 array (ignored when ``precomputed`` is supplied).
    ``valid`` is the scored footprint.  Non-finite or out-of-range predictions
    inside ``valid`` raise, matching the competition's [0, 1] requirement.
    """
    pred = np.asarray(prediction, dtype=np.float64)
    if pred.ndim != 2:
        raise ValueError("prediction must be 2-D")
    if valid is None:
        valid = np.ones(pred.shape, dtype=bool)
    else:
        valid = np.asarray(valid, dtype=bool)
        if valid.shape != pred.shape:
            raise ValueError("valid mask shape must match prediction")

    if np.any(~np.isfinite(pred[valid])):
        raise ValueError("prediction has non-finite values inside the scored footprint")
    if np.any((pred[valid] < 0.0) | (pred[valid] > 1.0)):
        raise ValueError("prediction has values outside [0,1] inside the scored footprint")

    p = np.where(valid, pred, 0.0)

    row_m = col_m = float(np.asarray(pixel_size_m).reshape(-1)[0])

    if precomputed is None:
        if truth is None:
            raise ValueError("truth is required unless precomputed is supplied")
        g = np.asarray(truth).astype(bool) & valid
        precomputed = Precomputed.build(g, radius_m=radius_m, pixel_m=row_m)

    # --- FP_w: prediction-centred, uses the distance from each prediction to truth
    fp = float(np.sum(p * (1.0 - precomputed.k_to_truth)))

    if not precomputed.truth.any():
        return Components(0.0, fp, 0.0, 0.0 / (0.0 + alpha * fp + epsilon))

    # --- TP_w / FN_w: truth-centred, a maximum over predictions for each truth cell
    offsets = _offsets(radius_m, row_m)
    best = np.zeros(p.shape, dtype=np.float64)
    for dy, dx, w in offsets:
        np.maximum(best, _shift(p, dy, dx) * w, out=best)

    tp = float(best[precomputed.truth].sum())
    fn = float(precomputed.truth.sum() - tp)
    denom = tp + alpha * fp + beta * fn + epsilon
    return Components(tp, fp, fn, tp / denom)


@dataclass(frozen=True)
class Precomputed:
    """Truth-mask-derived fields that do not depend on the prediction."""

    truth: np.ndarray
    k_to_truth: np.ndarray

    @classmethod
    def build(cls, truth: np.ndarray, *, radius_m: float = RADIUS_M, pixel_m: float = 100.0) -> "Precomputed":
        t = np.asarray(truth).astype(bool)
        d = distance_transform_edt(~t, sampling=(pixel_m, pixel_m)) if t.any() else np.full(t.shape, np.inf)
        return cls(truth=t, k_to_truth=kernel(d, radius_m))


def dti(prediction: np.ndarray, truth: np.ndarray, **kw) -> float:
    return dti_components(prediction, truth, **kw).dti


def brute_force_components(
    prediction: np.ndarray,
    truth: np.ndarray,
    *,
    pixel_size_m: float = 100.0,
    radius_m: float = RADIUS_M,
    alpha: float = ALPHA,
    beta: float = BETA,
) -> Components:
    """O(N_truth * N_pred) reference implementation used only to test the fast path."""
    p = np.asarray(prediction, dtype=np.float64)
    g = np.asarray(truth).astype(bool)
    yy, xx = np.nonzero(p > 0)
    py, px = np.nonzero(g)
    tp = 0.0
    for y, x in zip(py, px):
        d = np.hypot((yy - y) * pixel_size_m, (xx - x) * pixel_size_m)
        w = kernel(d, radius_m) * p[yy, xx]
        tp += float(w.max()) if w.size else 0.0
    if py.size:
        fp = 0.0
        for y, x in zip(yy, xx):
            d = np.hypot((py - y) * pixel_size_m, (px - x) * pixel_size_m)
            fp += float(p[y, x] * (1.0 - kernel(d, radius_m).max()))
    else:
        fp = float(p.sum())
    fn = float(py.size - tp)
    return Components(tp, fp, fn, tp / (tp + alpha * fp + beta * fn + EPS))


def maximum_useful_distance_m(dti_value: float, radius_m: float = RADIUS_M, alpha: float = ALPHA) -> float:
    """Distance beyond which appending one unit dot *lowers* the index.

    From the published definitions with ``FN_w = G - T``:

        DTI = T / (T + alpha*FP_w + beta*(G - T))

    Appending one unit dot that carries truth-credit ``c`` and raises the
    prediction-centred false-positive mass by ``1 - c`` changes the index by a
    factor proportional to ``c*(alpha*M + beta*G) - alpha*T``, where ``M`` is the
    emitted mass.  The dot is therefore profitable exactly when
    ``c > alpha * DTI``: it must sit within ``R * (1 - alpha * DTI)`` of a truth
    pixel.  At ``DTI = 0.28`` the bar is ``c > 0.056``, i.e. 283 m.

    This is the marginal rule used to choose the dot spacing and the catalogue
    exclusion radius; it is an *accounting* identity, not a claim about geology.
    """
    return radius_m * (1.0 - alpha * dti_value)


def unit_dot_dti(n_dots: int, mean_credit: float, truth_mass: float,
                 alpha: float = ALPHA, beta: float = BETA) -> float:
    """Closed form for non-overlapping unit dots.

    With ``T = mean_credit * n_dots`` and ``FP_w = n_dots - T`` (exact when no
    dot's 300 m kernel overlaps another dot, and the small-angle form otherwise),
    and using ``alpha + beta = 1``:

        DTI = mean_credit / (alpha + beta * truth_mass / n_dots)

    The two consequences that drive this repository's emission design:

    * for a fixed ``mean_credit``, DTI *increases* with ``n_dots`` -- emitting more
      dots on real structure always helps, so coverage beats pruning at equal
      placement quality;
    * for a fixed mass, DTI is *linear* in ``mean_credit`` -- placement quality is
      the only lever that can move the index at constant ``n_dots``.
    """
    if n_dots <= 0:
        return 0.0
    return mean_credit / (alpha + beta * truth_mass / n_dots)
