#!/usr/bin/env python3
"""H63M — emission-policy sweep on the cached, spatially-blocked holdout probabilities.

Reads the per-fold out-of-sample probability fields written by ``h63_train.py`` and
evaluates emission policies the way the protocol asks:

* the emission is selected **inside each held-out fold's core only** (that is the
  hide-and-recover analogue of "train on everything, predict everywhere, emit the top
  fraction" -- the model for a fold never saw that fold);
* visible catalogue faults are masked pixel-exactly before the budget is spent;
* pooled weighted TP / FP / FN over the four folds, exact 300 m triangular kernel,
  alpha 0.2, beta 0.8, using ``src/gems62/metric.py``.

Both truth populations are proxies for the organiser's hidden set; neither is a score.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62.metric import dti_components, ALPHA, BETA, RADIUS_M  # noqa: E402
from gems62.grid import HEIGHT, WIDTH, PIXEL_M  # noqa: E402

OUT = HERE / "data" / "h63"
EV = HERE / "evidence"
COLLAR = 3


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def blocks_and_folds(cat):
    H, W = HEIGHT, WIDTH
    br, bc = int(np.ceil(H / 8)), int(np.ceil(W / 7))
    yy = np.arange(H)[:, None] // br
    xx = np.arange(W)[None, :] // bc
    blocks = (yy * 7 + xx).astype(np.int32)
    bm = np.zeros(56)
    np.add.at(bm, blocks[cat], 1.0)
    order = np.argsort(-bm)
    load = np.zeros(4)
    assign = np.full(56, -1, np.int32)
    for b in order:
        f = int(np.argmin(load))
        assign[b] = f
        load[f] += bm[b]
    return assign[blocks]


def nms_peaks(p, radius_px, valid):
    size = 2 * int(radius_px) + 1
    mx = ndi.maximum_filter(np.where(valid, p, -np.inf), size=size, mode="constant", cval=-np.inf)
    return valid & np.isfinite(p) & (p >= mx) & (p > 0)


def topk(mask, p, k):
    idx = np.flatnonzero(mask.ravel())
    if idx.size <= k:
        return mask
    v = p.ravel()[idx]
    keep = idx[np.argpartition(-v, k - 1)[:k]]
    out = np.zeros(mask.size, dtype=bool)
    out[keep] = True
    return out.reshape(mask.shape)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prob", default="h63a_prob.npy")
    ap.add_argument("--out", default="h63a")
    ap.add_argument("--folds", type=int, default=4)
    args = ap.parse_args()

    t0 = time.time()
    prob = np.load(OUT / args.prob)
    n = prob.shape[1]
    usable = np.load(OUT / "valid_mask.npy")
    cat = np.load(OUT / "catalogue.npy")
    pro = np.load(OUT / "proxy_off.npy")
    foldmap = blocks_and_folds(cat)

    cores, tris = [], []
    for f in range(args.folds):
        core = ndi.binary_erosion(foldmap == f, structure=np.ones((2 * COLLAR + 1,) * 2)) & usable
        core &= ~(cat & (foldmap != f))          # visible catalogue masked pixel-exactly
        cores.append(core)
        tris.append({"catalogue": cat & core & (foldmap == f),
                     "proxy_off": pro & core & (foldmap == f)})
    log("core cells per fold: " + json.dumps([int(c.sum()) for c in cores]))

    # ---- model quality, independent of the emission policy ----------------------
    from sklearn.metrics import roc_auc_score
    auc_rows = []
    for f in range(args.folds):
        g = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
        g[usable] = prob[f]
        row = {"fold": f}
        for tn in ("catalogue", "proxy_off"):
            yb = tris[f][tn].ravel()[np.flatnonzero(cores[f].ravel())]
            sb = g.ravel()[np.flatnonzero(cores[f].ravel())]
            row[f"auc_{tn}"] = round(float(roc_auc_score(yb, sb)), 4) if yb.sum() > 50 else None
            row[f"n_pos_{tn}"] = int(yb.sum())
        auc_rows.append(row)
        log(f"  fold {f}: AUC catalogue={row['auc_catalogue']}  proxy_off={row['auc_proxy_off']}"
            f"  (pos {row['n_pos_catalogue']} / {row['n_pos_proxy_off']})")

    # ---- policy sweep ----------------------------------------------------------
    grid = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    rows_out = []
    for sigma in (0.0, 1.0, 2.0):
        for r in (0, 2, 3, 4):
            for kf in (0.0025, 0.005, 0.01, 0.02, 0.04):
                per_fold = []
                for f in range(args.folds):
                    grid[usable] = prob[f]
                    if sigma > 0:
                        g = ndi.gaussian_filter(grid, sigma, mode="nearest")
                        g[~np.isfinite(grid)] = np.nan
                    else:
                        g = grid
                    core = cores[f]
                    m = nms_peaks(g, r, core) if r > 0 else (core & (g > 0))
                    m = topk(m, g, int(round(kf * int(core.sum()))))
                    per_fold.append(m)
                S = float(sum(int(m.sum()) for m in per_fold))
                rec = {"sigma_px": sigma, "radius_px": r, "k_frac_of_core": kf, "mass": S}
                for tn in ("catalogue", "proxy_off"):
                    tp = fp = fn = 0.0
                    for f, m in enumerate(per_fold):
                        t = tris[f][tn]
                        if not t.any():
                            continue
                        c = dti_components(m.astype(np.float32), t, valid=cores[f],
                                           pixel_size_m=PIXEL_M, radius_m=RADIUS_M)
                        tp += c.tp_w
                        fp += c.fp_w
                        fn += c.fn_w
                    rec[tn] = {"tp": round(tp, 2), "fp": round(fp, 2), "fn": round(fn, 2),
                               "K": round(tp + fn, 1),
                               "dti": round(tp / (tp + ALPHA * fp + BETA * fn + 1e-12), 5),
                               "credit_per_mass": round(tp / S, 5) if S else 0.0}
                rows_out.append(rec)
                log(f"  s={sigma} r={r} kf={kf:<6} mass={S:8.0f}  cat={rec['catalogue']['dti']:.4f}"
                    f"  proxy={rec['proxy_off']['dti']:.4f}"
                    f"  c/m={rec['catalogue']['credit_per_mass']:.4f}")

    by_cat = sorted(rows_out, key=lambda d: -d["catalogue"]["dti"])
    by_pro = sorted(rows_out, key=lambda d: -d["proxy_off"]["dti"])
    res = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": ("HOLDOUT-DTI (evaluator src/gems62/metric.py; 4 spatially blocked "
                           f"folds of 512 px blocks; {COLLAR} px collar; visible catalogue masked "
                           "pixel-exactly; emission selected inside the held-out core; pooled "
                           "TP/FP/FN; alpha 0.2 beta 0.8 R 300 m)"),
        "prob_file": args.prob,
        "auc_per_fold": auc_rows,
        "best_by_catalogue_dti": by_cat[0],
        "best_by_proxy_dti": by_pro[0],
        "policies": rows_out,
        "seconds": round(time.time() - t0, 1),
    }
    (EV / f"{args.out}_emission.json").write_text(json.dumps(res, indent=1))
    log("wrote " + str(EV / f"{args.out}_emission.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
