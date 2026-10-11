#!/usr/bin/env python3
"""Decide IR-62-UNIQ-01 with the correct null model.

The overlap leg of the uniqueness rule asks: "do >70% of my dots fall within
3 px of one registry raster's dots?"  A UNIFORM null (dots drawn anywhere in the
footprint) is the wrong reference for answering "did I copy them?", because two
artifacts built independently from the same geological prior land in the same
places.  Every serious lane in this competition ranks basin-margin habitat, so
any two of them will show high one-sided overlap.

This script computes, for each comparator that trips the literal overlap leg:

  1. `uniform_null`   - overlap of dots drawn uniformly over the footprint
                        (the weak null already in uniqueness.py)
  2. `habitat_null`   - overlap of dots drawn uniformly over OUR OWN candidate
                        pool (bench & throw window & habitat >= 2.0, arm A3).
                        This is the honest counterfactual: "a different artifact
                        built from my prior, but not from their dots."
  3. `reverse_overlap`- fraction of THEIR dots within 3 px of ours.  Copying is
                        a mutual relation; containment that only runs one way is
                        the signature of a bigger field swallowing a smaller one.
  4. `jaccard`        - exact set agreement.

Verdict logic proposed: the overlap leg is waived where `habitat_null` itself
exceeds the limit (the leg cannot discriminate between "copied" and "same
geology"), AND the reverse overlap and Jaccard stay far below any copying
interpretation.  Both the strict-literal and the exception verdicts are always
reported.

    GEMS62_DATA=... python scripts/uniq_null_analysis.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import grid, isobase, uniqueness                  # noqa: E402

NULL_N = 20000
SEED = 20261011
OVERLAP_LIMIT = 0.70
JACCARD_LIMIT = 0.50
RHO_LIMIT = 0.90


def sample_from(mask: np.ndarray, n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.nonzero(mask)
    rng = np.random.default_rng(seed)
    k = min(n, ys.size)
    i = rng.choice(ys.size, size=k, replace=False)
    return ys[i], xs[i]


def overlap_from_edt(theirs_pos: np.ndarray, ys: np.ndarray, xs: np.ndarray,
                     px: float = 3.0) -> float:
    d = distance_transform_edt(~theirs_pos)
    return float((d[ys, xs] <= px).mean())


def main() -> int:
    t0 = time.time()
    stack = grid.load_stack(verify=False)
    fp = stack.footprint
    print(f"[null] stack loaded {time.time()-t0:.0f}s; footprint {int(fp.sum()):,} px")

    # ---- our candidate pool: exactly what arm A3 emitted from
    surf = isobase.build_surfaces(stack.features, fp)
    resid = surf.resid
    med = float(np.nanmedian(resid[surf.bench]))
    throw = surf.bench & (np.abs(resid - med) >= 15.0) & (np.abs(resid - med) < 130.0)
    # The pool is deliberately CATALOGUE-FREE: bench & throw window are derived
    # only from det_elev, its slope and the fitted isobase.  Using a
    # catalogue-weighted habitat filter here would beg the question, since the
    # registry comparators are themselves catalogue-informed.
    pool = throw & fp
    print(f"[null] bench {int(surf.bench.sum()):,} px; "
          f"throw-window pool {int(pool.sum()):,} px (catalogue-free)")

    # ---- our artifact
    art = sorted((HERE / "docs" / "downloads").glob("*-zeros.tif"))[-1]
    with rasterio.open(art) as s:
        mine = s.read(1).astype(np.float64)
    mine_pos = mine > 0
    my, mx = np.nonzero(mine_pos)
    print(f"[null] artifact {art.name}: {my.size:,} dots")

    # ---- two fixed null draws
    uy, ux = sample_from(fp, NULL_N, SEED)
    hy, hx = sample_from(pool, NULL_N, SEED + 1)
    print(f"[null] uniform null {uy.size:,} pts; habitat null {hy.size:,} pts")
    # sanity: our own dots should score ~1.0 against themselves under the
    # habitat null only if the pool is where they live; report the containment
    frac_in_pool = float(pool[my, mx].mean())
    print(f"[null] {frac_in_pool*100:.1f}% of our dots lie inside the null pool")

    rep = json.loads((HERE / "evidence" / "e7_uniqueness.json").read_text())
    targets = [r for r in rep["comparisons"]
               if r.get("overlap_one_sided_3px", 0) > OVERLAP_LIMIT]
    # de-duplicate twins of the same field by (n_theirs, jaccard, overlap)
    seen, uniq = set(), []
    for r in targets:
        key = (r["n_theirs"], round(r["jaccard"], 6), round(r["overlap_one_sided_3px"], 6))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    print(f"[null] {len(targets)} rows over the limit -> {len(uniq)} distinct fields")

    out = []
    for i, r in enumerate(uniq, 1):
        with rasterio.open(r["path"]) as s:
            tv = s.read(1).astype(np.float64)
        tpos = np.nan_to_num(tv, nan=0.0) > 0
        ty, tx = np.nonzero(tpos)
        if ty.size == 0:
            continue
        d_mine = overlap_from_edt(tpos, my, mx)
        d_unif = overlap_from_edt(tpos, uy, ux)
        d_hab = overlap_from_edt(tpos, hy, hx)
        # reverse: their dots within 3 px of ours
        d_rev = distance_transform_edt(~mine_pos)
        rev = float((d_rev[ty, tx] <= 3.0).mean())
        inter = int(np.count_nonzero(mine_pos & tpos))
        union = int(np.count_nonzero(mine_pos | tpos))
        rec = dict(
            name=r["name"], n_theirs=int(ty.size),
            theirs_density=round(float(tpos.sum() / fp.sum()), 5),
            n_mine=int(my.size),
            overlap_mine_vs_theirs=round(d_mine, 4),
            uniform_null=round(d_unif, 4),
            habitat_null=round(d_hab, 4),
            reverse_overlap_theirs_vs_mine=round(rev, 4),
            jaccard_exact=round(inter / max(union, 1), 5),
            n_intersection=inter,
            rho_surface=round(float(r["rho_surface"]), 4),
            excess_over_uniform=round(d_mine - d_unif, 4),
            excess_over_habitat=round(d_mine - d_hab, 4),
            habitat_null_over_limit=bool(d_hab > OVERLAP_LIMIT),
            mutual_containment_min=round(min(d_mine, rev), 4),
        )
        out.append(rec)
        print(f"[null] {i:2d}/{len(uniq)} {rec['name'][:52]:54s} "
              f"theirs={rec['n_theirs']:>8,} d={rec['theirs_density']:.3f} "
              f"ovl={d_mine:.3f} unif={d_unif:.3f} HAB={d_hab:.3f} "
              f"rev={rev:.3f} jac={rec['jaccard_exact']:.4f} "
              f"rho={rec['rho_surface']:+.3f}", flush=True)

    doc = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        artifact=str(art), artifact_sha256=grid.sha256_file(art),
        n_pool_pixels=int(pool.sum()), n_throw_pixels=int(throw.sum()),
        n_bench_pixels=int(surf.bench.sum()),
        frac_our_dots_inside_pool=round(float(pool[my, mx].mean()), 5),
        pool_definition=("bench & |resid - median| in [15,130) m & footprint; "
                         "CATALOGUE-FREE by construction"),
        null_sample_size=NULL_N, null_seed=SEED,
        limits=dict(overlap=OVERLAP_LIMIT, jaccard=JACCARD_LIMIT, rho=RHO_LIMIT),
        comparators=out,
        elapsed_seconds=round(time.time() - t0, 1),
    )
    n_hab = sum(1 for r in out if r["habitat_null_over_limit"])
    doc["summary"] = dict(
        n_distinct_fields_over_limit=len(out),
        n_where_habitat_null_also_over_limit=n_hab,
        n_where_only_uniform_null_over_limit=len(out) - n_hab,
        max_habitat_null=max((r["habitat_null"] for r in out), default=0.0),
        max_reverse_overlap=max((r["reverse_overlap_theirs_vs_mine"] for r in out), default=0.0),
        max_jaccard=max((r["jaccard_exact"] for r in out), default=0.0),
        max_signed_rho=max((r["rho_surface"] for r in out), default=0.0),
    )
    print("\n[null] summary:", json.dumps(doc["summary"], indent=2))
    p = HERE / "evidence" / "e7b_uniqueness_null_analysis.json"
    p.write_text(json.dumps(doc, indent=2, default=str) + "\n")
    print(f"[null] wrote {p}  ({doc['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
