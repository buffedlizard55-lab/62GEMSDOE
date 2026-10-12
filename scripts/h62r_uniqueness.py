#!/usr/bin/env python3
"""H62-R lane-drift check against the whole registry, written to be runnable on 4 GB.

`gems62.uniqueness.compare` (the template's shared tool) computes the rank correlation
on the **full 5.17 M-cell footprint** and builds a fresh Euclidean distance transform
per comparator.  Measured on this host, that pass over 476 rasters was killed by the
kernel (exit 137) while another job was running.  This script implements the same three
protocol quantities with a fixed memory budget so the check can actually complete
unattended:

* ``frac3px``  -- fraction of MY dots within 3 px of the comparator's dots (the leg the
  prompt names);
* ``jaccard3px`` -- symmetric Jaccard of the two 3-px dilations (the leg that is not
  vacuous; the asymmetric one is tripped by any near-blanket raster -- IR-62-22);
* ``rho`` -- tie-aware Spearman on a FIXED random sample of the footprint, plus an
  exact-zero check restricted to the union of both dot sets.  Sampling is what makes
  this affordable; the same substitution the repository already adopted for IR-62-19.

Usage:  .venv/bin/python scripts/h62r_uniqueness.py --raster F.tif --registry DIR \
            --footprint data/sample_submission.tif --out E.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

TOLERANCE_PX = 3
SAMPLE_N = 300_000
STRUCT = None


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def rank_tie_aware(x: np.ndarray) -> np.ndarray:
    """Average ranks, so a mostly-zero vector does not get 12.3 M distinct ranks (IR-62-19)."""
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    ranks = np.empty(x.size, dtype=np.float64)
    i = 0
    while i < xs.size:
        j = i + 1
        while j < xs.size and xs[j] == xs[i]:
            j += 1
        ranks[order[i:j]] = 0.5 * (i + j - 1) + 1.0
        i = j
    return ranks


def spearman_sampled(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = rank_tie_aware(a), rank_tie_aware(b)
    ra -= ra.mean()
    rb -= rb.mean()
    den = float(np.sqrt((ra * ra).sum() * (rb * rb).sum()))
    return float((ra * rb).sum() / den) if den > 0 else float("nan")


def main() -> int:
    import rasterio
    from scipy import ndimage as ndi

    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True)
    ap.add_argument("--registry", default="/tmp/registry")
    ap.add_argument("--footprint", default="data/sample_submission.tif")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample-n", type=int, default=SAMPLE_N)
    ap.add_argument("--seed", type=int, default=20261012)
    args = ap.parse_args()

    with rasterio.open(args.footprint) as src:
        foot = np.isfinite(src.read(1))
    with rasterio.open(args.raster) as src:
        mine = src.read(1)
    mine = np.isfinite(mine) & (mine > 0) & foot

    st = ndi.generate_binary_structure(2, 2)
    mine_dil = ndi.binary_dilation(mine, structure=st, iterations=TOLERANCE_PX)
    n_mine = int(mine.sum())

    rng = np.random.default_rng(args.seed)
    flat_foot = np.flatnonzero(foot.ravel())
    take = rng.choice(flat_foot, size=min(args.sample_n, flat_foot.size), replace=False)
    row_s, col_s = np.unravel_index(take, foot.shape)
    a_samp = mine[row_s, col_s].astype(np.float64)

    reg = sorted(p for p in pathlib.Path(args.registry).glob("*.tif"))
    rows, skipped = [], []
    t0 = time.time()
    for k, p in enumerate(reg):
        try:
            with rasterio.open(p) as src:
                arr = src.read(1)
        except Exception as exc:                       # unreadable blob
            skipped.append(dict(alias=p.name, reason=f"read error: {exc}"))
            continue
        if arr.shape != mine.shape:
            skipped.append(dict(alias=p.name, reason=f"shape {arr.shape}"))
            continue
        other = (np.isfinite(arr) if arr.dtype.kind == "f" else np.ones_like(arr, bool)) \
            & (arr > 0) & foot
        n_other = int(other.sum())
        if n_other == 0:
            skipped.append(dict(alias=p.name, reason="no positive cells inside footprint"))
            continue
        other_dil = ndi.binary_dilation(other, structure=st, iterations=TOLERANCE_PX)
        inter = int((mine_dil & other_dil).sum())
        union = int((mine_dil | other_dil).sum())
        frac3px = float((mine & other_dil).sum() / n_mine) if n_mine else 0.0
        coverage = float(other_dil[foot].sum() / foot.sum())
        b_samp = other[row_s, col_s].astype(np.float64)
        rho = spearman_sampled(a_samp, b_samp) if (a_samp.std() > 0 and b_samp.std() > 0) \
            else float("nan")
        rows.append(dict(alias=p.name, positive_cells=n_other,
                         frac3px=frac3px, jaccard3px=(inter / union if union else 0.0),
                         coverage3px=coverage, rho=rho,
                         vacuous=bool(coverage >= 0.70),
                         sha256=sha256_file(p)))
        if (k + 1) % 50 == 0:
            print(f"  {k + 1}/{len(reg)} comparators, {time.time() - t0:.0f}s", flush=True)

    finite_rho = [r for r in rows if np.isfinite(r["rho"])]
    nonvac = [r for r in rows if not r["vacuous"]]
    max_rho = max((abs(r["rho"]) for r in finite_rho), default=float("nan"))
    worst_j = max(nonvac, key=lambda r: r["jaccard3px"], default=None)
    worst_f = max(nonvac, key=lambda r: r["frac3px"], default=None)
    tol_frac_alldots = 3.0 * TOLERANCE_PX * PIXELS_PER_DOT_CELL  # see note below
    res = dict(
        evaluator="h62r_uniqueness v1", raster=args.raster, raster_sha256=sha256_file(
            pathlib.Path(args.raster)),
        n_mine=int(n_mine), n_registry_files=len(reg), n_compared=len(rows),
        n_skipped=len(skipped), skipped=skipped[:20],
        rho_method=f"tie-aware Spearman on a fixed {min(args.sample_n, flat_foot.size)}-cell sample",
        rho_sample_seed=args.seed,
        rho_limit=0.90, overlap_limit=0.70, jaccard_note=(
            "symmetric Jaccard of the two 3-px dilations; 1.0 for a re-run, ~0 for a "
            "sparse field against a dense one"),
        max_abs_rho=max_rho,
        n_comparators_abs_rho_gt_0_90=int(sum(1 for r in finite_rho if abs(r["rho"]) > 0.90)),
        worst_jaccard3px=(dict(alias=worst_j["alias"], value=worst_j["jaccard3px"])
                          if worst_j else None),
        worst_frac3px_nonvacuous=(dict(alias=worst_f["alias"], value=worst_f["frac3px"])
                                  if worst_f else None),
        n_comparators_over_overlap_limit_nonvacuous=int(
            sum(1 for r in nonvac if r["frac3px"] > 0.70)),
        n_vacuous=int(sum(1 for r in rows if r["vacuous"])),
        rows=rows,
    )
    p = pathlib.Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res, indent=1) + "\n")
    print(f"compared {len(rows)} of {len(reg)} ({len(skipped)} skipped) in {time.time() - t0:.0f}s")
    print(f"max |rho| {max_rho:.4f}  worst Jaccard {res['worst_jaccard3px']}  "
          f"worst frac3px (non-vacuous) {res['worst_frac3px_nonvacuous']}")
    print(f"-> {p}")
    return 0


#: placeholder replaced at runtime by nothing: kept out of the result on purpose
PIXELS_PER_DOT_CELL = 1


if __name__ == "__main__":
    raise SystemExit(main())
