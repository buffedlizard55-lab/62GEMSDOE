"""Distance-Weighted Tversky Index (DTI) for the DOE GEMS Prize Challenge.

Metric definition transcribed from the official problem description
(DrivenData competition 306, page 967) and cross-checked against the shared
family implementation in ``57GEMSDOE/src/gems57/metric.py`` (cloned from
<https://github.com/buffedlizard55-lab/57GEMSDOE>).  The arithmetic is the
group's shared contract; this copy exists so the 61GEMSDOE lane is runnable
standalone, and ``tests/test_metric.py`` re-derives every identity from the
published formula.

Definitions
-----------
Triangular kernel, radius R = 300 m = 3 px at the 100 m grid::

    k(d) = max(1 - d / R, 0)

Components (G = truth pixels, P = predicted pixels, p(x) = predicted value)::

    TP_w = sum_{g in G} max_{x : d(x,g) <= R} p(x) * k(d(x,g))
    FP_w = sum_{x : p(x) > 0} p(x) * [1 - max_{g in G} k(d(x,g))]
    FN_w = |G| - TP_w
    DTI  = TP_w / (TP_w + alpha*FP_w + beta*FN_w)      alpha = 0.2, beta = 0.8

Known (mapped catalogue) pixels are removed from the scored domain: the
organiser masks them out of every term, so a prediction placed on a mapped
fault is worthless, and it cannot radiate credit into the scored domain.

Two exact consequences used by the emitter
------------------------------------------
1. **Binary beats calibrated.**  For a support scaled by lambda in (0,1],
   ``DTI(lambda) = lambda*T / (alpha*lambda*(T+F) + 0.8*G)`` and
   ``dDTI/dlambda = 0.8*T*G / (...)**2 > 0``: a graded probability map is
   strictly dominated by its own thresholded support.
2. **Marginal inclusion.**  Adding a dot whose nearest-truth kernel credit is
   ``k`` and whose marginal truth credit is ``dT`` raises DTI iff
   ``(T + dT)/(D + alpha*(dT + 1 - k)) > T/D``.  For a non-redundant dot
   (``dT == k``) this reduces to ``k > alpha*s/(1 - alpha*s)``, i.e. at the
   current public-leader level ``s = 0.3195`` a dot pays for itself only inside
   ~280 m.  :func:`marginal_accept` implements the exact two-sided test.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA: float = 0.2
BETA: float = 0.8
RADIUS_PX: float = 3.0      # 300 m at the 100 m competition grid
PIXEL_M: float = 100.0
R_M: float = RADIUS_PX * PIXEL_M
EPS: float = 1e-12


def kernel(d, radius: float = RADIUS_PX) -> np.ndarray:
    """Triangular kernel ``max(1 - d/R, 0)``; ``d`` in pixels."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def offsets(radius: float = RADIUS_PX) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """All lattice offsets with non-zero kernel weight, and their weights."""
    r = int(np.ceil(radius))
    dy, dx, kw = [], [], []
    for j in range(-r, r + 1):
        for i in range(-r, r + 1):
            k = float(kernel(np.hypot(j, i), radius))
            if k > 0.0:
                dy.append(j)
                dx.append(i)
                kw.append(k)
    return np.array(dy, np.int64), np.array(dx, np.int64), np.array(kw, np.float64)


OFF_DY, OFF_DX, OFF_K = offsets()


def marginal_inclusion_threshold(current_dti: float, alpha: float = ALPHA) -> float:
    """Minimum realised kernel credit for one more **non-redundant** dot."""
    return alpha * float(current_dti) / (1.0 - alpha * float(current_dti))


def marginal_accept(dT: float, k_self: float, T: float, M: float, n: int,
                    K: float, alpha: float = ALPHA, beta: float = BETA) -> bool:
    """Exact test: does adding one dot raise DTI?

    ``dT`` is the increase in ``TP_w``; ``k_self`` is the dot's own
    ``max_g k(d(x,g))``; ``T``/``M``/``n`` are current totals; ``K = |G|``.
    Implemented by recomputing DTI before and after so it cannot drift from
    the metric.
    """
    D0 = alpha * (T + n - M) + beta * K + EPS
    D1 = alpha * (T + dT + (n + 1) - (M + k_self)) + beta * K + EPS
    return (T + dT) / D1 > T / D0


def dti_from_components(tp: float, fp: float, fn: float,
                        alpha: float = ALPHA, beta: float = BETA) -> float:
    return float(tp / (tp + alpha * fp + beta * fn + EPS))


def dti_binary(pred_bool, truth, valid=None, known=None,
               alpha: float = ALPHA, beta: float = BETA) -> dict:
    """Exact DTI for a binary prediction field via Euclidean distance transforms."""
    pred_bool = np.asarray(pred_bool, bool)
    truth = np.asarray(truth, bool)
    valid_ = np.ones(pred_bool.shape, bool) if valid is None else np.asarray(valid, bool)
    known_ = np.zeros(pred_bool.shape, bool) if known is None else np.asarray(known, bool)
    if pred_bool.shape != truth.shape or pred_bool.shape != valid_.shape:
        raise ValueError("grid shape mismatch")
    active = valid_ & ~known_
    p = pred_bool & active
    g = truth & active
    n = int(g.sum())
    n_emit = int(p.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(n_emit), fn=0.0, n_truth=0, n_emitted=n_emit,
                    dti=0.0, coverage=0.0)
    if n_emit == 0:
        return dict(tp=0.0, fp=0.0, fn=float(n), n_truth=n, n_emitted=0,
                    dti=0.0, coverage=0.0)
    dp = distance_transform_edt(~p)
    tp = float(kernel(dp[g]).sum())
    fn = float(n) - tp
    dg = distance_transform_edt(~g)
    fp = float((1.0 - kernel(dg[p])).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, n_emitted=n_emit,
                dti=dti_from_components(tp, fp, fn, alpha, beta), coverage=tp / n)


def max_cover(pred, truth):
    """Shared official-kernel primitives for soft predictions.

    Returns the per-truth-pixel credit (in the row-major order of
    ``np.nonzero(truth)``), the kernel credit at every prediction location,
    and the distance to the nearest truth pixel.
    """
    p = np.asarray(pred, np.float64)
    g = np.asarray(truth, bool)
    if p.ndim != 2 or p.shape != g.shape:
        raise ValueError("grid shape mismatch")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("predictions must be finite in [0,1]")
    yy, xx = np.nonzero(g)
    credit = np.zeros(len(yy), np.float64)
    h, w = p.shape
    for j, i, k in zip(OFF_DY, OFF_DX, OFF_K):
        ny, nx = yy + j, xx + i
        ok = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
        credit[ok] = np.maximum(credit[ok], p[ny[ok], nx[ok]] * k)
    dg = distance_transform_edt(~g) if len(yy) else np.full(p.shape, np.inf)
    return credit, kernel(dg), dg


def dti_exact(pred, truth, valid=None, known=None,
              alpha: float = ALPHA, beta: float = BETA) -> dict:
    """Exact DTI for arbitrary soft predictions in [0, 1] (max over the kernel)."""
    pred = np.asarray(pred, np.float64)
    truth = np.asarray(truth, bool)
    valid_ = np.ones(pred.shape, bool) if valid is None else np.asarray(valid, bool)
    known_ = np.zeros(pred.shape, bool) if known is None else np.asarray(known, bool)
    active = valid_ & ~known_
    vals = pred[active]
    if not np.isfinite(vals).all() or (vals < 0).any() or (vals > 1).any():
        raise ValueError("predictions inside the scored domain must be finite and in [0, 1]")
    p = np.where(active, pred, 0.0)
    g = active & truth
    yy, xx = np.nonzero(g)
    n = int(yy.size)
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0,
                    n_emitted=int((p > 0).sum()), dti=0.0, coverage=0.0)
    credit, q, _ = max_cover(p, g)
    tp = float(credit.sum())
    fn = float(n) - tp
    fp = float((p * (1.0 - q)).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, n_emitted=int((p > 0).sum()),
                dti=dti_from_components(tp, fp, fn, alpha, beta), coverage=tp / n)


def dti_bruteforce(pred, truth, alpha: float = ALPHA, beta: float = BETA,
                   radius: float = RADIUS_PX) -> dict:
    """Literal O(|G|*|P|) transcription of the published equations (unit-test oracle)."""
    pred = np.asarray(pred, float)
    truth = np.asarray(truth, bool)
    gs = np.argwhere(truth)
    xs = np.argwhere(pred > 0)
    tp = fn = 0.0
    for g in gs:
        best = 0.0
        for x in xs:
            d = float(np.hypot(*(x - g)))
            if d <= radius:
                best = max(best, pred[tuple(x)] * max(1.0 - d / radius, 0.0))
        tp += best
        fn += 1.0 - best
    fp = 0.0
    for x in xs:
        kmax = 0.0
        for g in gs:
            kmax = max(kmax, max(1.0 - float(np.hypot(*(x - g))) / radius, 0.0))
        fp += pred[tuple(x)] * (1.0 - kmax)
    return dict(tp=tp, fp=fp, fn=fn, dti=dti_from_components(tp, fp, fn, alpha, beta))
