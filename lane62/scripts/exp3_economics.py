#!/usr/bin/env python3
"""EXPERIMENT 3 (last of this session's budget of 3) -- emission economics.

EXP-2 showed the flagged datum breaks carry real signal (positive edge against a
same-stratum random control on both instruments at every operating point) but
only 6-7,798 dots' worth.  The remaining question is the one that decides
whether ANY of this belongs in a submission slot:

    For a dot emitted at a flagged datum break, what is the mean realised
    credit per dot, and does it clear the marginal bar 0.2*s ?

Identity I2 from src/gems62/metric.py: a non-redundant dot raises the score iff
its realised kernel credit kbar exceeds alpha*s.  At the public leader's s, the
bar is a single number; a dot's credit is measurable on an independent truth
set.  If mean credit >= bar, the dots are net-positive and worth shipping; if
not, the lane is a negative for the leaderboard no matter how unique the file is.

Writes evidence/exp3_economics.json and the final chosen emission mask.
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
from gems62.metric import dti_exact, kernel, credit_bar, _OFF   # noqa: E402

SEP_PX = 2.8284271247461903
BAR_S = 0.2778      # the group's owner-reported best; a reference point, not a verified rank


def u8(path, b):
    with rasterio.open(path) as d:
        a = d.read(b).astype(np.float64)
        nod = d.nodata
        v = np.ones(a.shape, bool) if nod is None else (a != nod)
    a = np.where(v, a, np.nan)
    lo, hi = np.nanpercentile(a, [2, 98])
    return np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)


def per_dot_credit(pred, truth, footprint, known):
    """Realised kernel credit kbar at every emitted pixel (identity I2's kbar)."""
    g = truth & footprint & ~known
    p = np.where(footprint & ~known, pred > 0, False)
    ys, xs = np.nonzero(p)
    if ys.size == 0:
        return np.array([]), np.array([])
    dg = ndi.distance_transform_edt(~g)
    return kernel(dg[ys, xs]), np.column_stack([ys, xs])


def thin_from_order(yy, xx, strength, sep):
    pts = np.column_stack([yy, xx]).astype(float)
    order = np.argsort(-strength)
    tree = cKDTree(pts)
    banned = np.zeros(yy.size, bool); keep = np.zeros(yy.size, bool)
    for i in order:
        if banned[i]:
            continue
        keep[i] = True
        banned[tree.query_ball_point(pts[i], sep)] = True
    return keep


def main():
    g = G.load_grid(ROOT)
    h, w = g.footprint.shape
    with rasterio.open(ROOT / "data/external/geodawn_dem_a2_100m.tif") as d:
        z = d.read(1).astype(np.float64)
    z[z <= -99999] = np.nan
    dem_valid = np.isfinite(z) & g.footprint
    TOPO = ROOT / "data/external/topo_10m_derived_100m_u8.tif"
    LIDAR = ROOT / "data/external/lidar_scarp_features_u8.tif"
    E = (0.30 * u8(LIDAR, 8) + 0.20 * u8(LIDAR, 7) + 0.20 * u8(LIDAR, 3)
         + 0.20 * u8(TOPO, 6) + 0.10 * u8(TOPO, 8))
    Ef = np.where(dem_valid, np.nan_to_num(E, nan=0.0), 0.0)

    with rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif") as d:
        sgmc = d.read(1)
    truthB = H.sgmc_truth(sgmc, g.catalogue, g.footprint)

    flags = json.load(open(ROOT / "evidence/profiles.json"))["flags"]
    mag = np.array([abs(f["magnitude_m"]) for f in flags])
    mag_n = (mag - mag.min()) / max(mag.max() - mag.min(), 1e-9)
    score = np.array([float(Ef[max(0, f["row"] - 1):f["row"] + 2,
                               max(0, f["col"] - 1):f["col"] + 2].mean()) for f in flags]) \
        * (0.5 + 0.5 * mag_n) * np.array([1.0 if f["kind"] == "vertical_step" else 0.5 for f in flags])
    order = np.argsort(-score)
    flags_ranked = [flags[i] for i in order]
    print(f"flags: {len(flags_ranked)}")

    def build(subset, half, max_len):
        cand = np.zeros((h, w), bool)
        for f in subset:
            r, c = f["row"], f["col"]
            r1, r2 = max(0, r - 5), min(h, r + 6)
            c1, c2 = max(0, c - 5), min(w, c + 6)
            gy, gx = np.gradient(Ef[r1:r2, c1:c2])
            Jxx, Jyy, Jxy = float((gx * gx).sum()), float((gy * gy).sum()), float((gx * gy).sum())
            th = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
            for t in np.arange(-half, half + 1):
                ri = int(round(r + t * np.cos(th))); ci = int(round(c + t * np.sin(th)))
                if 0 <= ri < h and 0 <= ci < w and dem_valid[ri, ci]:
                    cand[ri, ci] = True
        ys, xs = np.nonzero(cand)
        if ys.size == 0:
            return np.zeros((h, w), bool)
        keep = thin_from_order(ys, xs, Ef[ys, xs], SEP_PX)
        out = np.zeros((h, w), bool)
        out[ys[keep], xs[keep]] = True
        out[ndi.binary_dilation(g.catalogue, iterations=3)] = False
        return out

    rows = []
    best = None
    for N in [50, 200, 600, 1200, 2000, 3552]:
        for half in [4, 9, 16, 30]:
            pred = build(flags_ranked[:N], half, 2 * half)
            n = int(pred.sum())
            if n == 0:
                continue
            kb, pts = per_dot_credit(pred, truthB, g.footprint, g.catalogue)
            B = dti_exact(pred.astype(float), truthB, valid=g.footprint, known=g.catalogue)
            bar = credit_bar(B["dti"])
            frac_above = float((kb > credit_bar(BAR_S)).mean()) if kb.size else 0.0
            rec = dict(N_flags=int(N), half=half, n_dots=n,
                       mean_credit_per_dot=float(kb.mean()) if kb.size else 0.0,
                       median_credit_per_dot=float(np.median(kb)) if kb.size else 0.0,
                       frac_dots_clearing_bar_at_0p2778=frac_above,
                       instrumentB_dti=B["dti"], instrumentB_tp=B["tp"],
                       credit_bar_alpha_times_s=credit_bar(BAR_S),
                       edge_over_same_stratum_random=None)
            rows.append(rec)
            key = rec["mean_credit_per_dot"]
            if best is None or key > best["mean_credit_per_dot"]:
                best = rec
            print(f"N={N:>5} half={half:>2}  dots={n:>6}  mean kbar={rec['mean_credit_per_dot']:.5f} "
                  f" median={rec['median_credit_per_dot']:.5f}  frac>bar(0.2778)={frac_above:.3f}  "
                  f"B={B['dti']:.6f}")

    # The verdict rule is arithmetic, not taste:
    #   the official metric gains from an added dot iff its realised credit clears
    #   alpha*s.  frac_dots_clearing_bar is measured against the independent truth.
    fracs = [r["frac_dots_clearing_bar_at_0p2778"] for r in rows]
    verdict = "positive-edge-but-below-bar" if max(fracs) < 0.5 else "dot-class-clears-bar"
    out = dict(
        experiment="EXP-3 emission economics; final experiment of the session's budget of 3",
        rule="identity I2: a non-redundant dot raises DTI iff its realised kernel credit "
             "kbar > alpha*s.  alpha = 0.2.",
        reference_s=dict(value=BAR_S, label="owner-reported best (extradr19 row on the live "
                                            "leaderboard, rank 23 as read 2026-10-11) -- a "
                                            "reference point, NOT a verified rank for our file"),
        bar_at_reference_s=credit_bar(BAR_S),
        truth="instrument B (SGMC off-catalogue, 79,615 px)",
        rows=rows, best_row=best, verdict=verdict,
        interpretation=("mean realised credit per emitted dot, measured on an independent "
                        "public fault compilation, compared with the marginal bar alpha*s of "
                        "the official metric."))
    json.dump(out, open(ROOT / "evidence/exp3_economics.json", "w"), indent=1)
    print("verdict:", verdict)
    print("wrote evidence/exp3_economics.json")


if __name__ == "__main__":
    main()
