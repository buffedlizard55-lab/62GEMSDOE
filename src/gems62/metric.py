"""Distance-weighted Tversky index (DTI) exactly as the competition defines it.

Source of truth (fetched 2026-10-11, quoted in the run card / docs/sources):
  https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
  - triangular kernel k(d) = max(1 - d/R, 0), R = 300 m (= 3 px at 100 m)
  - TP_w = sum_{g in G} max_{x: d(x,g) <= R} p(x) k(d(x,g))
  - FP_w = sum_{x: p(x)>0} p(x) [1 - max_{g in G} k(d(x,g))]
  - FN_w = sum_{g in G} [1 - max_{x: d(x,g) <= R} p(x) k(d(x,g))] = |G| - TP_w
  - DTI(alpha=0.2, beta=0.8) = TP_w / (TP_w + alpha FP_w + beta FN_w + eps)
  - published worked example: TP_w=3.00, FP_w=1.89, FN_w=2.00 -> 3.00/(3.00+0.2*1.89+0.8*2.00) = 0.60

Nothing here is imported from a sibling repository: this module is an independent
implementation, and `tests/test_metric62.py` checks the published worked example plus a
brute-force O(|G|*|P|) transcription of the formulas above.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA = 0.2
BETA = 0.8
RADIUS_PX = 3.0
EPS = 1e-12


def kernel(d, radius=RADIUS_PX):
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def dti_from_components(tp: float, fp: float, fn: float, alpha=ALPHA, beta=BETA) -> float:
    """The published formula. Also the place the printed worked example is checked."""
    return tp / (tp + alpha * fp + beta * fn + EPS)


def dti_binary(pred_bool: np.ndarray, truth: np.ndarray, active: np.ndarray | None = None) -> dict:
    """Exact DTI for binary predictions, via Euclidean distance transforms.

    `active` is the scored domain (valid footprint minus the known/masked catalogue).  Pixels
    of known USGS/INGENIOUS faults are excluded from evaluation -- organizer clarification,
    DrivenData forum thread 11516 (chrisk-dd, 2026-09-16):
    "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation,
    so they do not count towards penalty terms."
    """
    pred = np.asarray(pred_bool, bool)
    truth = np.asarray(truth, bool)
    act = np.ones(pred.shape, bool) if active is None else np.asarray(active, bool)
    p = pred & act
    g = truth & act
    n = int(g.sum())
    if n == 0:
        return dict(tp=0.0, fp=float(p.sum()), fn=0.0, n_truth=0, n_active_pred=int(p.sum()), dti=0.0)
    if not p.any():
        return dict(tp=0.0, fp=0.0, fn=float(n), n_truth=n, n_active_pred=0, dti=0.0)
    dp = distance_transform_edt(~p)
    tp = float(kernel(dp[g]).sum())
    fn = float(n) - tp
    dg = distance_transform_edt(~g)
    fp = float((1.0 - kernel(dg[p])).sum())
    return dict(tp=tp, fp=fp, fn=fn, n_truth=n, n_active_pred=int(p.sum()),
                dti=dti_from_components(tp, fp, fn))


def dti_bruteforce(pred, truth, alpha=ALPHA, beta=BETA, radius=RADIUS_PX) -> dict:
    """Literal transcription of the published equations: O(|G| * |P|). Used by tests only."""
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
                best = max(best, float(pred[tuple(x)]) * max(1.0 - d / radius, 0.0))
        tp += best
        fn += 1.0 - best
    fp = 0.0
    for x in xs:
        kmax = 0.0
        for g in gs:
            kmax = max(kmax, max(1.0 - float(np.hypot(*(x - g))) / radius, 0.0))
        fp += float(pred[tuple(x)]) * (1.0 - kmax)
    return dict(tp=tp, fp=fp, fn=fn, dti=tp / (tp + alpha * fp + beta * fn + EPS))


def marginal_bar(current_dti: float, alpha=ALPHA) -> float:
    """d(DTI) > 0 for an added unit of mass whose realised kernel weight is k  <=>  k > alpha*DTI.

    Derivation (independent of any sibling repo): with T = TP_w, F = FP_w, K = |G| and
    D = alpha*(T+F) + beta*K, adding mass p with realised weight k gives dT = k*p, dF = (1-k)*p,
    so dD = alpha*p regardless of k, and d(DTI) > 0 <=> k*D > alpha*T <=> k > alpha*DTI.
    """
    return alpha * current_dti


def credit_audit(mask: np.ndarray) -> dict:
    """Structure-only audit of an emission: redundancy fraction and mean self-kernel."""
    m = np.asarray(mask, float)
    pos = m > 0
    n = int(pos.sum())
    if n == 0:
        return dict(n_emitted=0, total_mass=0.0, redundancy_fraction=0.0, mean_self_kernel=0.0)
    # distance from every emitted pixel to the nearest *other* emitted pixel
    dy, dx = np.mgrid[-3:4, -3:4]
    offsets = [(int(a), int(b)) for a, b in zip(dy.ravel(), dx.ravel())
               if (a, b) != (0, 0) and np.hypot(a, b) <= RADIUS_PX]
    best = np.zeros(m.shape)
    h, w = m.shape
    for oy, ox in offsets:
        k = float(kernel(np.hypot(oy, ox)))
        shifted = np.zeros_like(m)
        ys0, ys1 = max(0, oy), min(h, h + oy)
        xs0, xs1 = max(0, ox), min(w, w + ox)
        shifted[ys0:ys1, xs0:xs1] = m[max(0, -oy):min(h, h - oy), max(0, -ox):min(w, w - ox)]
        np.maximum(best, shifted * k, out=best)
    return dict(n_emitted=n, total_mass=float(m.sum()),
                redundancy_fraction=float((best[pos] > 0).mean()),
                mean_self_kernel=float(best[pos].mean()))


# Compatibility API for the shared spatial holdout and its unit tests.  The
# active fast path above remains the root pipeline's evaluator; these exact
# physical-unit routines back catalogue-segment holdout and the brute-force
# reference tests.  Keep the adapters here (the canonical package surface) so
# callers never import the archived `superseded_20261011` package directly.
from .superseded_20261011.metric import (  # noqa: E402
    Components,
    Precomputed,
    brute_force_components,
    dti as dti_physical,
    dti_components,
    maximum_useful_distance_m,
    unit_dot_dti,
)

RADIUS_M = 300.0
