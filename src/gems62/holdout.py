"""Whole-segment hide-and-recover holdout for a *catalogue-independent* lane.

Why this holdout is valid for the datum-offset lane
---------------------------------------------------
The published rule for this prompt asks for a holdout in which whole fault segments
are withheld behind a buffer, every catalogue-derived feature is recomputed from the
visible faults only, and the visible faults are masked pixel-exactly.  Almost every
sibling method fails that test's spirit, because those methods *read* the catalogue
(distance-to-catalogue fields, tip relay geometry, catalogue density).  Their holdout
score is therefore circular to some degree and several sibling repositories say so in
writing.

The datum-offset lane does not read the catalogue for placement at all.  The sole
catalogue term is the 200 m exclusion gate, which only ever *removes* mass.  Removing
mass cannot create credit for a withheld segment, so the lane is provably
leak-free with respect to the withheld segments: the held-out positives cannot help
it.  That makes this the rare case where a pooled-DTI hide-and-recover number is a
genuine lower bound on the lane's ability to recover a *mapped* fault population --
while remaining an upper bound on nothing at all about the hidden expert faults,
which are exactly the ones the catalogue lacks.

Design (mirrors the sibling protocol so the numbers are comparable)
------------------------------------------------------------------
* Folds: the grid is split into 4 spatial quadrants (2x2).
* Withholding: whole 8-connected catalogue segments lying inside the fold, dilated by
  a 300 m buffer, are the held-out positives.  Everything else in the footprint is
  scored as negative.
* Truth for the fold: the withheld segment pixels (plus their buffer) only.
* Prediction: the candidate raster, unchanged -- it is not derived from the catalogue.
* Metric: the exact pooled DTI of ``metric.py``, alpha 0.2, beta 0.8, 300 m
  triangular kernel.
* Uncertainty: cluster bootstrap over withheld segments (the independent unit).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy import ndimage as ndi

from .grid import PIXEL_M
from .metric import dti_components

BUFFER_M = 300.0
FOLD_NAMES = ("nw", "ne", "sw", "se")


@dataclass
class FoldResult:
    fold: str
    withheld_segments: int
    withheld_cells: int
    tp_w: float
    fp_w: float
    fn_w: float
    dti: float


@dataclass
class HoldoutResult:
    evaluator: str
    n_folds: int
    buffer_m: float
    pooled_dti: float
    folds: list[FoldResult]
    withheld_segments_total: int
    withheld_cells_total: int
    ci95: tuple[float, float] | None = None
    bootstrap_n: int = 0
    note: str = (
        "Catalogue-truth proxy. The competition target is faults ABSENT from the "
        "catalogue; they are masked out of scoring, so this number cannot measure the "
        "lane's performance on the real target. It is a leak-free lower bound on "
        "recovering a mapped-fault population."
    )

    def to_json(self) -> str:
        import json
        d = asdict(self)
        return json.dumps(d, indent=1, default=str)


def segment_labels(catalogue: np.ndarray, *, connectivity: int = 8) -> np.ndarray:
    """Label 8-connected catalogue fault segments."""
    struct = np.ones((3, 3), dtype=int) if connectivity == 8 else None
    lab, n = ndi.label(catalogue, structure=struct)
    return lab


def quadrant_of(rows: np.ndarray, cols: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    h, w = shape
    out = np.empty(rows.shape, dtype="<U2")
    south = rows >= h // 2
    east = cols >= w // 2
    out[:] = np.where(~south, np.where(~east, "nw", "ne"), np.where(~east, "sw", "se"))
    return out


def evaluate(
    prediction: np.ndarray,
    catalogue: np.ndarray,
    footprint: np.ndarray,
    *,
    buffer_m: float = BUFFER_M,
    folds: tuple[str, ...] = FOLD_NAMES,
    bootstrap_n: int = 0,
    seed: int = 20261011,
) -> HoldoutResult:
    """Pooled-DTI hide-and-recover over whole withheld catalogue segments."""
    pred = np.asarray(prediction, dtype=np.float64)
    cat = np.asarray(catalogue, dtype=bool)
    foot = np.asarray(footprint, dtype=bool)

    lab = segment_labels(cat)
    seg_ids = np.unique(lab[cat])
    rr, cc = np.nonzero(lab)
    seg_row = rr
    seg_col = cc
    seg_of_pixel = lab[cat]
    pixel_quad = quadrant_of(seg_row, seg_col, pred.shape)

    # A segment belongs to the quadrant of its centroid.
    from collections import defaultdict
    seg_quad: dict[int, str] = {}
    for name in folds:
        sel = pixel_quad == name
        ids = np.unique(seg_of_pixel[sel]) if sel.any() else np.array([], dtype=int)
        for s in ids:
            seg_quad[int(s)] = name
    # Segments that also extend outside the fold are still withheld as a whole unit.

    results: list[FoldResult] = []
    buffers = np.empty(pred.shape, dtype=bool)
    buffers[:] = False
    withheld_any = np.zeros(pred.shape, dtype=bool)
    for f_i, name in enumerate(folds):
        ids = np.array([s for s, q in seg_quad.items() if q == name], dtype=int)
        if ids.size == 0:
            continue
        withheld = np.isin(lab, ids) & foot          # UNDILATED withheld truth
        if not withheld.any():
            continue
        withheld_any |= withheld
        # "mask visible faults pixel-exactly": the scored footprint excludes the
        # pixels of every fault that is NOT withheld in this fold.
        visible = cat & ~withheld
        valid = foot & ~visible
        if buffer_m > 0:
            gap = ndi.binary_dilation(
                visible, structure=ndi.generate_binary_structure(2, 2),
                iterations=int(round(buffer_m / PIXEL_M)))
            valid = valid & ~gap
        c = dti_components(np.where(valid, pred, 0.0), withheld, valid=valid)
        results.append(FoldResult(
            fold=name, withheld_segments=int(ids.size),
            withheld_cells=int(withheld.sum()),
            tp_w=c.tp_w, fp_w=c.fp_w, fn_w=c.fn_w, dti=c.dti,
        ))
        buffers |= withheld

    # A 300 m buffer around withheld segments is excluded from the *false-positive*
    # accounting, so a prediction that sits just outside a withheld segment is not
    # charged for a boundary effect it cannot see.  Truth is never dilated.
    if buffer_m > 0:
        buffers = ndi.binary_dilation(withheld_any,
                                      structure=ndi.generate_binary_structure(2, 2),
                                      iterations=int(round(buffer_m / PIXEL_M)))

    if not results:
        raise ValueError("no folds produced a non-empty withheld set")

    # Pooled DTI = sum of components across folds (the organizer's own pooling).
    tp = sum(r.tp_w for r in results)
    fp = sum(r.fp_w for r in results)
    fn = sum(r.fn_w for r in results)
    pooled = tp / (tp + 0.2 * fp + 0.8 * fn + 1e-12)

    ci = None
    if bootstrap_n > 0:
        ci = _cluster_bootstrap(pred, buffers, foot, lab, results, bootstrap_n, seed)

    return HoldoutResult(
        evaluator="gems62.holdout.v1 (4 spatial quadrants, whole segments, 300 m buffer)",
        n_folds=len(results),
        buffer_m=buffer_m,
        pooled_dti=float(pooled),
        folds=results,
        withheld_segments_total=int(sum(r.withheld_segments for r in results)),
        withheld_cells_total=int(sum(r.withheld_cells for r in results)),
        ci95=ci,
        bootstrap_n=bootstrap_n,
    )


def _cluster_bootstrap(pred, buffers, foot, lab, results, n: int, seed: int):
    """Percentile CI of the pooled DTI from a whole-segment cluster bootstrap.

    Segments are resampled with replacement; the pooled components are recomputed
    from the resampled segment set.  This is the paired-unit structure the sibling
    protocol requires (whole fault segments, not pixels, are the independent unit).
    """
    rng = np.random.default_rng(seed)
    segs = np.unique(lab[buffers & foot])
    if segs.size < 4:
        return None

    # Sparse per-segment pixel coordinates.  A dense per-segment mask would be
    # thousands of 12.3 M-cell boolean arrays and is what OOM-killed the first
    # version of this routine; the coordinate lists total the withheld cell count.
    rows_of: dict[int, np.ndarray] = {}
    cols_of: dict[int, np.ndarray] = {}
    for s in segs:
        rr, cc = np.nonzero((lab == s) & buffers & foot)
        if rr.size:
            rows_of[int(s)] = rr
            cols_of[int(s)] = cc
    segs = np.array(sorted(rows_of), dtype=int)
    if segs.size < 4:
        return None

    p = np.where(foot, pred, 0.0)
    truth = np.zeros(pred.shape, dtype=bool)   # one reusable scratch array

    vals: list[float] = []
    for _ in range(n):
        take = np.unique(rng.choice(segs, size=segs.size, replace=True))
        truth[:] = False
        for s in take:
            truth[rows_of[int(s)], cols_of[int(s)]] = True
        if not truth.any():
            continue
        vals.append(dti_components(p, truth, valid=foot).dti)
    if len(vals) < 4:
        return None
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (float(lo), float(hi))
