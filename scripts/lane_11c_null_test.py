#!/usr/bin/env python3
"""Is the datum-offset detector better than a random point in the SAME datum band?

The earlier lane sessions in this repository could not answer this: they benchmarked the
lane against a *footprint-wide* uniform field, which conflates two different questions --
"is the pluvial-lake margin bad real estate?" and "is the detector picking the wrong spots
inside it?".  This script separates them with the correct null.

Nulls used, both MEASURED in this checkout:
  * ``footprint_uniform``  -- uniform random cells anywhere inside the survey footprint;
  * ``band_uniform``       -- uniform random cells inside the *same* published datum band
                              that produced the loci.  This is the right control: a locus
                              must beat a random point on its own datum surface.

Instruments (both public, both on the competition grid):
  * ``sgmc_off_catalogue`` -- SGMC 1:750k faults MINUS the competition catalogue, i.e. a
                              public compilation of faults the catalogue does not contain.
                              This is the only local quantity found to track the leaderboard
                              positively (Spearman +0.617 over 20 owner-reported scores).
  * ``catalogue``          -- the mapped USGS/INGENIOUS catalogue.  The leaderboard rewards
                              *avoiding* it (Spearman -0.597), so a lower ratio is better.

Usage: python3 scripts/lane_11c_null_test.py --loci build/lane11c/loci.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import datum11c as D, grid  # noqa: E402
from gems62.metric import kernel  # noqa: E402
from scipy.ndimage import distance_transform_edt  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loci", default="build/lane11c/loci.json")
    ap.add_argument("--sgmc", default="build/ext/derived_sgmc_faults_100m.tif")
    ap.add_argument("--dem", default="build/ext/geodawn_dem_a2_100m.tif")
    ap.add_argument("--labels", default="data/labels.tif")
    ap.add_argument("--out", default="evidence/lane11c_null_test.json")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    import rasterio
    loci = json.loads(pathlib.Path(args.loci).read_text())
    labels = grid.read_labels(args.labels)
    footprint = labels != -1
    catalogue = labels == 1
    dem = grid.read_dem(args.dem)
    with rasterio.open(args.sgmc) as src:
        sgmc = src.read(1) > 0
    off = sgmc & ~catalogue

    d_cat = distance_transform_edt(~catalogue, sampling=(100.0, 100.0))
    d_off = distance_transform_edt(~off, sampling=(100.0, 100.0))
    k_cat = kernel(d_cat, 300.0)
    k_off = kernel(d_off, 300.0)

    a, b, c, d, e, f = grid.TRANSFORM
    rng = np.random.default_rng(args.seed)
    out: dict = {
        "question": "is a datum-offset locus better than a random cell on the same datum?",
        "instruments": {
            "sgmc_off_catalogue_cells": int(off.sum()),
            "catalogue_cells": int(catalogue.sum()),
        },
        "by_datum": {},
    }
    pool_loci: list[dict] = []
    pool_null_idx: list[np.ndarray] = []
    for name, (lo, hi) in D.DATUMS.items():
        band = footprint & np.isfinite(dem) & (dem >= lo) & (dem <= hi)
        band_idx = np.flatnonzero(band.ravel())
        if band_idx.size == 0:
            continue
        sel = rng.choice(band_idx, size=min(60000, band_idx.size), replace=False)
        rr, cc = sel // grid.WIDTH, sel % grid.WIDTH
        ls = loci.get(name, [])
        lr = np.array([int((f - s["y"]) / e) for s in ls], dtype=int)
        lc = np.array([int((s["x"] - c) / a) for s in ls], dtype=int)
        fp_idx = np.flatnonzero(footprint.ravel())
        fsel = rng.choice(fp_idx, size=min(60000, fp_idx.size), replace=False)
        fr, fc = fsel // grid.WIDTH, fsel % grid.WIDTH
        rec = {
            "band_lo_m": lo, "band_hi_m": hi, "band_cells": int(band.sum()),
            "n_loci": int(len(ls)),
            "band_uniform": {"k_off": float(k_off[rr, cc].mean()),
                             "k_cat": float(k_cat[rr, cc].mean())},
            "footprint_uniform": {"k_off": float(k_off[fr, fc].mean()),
                                  "k_cat": float(k_cat[fr, fc].mean())},
        }
        if len(ls):
            rec["loci"] = {"k_off": float(k_off[lr, lc].mean()),
                           "k_cat": float(k_cat[lr, lc].mean()),
                           "frac_within_300m_cat": float((d_cat[lr, lc] <= 300).mean()),
                           "frac_within_300m_off": float((d_off[lr, lc] <= 300).mean())}
            rec["ratio_vs_band_uniform"] = {
                "k_off": rec["loci"]["k_off"] / max(rec["band_uniform"]["k_off"], 1e-12),
                "k_cat": rec["loci"]["k_cat"] / max(rec["band_uniform"]["k_cat"], 1e-12),
            }
            rec["ratio_vs_footprint_uniform"] = {
                "k_off": rec["loci"]["k_off"] / max(rec["footprint_uniform"]["k_off"], 1e-12),
                "k_cat": rec["loci"]["k_cat"] / max(rec["footprint_uniform"]["k_cat"], 1e-12),
            }
            pool_loci.extend(ls)
            pool_null_idx.append(sel)
        out["by_datum"][name] = rec

    if pool_loci:
        lr = np.array([int((f - s["y"]) / e) for s in pool_loci], dtype=int)
        lc = np.array([int((s["x"] - c) / a) for s in pool_loci], dtype=int)
        sel = np.concatenate(pool_null_idx)
        rr, cc = sel // grid.WIDTH, sel % grid.WIDTH
        out["pooled"] = {
            "n_loci": len(pool_loci),
            "loci": {"k_off": float(k_off[lr, lc].mean()), "k_cat": float(k_cat[lr, lc].mean())},
            "band_uniform": {"k_off": float(k_off[rr, cc].mean()),
                             "k_cat": float(k_cat[rr, cc].mean())},
            "ratio_vs_band_uniform": {
                "k_off": float(k_off[lr, lc].mean()) / max(float(k_off[rr, cc].mean()), 1e-12),
                "k_cat": float(k_cat[lr, lc].mean()) / max(float(k_cat[rr, cc].mean()), 1e-12),
            },
        }

    p = pathlib.Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
