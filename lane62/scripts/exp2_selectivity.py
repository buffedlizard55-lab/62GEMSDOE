#!/usr/bin/env python3
"""EXPERIMENT 2 -- selectivity sweep on the flagged datum breaks.

Question the lane forces on us: "If only a handful are convincing, emit only
those."  So: rank the flagged steps by the strength of the independent DEM-ridge
evidence at the flag, sweep the number of flags emitted N from 3 to all, and
measure pooled HOLDOUT-DTI on BOTH instruments at every N, against random
controls drawn from the SAME spatial stratum (the shoreline zone) at the same
dot count.

This is a real experiment, not a fit: nothing is tuned on the holdout truth; the
sweep simply reports the whole curve so a selector can see whether any
operating point beats its own control.

Writes evidence/exp2_selectivity.json.
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
from gems62.metric import dti_exact, credit_bar   # noqa: E402

SEP_PX = 2.8284271247461903


def u8(path, b):
    with rasterio.open(path) as d:
        a = d.read(b).astype(np.float64)
        nod = d.nodata
        v = np.ones(a.shape, bool) if nod is None else (a != nod)
    a = np.where(v, a, np.nan)
    lo, hi = np.nanpercentile(a, [2, 98])
    return np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)


def thin_from_order(yy, xx, strength, sep):
    pts = np.column_stack([yy, xx]).astype(float)
    order = np.argsort(-strength)
    tree = cKDTree(pts)
    banned = np.zeros(yy.size, bool)
    keep = np.zeros(yy.size, bool)
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
        z = d.read(1).astype(np.float64); tr = d.transform
    z[z <= -99999] = np.nan
    dem_valid = np.isfinite(z) & g.footprint

    TOPO = ROOT / "data/external/topo_10m_derived_100m_u8.tif"
    LIDAR = ROOT / "data/external/lidar_scarp_features_u8.tif"
    E = (0.30 * u8(LIDAR, 8) + 0.20 * u8(LIDAR, 7) + 0.20 * u8(LIDAR, 3)
         + 0.20 * u8(TOPO, 6) + 0.10 * u8(TOPO, 8))
    E = np.where(dem_valid, np.nan_to_num(E, nan=0.0), np.nan)
    Ef = np.nan_to_num(E, nan=0.0)

    prof = json.load(open(ROOT / "evidence/profiles.json"))
    flags = prof["flags"]
    print(f"flags available: {len(flags)}")

    # evidence at, and in a 3x3 block around, each flag
    for f in flags:
        r, c = f["row"], f["col"]
        f["E_flag"] = float(Ef[r, c])
        f["E_loc"] = float(Ef[max(0, r - 1):r + 2, max(0, c - 1):c + 2].mean())
        f["kind_w"] = 1.0 if f["kind"] == "vertical_step" else 0.5

    # rank by evidence strength: local evidence x normalised magnitude
    mag = np.array([abs(f["magnitude_m"]) for f in flags])
    mag_n = (mag - mag.min()) / max(mag.max() - mag.min(), 1e-9)
    score = np.array([f["E_loc"] for f in flags]) * (0.5 + 0.5 * mag_n) \
        * np.array([f["kind_w"] for f in flags])
    order = np.argsort(-score)
    flags_ranked = [flags[i] for i in order]

    # instrument B truth
    with rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif") as d:
        sgmc = d.read(1)
    truthB = H.sgmc_truth(sgmc, g.catalogue, g.footprint)

    # the shoreline stratum = every flagged pixel's 5x5 neighbourhood (for controls)
    stratum = np.zeros((h, w), bool)
    yy = np.array([f["row"] for f in flags]); xx = np.array([f["col"] for f in flags])
    stratum[yy, xx] = True
    stratum = ndi.binary_dilation(stratum, iterations=3) & dem_valid

    def build(subset, dots_per=9, half=4, walk=False, max_len=20):
        """Emit a dot train through each selected flag, thinned to SEP_PX."""
        cand = np.zeros((h, w), bool)
        for f in subset:
            r, c = f["r_"] if "r_" in f else f["row"], f["c_"] if "c_" in f else f["col"]
            if walk:
                gy, gx = np.gradient(Ef[max(0, r - 9):r + 10, max(0, c - 9):c + 10])
                Jxx, Jyy, Jxy = float((gx * gx).sum()), float((gy * gy).sum()), float((gx * gy).sum())
                th = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
                dirs = [(np.cos(th), np.sin(th)), (-np.cos(th), -np.sin(th))]
                for dr, dc in dirs:
                    rr, cc = float(r), float(c)
                    for _ in range(max_len):
                        rr += dr; cc += dc
                        ri, ci = int(round(rr)), int(round(cc))
                        if not (0 <= ri < h and 0 <= ci < w) or not dem_valid[ri, ci]:
                            break
                        cand[ri, ci] = True
            else:
                # local ridge direction from E, then a symmetric dot train
                r1, r2 = max(0, r - 5), min(h, r + 6)
                c1, c2 = max(0, c - 5), min(w, c + 6)
                gy, gx = np.gradient(Ef[r1:r2, c1:c2])
                Jxx, Jyy, Jxy = float((gx * gx).sum()), float((gy * gy).sum()), float((gx * gy).sum())
                th = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
                for t in np.arange(-half, half + 1):
                    ri = int(round(r + t * np.cos(th)))
                    ci = int(round(c + t * np.sin(th)))
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

    def measure(pred):
        p = pred > 0
        n = int(p.sum())
        A = H.hide_and_recover(p, g.catalogue, g.footprint, rows=2, cols=2)
        B = dti_exact(p.astype(float), truthB, valid=g.footprint, known=g.catalogue)
        return n, A["pooled"]["dti"], A["ci95"], B["dti"], credit_bar(B["dti"]) if B["dti"] > 0 else None

    # controls: same dot count, drawn from the shoreline stratum
    sidx = np.flatnonzero(stratum & g.active)
    rng = np.random.default_rng(7)

    def control(n, reps=5):
        bb, aa = [], []
        for k in range(reps):
            ctrl = np.zeros((h, w), bool)
            sel = rng.choice(sidx, min(n, sidx.size), replace=False)
            ctrl.ravel()[sel] = True
            ctrl[ndi.binary_dilation(g.catalogue, iterations=3)] = False
            B = dti_exact(ctrl.astype(float), truthB, valid=g.footprint, known=g.catalogue)
            A = H.hide_and_recover(ctrl, g.catalogue, g.footprint, rows=2, cols=2)
            bb.append(B["dti"]); aa.append(A["pooled"]["dti"])
        return float(np.mean(aa)), float(np.mean(bb))

    sweep = []
    for N in [3, 5, 8, 12, 20, 30, 50, 80, 120, 200, 350, 600, 1000, 1500, 3552]:
        sub = flags_ranked[:N]
        pred = build(sub, dots_per=9, half=4)
        n, a, aci, b, bar = measure(pred)
        ca, cb = control(n)
        sweep.append(dict(N_flags=int(N), n_dots=n, instrumentA=a, instrumentA_ci95=aci,
                          instrumentB=b, credit_bar_at_B=bar,
                          controlA=ca, controlB=cb,
                          edgeA=a - ca, edgeB=b - cb))
        print(f"N={N:>5}  dots={n:>6}  A={a:.6f} (ctrl {ca:.6f}, edge {a-ca:+.6f})  "
              f"B={b:.6f} (ctrl {cb:.6f}, edge {b-cb:+.6f})  bar={bar}")

    json.dump(dict(
        experiment="EXP-2 selectivity sweep; 3rd and last experiment of this session's budget",
        rank_rule="flags ranked by (3x3 mean evidence) x (0.5 + 0.5*normalised |magnitude|) x "
                  "(1.0 vertical_step, 0.5 lateral_deflection)",
        controls="random dots from the SAME stratum (the shoreline zone: 3-px dilation of the "
                 "flagged pixels), same dot count, same 3-px catalogue prune, 5 realisations",
        instruments=dict(A="catalogue-segment holdout (IR-30-046 caveat)",
                         B="SGMC off-catalogue truth"),
        sweep=sweep), open(ROOT / "evidence/exp2_selectivity.json", "w"), indent=1)
    print("wrote evidence/exp2_selectivity.json")


if __name__ == "__main__":
    main()
