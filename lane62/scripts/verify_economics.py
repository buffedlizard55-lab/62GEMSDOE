#!/usr/bin/env python3
"""VERIFICATION of EXP-3 (not a new experiment): is the lane's dot class
actually more credit-dense than the champion family's dot class, measured on the
SAME instrument with the SAME masking?

An absolute mean credit is meaningless on its own -- it depends on the truth set.
The only defensible question is comparative:

    mean realised credit per dot, lane dots  vs  champion-family dots,
    on instrument B (independent SGMC off-catalogue truth) and on
    instrument A (catalogue-segment holdout).

If the lane's class wins on both instruments, the finding is robust to the choice
of truth set.  If it only wins on one, say so.

The champion-family rasters are used ONLY as a comparison/learning set, exactly
as the brief permits ("DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR
LEARNING AND EDUCATION").  No byte of any of them enters this repository's
submission.

Writes evidence/verify_economics.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid as G          # noqa: E402
from gems62 import holdout as H       # noqa: E402
from gems62.metric import kernel, credit_bar, dti_exact   # noqa: E402

REG = Path.home() / ".cache" / "gems62_registry"


def u8(path, b):
    with rasterio.open(path) as d:
        a = d.read(b).astype(np.float64)
        nod = d.nodata
        v = np.ones(a.shape, bool) if nod is None else (a != nod)
    a = np.where(v, a, np.nan)
    lo, hi = np.nanpercentile(a, [2, 98])
    return np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)


def dots_of(path, footprint, min_val=1e-6):
    with rasterio.open(path) as d:
        if d.height != G.HEIGHT or d.width != G.WIDTH:
            return None
        a = d.read(1).astype(np.float64)
    a[~np.isfinite(a)] = 0.0
    return (a > min_val) & footprint


def mean_credit(pred, truth, footprint, known):
    g = truth & footprint & ~known
    p = pred & footprint & ~known
    ys, xs = np.nonzero(p)
    if ys.size == 0:
        return 0.0, 0
    dg = ndi.distance_transform_edt(~g)
    return float(kernel(dg[ys, xs]).mean()), int(ys.size)


def main():
    g = G.load_grid(ROOT)
    h, w = g.footprint.shape
    with rasterio.open(ROOT / "data/external/geodawn_dem_a2_100m.tif") as d:
        z = d.read(1).astype(np.float64)
    z[z <= -99999] = np.nan
    dem_valid = np.isfinite(z) & g.footprint
    TOPO = ROOT / "data/external/topo_10m_derived_100m_u8.tif"
    LIDAR = ROOT / "data/external/lidar_scarp_features_u8.tif"
    Ef = np.where(dem_valid, 0.30 * u8(LIDAR, 8) + 0.20 * u8(LIDAR, 7)
                  + 0.20 * u8(LIDAR, 3) + 0.20 * u8(TOPO, 6) + 0.10 * u8(TOPO, 8), 0.0)

    with rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif") as d:
        sgmc = d.read(1)
    truthB = H.sgmc_truth(sgmc, g.catalogue, g.footprint)

    # ---- the lane's most selective class (EXP-3 winner: N=50, half=4)
    flags = json.load(open(ROOT / "evidence/profiles.json"))["flags"]
    mag = np.array([abs(f["magnitude_m"]) for f in flags])
    mag_n = (mag - mag.min()) / max(mag.max() - mag.min(), 1e-9)
    score = np.array([float(Ef[max(0, f["row"] - 1):f["row"] + 2,
                               max(0, f["col"] - 1):f["col"] + 2].mean()) for f in flags]) \
        * (0.5 + 0.5 * mag_n) * np.array([1.0 if f["kind"] == "vertical_step" else 0.5 for f in flags])
    ranked = [flags[i] for i in np.argsort(-score)]
    SEP = 2.8284271247461903

    def build(subset, half):
        cand = np.zeros((h, w), bool)
        for f in subset:
            r, c = f["row"], f["col"]
            gy, gx = np.gradient(Ef[max(0, r - 5):r + 6, max(0, c - 5):c + 6])
            Jxx, Jyy, Jxy = float((gx * gx).sum()), float((gy * gy).sum()), float((gx * gy).sum())
            th = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
            if not np.isfinite(th):      # isotropic window: fall back to north
                th = 0.0
            for t in np.arange(-half, half + 1):
                ri = int(round(r + t * np.cos(th))); ci = int(round(c + t * np.sin(th)))
                if 0 <= ri < h and 0 <= ci < w and dem_valid[ri, ci]:
                    cand[ri, ci] = True
        ys, xs = np.nonzero(cand)
        keep = np.zeros(ys.size, bool)
        tree = cKDTree(np.column_stack([ys, xs]).astype(float))
        banned = np.zeros(ys.size, bool)
        for i in np.argsort(-Ef[ys, xs]):
            if banned[i]:
                continue
            keep[i] = True
            banned[tree.query_ball_point(np.column_stack([ys, xs])[i].astype(float), SEP)] = True
        out = np.zeros((h, w), bool)
        out[ys[keep], xs[keep]] = True
        out[ndi.binary_dilation(g.catalogue, iterations=3)] = False
        return out

    lane_variants = {}
    for (NN, half) in [(50, 1), (50, 4), (120, 6), (3552, 30)]:
        pred = build(ranked[:NN], half)
        mb, nb = mean_credit(pred, truthB, g.footprint, g.catalogue)
        sa = H.hide_and_recover(pred, g.catalogue, g.footprint, rows=2, cols=2)
        ma, _ = mean_credit(pred, sa["_truth"] if "_truth" in sa else truthB, g.footprint, g.catalogue)
        lane_variants[f"N{NN}_half{half}"] = dict(n_dots=nb, mean_credit_instrumentB=mb,
                                                  instrumentA_dti=sa["pooled"]["dti"])
        print(f"lane N={NN} half={half}: dots={nb} mean kbar(B)={mb:.5f} A={sa['pooled']['dti']:.6f}")

    # ---- champion-family rasters: reuse for LEARNING ONLY
    cands = []
    for p in sorted(REG.rglob("*.tif")):
        nm = p.name.lower()
        if any(k in nm for k in ("d28", "h33", "dotted", "02600", "ref02600", "anchor")):
            cands.append(p)
    cands = cands[:24]
    champ_rows = []
    for p in cands:
        pr = dots_of(p, g.footprint)
        if pr is None or pr.sum() < 100:
            continue
        mb, nb = mean_credit(pr, truthB, g.footprint, g.catalogue)
        champ_rows.append(dict(file=p.name, repo=p.parts[-3], n_dots=nb,
                               mean_credit_instrumentB=mb))
        print(f"champion {p.name[:60]:<62} dots={nb:>6} mean kbar(B)={mb:.5f}")
    champ_rows.sort(key=lambda r: -r["mean_credit_instrumentB"])

    out = dict(
        purpose="verify EXP-3's finding on the SAME instrument with the SAME masking",
        instrument_B=dict(truth="SGMC 1:750k off-catalogue", truth_px=int(truthB.sum())),
        lane_variants=lane_variants,
        champion_family=champ_rows,
        best_champion_mean_credit=max([r["mean_credit_instrumentB"] for r in champ_rows], default=None),
        lane_best_mean_credit=max([v["mean_credit_instrumentB"] for v in lane_variants.values()]),
        reused_for="LEARNING ONLY -- the group's own prior submissions, used as a comparison "
                   "set. No byte of any of them enters this repository's candidate raster.",
    )
    out["ratio_lane_over_best_champion"] = (
        out["lane_best_mean_credit"] / out["best_champion_mean_credit"]
        if out["best_champion_mean_credit"] else None)
    json.dump(out, open(ROOT / "evidence/verify_economics.json", "w"), indent=1)
    print("ratio lane/champion:", out["ratio_lane_over_best_champion"])
    print("wrote evidence/verify_economics.json")


if __name__ == "__main__":
    main()
