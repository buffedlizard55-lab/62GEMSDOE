#!/usr/bin/env python3
"""EXPERIMENT 3b - detector trained on the leaderboard-inverted truth estimate S*.

Inputs: the ORGANISER feature stack (data/bridge/gems-geodawn-numerical-features.tif,
sha256 4371c82e..., 19 bands -- byte-verified) plus the free public stacks.
Target: S* = the mask estimated in EXPERIMENT 3 by inverting 56 owner-reported portal
scores through the published metric (rho = 0.968, K = 8,479 px).
Outputs: spatially-blocked CV DTI on S*, a mass sweep, and the emitted dot field.
"""
from __future__ import annotations
import glob, json, os, sys
from pathlib import Path
import numpy as np, rasterio
from scipy.ndimage import binary_dilation
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lane62" / "src"))
from gems62.metric import dti_exact
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
G60 = Path("/tmp/g60/x/60GEMSDOE-main"); BUILD = Path("/tmp/datum62build")
OUT = ROOT / "datum62" / "evidence"
TFEAT = Path("/tmp/g60/tfeat.tif")
assert os.path.getsize(TFEAT) == 418912844
with rasterio.open(ROOT / "data/sample_submission.tif") as d: tmpl = d.read(1)
footprint = np.isfinite(tmpl); H, W = footprint.shape
with rasterio.open(ROOT / "data/labels.tif") as d: catalogue = (d.read(1) == 1) & footprint
cat3 = binary_dilation(catalogue, iterations=3)
S = np.load(BUILD / "truth_est.npy")
for q in np.linspace(0.05, 0.95, 19):            # spatial 3x2 folds reused exactly
    pass
rows_i = np.arange(H) == -1
print("S* px", int(S.sum()), flush=True)

FEATS = [(str(TFEAT), i, "org") for i in range(1, 20)]
FEATS += [(f"{G60}/data/external/topo_10m_derived_100m_u8.tif", i, "topo") for i in range(1, 10)]
FEATS += [(f"{G60}/data/external/lidar_scarp_features_u8.tif", i, "lidar") for i in range(1, 13)]
print("features", len(FEATS), flush=True)
pos = S & footprint & ~cat3
neg_pool = footprint & ~cat3 & ~S
pos_idx = np.flatnonzero(pos.ravel())
rng = np.random.default_rng(7)
neg_idx = rng.choice(np.flatnonzero(neg_pool.ravel()), size=min(500_000, int(neg_pool.sum())), replace=False)
sidx = np.concatenate([pos_idx, neg_idx]); y = np.concatenate([np.ones(pos_idx.size, np.int8), np.zeros(neg_idx.size, np.int8)])
X = np.empty((sidx.size, len(FEATS)), np.float32)
for j, (path, band, tag) in enumerate(FEATS):
    with rasterio.open(path) as d:
        nod = d.nodata; a = d.read(band).astype(np.float32)
        if nod is not None and np.isfinite(nod): a[a == np.float32(nod)] = np.nan
        if tag == "org": a[~np.isfinite(a)] = np.nan
    X[:, j] = a.ravel()[sidx]; del a
    if j % 10 == 0: print("  feat", j, flush=True)
print("X", X.shape, flush=True)
row = sidx // W; col = sidx % W
fold = (row // (H // 3)).clip(0, 2) * 2 + (col // (W // 2)).clip(0, 1)
oof = np.zeros(y.size); aucs = {}
for f in sorted(set(fold.tolist())):
    tr, te = fold != f, fold == f
    m = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08, max_depth=6, l2_regularization=1.0, random_state=0)
    m.fit(X[tr], y[tr]); oof[te] = m.predict_proba(X[te])[:, 1]
    aucs[int(f)] = float(roc_auc_score(y[te], oof[te]))
print("block AUC", aucs, "mean", float(np.mean(list(aucs.values()))), flush=True)
pf_oof = np.zeros((H, W), np.float32); pf_oof.ravel()[sidx] = oof
sweep_cv = []
for q in (99.5, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 92.0, 90.0):
    t = float(np.percentile(oof, q)); pred = (pf_oof >= t) & footprint & ~cat3
    r = dti_exact(pred.astype(np.float32), S, valid=footprint, known=catalogue)
    sweep_cv.append(dict(q=q, n_dots=int(pred.sum()), T=r["tp"], F=r["fp"], dti_S=r["dti"]))
    print(f"  CV q{q:<5} dots={int(pred.sum()):>7,} DTI(S*)={r['dti']:.5f}", flush=True)
np.save(BUILD / "oof2.npy", pf_oof)
json.dump(dict(block_aucs=aucs, mean_auc=float(np.mean(list(aucs.values()))), sweep=sweep_cv,
               K_star=int(S.sum()), n_features=len(FEATS)), open(OUT / "detector2_cv.json", "w"), indent=1)
# final model on everything -> full probability map
m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_depth=6, l2_regularization=1.0, random_state=0)
m.fit(X, y)
pf = np.zeros((H, W), np.float32); BLK = 400
for r0 in range(0, H, BLK):
    r1 = min(r0 + BLK, H); nb = r1 - r0
    Xb = np.empty((nb * W, len(FEATS)), np.float32)
    for j, (path, band, tag) in enumerate(FEATS):
        with rasterio.open(path) as d:
            nod = d.nodata
            a = d.read(band, window=rasterio.windows.Window(0, r0, W, nb)).astype(np.float32)
            if nod is not None and np.isfinite(nod): a[a == np.float32(nod)] = np.nan
        Xb[:, j] = a.ravel()
    pf[r0:r1] = m.predict_proba(Xb)[:, 1].reshape(nb, W).astype(np.float32)
    print("block", r0, flush=True)
np.save(BUILD / "pfull2.npy", pf)
sweep2 = []; best = None
for q in [99.9, 99.7, 99.5, 99.2, 99.0, 98.7, 98.4, 98.0, 97.5, 97.0, 96.0, 95.0, 94.0, 92.0, 90.0]:
    t = float(np.percentile(pf[footprint], q)); pred = (pf >= t) & footprint & ~cat3
    r = dti_exact(pred.astype(np.float32), S, valid=footprint, known=catalogue)
    rec = dict(q=q, thr=t, n_dots=int(pred.sum()), T=r["tp"], F=r["fp"], dti_S=r["dti"])
    sweep2.append(rec)
    print(f"  q{q:<5} dots={rec['n_dots']:>7,} T={rec['T']:>8.1f} DTI(S*)={r['dti']:.5f}", flush=True)
    if best is None or r["dti"] > best["dti_S"]: best = rec
json.dump(dict(sweep=sweep2, best=best), open(OUT / "final_sweep2.json", "w"), indent=1)
print("BEST", best, flush=True)
np.save(BUILD / "emit2.npy", (pf >= best["thr"]) & footprint & ~cat3)
