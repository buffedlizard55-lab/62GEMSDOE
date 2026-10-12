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

from dataclasses import dataclass
from math import ceil, hypot

import numpy as np
from scipy.ndimage import distance_transform_edt

ALPHA = 0.2
BETA = 0.8
RADIUS_PX = 3.0
#: The same kernel radius in metres.  IR-62-11 FIX: ``score_model`` imported this name
#: and raised ImportError on a clean checkout.  3.0 px x 100 m = 300 m, which is what the
#: published metric states, so the two spellings are the same quantity, not two models.
RADIUS_M = 300.0
EPS = 1e-12


def kernel(d, radius=RADIUS_PX):
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def dti_from_components(tp: float, fp: float, fn: float, alpha=ALPHA, beta=BETA) -> float:
    """The published formula. Also the place the printed worked example is checked."""
    return tp / (tp + alpha * fp + beta * fn + EPS)


def dti_binary(pred_bool: np.ndarray, truth: np.ndarray, active: np.ndarray | None = None,
               *, valid: np.ndarray | None = None, known: np.ndarray | None = None) -> dict:
    """Exact DTI for binary predictions, via Euclidean distance transforms.

    `active` is the scored domain (valid footprint minus the known/masked catalogue).  Pixels
    of known USGS/INGENIOUS faults are excluded from evaluation -- organizer clarification,
    DrivenData forum thread 11516 (chrisk-dd, 2026-09-16):
    "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation,
    so they do not count towards penalty terms."

    IR-62-18 FIX (2026-10-11b): the sibling evaluator
    (`lane62-h62a/src/gems62/holdout.py`) calls ``dti_binary(pred, truth, valid=..., known=...)``
    while this module exposed only the positional `active`.  Two spellings of one quantity is the
    same class of defect as IR-62-11, so the keyword form is added *additively* here rather than
    letting a fourth private copy of the metric exist.  `active = valid & ~known`, exactly the
    composition the sibling evaluator performs in `_prepare` (`lane62-h62a/src/gems62/metric.py`
    lines 96-101), so the two paths are the same arithmetic, not two models.
    """
    if valid is not None or known is not None:
        if active is not None:
            raise TypeError("pass either `active` or (`valid`, `known`), not both")
        v = np.ones(np.shape(truth), bool) if valid is None else np.asarray(valid, bool)
        k = np.zeros(np.shape(truth), bool) if known is None else np.asarray(known, bool)
        active = v & ~k
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


# =====================================================================================
# Metres-based API (IR-62-11 fix, 2026-10-11)
# -------------------------------------------------------------------------------------
# ``holdout.py``, ``validate.py`` and ``tests/test_metric.py`` are written against a
# metres-based metric API (``dti_components`` returning a ``Components`` record,
# ``brute_force_components``, ``maximum_useful_distance_m``, ``unit_dot_dti``).  A later
# rewrite of this module kept only the pixel-based helpers, so those imports raised
# ImportError.  The functions below are restored *additively* from the archived variant in
# ``superseded_20261011/metric.py``; they are the same published index, expressed in
# metres, and ``tests/test_metric.py::test_fast_path_matches_brute_force`` cross-checks the
# fast path against the O(|G|*|P|) transcription on random fields.
#
# ``kernel`` is shared: it is ``max(1 - d/radius, 0)`` and every metres-based caller below
# passes ``radius_m`` explicitly, so there is no ambiguity with ``RADIUS_PX``.
# =====================================================================================


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
    """``values[y+dy, x+dx]`` sampled at ``(y, x)``; zero outside the grid."""
    arr = np.asarray(values)
    h, w = arr.shape
    out = np.zeros(arr.shape, dtype=np.float64)
    y0, y1 = max(0, -dy), min(h, h - dy)
    x0, x1 = max(0, -dx), min(w, w - dx)
    if y0 < y1 and x0 < x1:
        out[y0:y1, x0:x1] = arr[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
    return out


@dataclass(frozen=True)
class Precomputed:
    """Truth-derived fields that do not depend on the prediction."""

    truth: np.ndarray
    k_to_truth: np.ndarray

    @classmethod
    def build(cls, truth: np.ndarray, *, radius_m: float = RADIUS_M,
              pixel_m: float = 100.0) -> "Precomputed":
        t = np.asarray(truth).astype(bool)
        d = (distance_transform_edt(~t, sampling=(pixel_m, pixel_m))
             if t.any() else np.full(t.shape, np.inf))
        return cls(truth=t, k_to_truth=kernel(d, radius_m))


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
    """Exact DTI and its three weighted components, in metres.

    ``valid`` is the scored footprint.  Non-finite or out-of-range predictions inside
    ``valid`` raise, which is what makes this module also a [0, 1] gate.
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
    row_m = float(np.asarray(pixel_size_m).reshape(-1)[0])

    if precomputed is None:
        if truth is None:
            raise ValueError("truth is required unless precomputed is supplied")
        g = np.asarray(truth).astype(bool) & valid
        precomputed = Precomputed.build(g, radius_m=radius_m, pixel_m=row_m)

    fp = float(np.sum(p * (1.0 - precomputed.k_to_truth)))
    if not precomputed.truth.any():
        return Components(0.0, fp, 0.0, 0.0 / (0.0 + alpha * fp + epsilon))

    best = np.zeros(p.shape, dtype=np.float64)
    for dy, dx, w in _offsets(radius_m, row_m):
        np.maximum(best, _shift(p, dy, dx) * w, out=best)
    tp = float(best[precomputed.truth].sum())
    fn = float(precomputed.truth.sum() - tp)
    return Components(tp, fp, fn, tp / (tp + alpha * fp + beta * fn + epsilon))


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
    """O(N_truth * N_pred) reference implementation, used only to test the fast path."""
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


def maximum_useful_distance_m(dti_value: float, radius_m: float = RADIUS_M,
                              alpha: float = ALPHA) -> float:
    """Distance beyond which appending one unit dot *lowers* the index.

    Appending a unit dot with truth-credit ``c`` raises the denominator by exactly
    ``alpha`` and the numerator by ``c``, so it is profitable iff ``c > alpha * DTI``,
    i.e. iff it lies within ``R * (1 - alpha * DTI)`` of a truth pixel.  At DTI = 0.2778
    the bar is ``c > 0.0556``, i.e. 283 m.  Accounting identity, not a geological claim.
    """
    return radius_m * (1.0 - alpha * dti_value)


def unit_dot_dti(n_dots: int, mean_credit: float, truth_mass: float,
                 alpha: float = ALPHA, beta: float = BETA) -> float:
    """Closed form for non-overlapping unit dots: ``c / (alpha + beta*G/N)``.

    Consequences used by the emission design: at fixed ``mean_credit`` the index
    *increases* with ``n_dots`` (coverage beats pruning at equal placement quality), and at
    fixed mass it is *linear* in ``mean_credit`` (placement quality is the only lever at
    constant mass).
    """
    if n_dots <= 0:
        return 0.0
    return mean_credit / (alpha + beta * truth_mass / n_dots)
