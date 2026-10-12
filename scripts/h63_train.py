#!/usr/bin/env python3
"""H63M — spatially-blocked hide-and-recover training + emission-policy sweep.

Instrument (the protocol's hide-and-recover, built on the template's own metric)
------------------------------------------------------------------------------
Withhold whole *spatial blocks* of the catalogue, with a 3 px collar; derive every
catalogue-derived feature only from the visible faults; mask the visible faults
pixel-exactly; score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel) with
``src/gems62/metric.py``.

Two truth populations, both free and official:
  * ``catalogue``  -- the competition's own training labels (= existing_faults.tif)
  * ``proxy_off``  -- USGS SGMC faults absent from the competition catalogue
                      (data/sibling/proxy_catalogue.tif, code 2)

Both are *proxies* for the organiser's hidden set.  Nothing here is an organiser score.
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
EV.mkdir(exist_ok=True)

R_PX = 3            # 300 m kernel radius in 100 m cells
COLLAR = 3          # px excluded around every block boundary
N_BLOCK_ROWS, N_BLOCK_COLS = 8, 7
N_FOLDS = 4
SEED = 20261012
RADII = [0, 2, 3, 4, 6]
KFRACS = [0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02]


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


# ------------------------------------------------------------------ blocks
def block_index(shape=(HEIGHT, WIDTH), nr=N_BLOCK_ROWS, nc=N_BLOCK_COLS):
    h, w = shape
    br, bc = int(np.ceil(h / nr)), int(np.ceil(w / nc))
    yy = np.arange(h)[:, None] // br
    xx = np.arange(w)[None, :] // bc
    return (yy * nc + xx).astype(np.int32), nr * nc


def balanced_folds(mass: np.ndarray, n_folds: int = N_FOLDS) -> np.ndarray:
    order = np.argsort(-mass)
    load = np.zeros(n_folds)
    assign = np.full(mass.size, -1, dtype=np.int32)
    for b in order:
        f = int(np.argmin(load))
        assign[b] = f
        load[f] += mass[b]
    return assign


# ------------------------------------------------------------------ emission helpers
def nms_peaks(p: np.ndarray, radius_px: int, valid: np.ndarray) -> np.ndarray:
    size = 2 * int(radius_px) + 1
    mx = ndi.maximum_filter(np.where(valid, p, -np.inf), size=size, mode="constant", cval=-np.inf)
    return valid & np.isfinite(p) & (p >= mx) & (p > 0)


def topk(mask: np.ndarray, p: np.ndarray, k: int) -> np.ndarray:
    idx = np.flatnonzero(mask.ravel())
    if idx.size <= k:
        return mask
    v = p.ravel()[idx]
    keep = idx[np.argpartition(-v, k - 1)[:k]]
    out = np.zeros(mask.size, dtype=bool)
    out[keep] = True
    return out.reshape(mask.shape)


def dilate(mask: np.ndarray, r: int) -> np.ndarray:
    return ndi.binary_dilation(mask, structure=np.ones((2 * r + 1, 2 * r + 1)))


# ------------------------------------------------------------------ model
def fit_predict(Xtr, ytr, wtr, Xall, nf, max_iter):
    from sklearn.ensemble import HistGradientBoostingClassifier
    m = HistGradientBoostingClassifier(
        max_iter=max_iter, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40,
        l2_regularization=1.0, max_bins=128, early_stopping=True,
        validation_fraction=0.12, n_iter_no_change=20, random_state=SEED,
    )
    m.fit(Xtr, ytr, sample_weight=wtr)
    out = np.empty(Xall.shape[0], dtype=np.float32)
    step = 500_000
    for i in range(0, Xall.shape[0], step):
        out[i:i + step] = m.predict_proba(Xall[i:i + step, :nf + 1])[:, 1].astype(np.float32)
    return out, int(m.n_iter_)


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=N_FOLDS)
    ap.add_argument("--neg", type=int, default=400_000)
    ap.add_argument("--pos-pop", default="catalogue",
                    choices=["catalogue", "proxy_off", "union"])
    ap.add_argument("--maxiter", type=int, default=250)
    ap.add_argument("--out", default="h63_model")
    ap.add_argument("--canary", action="store_true")
    ap.add_argument("--train-only", action="store_true")
    ap.add_argument("--prob-file", default=None)
    args = ap.parse_args()

    t0 = time.time()
    rng = np.random.default_rng(SEED)

    _shape = json.loads((OUT / "design_shape.json").read_text())
    n, nf = _shape["n_rows"], _shape["n_cols"]
    X = np.memmap(OUT / "design.f32", dtype=np.float32, mode="r", shape=(n, nf))
    idx = np.load(OUT / "idx.npy")
    usable = np.load(OUT / "valid_mask.npy")
    cat = np.load(OUT / "catalogue.npy")
    pro = np.load(OUT / "proxy_off.npy")
    names = json.loads((OUT / "feature_names.json").read_text())
    log(f"design {X.shape}")

    blocks, nb = block_index()
    bm = np.zeros(nb)
    np.add.at(bm, blocks[cat], 1.0)
    fold_of_block = balanced_folds(bm, args.folds)
    foldmap = fold_of_block[blocks]
    log("fold fault mass: " + json.dumps(
        [int(bm[fold_of_block == f].sum()) for f in range(args.folds)]))

    # design matrix + one extra column: log1p(distance to VISIBLE catalogue), per fold
    Xall = np.memmap(OUT / f"{args.out}_design_aug.f32", dtype=np.float32, mode="w+",
                     shape=(n, nf + 1))
    step = 500_000
    for i in range(0, n, step):
        Xall[i:i + step, :nf] = X[i:i + step]
    del X

    fold_core, prob = {}, np.zeros((args.folds, n), dtype=np.float32)
    prob_path = OUT / (args.prob_file or f"{args.out}_prob.npy")
    for f in range(args.folds):
        core = ndi.binary_erosion(foldmap == f,
                                  structure=np.ones((2 * COLLAR + 1, 2 * COLLAR + 1)))
        core &= usable
        fold_core[f] = core

    if args.prob_file and prob_path.exists():
        log(f"reusing cached probabilities {prob_path.name}")
        prob = np.load(prob_path)
    for f in range(args.folds):
        if args.prob_file and prob_path.exists():
            break
        log(f"--- fold {f}: assembling training set")
        vis = cat & (foldmap != f)
        vispro = pro & (foldmap != f)
        pos = {"catalogue": vis, "proxy_off": vispro, "union": (vis | vispro)}[args.pos_pop]
        pos &= usable

        dist = ndi.distance_transform_edt(~vis) * PIXEL_M
        for i in range(0, n, step):
            Xall[i:i + step, nf] = np.log1p(dist[usable][i:i + step]).astype(np.float32)

        pos_rows = idx[pos]
        amb = dilate(vis, R_PX)
        # NOTE: np.flatnonzero gives (H, W)-flat indices; map them into design-row space
        neg_pool = idx.ravel()[np.flatnonzero(usable.ravel() & ~pos.ravel() & ~amb.ravel())]
        take = rng.choice(neg_pool.size, size=min(args.neg, neg_pool.size), replace=False)
        neg_rows = neg_pool[take]
        rows = np.concatenate([pos_rows, neg_rows])
        y = np.concatenate([np.ones(pos_rows.size, np.float32), np.zeros(neg_rows.size, np.float32)])
        w = np.concatenate([np.full(pos_rows.size, float(neg_rows.size) / max(pos_rows.size, 1)),
                            np.ones(neg_rows.size)])
        Xtr = np.asarray(Xall[rows])
        log(f"    rows {Xtr.shape} pos {pos_rows.size} neg {neg_rows.size}")
        prob[f], n_iter = fit_predict(Xtr, y, w, Xall, nf, args.maxiter)
        del Xtr
        log(f"    predicted ({n_iter} boosting iterations)")

    if not (args.prob_file and prob_path.exists()):
        np.save(prob_path, prob)
    if args.train_only:
        log("train-only: done")
        return 0

    # ------------------------------------------------------------ leakage canary
    canary = {}
    if args.canary:
        from sklearn.metrics import roc_auc_score
        log("leakage canary: single features, alone, on the held-out blocks")
        for f in range(args.folds):
            core = fold_core[f]
            g_all = (cat & core & (foldmap == f))
            for j, nm in enumerate(names + ["log1p_dist_visible_cat"]):
                v = Xall[:, j] if j == nf else Xall[:, j]
                if j == nf:
                    continue
                s = v[idx[core]]
                yb = g_all.ravel()[np.flatnonzero(core.ravel())]
                if yb.sum() < 50:
                    continue
                try:
                    a = roc_auc_score(yb, s)
                except ValueError:
                    continue
                canary.setdefault(nm, []).append(round(float(a), 4))
        canary = {k: {"per_fold": v, "mean_auc": round(float(np.mean(v)), 4),
                      "verdict": "LEAKAGE-SUSPECT" if np.mean(v) > 0.90 else "ok"}
                  for k, v in canary.items()}
        ordered = sorted(canary.items(), key=lambda kv: -kv[1]["mean_auc"])
        for nm, d in ordered[:8]:
            log(f"    {nm:28s} AUC {d['mean_auc']:.4f}  {d['verdict']}")
        log(f"    ... {len(ordered)} features tested, top 8 shown")

    # ------------------------------------------------------------ policy sweep
    log("emission policy sweep")
    truths = {"catalogue": cat, "proxy_off": pro}
    grid_p = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    rows_out = []
    for r in RADII:
        for kf in KFRACS:
            Kf = int(round(kf * n)) // args.folds
            per_fold = []
            for f in range(args.folds):
                grid_p[usable] = prob[f]
                m = nms_peaks(grid_p, r, usable) if r > 0 else (usable & (grid_p > 0))
                m = topk(m, grid_p, Kf)
                m &= fold_core[f]
                m &= ~(cat & (foldmap != f))       # visible catalogue masked pixel-exactly
                per_fold.append(m)
            S = float(sum(int(m.sum()) for m in per_fold))
            rec = {"radius_px": r, "k_frac": kf, "k_per_fold": Kf, "mass": S}
            for tname, tmask in truths.items():
                tp = fp = fn = 0.0
                for f, m in enumerate(per_fold):
                    g = tmask & fold_core[f] & (foldmap == f)
                    if not g.any():
                        continue
                    c = dti_components(m.astype(np.float32), g, valid=fold_core[f],
                                       pixel_size_m=PIXEL_M, radius_m=RADIUS_M)
                    tp += c.tp_w
                    fp += c.fp_w
                    fn += c.fn_w
                d = tp / (tp + ALPHA * fp + BETA * fn + 1e-12)
                rec[tname] = {"tp": round(tp, 2), "fp": round(fp, 2), "fn": round(fn, 2),
                              "K": round(tp + fn, 1), "dti": round(d, 5),
                              "credit_per_mass": round(tp / S, 5) if S else 0.0}
            rows_out.append(rec)
            log(f"  r={r} kf={kf:<6} mass={S:8.0f}  cat_dti={rec['catalogue']['dti']:.4f}"
                f"  proxy_dti={rec['proxy_off']['dti']:.4f}"
                f"  c/m={rec['catalogue']['credit_per_mass']:.4f}")

    by_cat = sorted(rows_out, key=lambda d: -d["catalogue"]["dti"])
    by_pro = sorted(rows_out, key=lambda d: -d["proxy_off"]["dti"])
    result = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": ("HOLDOUT-DTI (evaluator src/gems62/metric.py; spatially blocked "
                           f"{args.folds} folds of {int(np.ceil(HEIGHT/N_BLOCK_ROWS))}x"
                           f"{int(np.ceil(WIDTH/N_BLOCK_COLS))} blocks; {COLLAR} px collar; "
                           "visible catalogue masked pixel-exactly; pooled TP/FP/FN)"),
        "positive_population": args.pos_pop,
        "n_train_neg": args.neg,
        "scored_core_cells": {str(f): int(fold_core[f].sum()) for f in fold_core},
        "best_by_catalogue_dti": by_cat[0],
        "best_by_proxy_dti": by_pro[0],
        "policies": rows_out,
        "leakage_canary": canary,
        "seconds": round(time.time() - t0, 1),
    }
    (EV / f"{args.out}_sweep.json").write_text(json.dumps(result, indent=1))
    log("wrote " + str(EV / f"{args.out}_sweep.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
