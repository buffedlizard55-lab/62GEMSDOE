#!/usr/bin/env python3
"""Apply the literal uniqueness stop rule against every registry raster.

A positive Spearman rho > 0.90 or one-sided Euclidean dot overlap > 0.70
within 3 px trips the gate. Dense comparators may make overlap uninformative,
but density and Jaccard are diagnostics only: neither may suppress a trip.

Effective 3 px coverage is retained to expose the known density-blindness of
the one-sided rule. The registry is streamed (one comparator in memory at a
time) so the comparison does not OOM.

Usage:
  python3 scripts/uniqueness_gate.py <candidate.tif> [<candidate.tif> ...]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid as G          # noqa: E402

REG = Path.home() / ".cache" / "gems62_registry"
EFFECTIVE_DISCRIMINATING = 0.50  # diagnostic only; never filters a comparator from the gate
OV_LIMIT = 0.70
RHO_LIMIT = 0.90
TOLERANCE_PX = 3.0
MAX_EXACT_COVER = 40


def one_sided_overlap(candidate: np.ndarray, registry: np.ndarray,
                      footprint: np.ndarray, tolerance_px: float = TOLERANCE_PX) -> float:
    """Fraction of candidate positives within an inclusive Euclidean pixel radius."""
    mine = np.asarray(candidate, dtype=bool) & np.asarray(footprint, dtype=bool)
    other = np.asarray(registry, dtype=bool) & np.asarray(footprint, dtype=bool)
    if not mine.any() or not other.any():
        return 0.0
    distance = ndi.distance_transform_edt(~other)
    return float((distance[mine] <= tolerance_px).mean())


def protocol_verdict(max_rho: float, max_overlap: float, *, n_comparators: int) -> dict:
    """Apply the binding positive-rho and one-sided-overlap thresholds."""
    rho_trip = bool(np.isfinite(max_rho) and max_rho > RHO_LIMIT)
    overlap_trip = bool(max_overlap > OV_LIMIT)
    passed = bool(n_comparators) and not (rho_trip or overlap_trip)
    label = ("DISTINCT LANE" if passed else
             "NOT VERIFIED - EMPTY REGISTRY" if not n_comparators else "DUPLICATE - STOP")
    return dict(rho_trip=rho_trip, overlap_trip=overlap_trip, passed=passed,
                verdict=label, rho_limit=RHO_LIMIT, overlap_limit=OV_LIMIT,
                overlap_kernel_px=TOLERANCE_PX)


def positives(path):
    """Read a comparator and return (bool positive mask, coverage sanity) or None."""
    with rasterio.open(path) as d:
        if (d.height, d.width) != (G.HEIGHT, G.WIDTH):
            return None
        a = d.read(1)
        nod = d.nodata
    a = np.asarray(a, dtype=np.float32)
    if nod is not None and np.isfinite(nod):
        a = np.where(a == np.float32(nod), np.float32(0.0), a)
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    return a > 0


def main(paths):
    g = G.load_grid(ROOT)
    h, w = g.footprint.shape
    fp = int(g.footprint.sum())
    rasters = sorted(REG.rglob("*.tif"))
    t0 = time.time()

    meta, skipped = [], []
    for p in rasters:
        try:
            pos = positives(p)
        except Exception as e:                                    # noqa: BLE001
            skipped.append(dict(file=p.name, reason=f"read error: {e}")); continue
        if pos is None:
            skipped.append(dict(file=p.name, reason="not on the competition grid")); continue
        pos &= g.footprint
        n = int(pos.sum())
        del pos
        if n == 0:
            continue
        meta.append(dict(file=p.name, repo=p.relative_to(REG).parts[0],
                         path=str(p), bytes=p.stat().st_size, n_positive=n,
                         coverage_frac=n / fp))
    print(f"[gate] pass 1: {len(meta)} comparators with positives, {len(skipped)} skipped, "
          f"{time.time()-t0:.0f}s", flush=True)

    order = sorted(meta, key=lambda r: -r["n_positive"])
    eff = {}
    for r in order[:MAX_EXACT_COVER]:
        pos = positives(Path(r["path"])) & g.footprint
        distance = ndi.distance_transform_edt(~pos)
        eff[r["file"]] = float(((distance <= TOLERANCE_PX) & g.footprint).sum()) / fp
        del pos, distance
    for r in order[MAX_EXACT_COVER:]:
        # 29 integer-offset cells lie in a radius-3 Euclidean disk (including center).
        eff[r["file"]] = min(1.0, r["n_positive"] * 29.0 / fp)
    for r in meta:
        r["effective_coverage"] = eff[r["file"]]
        r["discriminating"] = bool(eff[r["file"]] <= EFFECTIVE_DISCRIMINATING)
    print(f"[gate] pass 2: effective coverage exact for {min(MAX_EXACT_COVER,len(order))}, "
          f"bounded for {max(0,len(order)-MAX_EXACT_COVER)}; "
          f"{sum(1 for r in meta if r['discriminating'])} discriminating comparators, "
          f"{time.time()-t0:.0f}s", flush=True)

    out = {}
    for path in paths:
        path = Path(path)
        with rasterio.open(path) as d:
            arr = np.asarray(d.read(1), dtype=np.float32)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        mine = (arr > 0) & g.footprint
        del arr
        rr, cc = np.nonzero(mine)
        n_mine = int(rr.size)
        rng = np.random.default_rng(3)
        # The rank-correlation leg is a correlation of two VALUE fields over the
        # common grid, so the sample must be drawn from the footprint -- not from
        # this file's own positive pixels (which would make one side constant and
        # the coefficient undefined).
        fpi = np.flatnonzero(g.footprint.ravel())
        sample = rng.choice(fpi, min(200_000, fpi.size), replace=False)
        s_r, s_c = np.divmod(sample, w)
        rows = []
        for r in meta:
            pos = positives(Path(r["path"])) & g.footprint
            ov = one_sided_overlap(mine, pos, g.footprint)
            inter_n = int((pos & mine).sum())
            union_n = r["n_positive"] + n_mine - inter_n
            rho, meth = float("nan"), None
            if n_mine and s_r.size > 2:
                their = pos[s_r, s_c]
                x = mine[s_r, s_c]
                if np.unique(x).size > 1 and np.unique(their).size > 1:
                    rho, meth = float(spearmanr(x, their).statistic), "spearman"
                elif x.std() > 0 and their.std() > 0:
                    rho, meth = float(np.corrcoef(x, their)[0, 1]), "point_biserial"
                elif x.std() == 0 and their.std() == 0:
                    rho, meth = float("nan"), "both_constant_over_sample"
            del pos
            rows.append(dict(file=r["file"], repo=r["repo"], n_positive=r["n_positive"],
                             coverage_frac=r["coverage_frac"],
                             effective_coverage=r["effective_coverage"],
                             discriminating=r["discriminating"],
                             overlap_3px_one_sided=ov,
                             jaccard=inter_n / union_n if union_n else 0.0,
                             spearman=rho, spearman_method=meth))
        rows.sort(key=lambda r: -r["overlap_3px_one_sided"])
        disc = [r for r in rows if r["discriminating"]]
        nond = [r for r in rows if not r["discriminating"]]
        fin = [r for r in rows if np.isfinite(r["spearman"])]
        worst_all = rows[0] if rows else None
        worst_disc = disc[0] if disc else None
        worst_rho_abs = max(fin, key=lambda r: abs(r["spearman"])) if fin else None
        max_positive_rho = max((r["spearman"] for r in fin), default=float("nan"))
        worst_jac = max(nond, key=lambda r: r["jaccard"]) if nond else None
        max_overlap_all = max((r["overlap_3px_one_sided"] for r in rows), default=0.0)
        max_overlap_disc = max((r["overlap_3px_one_sided"] for r in disc), default=0.0)
        protocol = protocol_verdict(max_positive_rho, max_overlap_all,
                                   n_comparators=len(rows))
        strict = bool(rows) and not protocol["overlap_trip"]
        inform = bool(worst_disc is None or max_overlap_disc <= OV_LIMIT)
        rho_ok = not protocol["rho_trip"]
        verdict = protocol["verdict"]
        out[path.name] = dict(
            n_positive=n_mine, verdict=verdict, passed=protocol["passed"],
            strict_leg_pass=strict, informative_leg_pass=inform,
            correlation_leg_pass=rho_ok,
            rho_trip=protocol["rho_trip"], overlap_trip=protocol["overlap_trip"],
            n_comparators=len(rows), n_discriminating=len(disc),
            max_positive_spearman=max_positive_rho,
            max_abs_spearman_diagnostic=(abs(worst_rho_abs["spearman"])
                                         if worst_rho_abs else float("nan")),
            max_overlap_all=max_overlap_all,
            max_overlap_discriminating_diagnostic=max_overlap_disc,
            worst_overlap_all=worst_all, worst_overlap_discriminating=worst_disc,
            worst_spearman=worst_rho_abs,
            worst_jaccard_among_nondiscriminating=worst_jac,
            rule=dict(overlap_limit=OV_LIMIT, rho_limit=RHO_LIMIT,
                      tolerance_px=TOLERANCE_PX,
                      effective_discriminating_diagnostic=EFFECTIVE_DISCRIMINATING,
                      dense_comparator_action="report diagnostic; preserve strict trip",
                      jaccard_is_gate=False),
            rows=rows)
        print(f"[gate] {path.name}: n={n_mine} -> {verdict}; strict worst ov "
              f"{(worst_all['overlap_3px_one_sided'] if worst_all else float('nan')):.4f}; "
              f"discriminating diagnostic "
              f"{(worst_disc['overlap_3px_one_sided'] if worst_disc else float('nan')):.4f} "
              f"over {len(disc)} comparators; max positive rho {max_positive_rho:.4f}", flush=True)
    json.dump(out, open(ROOT / "evidence/uniqueness_gate.json", "w"), indent=1, default=str)
    json.dump(dict(comparators=meta, skipped=skipped, footprint_px=fp),
              open(ROOT / "evidence/registry_comparators.json", "w"), indent=1, default=str)
    print(f"wrote evidence/uniqueness_gate.json in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
