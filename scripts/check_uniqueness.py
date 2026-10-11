#!/usr/bin/env python3
"""Literal lane-drift gate for the submitted raster and every registry comparator.

The binding parallel-run protocol trips when rank correlation exceeds 0.90 or
more than 70% of the candidate's positive cells are within 3 px of any one
registry raster. The Euclidean one-sided overlap is the gate; Jaccard is retained
as a diagnostic only. A dense comparator can make the one-sided condition
uninformative, but that limitation is reported and does not silently change the
specified decision rule.

The registry may contain a very dense raster whose 3 px neighbourhood covers most of the
footprint. That can trip the literal test even when the candidates are not meaningfully similar;
the script reports comparator coverage and Jaccard so reviewers can see this failure mode, but it
does not replace the binding overlap verdict.

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
from gems62.uniqueness import (OVERLAP_LIMIT, RHO_LIMIT, TOLERANCE_PX,
                               protocol_verdict)  # noqa: E402


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
    ap.add_argument("--rank-threshold", type=float, default=RHO_LIMIT)
    ap.add_argument("--overlap-threshold", type=float, default=OVERLAP_LIMIT)
    ap.add_argument("--kernel-px", type=float, default=TOLERANCE_PX)
    ap.add_argument("--jaccard-threshold", type=float, default=0.25)
    args = ap.parse_args()

    import rasterio
    from scipy import ndimage

    with rasterio.open(args.raster) as s:
        mine = s.read(1).astype(np.float32)
    H, W = mine.shape
    if args.footprint:
        with rasterio.open(args.footprint) as s:
            footprint = np.isfinite(s.read(1))
    else:
        footprint = np.ones_like(mine, bool)
    if footprint.shape != mine.shape:
        raise ValueError(f"footprint shape {footprint.shape} != raster shape {mine.shape}")
    mine_pos = (mine > 0) & footprint
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
        other_pos = (other > 0) & footprint
        rr, cc = np.nonzero(mine_pos | other_pos)
        if rr.size == 0:
            results.append(dict(file=p.name, skipped="no-positives"))
            continue
        a = np.concatenate([mine[rr, cc], mine[bg]])
        b = np.concatenate([other[rr, cc], other[bg]])
        rho = spearman(a, b)
        # Binding one-sided overlap and the density/vacuity diagnostic use the
        # same Euclidean 3 px neighbourhood on the official footprint.
        if other_pos.any():
            d = ndimage.distance_transform_edt(~other_pos)
            near = d <= args.kernel_px
            frac = float(near[mine_pos].mean()) if mine_pos.any() else 0.0
            coverage = float(near[footprint].mean()) if footprint.any() else 0.0
        else:
            frac = 0.0
            coverage = 0.0
        # Symmetric dilation/Jaccard is reported as a diagnostic only. It does
        # not override the binding one-sided overlap condition above.
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
                            comparator_coverage_within_kernel=round(coverage, 4),
                            comparator_vacuous=bool(coverage >= args.overlap_threshold),
                            dilated_jaccard=round(jac, 4),
                            n_mine=int(mine_pos.sum()), n_theirs=int(other_pos.sum()),
                            rank_flag=bool(rho > args.rank_threshold) if not np.isnan(rho) else False,
                            overlap_flag=bool(frac > args.overlap_threshold),
                            jaccard_diagnostic_flag=bool(jac > args.jaccard_threshold)))
    comparable = [r for r in results if "dot_overlap_within_kernel" in r]
    ranked = [r for r in comparable if r.get("rank_corr") is not None]
    worst_rank = max(ranked, key=lambda r: r["rank_corr"]) if ranked else None
    worst_ovl = max(comparable, key=lambda r: r["dot_overlap_within_kernel"]) if comparable else None
    worst_jac = max(comparable, key=lambda r: r["dilated_jaccard"]) if comparable else None
    max_rho = max((r["rank_corr"] for r in ranked), default=float("nan"))
    max_overlap = max((r["dot_overlap_within_kernel"] for r in comparable), default=0.0)
    gate = protocol_verdict(max_rho, max_overlap,
                            n_comparators=len(comparable),
                            rho_limit=args.rank_threshold,
                            overlap_limit=args.overlap_threshold)
    rank_trip = gate["rho_trip"]
    overlap_trip = gate["overlap_trip"]
    report = dict(raster=pathlib.Path(args.raster).name, raster_sha256=grid.sha256(args.raster),
                  n_registry=len(comparable), n_rank_comparable=len(ranked),
                  thresholds=dict(rank=args.rank_threshold, overlap=args.overlap_threshold,
                                  kernel_px=args.kernel_px,
                                  jaccard_diagnostic=args.jaccard_threshold),
                  protocol=dict(rank_rule="positive Spearman rho > rank threshold",
                                overlap_rule="one-sided Euclidean dot fraction > overlap threshold",
                                dense_comparator_action="report diagnostic but preserve strict trip"),
                  worst_rank_corr=worst_rank, worst_overlap=worst_ovl, worst_jaccard=worst_jac,
                  n_vacuous_comparators=sum(bool(r.get("comparator_vacuous")) for r in comparable),
                  any_rank_flag=rank_trip, any_overlap_flag=overlap_trip,
                  protocol_gate=gate, verdict=gate["verdict"],
                  note=("Jaccard is diagnostic only. A trip against a dense comparator still follows "
                        "the binding threshold and must be logged as duplicate/stop."),
                  results=results)
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in ("verdict", "n_registry", "worst_rank_corr",
                                             "worst_overlap", "worst_jaccard")}, indent=1))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
