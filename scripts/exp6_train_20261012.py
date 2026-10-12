#!/usr/bin/env python3
"""EXP-6 (session arena/7b275dfb-62gemsdoe): screen hypotheses, train, spatially-blocked CV.

Subcommands:
  screen  single-feature leakage canaries + H62-Z1 buffer test + credit table
  train   three models (A raw bands = H-2 reproduction, B A+H-2R consensus features,
          C B+vent interaction) with 3x2 spatially-blocked folds against the rebuilt
          S* instrument; OOF DTI(S*) mass sweep; evidence JSON.

All numbers written to evidence/e5_screen_20261012.json / e6_train_20261012.json.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import metric as M  # noqa: E402

CACHE = ROOT / "build" / "cache"
EVID = ROOT / "evidence"


def load_footprint():
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as d:
        tmpl = d.read(1)
    return np.isfinite(tmpl)


def load_catalogue():
    with rasterio.open(ROOT / "data" / "labels.tif") as d:
        return d.read(1) == 1


def feat_names(which: str) -> list[str]:
    meta = json.loads((CACHE / "meta.json").read_text())
    all_names = [f["name"] for f in meta["features"]]
    org = [n for n in all_names if n.startswith("org_") and not n.endswith("_nanflag")]
    topo = [n for n in all_names if n.startswith("topo_") or n.startswith("chi_")
            or n.startswith("lidar_")]
    h2r = [n for n in all_names if n.startswith(("vess_", "orient_", "vote90_", "vess_mean_",
                                                 "step_", "topo_coh_grad"))]
    z1 = [n for n in all_names if n.startswith(("vent_", "vvent_"))]
    if which == "A":
        return org + topo
    if which == "B":
        return org + topo + h2r
    if which == "C":
        return org + topo + h2r + z1
    raise ValueError(which)


def load_matrix(names: list[str], flat_idx: np.ndarray) -> np.ndarray:
    X = np.empty((flat_idx.size, len(names)), np.float32)
    for j, n in enumerate(names):
        a = np.load(CACHE / f"feat_{n}.npy").astype(np.float32)
        X[:, j] = a.ravel()[flat_idx]
    return X


def credit_per_dot(pred: np.ndarray, truth: np.ndarray) -> float:
    """mean 300 m kernel credit per dot against a truth mask (e2b convention)."""
    n = int(pred.sum())
    if n == 0:
        return 0.0
    dp = ndi.distance_transform_edt(~pred)
    tp = float(M.kernel(dp[truth]).sum())
    return tp / n


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    den = np.sqrt((ra @ ra) * (rb @ rb))
    return float(ra @ rb / den) if den > 0 else float("nan")


def screen() -> int:
    footprint = load_footprint()
    cat = load_catalogue() & footprint
    cat3 = ndi.binary_dilation(cat, iterations=3)
    S = np.load(ROOT / "build" / "sstar" / "truth_est.npy")
    S = S & footprint
    with rasterio.open(ROOT / "build" / "ext" / "derived_sgmc_faults_100m.tif") as d:
        sgmc = d.read(1) > 0
    sgmc_off = sgmc & footprint & ~cat3
    H, W = footprint.shape
    row = np.arange(H)[:, None] * np.ones((1, W), np.int64)
    col = np.ones((H, 1), np.int64) * np.arange(W)[None, :]
    fold = (row // (H // 3)).clip(0, 2) * 2 + (col // (W // 2)).clip(0, 1)
    fold = fold.ravel()
    foot_idx = np.flatnonzero(footprint.ravel())
    pos = S & footprint & ~cat3
    rng = np.random.default_rng(7)
    pos_idx = np.flatnonzero(pos.ravel())
    neg_pool = np.flatnonzero((footprint & ~cat3 & ~S).ravel())
    neg_idx = rng.choice(neg_pool, size=min(300_000, neg_pool.size), replace=False)
    sidx = np.concatenate([pos_idx, neg_idx])
    y = np.concatenate([np.ones(pos_idx.size, np.int8), np.zeros(neg_idx.size, np.int8)])
    f = fold[sidx]

    meta = json.loads((CACHE / "meta.json").read_text())
    names = [x["name"] for x in meta["features"]]
    out = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               instrument="S* rebuild v2 (fixed 300 m kernel)",
               n_pos=int(pos_idx.size), n_neg=int(neg_idx.size),
               single_feature_auc={}, z1_buffer_test=None)
    print(f"screening {len(names)} features, pos={pos_idx.size:,} neg={neg_idx.size:,}", flush=True)
    for n in names:
        X = load_matrix([n], sidx)
        aucs = []
        for fv in range(6):
            tr, te = f != fv, f == fv
            if y[te].sum() == 0 or (1 - y[te]).sum() == 0:
                continue
            # rank-based single-feature AUC on the held-out fold
            sc = X[te, 0]
            try:
                aucs.append(float(roc_auc_score(y[te], sc)))
            except ValueError:
                pass
        out["single_feature_auc"][n] = dict(
            auc_mean=float(np.mean(aucs)) if aucs else float("nan"),
            auc_max=float(np.max(aucs)) if aucs else float("nan"),
            canary_leak=bool(aucs and np.mean(aucs) > 0.90))
        del X

    # H62-Z1 buffer test on a mass-matched control field (detector-free):
    # top-38k pixels of each vent layer's density vs isolated-random, credit on SGMC-offcat
    vent = np.load(CACHE / "feat_vent_kd_5km.npy").astype(np.float32)
    dpx = np.load(CACHE / "feat_vent_dpx.npy").astype(np.float32)
    wk = vent.ravel()[foot_idx]
    top = foot_idx[np.argsort(-wk)[:38_000]]
    cand = np.zeros(footprint.shape, bool)
    cand.ravel()[top] = True
    iso = np.zeros(footprint.shape, bool)
    order = top.copy()
    rng2 = np.random.default_rng(11)
    placed = 0
    supp = np.zeros(footprint.shape, bool)
    for i in order:
        r, c = divmod(int(i), W)
        if supp[r, c]:
            continue
        iso[r, c] = True
        placed += 1
        r0, r1 = max(r - 3, 0), min(r + 4, H)
        c0, c1 = max(c - 3, 0), min(c + 4, W)
        supp[r0:r1, c0:c1] = True
        if placed >= 38_000:
            break
    rand = np.zeros(footprint.shape, bool)
    ridx = rng2.choice(foot_idx, size=120_000, replace=False)
    rsel = []
    supp[:] = False
    for i in ridx:
        r, c = divmod(int(i), W)
        if supp[r, c]:
            continue
        rsel.append(i)
        r0, r1 = max(r - 3, 0), min(r + 4, H)
        c0, c1 = max(c - 3, 0), min(c + 4, W)
        supp[r0:r1, c0:c1] = True
        if len(rsel) >= placed:
            break
    rand.ravel()[np.array(rsel, np.int64)] = True

    res_z1 = {}
    for buf_px, tag in ((50, "5km"), (100, "10km"), (200, "20km")):
        inside = dpx <= buf_px
        for label, field in (("vent_top", iso), ("random_control", rand)):
            dd = field & inside
            do = field & ~inside
            res_z1[f"{label}_{tag}"] = dict(
                n_in=int(dd.sum()), n_out=int(do.sum()),
                credit_in=credit_per_dot(dd, sgmc_off) if dd.sum() else 0.0,
                credit_out=credit_per_dot(do, sgmc_off) if do.sum() else 0.0)
    out["z1_buffer_test"] = res_z1
    out["vent_feature_rows"] = dict(
        n_thermal=int((dpx == 0).sum()),
        note="gdr_wellspring_in_footprint.csv thermal subset (T>=40C or Hot/Warm class or geotherm>=60C)")
    out["credit_convention"] = "mean 300 m kernel credit per dot = sum_g k(dist(g,dots))/n_dots; instrument = derived SGMC 1:750k minus catalogue dilated 3px"
    out["sgmc_offcat_pixels"] = int(sgmc_off.sum())
    (EVID / "e5_screen_20261012.json").write_text(json.dumps(out, indent=1) + "\n")
    top_leak = sorted(out["single_feature_auc"].items(),
                      key=lambda kv: -(kv[1]["auc_mean"] or 0))[:8]
    print("top single-feature AUCs:")
    for n, v in top_leak:
        print(f"  {n:<28} {v['auc_mean']:.4f}  canary={v['canary_leak']}")
    print(json.dumps(res_z1, indent=1)[:1200])
    return 0


def train() -> int:
    footprint = load_footprint()
    cat = load_catalogue() & footprint
    cat3 = ndi.binary_dilation(cat, iterations=3)
    S = np.load(ROOT / "build" / "sstar" / "truth_est.npy") & footprint
    H, W = footprint.shape
    row = np.arange(H)[:, None] * np.ones((1, W), np.int64)
    col = np.ones((H, 1), np.int64) * np.arange(W)[None, :]
    foldmap = ((row // (H // 3)).clip(0, 2) * 2 + (col // (W // 2)).clip(0, 1)).ravel()
    pos = S & ~cat3
    rng = np.random.default_rng(7)
    pos_idx = np.flatnonzero(pos.ravel())
    neg_pool = np.flatnonzero((footprint & ~cat3 & ~S).ravel())
    neg_idx = rng.choice(neg_pool, size=min(500_000, neg_pool.size), replace=False)
    sidx = np.concatenate([pos_idx, neg_idx])
    y = np.concatenate([np.ones(pos_idx.size, np.int8), np.zeros(neg_idx.size, np.int8)])
    f = foldmap[sidx]
    foot_idx = np.flatnonzero(footprint.ravel())

    results = {}
    best = None
    for which in ("A", "B", "C"):
        names = feat_names(which)
        X = load_matrix(names, sidx)
        oof = np.zeros(y.size, np.float64)
        fold_auc = {}
        for fv in range(6):
            tr, te = f != fv, f == fv
            m = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08,
                                               max_depth=6, l2_regularization=1.0,
                                               random_state=0)
            m.fit(X[tr], y[tr])
            oof[te] = m.predict_proba(X[te])[:, 1]
            fold_auc[fv] = float(roc_auc_score(y[te], oof[te]))
            # full-grid OOF for the held-out block
        auc_all = float(roc_auc_score(y, oof))
        # full-grid OOF probabilities (6 models -> each predicts its fold's block)
        p_oof = np.zeros(foot_idx.size, np.float32)
        for fv in range(6):
            m = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.08,
                                               max_depth=6, l2_regularization=1.0,
                                               random_state=0)
            m.fit(X[f != fv], y[f != fv])
            blk = foot_idx[foldmap[foot_idx] == fv]
            Xb = load_matrix(names, blk)
            p_oof[np.isin(foot_idx, blk)] = m.predict_proba(Xb)[:, 1].astype(np.float32)
        P = np.zeros((H, W), np.float32)
        P.ravel()[foot_idx] = p_oof
        # mass sweep on OOF
        sweep = []
        active = footprint & ~cat3
        for q in (99.9, 99.8, 99.6, 99.4, 99.2, 99.0, 98.5, 98.0, 97.0, 96.0, 94.0, 92.0, 90.0):
            thr = float(np.quantile(p_oof, q / 100.0))
            pred = (P >= thr) & active
            n = int(pred.sum())
            if n == 0:
                continue
            d = M.dti_binary(pred, S, active=active)
            sweep.append(dict(q=q, n_dots=n, dti_sstar=d["dti"],
                              credit_sstar=d["tp"] / n))
        best_d = max(sweep, key=lambda s: s["dti_sstar"])
        results[which] = dict(features=names, fold_auc=fold_auc, auc_oof=auc_all,
                              sweep=sweep, best=best_d)
        np.save(ROOT / "build" / f"p_oof_{which}.npy", P)
        print(f"model {which}: AUC={auc_all:.4f} best DTI(S*)={best_d['dti_sstar']:.4f} "
              f"at {best_d['n_dots']:,} dots (q={best_d['q']})", flush=True)
        if best is None or best_d["dti_sstar"] > results[best]["best"]["dti_sstar"]:
            best = which
    out = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               instrument="S* rebuild v2 (fixed 300 m kernel)",
               evaluator="gems62.metric.dti_binary (published formula, 300 m triangular kernel)",
               folds="3x2 spatial blocks (row//1243, col//1646)",
               models=results, selected=best,
               baseline_inherited="H-2 raw-band detector: blocked DTI(S*) 0.2178, AUC 0.863 "
                                  "(datum62/evidence/detector2_cv.json; old 75 m-kernel instrument)")
    (EVID / "e6_train_20261012.json").write_text(json.dumps(out, indent=1) + "\n")
    print("selected model:", best)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "screen"
    sys.exit(screen() if cmd == "screen" else train())
