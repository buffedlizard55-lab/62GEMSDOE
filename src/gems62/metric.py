"""Distance-weighted Tversky index (DTI) for the DOE GEMS challenge.

The published metric uses a triangular distance kernel with 300 m support,
alpha=0.2 and beta=0.8.  This module keeps two exact paths:

* ``dti_binary`` uses Euclidean distance transforms for the binary rasters used
  by the lane's holdout and submission scripts.
* ``dti_components`` handles soft probabilities and arbitrary pixel sizes; its
  small-grid reference is ``brute_force_components``.

For every truth pixel, TP credit is the maximum prediction value times kernel
weight within the support.  FP credit is prediction mass times one minus its
best kernel match to any truth pixel.  FN is exactly truth mass minus TP credit.
Source: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, hypot

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA = 0.2
BETA = 0.8
RADIUS_PX = 3.0
PIXEL_M = 100.0
RADIUS_M = RADIUS_PX * PIXEL_M
EPS = 1e-12


@dataclass(frozen=True)
class Components:
    """Weighted components and their resulting DTI."""

    tp_w: float
    fp_w: float
    fn_w: float
    dti: float

    def as_dict(self) -> dict[str, float]:
        return {"TPw": self.tp_w, "FPw": self.fp_w, "FNw": self.fn_w, "DTI": self.dti}


@dataclass(frozen=True)
class Precomputed:
    """Truth-derived fields reusable across predictions."""

    truth: np.ndarray
    k_to_truth: np.ndarray

    @classmethod
    def build(cls, truth: np.ndarray, *, radius_m: float = RADIUS_M,
              pixel_size_m: float | tuple[float, float] = PIXEL_M) -> "Precomputed":
        t = np.asarray(truth, dtype=bool)
        row_m, col_m = _pixel_pair(pixel_size_m)
        if t.any():
            distance = distance_transform_edt(~t, sampling=(row_m, col_m))
        else:
            distance = np.full(t.shape, np.inf, dtype=np.float64)
        return cls(truth=t, k_to_truth=kernel(distance, radius_m))


def _pixel_pair(pixel_size_m: float | tuple[float, float]) -> tuple[float, float]:
    values = np.asarray(pixel_size_m, dtype=np.float64).reshape(-1)
    if values.size == 1:
        row_m = col_m = float(values[0])
    elif values.size == 2:
        row_m, col_m = map(float, values)
    else:
        raise ValueError("pixel_size_m must be a scalar or (row, column) pair")
    if not np.isfinite([row_m, col_m]).all() or row_m <= 0 or col_m <= 0:
        raise ValueError("pixel dimensions must be finite and positive")
    return row_m, col_m


def kernel(distance_m: np.ndarray | float, radius_m: float = RADIUS_M) -> np.ndarray:
    """Triangular kernel ``max(1 - distance/radius, 0)`` (distance in metres)."""
    if not np.isfinite(radius_m) or radius_m <= 0:
        raise ValueError("radius_m must be finite and positive")
    return np.maximum(1.0 - np.asarray(distance_m, dtype=np.float64) / radius_m, 0.0)


def dti_from_components(tp: float, fp: float, fn: float,
                        alpha: float = ALPHA, beta: float = BETA,
                        epsilon: float = EPS) -> float:
    """Apply the published Tversky formula to already-computed components."""
    values = np.asarray([tp, fp, fn, alpha, beta, epsilon], dtype=np.float64)
    if not np.isfinite(values).all() or min(tp, fp, fn, alpha, beta) < 0 or epsilon < 0:
        raise ValueError("DTI components and weights must be finite and non-negative")
    denominator = tp + alpha * fp + beta * fn + epsilon
    return float(tp / denominator) if denominator > 0 else 0.0


def _offsets(radius_m: float, row_m: float, col_m: float) -> tuple[tuple[int, int, float], ...]:
    reach_y = int(ceil(radius_m / row_m))
    reach_x = int(ceil(radius_m / col_m))
    out: list[tuple[int, int, float]] = []
    for dy in range(-reach_y, reach_y + 1):
        for dx in range(-reach_x, reach_x + 1):
            weight = float(kernel(hypot(dy * row_m, dx * col_m), radius_m))
            if weight > 0.0:
                out.append((dy, dx, weight))
    return tuple(out)


def _shift(values: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Sample ``values[y+dy, x+dx]`` at every output cell; off-grid is zero."""
    h, w = values.shape
    out = np.zeros((h, w), dtype=np.float64)
    y0, y1 = max(0, -dy), min(h, h - dy)
    x0, x1 = max(0, -dx), min(w, w - dx)
    if y0 < y1 and x0 < x1:
        out[y0:y1, x0:x1] = values[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
    return out


def dti_components(
    prediction: np.ndarray,
    truth: np.ndarray | None = None,
    *,
    valid: np.ndarray | None = None,
    pixel_size_m: float | tuple[float, float] = PIXEL_M,
    radius_m: float = RADIUS_M,
    alpha: float = ALPHA,
    beta: float = BETA,
    epsilon: float = EPS,
    precomputed: Precomputed | None = None,
) -> Components:
    """Compute exact DTI components for soft predictions.

    Predictions outside ``valid`` are ignored.  Values inside ``valid`` must be
    finite and in [0, 1].  ``truth`` is binary; alternatively, provide a
    ``Precomputed`` object built from the same truth grid.
    """
    pred = np.asarray(prediction, dtype=np.float64)
    if pred.ndim != 2:
        raise ValueError("prediction must be 2-D")
    if valid is None:
        valid_mask = np.ones(pred.shape, dtype=bool)
    else:
        valid_mask = np.asarray(valid, dtype=bool)
        if valid_mask.shape != pred.shape:
            raise ValueError("valid mask shape must match prediction")
    if not np.isfinite(pred[valid_mask]).all():
        raise ValueError("prediction has non-finite values inside the scored footprint")
    if ((pred[valid_mask] < 0.0) | (pred[valid_mask] > 1.0)).any():
        raise ValueError("prediction has values outside [0,1] inside the scored footprint")

    row_m, col_m = _pixel_pair(pixel_size_m)
    p = np.where(valid_mask, pred, 0.0)
    if precomputed is None:
        if truth is None:
            raise ValueError("truth is required unless precomputed is supplied")
        truth_mask = np.asarray(truth, dtype=bool)
        if truth_mask.shape != pred.shape:
            raise ValueError("truth mask shape must match prediction")
        precomputed = Precomputed.build(truth_mask & valid_mask, radius_m=radius_m,
                                        pixel_size_m=(row_m, col_m))
    elif precomputed.truth.shape != pred.shape or precomputed.k_to_truth.shape != pred.shape:
        raise ValueError("precomputed truth fields must match prediction shape")
    else:
        truth_mask = precomputed.truth & valid_mask
        if not np.array_equal(truth_mask, precomputed.truth):
            precomputed = Precomputed.build(truth_mask, radius_m=radius_m,
                                            pixel_size_m=(row_m, col_m))

    fp = float(np.sum(p * (1.0 - precomputed.k_to_truth)))
    g = precomputed.truth
    if not g.any():
        return Components(0.0, fp, 0.0,
                          dti_from_components(0.0, fp, 0.0, alpha, beta, epsilon))

    best = np.zeros(pred.shape, dtype=np.float64)
    for dy, dx, weight in _offsets(radius_m, row_m, col_m):
        np.maximum(best, _shift(p, dy, dx) * weight, out=best)
    tp = float(best[g].sum())
    fn = float(g.sum()) - tp
    return Components(tp, fp, fn, dti_from_components(tp, fp, fn, alpha, beta, epsilon))


def dti(prediction: np.ndarray, truth: np.ndarray, **kwargs) -> float:
    """Convenience wrapper returning only DTI."""
    return dti_components(prediction, truth, **kwargs).dti


def brute_force_components(
    prediction: np.ndarray,
    truth: np.ndarray,
    *,
    pixel_size_m: float | tuple[float, float] = PIXEL_M,
    radius_m: float = RADIUS_M,
    alpha: float = ALPHA,
    beta: float = BETA,
    epsilon: float = EPS,
) -> Components:
    """Literal O(N_truth * N_prediction) reference implementation for tests."""
    p = np.asarray(prediction, dtype=np.float64)
    g = np.asarray(truth, dtype=bool)
    if p.ndim != 2 or g.shape != p.shape:
        raise ValueError("prediction and truth must be matching 2-D grids")
    if not np.isfinite(p).all() or ((p < 0.0) | (p > 1.0)).any():
        raise ValueError("prediction must be finite and in [0,1]")
    row_m, col_m = _pixel_pair(pixel_size_m)
    pred_y, pred_x = np.nonzero(p > 0)
    truth_y, truth_x = np.nonzero(g)

    tp = 0.0
    for gy, gx in zip(truth_y, truth_x):
        distances = np.hypot((pred_y - gy) * row_m, (pred_x - gx) * col_m)
        weights = kernel(distances, radius_m) * p[pred_y, pred_x]
        tp += float(weights.max()) if weights.size else 0.0

    fp = 0.0
    for py, px in zip(pred_y, pred_x):
        distances = np.hypot((truth_y - py) * row_m, (truth_x - px) * col_m)
        best_kernel = float(kernel(distances, radius_m).max()) if distances.size else 0.0
        fp += float(p[py, px]) * (1.0 - best_kernel)
    fn = float(truth_y.size) - tp
    return Components(tp, fp, fn,
                      dti_from_components(tp, fp, fn, alpha, beta, epsilon))


def dti_binary(pred_bool: np.ndarray, truth: np.ndarray,
               active: np.ndarray | None = None) -> dict:
    """Fast exact DTI for binary prediction/truth masks on the 100 m grid.

    ``active`` is the evaluated domain.  Pixels outside it are removed from
    both prediction and truth, matching the competition's catalogue mask rule.
    """
    pred = np.asarray(pred_bool, dtype=bool)
    g0 = np.asarray(truth, dtype=bool)
    if pred.ndim != 2 or g0.shape != pred.shape:
        raise ValueError("prediction and truth must be matching 2-D grids")
    act = np.ones(pred.shape, dtype=bool) if active is None else np.asarray(active, dtype=bool)
    if act.shape != pred.shape:
        raise ValueError("active mask shape must match prediction")
    p = pred & act
    g = g0 & act
    n = int(g.sum())
    if not g.any():
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0,
                    n_active_pred=int(p.sum()), dti=0.0)
    if not p.any():
        return dict(tp=0.0, fp=0.0, fn=float(n), n_truth=n,
                    n_active_pred=0, dti=0.0)
    dp = distance_transform_edt(~p)
    tp = float(kernel(dp[g] * PIXEL_M, RADIUS_M).sum())
    fn = float(n) - tp
    dg = distance_transform_edt(~g)
    fp = float((1.0 - kernel(dg[p] * PIXEL_M, RADIUS_M)).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, n_active_pred=int(p.sum()),
                dti=dti_from_components(tp, fp, fn))


def dti_bruteforce(prediction: np.ndarray, truth: np.ndarray, **kwargs) -> dict:
    """Backward-compatible dictionary wrapper around ``brute_force_components``."""
    c = brute_force_components(prediction, truth, **kwargs)
    return {"tp": c.tp_w, "fp": c.fp_w, "fn": c.fn_w, "dti": c.dti}


def marginal_bar(current_dti: float, alpha: float = ALPHA) -> float:
    """Minimum realized kernel credit ``k`` for an added non-redundant unit dot.

    The exact marginal condition is ``k > alpha * current_dti``.  This is an
    accounting identity, not a prediction of an organizer score.
    """
    if not np.isfinite(current_dti) or not 0 <= current_dti <= 1:
        raise ValueError("current_dti must be finite and in [0,1]")
    if not np.isfinite(alpha) or alpha < 0:
        raise ValueError("alpha must be finite and non-negative")
    return float(alpha * current_dti)


def maximum_useful_distance_m(dti_value: float, radius_m: float = RADIUS_M,
                              alpha: float = ALPHA) -> float:
    """Distance at which the triangular kernel reaches the marginal credit bar.

    A non-redundant unit dot improves DTI exactly when ``k > alpha*DTI``;
    with ``k(d)=max(1-d/R,0)``, the corresponding distance is
    ``R * (1-alpha*DTI)``.
    """
    if not np.isfinite(dti_value) or not 0 <= dti_value <= 1:
        raise ValueError("dti_value must be finite and in [0,1]")
    if not np.isfinite(radius_m) or radius_m < 0 or not np.isfinite(alpha) or alpha < 0:
        raise ValueError("radius_m and alpha must be finite and non-negative")
    return float(radius_m * (1.0 - alpha * dti_value))


def unit_dot_dti(n_dots: int, mean_credit: float, truth_mass: float,
                 alpha: float = ALPHA, beta: float = BETA) -> float:
    """Closed-form DTI for non-overlapping unit-valued dots with mean credit.

    This is a planning identity, not a score.  It assumes ``FP_w=n_dots-TP_w``
    and ``FN_w=truth_mass-TP_w``; use the exact evaluator when kernels overlap.
    """
    if n_dots <= 0:
        return 0.0
    vals = np.asarray([mean_credit, truth_mass, alpha, beta], dtype=np.float64)
    if not np.isfinite(vals).all() or mean_credit < 0 or min(truth_mass, alpha, beta) < 0:
        raise ValueError("mean_credit, truth_mass, alpha and beta must be valid")
    tp = mean_credit * n_dots
    # Closed-form planning approximation under FP ~= M - T and FN = G - T.
    # Exact TP_w per emitted pixel can exceed one when neighboring truth pixels
    # share a prediction, so do not impose a per-dot [0,1] bound on this aggregate.
    denominator = tp + alpha * (n_dots - tp) + beta * (truth_mass - tp)
    return float(tp / denominator) if denominator > 0 else 0.0


def credit_audit(mask: np.ndarray) -> dict:
    """Structure-only audit of spacing/redundancy in an emitted binary mask."""
    m = np.asarray(mask, dtype=bool)
    if m.ndim != 2:
        raise ValueError("mask must be 2-D")
    pos = m
    n = int(pos.sum())
    if n == 0:
        return dict(n_emitted=0, total_mass=0.0, redundancy_fraction=0.0,
                    mean_self_kernel=0.0)
    dy, dx = np.mgrid[-3:4, -3:4]
    offsets = [(int(a), int(b)) for a, b in zip(dy.ravel(), dx.ravel())
               if (a, b) != (0, 0) and np.hypot(a, b) <= RADIUS_PX]
    best = np.zeros(m.shape, dtype=np.float32)
    h, w = m.shape
    for oy, ox in offsets:
        shifted = np.zeros(m.shape, dtype=np.float32)
        y0, y1 = max(0, oy), min(h, h + oy)
        x0, x1 = max(0, ox), min(w, w + ox)
        if y0 < y1 and x0 < x1:
            shifted[y0:y1, x0:x1] = m[max(0, -oy):min(h, h - oy),
                                      max(0, -ox):min(w, w - ox)]
        np.maximum(best, shifted * float(kernel(np.hypot(oy, ox), RADIUS_PX)), out=best)
    return dict(n_emitted=n, total_mass=float(n),
                redundancy_fraction=float((best[pos] > 0).mean()),
                mean_self_kernel=float(best[pos].mean()))


def implied_truth_mass(dti_value: float, T: float, S: float, M: float,
                       alpha: float = ALPHA, beta: float = BETA) -> float:
    """Invert the algebraic DTI identity for truth mass; this is a model quantity."""
    if dti_value <= 0 or beta <= 0:
        raise ValueError("dti_value and beta must be positive")
    return float((T / dti_value - alpha * T - alpha * (S - M)) / beta)
