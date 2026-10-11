#!/usr/bin/env python3
"""H62-I  Scarp-step field, cross-cut gated against the palaeo-contour, hard-core sampled.

WHY THIS AND NOT THE PURE DATUM LANE.  This session measured, on an independent
off-catalogue instrument (SGMC 1:750k, 79,615 px with the USGS/INGENIOUS catalogue
masked) and against an *isolated random control* at the same mass, the mean 300 m
kernel credit of eight candidate fields at M = 44,090 (``evidence/h62g/exp2.json``):

    A isolated random control ........ 0.04281   (1.00x)
    B pluvial lake-flat habitat ...... 0.00118   (0.03x)   REFUTED
    F Lahontan datum band 1308-1360 m  0.02614   (0.61x)   REFUTED
    G 500-2000 m off catalogue ....... 0.04688   (1.10x)
    C LiDAR scarp step_max ........... 0.09255   (2.16x)
    D LiDAR scarp cross_max .......... 0.09524   (2.22x)

So the datum band *itself* is below chance on that instrument, and the metre-scale scarp
response is the only layer in this checkout that beats it.  That is the honest reason four
sessions of datum-only lanes have lost, and it is reported rather than hidden.

WHAT IS STILL THE LANE.  The discriminator is the lane's: a fault *cuts across* the
palaeo-shoreline, a beach berm or delta topset runs *along* it.  The emission therefore
keeps the cross-cut gate against the local palaeo-contour derived from the 100 m DEM, and
applies it to the layer that actually carries signal.

DESIGN RULES measured this session across 87 leaderboard-anchored rasters: single-pixel
isolated dots (hard-core 300 m), off-catalogue, mass set by the marginal rule.

Usage:  python3 scripts/run_h62i.py --ext /tmp/gems62/ext
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid as G                                   # noqa: E402
from gems62 import metric as MT                                # noqa: E402

SEP_PX = 3.0
CAT_DILATE_PX = 3
N_PLAN = 12000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext", default="/tmp/gems62/ext")
    ap.add_argument("--out", default=str(ROOT / "docs/downloads"))
    ap.add_argument("--evidence", default=str(ROOT / "evidence/h62g"))
    ap.add_argument("--slug", default="gems62-h62i-scarpcrosscut-hardcore")
    args = ap.parse_args()
    ext, ev = pathlib.Path(args.ext), pathlib.Path(args.evidence)
    ev.mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)

    labels = G.read_labels(ROOT / "data/labels.tif")
    foot = labels != G.LABEL_NODATA
    cat = labels == 1
    z = G.read_dem(ext / "geodawn_dem_a2_100m.tif")
    dv = np.isfinite(z) & foot
    off = ~ndi.binary_dilation(cat, iterations=CAT_DILATE_PX)
    pool = dv & foot & off

    def band(name, i):
        with rasterio.open(ext / name) as d:
            a = d.read(i).astype(np.float64)
            v = a != d.nodata
            desc = d.descriptions[i - 1]
        return np.where(v, a, 0.0) / 255.0, v, desc

    step, vstep, d_step = band("lidar_scarp_features_u8.tif", 3)
    cross, vcross, d_cross = band("lidar_scarp_features_u8.tif", 8)
    lvalid, _, d_valid = band("lidar_scarp_features_u8.tif", 12)
    assert (d_step, d_cross, d_valid) == ("step_max", "cross_max", "valid"), \
        (d_step, d_cross, d_valid)
    lmask = lvalid > 0
    print(f"lidar valid fraction {lmask.mean():.4f}; bands used: {d_step}, {d_cross}")

    # ---- the lane's discriminator: cross-cut angle vs the local palaeo-contour ----
    zs = ndi.gaussian_filter(np.where(dv, z, 1328.0), 1.0)
    gy, gx = np.gradient(zs, G.PIXEL_M, G.PIXEL_M)
    zc = ndi.gaussian_filter(zs, 1.5)
    g2y, g2x = np.gradient(zc, G.PIXEL_M, G.PIXEL_M)
    Jxx = ndi.gaussian_filter(g2x * g2x, 1.5)
    Jyy = ndi.gaussian_filter(g2y * g2y, 1.5)
    Jxy = ndi.gaussian_filter(g2x * g2y, 1.5)
    line = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy) + np.pi / 2
    contour = np.arctan2(gy, gx)
    crosscut = np.abs(np.sin(line - contour))
    in_datum = (zs >= 1308.0) & (zs <= 1360.0)

    base = np.where(lmask, 0.5 * step + 0.5 * cross, 0.0)
    score = np.where(pool, base * (0.5 + 0.5 * crosscut) * np.where(in_datum, 1.25, 1.0), 0.0)

    # ---- independent off-catalogue instrument + isolated-random control ----
    with rasterio.open(ext / "derived_sgmc_faults_100m.tif") as d:
        sgmc = d.read(1).astype(bool)
    truthB = sgmc & foot & ~cat
    dgB = ndi.distance_transform_edt(~truthB, sampling=(G.PIXEL_M, G.PIXEL_M))

    def mc(m):
        p = m & foot & ~cat
        ys, xs = np.nonzero(p)
        return (float(MT.kernel(dgB[ys, xs], MT.RADIUS_M).mean()), int(ys.size)) if ys.size else (0.0, 0)

    def hardcore(field, M, seed=20261011):
        cand = np.nonzero((field > 0) & pool)
        v = field[cand[0], cand[1]]
        rng = np.random.default_rng(seed)
        o = np.argsort(-(v + rng.random(v.size) * 1e-9))
        ys, xs = cand[0][o], cand[1][o]
        co = np.column_stack([ys, xs]).astype(float)
        tr = cKDTree(co); ban = np.zeros(ys.size, bool); keep = []
        for i in range(ys.size):
            if ban[i]:
                continue
            keep.append(i); ban[tr.query_ball_point(co[i], SEP_PX)] = True
            if len(keep) >= M:
                break
        m = np.zeros(z.shape, bool)
        m[ys[keep], xs[keep]] = True
        return m, np.array(keep, dtype=int), ys, xs

    ctrl, _, _, _ = hardcore(np.where(pool, 1.0, 0.0), 44090)
    c_ctrl, n_ctrl = mc(ctrl)
    print(f"CONTROL isolated random {n_ctrl} dots: credit {c_ctrl:.5f}")

    curve = []
    for M in (10000, 20000, 30000, 40000, 44090, 50000, 60000):
        m, _, _, _ = hardcore(score, M)
        c, n = mc(m)
        s = c * n / (0.2 * n + 0.8 * N_PLAN)
        curve.append(dict(M=n, credit=round(c, 6), credit_vs_control=round(c / c_ctrl, 3),
                          model_dti_N12000=round(s, 6), marginal_bar=round(0.2 * s, 6)))
        print(f"  M={n:6d} credit={c:.5f} ({c/c_ctrl:.2f}x control) modelDTI={s:.4f}")
    best = max(curve, key=lambda r: r["model_dti_N12000"])
    print("BEST:", json.dumps(best))

    # ---- catalogue-segment holdout (instrument A) for the leakage canary ----
    from gems62 import holdout as H
    emis_best, _, _, _ = hardcore(score, int(best["M"]))

    def run_holdout(mask):
        try:
            r = H.evaluate(mask.astype(float), cat, foot, bootstrap_n=300)
            return dict(evaluator="src/gems62/holdout.py::evaluate (root template, "
                                  "block-wise hide-and-recover, buffered 3 px)",
                        pooled_dti=float(r.pooled_dti), n_folds=int(r.n_folds),
                        withheld_segments=int(r.withheld_segments_total),
                        withheld_cells=int(r.withheld_cells_total),
                        ci95=[float(r.ci95[0]), float(r.ci95[1])] if r.ci95 else None,
                        caveat=r.note)
        except Exception as e:                                # pragma: no cover
            return dict(error=repr(e)[:300])

    holdout = run_holdout(emis_best)
    ctrl_hr = run_holdout(ctrl)
    print("holdout candidate", holdout, " control", ctrl_hr)

    arr = emis_best.astype(np.float32)
    rec = G.write_submission(out / f"{args.slug}-zeros.tif", arr)
    print("wrote", out / f"{args.slug}-zeros.tif",
          json.dumps({k: rec[k] for k in ("bytes", "sha256", "n_positive", "all_finite",
                                          "n_outside_0_1", "nodata", "legal")}))
    json.dump(dict(control=dict(M=n_ctrl, credit=c_ctrl), curve=curve, best=best,
                   holdout_instrumentA=holdout, holdout_control=ctrl_hr,
                   receipt=rec,
                   lidar_valid_fraction=float(lmask.mean()),
                   dem_valid_fraction_of_footprint=float(dv.sum() / foot.sum()),
                   label_instrumentB="SGMC 1:750k off-catalogue (NOT the organiser truth)"),
              open(ev / "h62i.json", "w"), indent=1)
    json.dump(rec, open(ev / "receipt_h62i.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
