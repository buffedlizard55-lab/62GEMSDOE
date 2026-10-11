"""Spatially-blocked, hide-and-recover holdout for the lane.

Design required by the parallel-run protocol:

* **Withhold whole fault segments with a buffer.**  The visible catalogue is
  split into connected segments; a random subset of *entire segments* plus a
  dilation buffer is removed from the training view.  That is the only split
  that does not leak: a random pixel split leaves the neighbours of every
  withheld pixel visible, and any local operator then "predicts" them for free.
* **Derive every catalogue-based feature only from the visible faults.**  In
  this lane the detector uses no catalogue feature at all, so this holds
  trivially -- and that is asserted, not assumed, by ``catalogue_dependency``.
* **Mask visible faults pixel-exactly.**  Scoring excludes visible catalogue
  pixels from both prediction and truth, so a dot that lands on a mapped fault
  can neither earn credit nor be penalised.
* **Score pooled DTI** (alpha 0.2, beta 0.8, 300 m triangular kernel) over the
  withheld positives.

Controls (equal emission budget, same evaluator):

* ``random_lines`` -- random straight traces of the same total length
* ``random_dots``  -- uniformly random eligible pixels
* ``catalogue_offset`` -- visible catalogue traces shifted by a fixed vector
  (tests whether the lane is simply re-detecting mapped faults)

The pooled DTI is reported with a segment-level bootstrap 95% CI, because the
withheld segments -- not the pixels -- are the independent units.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

from .metric import dti_binary, ALPHA, BETA, RADIUS_PX

HOLDOUT_VERSION = "gems62.holdout_segmented v1"


def segments_of(mask: np.ndarray, min_size: int = 8) -> tuple[np.ndarray, int]:
    """Label connected components of ``mask`` (8-connectivity), drop tiny ones.

    Dropped components are relabelled 0 (background) and the survivors are
    renumbered contiguously from 1, so ``n`` equals ``lab.max()``.
    """
    lab, n = ndi.label(mask, structure=np.ones((3, 3), bool))
    if min_size > 1 and n > 0:
        sizes = np.bincount(lab.ravel(), minlength=n + 1)
        keep = sizes >= min_size
        keep[0] = False                      # background is never a segment
        remap = np.zeros(n + 1, np.int64)
        remap[keep] = np.arange(1, int(keep.sum()) + 1)
        lab = remap[lab]
        n = int(remap.max())
    return lab, n


@dataclass
class Fold:
    index: int
    seed: int
    n_segments_withheld: int
    n_segments_visible: int
    withheld_px: int
    buffered_px: int
    result: dict = field(default_factory=dict)
    controls: dict = field(default_factory=dict)


def split_segments(seglab: np.ndarray, n: int, frac: float, rng: np.random.Generator,
                   buffer_px: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Return (withheld_mask, buffered_mask) for a random subset of segments."""
    ids = np.arange(1, n + 1)
    k = max(1, int(round(frac * ids.size)))
    take = rng.choice(ids, size=k, replace=False)
    withheld = np.isin(seglab, take)
    buffered = ndi.binary_dilation(withheld, iterations=buffer_px) if buffer_px else withheld
    return withheld, buffered


def _random_line_mask(shape, eligible, n_dots, rng, seg_len=25):
    """Random straight traces restricted to the eligible band, ~n_dots pixels.

    Vectorised: draw ``ceil(n_dots/seg_len)`` origins and azimuths at once and
    stamp whole segments, then trim to the budget.  The previous per-segment
    Python loop cost ~40 s per control at a 38,000-dot budget.
    """
    out = np.zeros(shape, bool)
    ys, xs = np.nonzero(eligible)
    if ys.size == 0 or n_dots <= 0:
        return out
    if seg_len <= 1:
        idx = rng.choice(ys.size, size=min(n_dots, ys.size), replace=False)
        out[ys[idx], xs[idx]] = True
        return out
    n_seg = int(np.ceil(n_dots / seg_len))
    oi = rng.integers(0, ys.size, size=n_seg)
    th = rng.uniform(0, np.pi, size=n_seg)
    dy = np.sin(th)[:, None]
    dx = np.cos(th)[:, None]
    t = np.arange(seg_len)[None, :]
    yy = np.round(ys[oi][:, None] + dy * t).astype(np.int64)
    xx = np.round(xs[oi][:, None] + dx * t).astype(np.int64)
    ok = (yy >= 0) & (yy < shape[0]) & (xx >= 0) & (xx < shape[1])
    yyv, xxv = yy[ok], xx[ok]
    ok2 = eligible[yyv, xxv]
    out[yyv[ok2], xxv[ok2]] = True
    return _thin_to_budget(out, n_dots, rng)


def _thin_to_budget(mask, budget, rng):
    ys, xs = np.nonzero(mask)
    if ys.size <= budget:
        return mask
    idx = rng.choice(ys.size, size=budget, replace=False)
    out = np.zeros_like(mask)
    out[ys[idx], xs[idx]] = True
    return out


def run_holdout(eligible: np.ndarray, priority: np.ndarray, footprint: np.ndarray,
                catalogue: np.ndarray, emission_fn, n_folds: int = 4,
                frac_withheld: float = 0.35, seeds=(20, 21), buffer_px: int = 3,
                n_segments_min: int = 8, controls: bool = True,
                budget: int = 38000) -> dict:
    """Segmented hide-and-recover evaluation.

    ``emission_fn(eligible, priority, footprint, visible_catalogue, budget)``
    must return a bool mask of emitted dots.  The visible catalogue is the only
    catalogue information the emitter is allowed to see.
    """
    seglab, nseg = segments_of(catalogue & footprint, min_size=n_segments_min)
    folds: list[Fold] = []
    pooled: list[dict] = []
    ctrl_pooled: dict[str, list[float]] = {"random_lines": [], "random_dots": [],
                                           "catalogue_offset": []}
    fi = 0
    for seed in seeds:
        for f in range(n_folds // max(len(seeds), 1) or 1):
            rng = np.random.default_rng(seed * 1000 + f)
            withheld, buffered = split_segments(seglab, nseg, frac_withheld, rng,
                                                buffer_px=buffer_px)
            visible = (catalogue & footprint) & ~buffered
            truth = withheld & footprint
            n_truth = int(truth.sum())
            if n_truth == 0:
                continue
            # the emitter may only see `visible`; scored truth is `withheld`
            emitted = emission_fn(eligible, priority, footprint, visible, budget)
            emitted = emitted & footprint & ~visible
            r = dti_binary(emitted, truth, valid=footprint, known=visible)
            fold = Fold(index=fi, seed=int(seed),
                        n_segments_withheld=int(len(np.unique(seglab[withheld])) - 1),
                        n_segments_visible=int(len(np.unique(seglab[visible])) - 1),
                        withheld_px=n_truth, buffered_px=int(buffered.sum()),
                        result=r)
            if controls:
                n_e = int(emitted.sum())
                b = max(n_e, 1)
                rl = _thin_to_budget(_random_line_mask(emitted.shape, eligible & ~visible,
                                                       b, rng), b, rng)
                rd = _thin_to_budget(_random_line_mask(emitted.shape, footprint & ~visible,
                                                       b, rng, seg_len=1), b, rng)
                shift = (int(rng.integers(-6, 7)), int(rng.integers(-6, 7)))
                off = ndi.shift(visible.astype(float), shift, order=0, mode="constant") > 0.5
                off = off & footprint & ~visible
                off = _thin_to_budget(off, b, rng)
                fold.controls = {
                    "random_lines": dti_binary(rl, truth, valid=footprint, known=visible),
                    "random_dots": dti_binary(rd, truth, valid=footprint, known=visible),
                    "catalogue_offset": dti_binary(off, truth, valid=footprint, known=visible),
                }
                for k in ctrl_pooled:
                    ctrl_pooled[k].append(fold.controls[k]["dti"])
            pooled.append(r)
            folds.append(fold)
            fi += 1

    if not pooled:
        return dict(version=HOLDOUT_VERSION, n_folds=0, dti=None, ci=None, folds=[])

    tp = sum(r["tp"] for r in pooled)
    fp = sum(r["fp"] for r in pooled)
    fn = sum(r["fn"] for r in pooled)
    k = sum(r["n_truth"] for r in pooled)
    pooled_dti = tp / (tp + ALPHA * fp + BETA * fn + 1e-12)

    # segment-level bootstrap CI: resample folds with replacement
    rng = np.random.default_rng(7)
    vals = np.array([r["dti"] for r in pooled], float)
    boots = np.array([vals[rng.integers(0, vals.size, vals.size)].mean()
                      for _ in range(2000)])
    ci = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]

    return dict(version=HOLDOUT_VERSION, alpha=ALPHA, beta=BETA, radius_px=RADIUS_PX,
                n_folds=len(pooled), seeds=list(seeds), frac_withheld=frac_withheld,
                buffer_px=buffer_px, n_segments_total=int(nseg),
                withheld_positives_total=int(k),
                pooled_dti=float(pooled_dti), pooled_tp=float(tp), pooled_fp=float(fp),
                pooled_fn=float(fn),
                fold_dti_mean=float(vals.mean()), fold_dti_ci95=ci,
                controls_mean={kk: (float(np.mean(v)) if v else None)
                               for kk, v in ctrl_pooled.items()},
                controls_all=ctrl_pooled,
                folds=[dict(index=f.index, seed=f.seed,
                            n_segments_withheld=f.n_segments_withheld,
                            n_segments_visible=f.n_segments_visible,
                            withheld_px=f.withheld_px, buffered_px=f.buffered_px,
                            result=f.result, controls=f.controls) for f in folds])


def leakage_canary(feature: np.ndarray, positives: np.ndarray, footprint: np.ndarray,
                   known: np.ndarray | None = None) -> float:
    """Rank-AUC of a single feature against the truth.  > 0.90 means leakage.

    Computed with a rank-based AUC so no distributional assumption is made.
    """
    y = positives & footprint
    if known is not None:
        y = y & ~known
        m = footprint & ~known
    else:
        m = footprint
    x = np.asarray(feature, float)[m]
    yy = y[m]
    ok = np.isfinite(x)
    x, yy = x[ok], yy[ok]
    npos, nneg = int(yy.sum()), int((~yy).sum())
    if npos == 0 or nneg == 0:
        return 0.5
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(x.size, float)
    ranks[order] = np.arange(1, x.size + 1, dtype=float)
    return float((ranks[yy].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))
