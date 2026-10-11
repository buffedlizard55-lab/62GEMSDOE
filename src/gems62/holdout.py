"""Spatially-blocked hide-and-recover holdout, as the parallel-run protocol
specifies it, plus the one correction this repository adds.

PROTOCOL (as written):
  "withhold whole fault segments with a buffer, derive every catalogue-based
   feature only from the visible faults, mask visible faults pixel-exactly,
   score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel)."

Correction carried from the group's IR-30-046 (measured 2026-10-03): ranking by
this catalogue proxy is ANTI-CORRELATED with the public portal scores, because
the portal's ground truth is expert-labelled faults that are ABSENT from the
catalogue and catalogue pixels are masked out of scoring.  A catalogue-proxy
holdout therefore cannot reward finding a genuinely new fault.  It is reported
here as INSTRUMENT A, and never used alone to promote anything.

INSTRUMENT B is added: truth = an independent fault compilation that is not the
competition catalogue (SGMC 1:750k state map traces, rasterised to this grid).
It is a *proxy* for "mapped but not catalogued", which is the class the
competition actually scores, and it is the only independent instrument
available offline.  It is also not the organiser's private expert set.

Neither instrument is a competition score.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from .metric import dti_exact


def segments(mask: np.ndarray, min_px: int = 10):
    """Label connected fault segments; drop specks.

    Returns (lab, kept_ids) where `kept_ids` are the label values that survive
    (labels are NOT renumbered, so `lab` and `kept_ids` stay consistent).
    """
    lab, n = ndi.label(mask, structure=np.ones((3, 3), int))
    if n == 0:
        return np.zeros_like(lab), np.array([], int)
    sizes = np.bincount(lab.ravel())
    kept = np.flatnonzero(sizes >= min_px)
    kept = kept[kept > 0]
    return lab, kept


def block_folds(shape, rows: int = 2, cols: int = 2) -> np.ndarray:
    """Spatially blocked fold id per cell (square blocks, not stripes)."""
    h, w = shape
    f = np.zeros(shape, np.int16)
    rb = np.linspace(0, h, rows + 1).astype(int)
    cb = np.linspace(0, w, cols + 1).astype(int)
    k = 0
    for i in range(rows):
        for j in range(cols):
            f[rb[i]:rb[i + 1], cb[j]:cb[j + 1]] = k
            k += 1
    return f


def hide_and_recover(pred_dots: np.ndarray, catalogue: np.ndarray,
                     footprint: np.ndarray, *, orders_px: int = 3,
                     rows: int = 2, cols: int = 2, min_segment_px: int = 10,
                     seed_segments: list[int] | None = None) -> dict:
    """Instrument A: for every spatial block, hide the catalogue segments
    whose centroid falls in it (dilated by `orders_px` == the 300 m kernel
    radius, so a recovered pixel must be a genuine recovery and not a
    bleed-through of the visible catalogue), then score the prediction pooled
    over the whole grid with the hidden set as truth and everything else masked.

    `pred_dots` is a boolean mask of emitted pixels.  Returns pooled DTI, the
    number of withheld positives, and a bootstrap 95% CI over withheld truth
    pixels.
    """
    lab, ids = segments(catalogue, min_px=min_segment_px)
    if ids.size == 0:
        return dict(error="no catalogue segments")
    cy, cx = np.array(ndi.center_of_mass(catalogue, lab, ids)).T
    f = block_folds(catalogue.shape, rows, cols)
    truth_all = np.zeros(catalogue.shape, bool)
    for k in np.unique(f):
        sel = f[cy.astype(int), cx.astype(int)] == k
        if seed_segments is not None:
            sel &= np.isin(ids, seed_segments)
        if not sel.any():
            continue
        m = np.isin(lab, ids[sel])
        truth_all |= ndi.binary_dilation(m, iterations=orders_px)
    truth_all &= footprint
    visible = catalogue & ~truth_all
    res = dti_exact(pred_dots.astype(np.float64), truth_all,
                    valid=footprint, known=visible)
    ci = bootstrap_dti_ci(pred_dots, truth_all, footprint, visible)
    return dict(instrument="A",
                truth="hidden catalogue segments (dilated by the 300 m kernel)",
                n_truth_px=int(truth_all.sum()),
                n_segments_total=int(ids.size),
                pooled=res, ci95=ci, folds=[int(rows), int(cols)],
                caveat="IR-30-046: this proxy ranks anti-correlated with the "
                       "public portal scores; never a promotion gate on its own.")


def bootstrap_dti_ci(pred_dots, truth, footprint, known, n_boot: int = 400,
                     alpha: float = 0.05, seed: int = 0) -> list[float]:
    """Non-parametric bootstrap of the pooled DTI by resampling withheld truth
    pixels (the only source of variance that matters for a fixed prediction).

    FAIL-CLOSED: the plug-in value of the resampled estimator is asserted to
    equal the pooled DTI returned by ``metric.dti_exact`` for the same inputs, to
    1e-9.  An earlier draft of this module used the algebra
    ``T/(0.2T + 0.2*F + 0.8*n)`` while the point estimate came from
    ``dti_from_components``; the two differed in the third decimal place and the
    interval did not contain the point estimate.  That is exactly the class of
    silent inconsistency this repository is supposed to refuse, so it is now a
    hard assertion rather than a comment.
    """
    from .metric import _OFF, kernel, dti_exact, dti_from_components  # noqa: PLC0415
    rng = np.random.default_rng(seed)
    g = truth & footprint & ~known
    ys, xs = np.nonzero(g)
    if ys.size < 20:
        return [float("nan"), float("nan")]
    p = np.where(footprint & ~known, pred_dots, 0.0).astype(np.float64)
    h, w = p.shape
    credit = np.zeros(ys.size, np.float64)
    for j, i, kw in _OFF:
        ny, nx = ys + j, xs + i
        ok = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
        credit[ok] = np.maximum(credit[ok], p[ny[ok], nx[ok]] * kw)
    kbar = kernel(ndi.distance_transform_edt(~g))
    fp_total = float((p * (1.0 - kbar)).sum())
    K = int(ys.size)
    pooled = dti_exact(pred_dots.astype(np.float64), truth, valid=footprint, known=known)["dti"]
    plugin = dti_from_components(float(credit.sum()), fp_total, float(K) - float(credit.sum()))
    if abs(plugin - pooled) > 1e-9:
        raise AssertionError(
            f"bootstrap plug-in {plugin!r} != pooled DTI {pooled!r}; the interval "
            "would not be the interval of the reported number")
    out = np.empty(n_boot)
    for b in range(n_boot):
        c = credit[rng.integers(0, K, K)]
        T = float(c.sum())
        out[b] = dti_from_components(T, fp_total, float(K) - T)
    return [float(np.percentile(out, 100 * alpha / 2)),
            float(np.percentile(out, 100 * (1 - alpha / 2)))]


def sgmc_truth(sgmc_raster: np.ndarray, catalogue: np.ndarray,
               footprint: np.ndarray) -> np.ndarray:
    """Instrument B truth: independent compilation minus the competition
    catalogue (which is masked out of scoring)."""
    return (sgmc_raster > 0) & footprint & ~catalogue


def feature_auc(score: np.ndarray, truth: np.ndarray, valid: np.ndarray,
                n_sample: int = 200_000, seed: int = 1) -> float:
    """Leakage canary: AUC of a single feature against the holdout truth."""
    rng = np.random.default_rng(seed)
    idx = np.flatnonzero(valid)
    if idx.size > n_sample:
        idx = rng.choice(idx, n_sample, replace=False)
    s = score.ravel()[idx]
    t = truth.ravel()[idx].astype(np.int8)
    ok = np.isfinite(s)
    s, t = s[ok], t[ok]
    if t.sum() == 0 or t.sum() == t.size:
        return float("nan")
    order = np.argsort(s)
    ranks = np.empty(s.size, float)
    ranks[order] = np.arange(1, s.size + 1)
    # average ranks for ties
    uniq, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    csum = np.cumsum(cnt)
    avg = (csum - cnt / 2.0 + 0.5)
    ranks = avg[inv]
    n1 = int(t.sum())
    n0 = t.size - n1
    return float((ranks[t == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))
