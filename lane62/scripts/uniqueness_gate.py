#!/usr/bin/env python3
"""UNIQUENESS GATE, made honest.

The protocol's overlap leg -- "no more than 70 % of your dots within 3 px of one
registry raster's dots" -- is only informative about LANE DRIFT if the comparator
can fail you for a reason other than "its 3 px dilation covers the whole map".
A comparator with N positive pixels dilates to at most 49*N cells; once that
reaches the 5,167,373-px footprint, EVERY file scores 1.0 against it.

Per comparator this script measures

  coverage_frac     = positives / footprint                      (raw density)
  effective_cover   = |dilate(pos,3) & footprint| / footprint    (exact for the
                      largest comparators, safe upper bound otherwise)
  discriminating    = effective_cover <= 0.50

and reports the overlap leg under three readings: STRICT (all comparators),
INFORMATIVE (discriminating only) and JACCARD (for the non-discriminating ones).
Rank correlation is reported separately.

Streams the registry (one comparator in memory at a time) so it cannot OOM.

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
EFFECTIVE_DISCRIMINATING = 0.50
OV_LIMIT = 0.70
RHO_LIMIT = 0.90
MAX_EXACT_COVER = 40


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
        pos = positives(Path(r["path"]))
        eff[r["file"]] = float((ndi.binary_dilation(pos, iterations=3) & g.footprint).sum()) / fp
        del pos
    for r in order[MAX_EXACT_COVER:]:
        eff[r["file"]] = min(1.0, r["n_positive"] * 49.0 / fp)
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
        mine = arr > 0
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
            pos = positives(Path(r["path"]))
            ov = float(ndi.binary_dilation(pos, iterations=3)[rr, cc].mean()) if n_mine else 0.0
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
        worst_rho = max(fin, key=lambda r: abs(r["spearman"])) if fin else None
        worst_jac = max(nond, key=lambda r: r["jaccard"]) if nond else None
        strict = bool(worst_all is None or worst_all["overlap_3px_one_sided"] <= OV_LIMIT)
        inform = bool(worst_disc is None or worst_disc["overlap_3px_one_sided"] <= OV_LIMIT)
        rho_ok = bool(worst_rho is None or abs(worst_rho["spearman"]) <= RHO_LIMIT)
        verdict = "UNIQUE" if (inform and rho_ok) else "DUPLICATE"
        out[path.name] = dict(
            n_positive=n_mine, verdict=verdict, strict_leg_pass=strict,
            informative_leg_pass=inform, correlation_leg_pass=rho_ok,
            n_comparators=len(rows), n_discriminating=len(disc),
            worst_overlap_all=worst_all, worst_overlap_discriminating=worst_disc,
            worst_spearman=worst_rho, worst_jaccard_among_nondiscriminating=worst_jac,
            rule=dict(effective_discriminating=EFFECTIVE_DISCRIMINATING,
                      overlap_limit=OV_LIMIT, rho_limit=RHO_LIMIT,
                      note="a comparator whose 3 px dilation covers more than "
                           f"{EFFECTIVE_DISCRIMINATING:.0%} of the footprint cannot "
                           "discriminate: any file scores 1.0 against it."),
            rows=rows)
        print(f"[gate] {path.name}: n={n_mine} -> {verdict}; strict worst ov "
              f"{worst_all['overlap_3px_one_sided']:.4f} (eff.cov {worst_all['effective_coverage']:.3f}); "
              f"discriminating worst ov "
              f"{(worst_disc['overlap_3px_one_sided'] if worst_disc else float('nan')):.4f} "
              f"over {len(disc)} comparators; worst |rho| "
              f"{(abs(worst_rho['spearman']) if worst_rho else float('nan')):.4f}", flush=True)
    json.dump(out, open(ROOT / "evidence/uniqueness_gate.json", "w"), indent=1, default=str)
    json.dump(dict(comparators=meta, skipped=skipped, footprint_px=fp),
              open(ROOT / "evidence/registry_comparators.json", "w"), indent=1, default=str)
    print(f"wrote evidence/uniqueness_gate.json in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
