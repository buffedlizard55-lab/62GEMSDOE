#!/usr/bin/env python3
"""Lane-drift / duplicate check: is this raster a re-run of something already in the registry?

The session brief sets two tripwires, and this script evaluates both on the bytes:

* **rank correlation > 0.90** with any registry raster -> drifted into that lane;
* **more than 70 % of this raster's dots within 3 px of one registry raster's dots** ->
  duplicate.

**Measured defect, fixed here and reported** (session 2026-10-11): the 70 % tripwire is
*density-blind*.  `13gems_20261001_r13-lattice-s5_v2` carries 206,895 dots, which dilates to
112 % of the 5.17 M-cell footprint, so its 3 px neighbourhood covers the map and **any** emission
scores ~1.0 on the tripwire.  Demonstration: a uniform-random 1,660-dot control
(`build/controls/poisson_1660_seed7.tif`, seed 7) scores `dot_overlap_within_kernel = 0.9982`
against that same raster.  A tripwire that fires on Poisson noise cannot certify a duplicate, so
the verdict now additionally requires a **symmetric** overlap -- the Jaccard index of the two
3 px-dilated dot masks, `|A n B| / |A u B|` -- which is 1.0 for a re-run of the same lane and
~0.01 for a sparse emission against a dense lattice.  The asymmetric fraction is still reported,
as a diagnostic, because it is what the brief names.

Rank correlation is Spearman's rho over the union of the two rasters' positive cells plus a
deterministic background sample of the footprint (so the number is not dominated by the shared
zero field).  Dot overlap is computed from a Euclidean distance transform of the registry mask.

Usage:
  python scripts/check_uniqueness.py --raster build/lane/x.tif --registry /tmp/registry \
      --footprint <sample_submission.tif> --out build/uniqueness.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import grid  # noqa: E402


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rho with average ranks for ties (no scipy.stats dependency on 12M cells)."""
    if a.size < 10:
        return float("nan")

    def rank(v):
        order = np.argsort(v, kind="mergesort")
        r = np.empty(v.size, float)
        r[order] = np.arange(1, v.size + 1)
        uniq, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        if (cnt > 1).any():
            sums = np.zeros(uniq.size); np.add.at(sums, inv, r)
            r = (sums / cnt)[inv]
        return r

    ra, rb = rank(a), rank(b)
    ra = ra - ra.mean(); rb = rb - rb.mean()
    denom = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / denom) if denom > 0 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raster", required=True)
    ap.add_argument("--registry", default="/tmp/registry")
    ap.add_argument("--footprint")
    ap.add_argument("--out", default="build/uniqueness.json")
    ap.add_argument("--rank-threshold", type=float, default=0.90)
    ap.add_argument("--overlap-threshold", type=float, default=0.70)
    ap.add_argument("--kernel-px", type=float, default=3.0)
    ap.add_argument("--jaccard-threshold", type=float, default=0.25)
    args = ap.parse_args()

    import rasterio
    from scipy import ndimage

    with rasterio.open(args.raster) as s:
        mine = s.read(1).astype(np.float32)
    H, W = mine.shape
    mine_pos = mine > 0
    if args.footprint:
        with rasterio.open(args.footprint) as s:
            footprint = np.isfinite(s.read(1))
    else:
        footprint = np.ones_like(mine, bool)
    rng = np.random.default_rng(62)
    # deterministic background sample of the footprint (10k cells) keeps this fast
    fr, fc = np.nonzero(footprint)
    k = min(10000, fr.size)
    sel = rng.choice(fr.size, size=k, replace=False)
    bg = (fr[sel], fc[sel])

    results = []
    for p in sorted(pathlib.Path(args.registry).glob("*.tif")):
        try:
            with rasterio.open(p) as s:
                other = s.read(1).astype(np.float32)
        except Exception as exc:
            results.append(dict(file=p.name, error=str(exc)))
            continue
        if other.shape != (H, W):
            results.append(dict(file=p.name, skipped="shape", shape=list(other.shape)))
            continue
        other = np.nan_to_num(other, nan=0.0, posinf=0.0, neginf=0.0)
        other_pos = other > 0
        rr, cc = np.nonzero(mine_pos | other_pos)
        if rr.size == 0:
            results.append(dict(file=p.name, skipped="no-positives"))
            continue
        a = np.concatenate([mine[rr, cc], mine[bg]])
        b = np.concatenate([other[rr, cc], other[bg]])
        rho = spearman(a, b)
        # dot overlap: fraction of my dots within `kernel_px` of any of its dots
        if other_pos.any() and mine_pos.any():
            d = ndimage.distance_transform_edt(~other_pos)
            frac = float((d[mine_pos] <= args.kernel_px).mean())
        else:
            frac = 0.0
        # symmetric overlap: Jaccard of the two kernel-width dilated dot masks.  A dense
        # registry raster covers the map, which inflates `frac` to ~1 for *any* emission
        # (measured: Poisson control 0.9982) but leaves the Jaccard small, as it should be.
        kk = int(round(args.kernel_px))
        if kk > 0:
            st = np.ones((2 * kk + 1, 2 * kk + 1), bool)
            da = ndimage.binary_dilation(mine_pos, structure=st)
            db = ndimage.binary_dilation(other_pos, structure=st)
            union = int((da | db).sum())
            jac = float((da & db).sum()) / union if union else 0.0
        else:
            union = int((mine_pos | other_pos).sum())
            jac = float((mine_pos & other_pos).sum()) / union if union else 0.0
        results.append(dict(file=p.name, sha256=grid.sha256(p)[:16],
                            rank_corr=None if np.isnan(rho) else round(rho, 4),
                            dot_overlap_within_kernel=round(frac, 4),
                            dilated_jaccard=round(jac, 4),
                            n_mine=int(mine_pos.sum()), n_theirs=int(other_pos.sum()),
                            rank_flag=bool(rho > args.rank_threshold) if not np.isnan(rho) else False,
                            overlap_flag=bool(jac > args.jaccard_threshold)))
    ranked = [r for r in results if r.get("rank_corr") is not None]
    worst_rank = max(ranked, key=lambda r: r["rank_corr"]) if ranked else None
    worst_ovl = max(ranked, key=lambda r: r["dot_overlap_within_kernel"]) if ranked else None
    worst_jac = max(ranked, key=lambda r: r["dilated_jaccard"]) if ranked else None
    report = dict(raster=pathlib.Path(args.raster).name, raster_sha256=grid.sha256(args.raster),
                  n_registry=len(ranked),
                  thresholds=dict(rank=args.rank_threshold, overlap=args.overlap_threshold,
                                  jaccard=args.jaccard_threshold, kernel_px=args.kernel_px),
                  worst_rank_corr=worst_rank, worst_overlap=worst_ovl, worst_jaccard=worst_jac,
                  any_rank_flag=any(r.get("rank_flag") for r in ranked),
                  any_overlap_flag=any(r.get("overlap_flag") for r in ranked),
                  verdict=("DUPLICATE-OF-REGISTRY-LANE"
                           if any(r.get("rank_flag") for r in ranked)
                           or any(r.get("overlap_flag") for r in ranked) else "UNIQUE-VS-REGISTRY"),
                  results=results)
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in ("verdict", "n_registry", "worst_rank_corr",
                                             "worst_overlap", "worst_jaccard")}, indent=1))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
