"""Official Distance-Weighted Tversky Index (DTI) for the DOE GEMS Prize Challenge.

Transcribed from the organiser's published definition on the competition
problem-description page:

    https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric

Quoted verbatim from that page (retrieved 2026-10-11):

    k(d) = (1 - d/R)+ = max(1 - d/R, 0)          R = 300 m = 3 px at 100 m

    TP_w = sum_{g in G} max_{x : d(x,g) <= R} p(x) * k(d(x,g))
    FP_w = sum_{x : p(x) > 0} p(x) * [1 - max_{g in G} k(d(x,g))]
    FN_w = sum_{g in G} [1 - max_{x : d(x,g) <= R} p(x) * k(d(x,g))]

    DTI(alpha, beta) = TP_w / (TP_w + alpha*FP_w + beta*FN_w + eps)
    alpha = 0.2, beta = 0.8

Published worked example from the same page (single vertical ground-truth
line): TP_w = 3.00, FP_w = 1.89, FN_w = 2.00 ->
    3.00 / (3.00 + 0.2*1.89 + 0.8*2.00) = 0.60
``tests/test_metric.py`` asserts that identity and cross-checks the fast
vectorised implementation against ``dti_bruteforce`` (a literal O(|G||P|)
transcription of the three sums) on random grids.

Algebraic form used for reasoning about the marginal value of a dot.  Because
FN_w = |G| - TP_w,

    DTI = T / (alpha*(T + F) + beta*|G|)

Adding one unit of prediction mass that realises kernel weight k gives
dT = k and dF = 1 - k, so the denominator rises by exactly alpha regardless of
where the mass lands:

    dD = alpha*(dT + dF) = alpha
    dDTI > 0  <=>  k*D > alpha*T  <=>  k > alpha*DTI

``marginal_inclusion_threshold`` implements that break-even bar.  At the
group's organiser-confirmed best of 0.2778 the bar is k > 0.05556; on the
100 m lattice the attainable kernel weights are
1, 1-1/3 = 0.6667, 1-sqrt(2)/3 = 0.5286, 1-2/3 = 0.3333, 1-sqrt(5)/3 = 0.2540,
1-2*sqrt(2)/3 = 0.05719, 1-3/3 = 0 -- so a (2,2)-diagonal dot at 0.05719 still
clears the bar, but a (3,0) dot at 0 does not.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA: float = 0.2
BETA: float = 0.8
RADIUS_PX: float = 3.0      # 300 m at 100 m pixels
EPS: float = 1e-12


def kernel(d, radius: float = RADIUS_PX) -> np.ndarray:
    """Triangular kernel k(d) = max(1 - d/R, 0); d and radius in pixels."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def attainable_kernel_weights(radius: float = RADIUS_PX) -> list[float]:
    """The distinct kernel weights realisable on the square pixel lattice."""
    r = int(np.ceil(radius))
    vals = {float(kernel(np.hypot(dy, dx), radius))
            for dy in range(-r, r + 1) for dx in range(-r, r + 1)}
    return sorted((v for v in vals if v > 0.0), reverse=True)


def _offsets(radius: float = RADIUS_PX) -> list[tuple[int, int, float]]:
    r = int(np.ceil(radius))
    out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            k = float(kernel(np.hypot(dy, dx), radius))
            if k > 0.0:
                out.append((dy, dx, k))
    return out


_OFFS = _offsets()


def _prepare(pred, truth, valid, known):
    pred = np.asarray(pred, dtype=np.float64)
    truth = np.asarray(truth)
    if pred.ndim != 2 or pred.shape != truth.shape:
        raise ValueError("prediction and truth must be equal-shaped 2-D grids")
    valid = np.ones(pred.shape, bool) if valid is None else np.asarray(valid, bool)
    known = np.zeros(pred.shape, bool) if known is None else np.asarray(known, bool)
    if valid.shape != pred.shape or known.shape != pred.shape:
        raise ValueError("mask grid mismatch")
    active = valid & ~known
    vals = pred[active]
    if not np.isfinite(vals).all():
        raise ValueError("predictions inside the scored domain must be finite")
    if (vals < 0.0).any() or (vals > 1.0).any():
        raise ValueError("predictions inside the scored domain must be in [0, 1]")
    p = np.where(active, pred, 0.0)
    g = active & (truth > 0)
    return p, g, active


def dti(pred, truth, valid=None, known=None,
        alpha: float = ALPHA, beta: float = BETA, radius: float = RADIUS_PX) -> dict:
    """Exact DTI for arbitrary soft or binary predictions in [0, 1].

    ``valid``  -- footprint mask (True where the submission is scored).
    ``known``  -- pixels of already-mapped faults to exclude from scoring
                  (the organiser masks known faults; see forum thread 11516).
    """
    p, g, _ = _prepare(pred, truth, valid, known)
    H, W = p.shape
    yy, xx = np.nonzero(g)
    n = int(yy.size)
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0,
                    dti=0.0, coverage=0.0)
    # TP_w: best kernel-weighted prediction seen by each truth pixel
    best = np.zeros(p.shape, dtype=np.float64)
    r = int(np.ceil(radius))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            k = float(kernel(np.hypot(dy, dx), radius))
            if k <= 0.0:
                continue
            ys0, ys1 = max(0, dy), min(H, H + dy)
            xs0, xs1 = max(0, dx), min(W, W + dx)
            np.maximum(best[ys0:ys1, xs0:xs1],
                       p[max(0, -dy):min(H, H - dy),
                         max(0, -dx):min(W, W - dx)] * k,
                       out=best[ys0:ys1, xs0:xs1])
    tp = float(best[g].sum())
    fn = float(n) - tp
    # FP_w: mass not covered by the kernel of any truth pixel
    dg = distance_transform_edt(~g)
    fp = float((p * (1.0 - kernel(dg, radius))).sum())
    denom = tp + alpha * fp + beta * fn
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n,
                dti=float(tp / (denom + EPS)), coverage=float(tp / n))


def dti_binary(pred_bool, truth, valid=None, known=None,
               alpha: float = ALPHA, beta: float = BETA, radius: float = RADIUS_PX) -> dict:
    """Fast exact DTI when predictions are binary {0, 1}."""
    pred_bool = np.asarray(pred_bool, bool)
    truth = np.asarray(truth, bool)
    valid_ = np.ones(pred_bool.shape, bool) if valid is None else np.asarray(valid, bool)
    known_ = np.zeros(pred_bool.shape, bool) if known is None else np.asarray(known, bool)
    active = valid_ & ~known_
    p = pred_bool & active
    g = truth & active
    n = int(g.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, dti=0.0, coverage=0.0)
    if not p.any():
        return dict(tp=0.0, fp=0.0, fn=float(n), n_truth=n, dti=0.0, coverage=0.0)
    dp = distance_transform_edt(~p)
    tp = float(kernel(dp[g], radius).sum())
    fn = float(n) - tp
    dg = distance_transform_edt(~g)
    fp = float((1.0 - kernel(dg[p], radius)).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n,
                dti=float(tp / (tp + alpha * fp + beta * fn + EPS)),
                coverage=float(tp / n))


def dti_bruteforce(pred, truth, alpha: float = ALPHA, beta: float = BETA,
                   radius: float = RADIUS_PX) -> dict:
    """Literal transcription of the three published sums. Slow; unit tests only."""
    pred = np.asarray(pred, float)
    truth = np.asarray(truth, bool)
    gs = np.argwhere(truth)
    xs = np.argwhere(pred > 0)
    tp = 0.0
    for g in gs:
        b = 0.0
        for x in xs:
            d = float(np.hypot(*(x - g)))
            if d <= radius:
                b = max(b, float(pred[tuple(x)]) * max(1.0 - d / radius, 0.0))
        tp += b
    fn = float(len(gs)) - tp
    fp = 0.0
    for x in xs:
        kmax = 0.0
        for g in gs:
            kmax = max(kmax, max(1.0 - float(np.hypot(*(x - g))) / radius, 0.0))
        fp += float(pred[tuple(x)]) * (1.0 - kmax)
    return dict(tp=tp, fp=fp, fn=fn,
                dti=tp / (tp + alpha * fp + beta * fn + EPS))


def marginal_inclusion_threshold(current_dti: float, alpha: float = ALPHA) -> float:
    """Break-even kernel weight for one more unit of emitted mass.

    k > alpha * DTI   (derived in this module's docstring).
    """
    return alpha * float(current_dti)


def credit_bar(dti_level: float, alpha: float = ALPHA) -> float:
    """Alias of :func:`marginal_inclusion_threshold` used by the emission code."""
    return marginal_inclusion_threshold(dti_level, alpha)
