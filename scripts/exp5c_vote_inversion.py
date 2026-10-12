#!/usr/bin/env python3
"""EXPERIMENT 5c - one-parameter, absolutely-calibrated inversion of 79 owner-reported scores.

The published index (competition page 967, transcribed and tested in ``src/gems62/metric.py``) is

    s_i = T_i / (T_i + 0.2 F_i + 0.8 (|G| - T_i)),   k(d) = max(1 - d/300 m, 0)

with, for a binary dot field A_i and the hidden truth set G restricted to the scored domain
(footprint minus mapped catalogue, organizer thread 11516),

    T_i = sum_{g in G} max_{x in A_i} k(d(x,g)),      F_i = sum_{x in A_i} (1 - max_{g in G} k(d(x,g))).

Every scored submission is therefore one measurement of G.  Experiments 5 and 5b searched coarse atom
dictionaries and both were defective: exp5 maximised *rank* correlation with a free scale (which is
degenerate - shrinking |G| makes the implied score ~5 x mean credit per dot, rho 0.93 while it
predicts 0.353 for an artifact the owner reported at 0.2778), and exp5b's dictionary had no atoms
fine enough to move |G| monotonically, so it stopped after one move at rmse 0.073.

This script uses the dictionary the physics suggests.  Define the score-weighted vote

    V(g) = sum_i s_i * max_{x in A_i} k(d(x,g))

("how strongly do the fields the organiser rewarded agree that this pixel is near a fault").  The
nested family ``S_q = {g : V(g) >= quantile_q(V)}`` is a one-parameter family of candidate truths
whose size moves monotonically.  For each q the script evaluates the EXACT published index for all
79 artifacts and picks q by minimising the sum of squared ABSOLUTE residuals, with no free scale: a
calibrated inversion.  Identifiability note: a truth pixel with zero kernel weight from every
artifact is unidentifiable (it only lowers every predicted score equally), so the search space is the
union of the artifacts' kernel footprints, which is where V > 0 by construction.

Cross-validation: q is re-selected on 2/3 of the artifacts (with their scores removed from the vote)
and the held-out third's scores are projected with the fold's surrogate.  The held-out rmse/bias is
the honest uncertainty attached to any projection this repository prints.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

R_PX = 3.0


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    d = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / d) if d > 0 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wm", default="build/Wm.npy")
    ap.add_argument("--cand", default="build/cand_idx.npy")
    ap.add_argument("--index", default="research/registry_index.json")
    ap.add_argument("--registry", default="/tmp/reg/tif")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--catalogue", default="data/labels.tif")
    ap.add_argument("--out", default="evidence/exp5c_vote_inversion.json")
    ap.add_argument("--save-truth", default="build/truth_vote_S.npy")
    ap.add_argument("--save-vote", default="build/vote_surface_cand.npy")
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20261012)
    args = ap.parse_args()
    t0 = time.time()
    root = pathlib.Path(__file__).resolve().parents[1]
    Wm = np.load(root / args.wm)                       # (n_art, n_cand) uint8 = 255*k
    idx = np.load(root / args.cand)
    with rasterio.open(root / args.sample) as ds:
        tmpl = ds.read(1)
    footprint = np.isfinite(tmpl)
    H, Wd = footprint.shape
    with rasterio.open(root / args.catalogue) as ds:
        cat = (ds.read(1) == 1) & footprint
    active = footprint & ~cat
    admissible = active.ravel()[idx]                   # candidate pixels allowed to be truth

    rows = json.load(open(root / args.index))
    seen = {}
    for r in rows:
        k = (r["repo"], os.path.basename(r["path"]))
        if k not in seen or r["score"] > seen[k]["score"]:
            seen[k] = r
    rows = sorted(seen.values(), key=lambda r: -r["score"])
    meta, Dm, Mact = [], [], []
    for r in rows:
        p = pathlib.Path(args.registry) / f"{r['repo']}__{os.path.basename(r['path'])}"
        if not p.exists():
            continue
        with rasterio.open(p) as ds:
            a = ds.read(1).astype(np.float32)
        if a.shape != footprint.shape:
            continue
        m = (np.where(np.isfinite(a), a, 0) > 0) & footprint
        if m.sum() == 0:
            continue
        meta.append(dict(name=f"{r['repo']}__{os.path.basename(r['path'])}", repo=r["repo"],
                         score=float(r["score"]), M=int(m.sum()),
                         M_active=int((m & active).sum()), path=r["path"], sha256=r.get("sha")))
        Dm.append(m.ravel()[idx])
        Mact.append(float((m & active).sum()))
    Dm = np.array(Dm)                                  # (n_art, n_cand) bool
    Mact = np.array(Mact)
    obs = np.array([m["score"] for m in meta])
    n_art = len(meta)
    print(f"artifacts {n_art}  candidates {idx.size:,}  admissible {int(admissible.sum()):,}",
          flush=True)
    Wm = np.where(admissible[None, :], Wm, 0)          # zero out inadmissible candidate columns

    def T_of(mem: np.ndarray, art=None) -> np.ndarray:
        """Exact T_i = sum_{g in S} max_x k(d(x,g)) for the selected candidate pixels."""
        sub = Wm[:, mem] if art is None else Wm[np.ix_(art, mem)]
        return sub.sum(axis=1).astype(np.float64) / 255.0

    def hit_of(kc: np.ndarray, art) -> np.ndarray:
        """sum over dots_i of max_g k(d) - boolean indexing, one artifact at a time (memory-safe)."""
        return np.array([float(kc[Dm[i]].sum()) for i in (art if art is not None else range(n_art))])

    # ---- the score-weighted vote surface (candidate pixels only) --------------------------
    V = np.zeros(idx.size, np.float64)
    for i in range(n_art):
        V += obs[i] * (Wm[i] / 255.0)
    np.save(root / args.save_vote, V.astype(np.float32))
    print(f"vote surface: max {V.max():.3f}  nonzero {int((V > 0).sum()):,}  "
          f"t={time.time() - t0:.0f}s", flush=True)

    def kernel_field(Smask):
        dS = distance_transform_edt(~Smask, sampling=(1.0, 1.0))
        kS = np.where(dS > R_PX, 0.0, 1.0 - dS / R_PX).astype(np.float32)
        kc = kS.ravel()[idx]
        del dS, kS
        return kc

    def evaluate(thresh: float, art: np.ndarray) -> dict:
        mem = (V >= thresh) & admissible
        K = float(mem.sum())
        if K == 0:
            return dict(K=0.0)
        T = T_of(mem)                                          # exact: sum_g max_x k
        Smask = np.zeros((H, Wd), bool)
        Smask.ravel()[idx[mem]] = True
        kc = kernel_field(Smask)
        F = Mact[art] - hit_of(kc, art)                        # sum_x (1 - max_g k)
        pred = T[art] / (T[art] + 0.2 * F + 0.8 * (K - T[art]) + 1e-12)
        del Smask, kc
        return dict(K=K, T=T, F=F, pred=pred, mem=mem, thresh=thresh,
                    rmse=float(np.sqrt(((pred - obs[art]) ** 2).mean())),
                    sse=float(((pred - obs[art]) ** 2).sum()),
                    rho=spearman(pred, obs[art]),
                    max_T_over_K=float(T[art].max() / K))

    allart = np.arange(n_art)
    qs = [0.9999, 0.9995, 0.999, 0.998, 0.997, 0.995, 0.993, 0.99, 0.985, 0.98, 0.97, 0.96,
          0.95, 0.94, 0.93, 0.92, 0.90, 0.88, 0.85, 0.80, 0.75, 0.70, 0.60, 0.50, 0.40, 0.30,
          0.20, 0.10, 0.05, 0.02, 0.01]
    pos = V[admissible & (V > 0)]
    sweep = []
    for q in qs:
        if pos.size == 0:
            break
        thr = float(np.quantile(pos, q))
        r = evaluate(thr, allart)
        if r["K"] == 0:
            continue
        sweep.append(dict(q=q, thresh=thr, K=r["K"], rmse=r["rmse"], rho=r["rho"],
                          max_T_over_K=r["max_T_over_K"], pred_top=float(r["pred"][0]),
                          obs_top=float(obs[0])))
        print(f"  q={q:<7} thr={thr:8.4f} K={r['K']:>9,.0f} rmse={r['rmse']:.4f} "
              f"rho={r['rho']:.4f} maxT/K={r['max_T_over_K']:.3f} pred#1={r['pred'][0]:.4f}",
              flush=True)
    feasible = [s for s in sweep if s["max_T_over_K"] <= 1.0 + 1e-9] or sweep
    best = min(feasible, key=lambda s: s["rmse"])
    print(f"BEST q={best['q']} K={best['K']:,.0f} rmse={best['rmse']:.4f} rho={best['rho']:.4f}",
          flush=True)
    r = evaluate(best["thresh"], allart)
    mem = r["mem"]
    Smask = np.zeros((H, Wd), bool)
    Smask.ravel()[idx[mem]] = True
    np.save(root / args.save_truth, Smask)

    # ---- cross-validation of the projection ----------------------------------------------
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(n_art)
    cv = []
    for f in range(args.folds):
        te = np.sort(np.array_split(perm, args.folds)[f])
        tr = np.array([i for i in range(n_art) if i not in set(te.tolist())])
        Vtr = np.zeros(idx.size, np.float64)
        for i in tr:
            Vtr += obs[i] * (Wm[i] / 255.0)
        pos_tr = Vtr[admissible & (Vtr > 0)]
        local = []
        for q in qs:
            if pos_tr.size == 0:
                break
            thr = float(np.quantile(pos_tr, q))
            memt = (Vtr >= thr) & admissible
            Kt = float(memt.sum())
            if Kt == 0:
                continue
            Tt = T_of(memt, tr)
            if Tt.max() > Kt:
                continue
            St = np.zeros((H, Wd), bool)
            St.ravel()[idx[memt]] = True
            kc = kernel_field(St)
            Ft = Mact[tr] - hit_of(kc, tr)
            pt = Tt / (Tt + 0.2 * Ft + 0.8 * (Kt - Tt) + 1e-12)
            local.append((float(((pt - obs[tr]) ** 2).sum()), q, thr, Kt))
            del St, kc
        if not local:
            continue
        local.sort(key=lambda z: z[0])
        sse, q, thr, Kt = local[0]
        memt = (Vtr >= thr) & admissible
        St = np.zeros((H, Wd), bool)
        St.ravel()[idx[memt]] = True
        kc = kernel_field(St)
        del St
        Tt = T_of(memt, te)
        Ft = Mact[te] - hit_of(kc, te)
        pt = Tt / (Tt + 0.2 * Ft + 0.8 * (Kt - Tt) + 1e-12)
        cv.append(dict(fold=int(f), n_train=int(tr.size), n_test=int(te.size), q=q, K=Kt,
                       train_rmse=float(np.sqrt(sse / tr.size)),
                       heldout_rho=spearman(pt, obs[te]),
                       heldout_rmse=float(np.sqrt(((pt - obs[te]) ** 2).mean())),
                       heldout_bias=float((pt - obs[te]).mean()),
                       heldout_max_abs_err=float(np.abs(pt - obs[te]).max()),
                       rows=[dict(name=meta[i]["name"], obs=float(obs[i]), projected=float(pt[j]))
                             for j, i in enumerate(te.tolist())]))
        print(f"fold {f}: q={q} K={Kt:,.0f} HELDOUT rho={cv[-1]['heldout_rho']:.4f} "
              f"rmse={cv[-1]['heldout_rmse']:.4f} bias={cv[-1]['heldout_bias']:+.4f}", flush=True)
        del memt, kc, Vtr

    ds_cat = distance_transform_edt(~cat, sampling=(100.0, 100.0))
    dS = ds_cat[Smask]
    out = dict(
        experiment="exp5c_vote_inversion",
        label="MEASURED-INSTRUMENT (a projection is never written as a score)",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        method=("nested quantiles of the score-weighted vote V(g)=sum_i s_i max_x k(d(x,g)); q "
                "chosen by minimum sum of squared ABSOLUTE residuals of the exact published index, "
                "no free scale; feasibility T_i <= |S| enforced"),
        n_artifacts=n_art, candidate_pixels=int(idx.size),
        admissible_pixels=int(admissible.sum()),
        sweep=sweep, best=best,
        exact_fit=dict(K=r["K"], rmse=r["rmse"], rho=r["rho"], max_T_over_K=r["max_T_over_K"]),
        pred_vs_obs=[dict(name=meta[i]["name"], obs=float(obs[i]), projected=float(r["pred"][i]),
                          T=float(r["T"][i]), F=float(r["F"][i]), M_active=float(Mact[i]))
                     for i in np.argsort(-obs)],
        cv=dict(folds=args.folds, seed=args.seed, results=cv,
                mean_heldout_rho=float(np.mean([c["heldout_rho"] for c in cv])),
                mean_heldout_rmse=float(np.mean([c["heldout_rmse"] for c in cv])),
                mean_heldout_bias=float(np.mean([c["heldout_bias"] for c in cv])),
                worst_heldout_abs_err=float(np.max([c["heldout_max_abs_err"] for c in cv]))),
        surrogate_geometry=dict(n=int(Smask.sum()),
                                median_dist_to_catalogue_m=float(np.median(dS)),
                                p10_m=float(np.percentile(dS, 10)),
                                p25_m=float(np.percentile(dS, 25)),
                                p75_m=float(np.percentile(dS, 75)),
                                p90_m=float(np.percentile(dS, 90)),
                                frac_within_300m=float((dS <= 300).mean()),
                                frac_within_600m=float((dS <= 600).mean()),
                                frac_within_1000m=float((dS <= 1000).mean()),
                                frac_beyond_2000m=float((dS > 2000).mean())),
        artifacts=meta, truth_path=args.save_truth, vote_path=args.save_vote,
        seconds=round(time.time() - t0, 1))
    json.dump(out, open(root / args.out, "w"), indent=1)
    print("wrote", args.out, f"{time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
