"""Distance-Weighted Tversky Index (DTI) -- DOE GEMS Prize, DrivenData #306.

Transcribed verbatim from the official problem description, section
"Performance metric" -> "Mathematical representation":

    TP_w = sum_{g in G} max_{x : d(x,g) <= R} p(x) * k(d(x,g))
    FP_w = sum_{x : p(x) > 0} p(x) * [1 - max_{g in G} k(d(x,g))]
    FN_w = sum_{g in G} [1 - max_{x : d(x,g) <= R} p(x) * k(d(x,g))]
    DTI  = TP_w / (TP_w + alpha*FP_w + beta*FN_w + eps)
    k(d) = max(1 - d/R, 0),   R = 300 m = 3 px at 100 m,  alpha = 0.2, beta = 0.8

Source (read 2026-10-11):
  https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/

Organiser's own worked example on the same page:
  TP_w = 3.00, FP_w = 1.89, FN_w = 2.00
  TI_w = 3.00 / (3.00 + 0.2*1.89 + 0.8*2.00) = 0.60
`tests/test_metric.py::test_published_example_arithmetic` reproduces this.

Masking rule (organiser staff, forum thread 11516, 16 Sep 2026):
  "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded
   from evaluation, so they do not count towards penalty terms."
Source: https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516
Therefore `known` pixels are removed from BOTH the truth set and the prediction
before any term is accumulated.  This module makes that removal explicit.

Three exact identities used by the emitter (proved in tests/test_metric.py):

  (I1)  DTI = T / (0.2*T + 0.2*F + 0.8*K),  K = |G| in the active domain.
        Because FN_w = K - T exactly.
  (I2)  Marginal dot.  Adding one unit-valued pixel changes
        T -> T + dT, F -> F + (1 - kbar), so the score rises iff
        dT * D0  >  0.2 * T * (dT + 1 - kbar),   D0 = 0.2T + 0.2F + 0.8K.
        For a non-redundant dot (dT == kbar) this reduces to
        kbar > 0.2*s.          <-- the credit bar
  (I3)  Scaling.  DTI(lambda*p) = lambda*T / (lambda*0.2*(T+F) + 0.8*K)
        is strictly increasing in lambda in (0, 1]; hence a graded map is
        weakly dominated by its own thresholded support.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA: float = 0.2
BETA: float = 0.8
RADIUS_PX: float = 3.0
PIXEL_M: float = 100.0
R_M: float = RADIUS_PX * PIXEL_M
EPS: float = 1e-12

# Every lattice offset with non-zero triangular weight (25 offsets for R=3).
_OFF: list[tuple[int, int, float]] = [
    (j, i, float(max(1.0 - np.hypot(j, i) / RADIUS_PX, 0.0)))
    for j in range(-3, 4)
    for i in range(-3, 4)
    if np.hypot(j, i) <= RADIUS_PX
]


def kernel(d, radius: float = RADIUS_PX):
    """Triangular kernel k(d) = max(1 - d/R, 0); d in pixels."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def credit_bar(current_dti: float, alpha: float = ALPHA) -> float:
    """Identity I2, non-redundant case: minimum kernel credit a new dot must
    realise for the score to rise.  bar = alpha * s."""
    return alpha * float(current_dti)


def marginal_accept(dT: float, k_self: float, T: float, F: float, K: float,
                    alpha: float = ALPHA, beta: float = BETA) -> bool:
    """Exact marginal test (identity I2).  Compares DTI before/after."""
    D0 = alpha * T + alpha * F + beta * K + EPS
    D1 = alpha * (T + dT) + alpha * (F + 1.0 - k_self) + beta * K + EPS
    return (T + dT) / D1 > T / D0


def dti_from_components(tp: float, fp: float, fn: float,
                        alpha: float = ALPHA, beta: float = BETA) -> float:
    return float(tp / (tp + alpha * fp + beta * fn + EPS))


def _active(pred_shape, valid, known):
    valid_ = np.ones(pred_shape, bool) if valid is None else np.asarray(valid, bool)
    known_ = np.zeros(pred_shape, bool) if known is None else np.asarray(known, bool)
    return valid_ & ~known_


def dti_exact(pred, truth, valid=None, known=None,
              alpha: float = ALPHA, beta: float = BETA) -> dict:
    """Exact DTI for arbitrary soft predictions in [0, 1] on the exact grid.

    `truth` is the scored ground truth (expert labels), `known` is the
    organiser-masked catalogue, `valid` the footprint.  Both are removed from
    the active domain before any term is accumulated.  This is O(N) via
    Euclidean distance transforms; validated against a literal O(|G||P|)
    transcription in tests/test_metric.py.
    """
    pred = np.asarray(pred, np.float64)
    truth = np.asarray(truth, bool)
    if pred.shape != truth.shape:
        raise ValueError("grid shape mismatch")
    active = _active(pred.shape, valid, known)
    vals = pred[active]
    if vals.size and (not np.isfinite(vals).all() or (vals < 0).any() or (vals > 1).any()):
        raise ValueError("predictions inside the scored domain must be finite and in [0, 1]")
    p = np.where(active, pred, 0.0)
    g = active & truth
    ys, xs = np.nonzero(g)
    K = int(ys.size)
    n_emit = int((p > 0).sum())
    if K == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0,
                    n_predicted=n_emit, dti=0.0, coverage=0.0)
    # TP_w: for every truth pixel, the max p(x)*k(d(x,g)) within the kernel.
    credit = np.zeros(K, np.float64)
    h, w = p.shape
    for j, i, kw in _OFF:
        ny, nx = ys + j, xs + i
        ok = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
        credit[ok] = np.maximum(credit[ok], p[ny[ok], nx[ok]] * kw)
    tp = float(credit.sum())
    fn = float(K) - tp
    dg = distance_transform_edt(~g)
    kbar = kernel(dg)
    fp = float((p * (1.0 - kbar)).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_truth=K, n_predicted=n_emit,
                dti=dti_from_components(tp, fp, fn, alpha, beta),
                coverage=tp / K if K else 0.0)


def dti_bruteforce(pred, truth, alpha: float = ALPHA, beta: float = BETA,
                   radius: float = RADIUS_PX) -> dict:
    """Literal O(|G|*|P|) transcription of the published equations (test oracle).
    Applies NO masking -- it is the formula as printed."""
    pred = np.asarray(pred, float)
    truth = np.asarray(truth, bool)
    gs = np.argwhere(truth)
    xs = np.argwhere(pred > 0)
    if gs.size == 0:
        return dict(tp=0.0, fp=float(pred.sum()), fn=0.0,
                    dti=0.0)
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
    return dict(tp=float(tp), fp=float(fp), fn=float(fn),
                dti=dti_from_components(float(tp), float(fp), float(fn), alpha, beta))


def implied_truth_mass(dti: float, T: float, S: float, M: float,
                       alpha: float = ALPHA, beta: float = BETA) -> float:
    """Invert identity I1 for K given a published score and measured
    T (realised credit), S (emitted mass) and M (sum of per-pixel kbar).
    Model quantity -- never a measurement."""
    # dti = T / (alpha*T + alpha*(S-M) + beta*K)
    denom_needed = T / dti
    return (denom_needed - alpha * T - alpha * (S - M)) / beta
