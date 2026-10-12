#!/usr/bin/env python3
"""EXPERIMENT 2b — the reference frame: every prior artifact measured the same way.

For each registry raster (owner-reported portal score where one exists) plus the two
fields this session emits, compute on the SAME grid and with the SAME code:

  M            dots
  credit_cat   mean 300 m kernel credit per dot against labels.tif (mapped catalogue)
  credit_sgmc  mean 300 m kernel credit per dot against SGMC 1:750k minus catalogue
  dcat_med_m   median distance of the dots to the mapped catalogue, in metres
  frac3px_*    fraction of dots within 3 px of the named field (lane drift)

The point is to see which locally measurable quantity, if any, separates the artifacts
the portal liked from the artifacts it did not — without inverting a proxy.

Usage: python3 scripts/exp2b_reference_frame.py [--extra name:path ...]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import distance_transform_edt as edt

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
from gems62 import grid  # noqa: E402

EXT = HERE / "build" / "ext"
REG = HERE / "build" / "registry"

# owner-reported portal scores, from research/registry_index.json (NOT organizer receipts)
SCORES = {
    "champion_h33_2_b2_02778": 0.2778,
    "anderson_geothermal_02750": 0.2750,
    "h36_1_rung30_r1_02710": 0.2710,
    "h27_4_r1_solo_d2_8_02708": 0.2708,
    "h38_1_hf_euler_02707": 0.2707,
    "h32_1_prethin_02649": 0.2649,
    "h33d_tip_stepover_02632": 0.2632,
    "d28_poisson300m_offcat_02600": 0.2600,
    "h25_dotted_d2_8_02600": 0.2600,
    "h25_1_dotted_d1_5_02477": 0.2477,
    "topo_gap_closure_02449": 0.2449,
    "gate_ortho_w025_02376": 0.2376,
    "h59_cover_ds_belief_02296": 0.2296,
    "h19_5_powerlaw_01922": 0.1922,
    "h19_4_multiline_01894": 0.1894,
    "calib_h161_01855": 0.1855,
    "calib_h28ridge_01839": 0.1839,
    "hedge_v2_01563": 0.1563,
    "calib_h25ctx_01280": 0.1280,
    "calib_d15_02477": None,
    "r13_lattice_s5_00904": 0.0904,
    "h52_coincidence8_80k": None,
    "h60_officialstack_50k": None,
    "h60_union_d2_75308": None,
    "gems32_probe_s1_anchor_02600": 0.2600,
    "bayesopt_dilation_scarp_d28": None,      # never submitted
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", nargs="*", default=[])
    ap.add_argument("--out", default="evidence/e2b_reference_frame_20261011b.json")
    args = ap.parse_args()
    t0 = time.time()

    known, footprint = grid.load_catalogue(HERE / "data" / "labels.tif")
    dist_cat_px = edt(~known).astype(np.float32)
    import rasterio
    with rasterio.open(EXT / "derived_sgmc_faults_100m.tif") as src:
        sgmc = (src.read(1) > 0) & footprint
    cat3 = ndi.binary_dilation(known, iterations=3)
    sgmc_off = sgmc & ~cat3
    dist_sgmc_px = edt(~sgmc_off).astype(np.float32)
    print(f"[e2b] catalogue {int(known.sum()):,} px  sgmc-off-cat {int(sgmc_off.sum()):,} px")
    blanket_cat = float((np.maximum(1 - dist_cat_px / 3.0, 0)).mean())
    blanket_sgmc = float((np.maximum(1 - dist_sgmc_px / 3.0, 0)).mean())
    print(f"[e2b] blanket credit (uniform over the whole grid): cat {blanket_cat:.5f} "
          f"sgmc {blanket_sgmc:.5f}")
    blanket_cat_fp = float((np.maximum(1 - dist_cat_px / 3.0, 0))[footprint].mean())
    print(f"[e2b] blanket credit inside the footprint: cat {blanket_cat_fp:.5f}")

    masks: dict[str, np.ndarray] = {}
    for name, score in SCORES.items():
        f = REG / f"{name}.tif"
        if not f.exists():
            continue
        with rasterio.open(f) as src:
            if src.shape != footprint.shape:
                print(f"[e2b] SKIP {name}: shape {src.shape}")
                continue
            a = src.read(1)
        if not np.isfinite(a).all():
            a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
        masks[name] = (a > 0) & footprint
    for spec in args.extra:
        name, path = spec.split(":", 1)
        with rasterio.open(path) as src:
            a = src.read(1)
            if not np.isfinite(a).all():
                a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
            masks[name] = (a > 0) & footprint

    rows = []
    for name, m in masks.items():
        n = int(m.sum())
        if n == 0:
            continue
        ys, xs = np.nonzero(m)
        row = dict(
            name=name, owner_reported_score=SCORES.get(name),
            n_dots=n,
            credit_cat=float(np.maximum(1 - dist_cat_px[ys, xs] / 3.0, 0).mean()),
            credit_sgmc=float(np.maximum(1 - dist_sgmc_px[ys, xs] / 3.0, 0).mean()),
            dcat_med_m=float(np.median(dist_cat_px[ys, xs]) * 100.0),
            dsgmc_med_m=float(np.median(dist_sgmc_px[ys, xs]) * 100.0),
            enrichment_cat=None, enrichment_sgmc=None,
        )
        row["enrichment_cat"] = row["credit_cat"] / blanket_cat_fp
        row["enrichment_sgmc"] = row["credit_sgmc"] / blanket_sgmc
        rows.append(row)
        print(f"[e2b] {name:34s} n={n:>7,}  org={str(row['owner_reported_score']):>6s}  "
              f"credit_cat={row['credit_cat']:.4f} (x{row['enrichment_cat']:.1f})  "
              f"credit_sgmc={row['credit_sgmc']:.4f} (x{row['enrichment_sgmc']:.1f})  "
              f"dcat_med={row['dcat_med_m']:.0f}m", flush=True)

    scored = [r for r in rows if r["owner_reported_score"]]
    out = dict(
        experiment="E2b reference frame",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        note="owner_reported_score is the value quoted on the group's own sites "
             "(research/registry_index.json); it is NOT an organizer receipt.",
        footprint_cells=int(footprint.sum()), catalogue_cells=int(known.sum()),
        sgmc_offcat_cells=int(sgmc_off.sum()),
        blanket_credit_whole_grid=dict(cat=blanket_cat, sgmc=blanket_sgmc),
        blanket_credit_inside_footprint_cat=blanket_cat_fp,
        rows=rows,
    )
    p = HERE / args.out
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(f"[e2b] wrote {p} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
