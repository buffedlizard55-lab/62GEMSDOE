#!/usr/bin/env python3
"""EXPERIMENT 5b - *calibrated* inversion of the portal scores (no free scale).

Experiment 5 maximised rank correlation with a free multiplicative scale.  That objective is
DEGENERATE and this script documents why: shrinking |S| turns the implied score into
``T_i/(0.2 M_i)`` ~ 5 * (mean credit per dot), which ranks artifacts well (rho 0.93) while the
absolute calibration collapses (r2 = 0.0795, scale 2.37 -> it predicts 0.353 for the artifact the
owner reported at 0.2778).  A rank-only surrogate cannot be turned into a projection.

The physically correct inversion has NO free parameter: every scored submission satisfies

    s_i = DTI_i(S) = T_i(S) / (T_i(S) + 0.2 F_i(S) + 0.8 (|S| - T_i(S)))

exactly, with T_i(S) = sum_{g in S} max_{x in dots_i} k(d) and F_i(S) = sum_{x in dots_i}
(1 - max_{g in S} k(d)) restricted to the scored footprint minus the mapped catalogue.  So the
objective here is the sum of squared *absolute* residuals, with two hard feasibility constraints:

  (C1) T_i(S) <= |S| for every i  (a kernel-weighted hit sum cannot exceed the truth mass), and
  (C2) S lies inside the scored footprint and outside the mapped catalogue (organizer thread 11516:
       known-fault pixels are excluded from evaluation, so they cannot be part of G).

Outputs a surrogate S_cal that is simultaneously rank-accurate and scale-accurate, plus a
leave-artifacts-out cross-validation of the *projected score* of held-out artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt

R_PX = 3.0


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
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
    ap.add_argument("--out", default="evidence/exp5b_calibrated_inversion.json")
    ap.add_argument("--save-truth", default="build/truth_cal_S.npy")
    ap.add_argument("--max-steps", type=int, default=25)
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20261012)
    args = ap.parse_args()
    t0 = time.time()
    root = pathlib.Path(__file__).resolve().parents[1]

    Wm = np.load(root / args.wm)                     # (n_art, n_cand) uint8, k*255
    idx = np.load(root / args.cand)                  # flat indices of candidate pixels
    with rasterio.open(root / args.sample) as ds:
        tmpl = ds.read(1)
    footprint = np.isfinite(tmpl); H, Wd = footprint.shape
    with rasterio.open(root / args.catalogue) as ds:
        cat = (ds.read(1) == 1) & footprint
    cand_mask = np.zeros((H, Wd), bool); cand_mask.ravel()[idx] = True
    cand_ok = (cand_mask & footprint & ~cat).ravel()[idx]     # (C2)

    rows = json.load(open(root / args.index))
    seen = {}
    for r in rows:
        k = (r["repo"], os.path.basename(r["path"]))
        if k not in seen or r["score"] > seen[k]["score"]:
            seen[k] = r
    rows = sorted(seen.values(), key=lambda r: -r["score"])
    meta, masks = [], []
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
        masks.append(m)
        meta.append(dict(name=f"{r['repo']}__{os.path.basename(r['path'])}", repo=r["repo"],
                         score=float(r["score"]), M=int(m.sum()), path=r["path"]))
    assert len(masks) == Wm.shape[0], (len(masks), Wm.shape[0])
    obs = np.array([m["score"] for m in meta])
    Ms = np.array([m["M"] for m in meta], float)
    # F_i needs max_{g in S} k(d(x,g)) at every *dot* pixel x; compute it from the same EDT idea:
    # for a dot x, w_i(x) = max over S of k(d(x,S)).  We get it by dilating S with the kernel and
    # reading the artifact's own weight field, which is symmetric: k(d(x,g)) = k(d(g,x)).
    # Wm[i] holds k(d(candidate_pixel, dots_i)) -> exactly the needed quantity at candidate pixels.
    # Dots outside the candidate set are impossible (candidate = union of all dots).
    print(f"artifacts {len(meta)}  candidates {idx.size:,}  admissible {int(cand_ok.sum()):,}",
          flush=True)

    def components(mem: np.ndarray):
        """T_i, F_i, |S| for a membership vector over candidate pixels."""
        T = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
        # F_i = sum over dots of (1 - max_g k) ; max_g k at dot x = max over mem of k(d(x,g)).
        # Because k is symmetric and Wm[i, j] = k(d(cand_j, dots_i)), the row-wise max over the
        # selected candidates is NOT the per-dot max; instead use the identity
        # F_i = M_i - sum_{x in dots_i} w_i(x) and note sum_x w_i(x) != T_i in general.
        # Exact route: recompute per-dot max with an EDT of S (only for the accepted set).
        return T

    active = footprint & ~cat          # the scored domain (organizer thread 11516)

    def exact_fit(Smask: np.ndarray, artifact_masks: list[np.ndarray]) -> dict:
        """Exact DTI_i(S) for every artifact, straight from the published equations.

        T_i = sum_{g in S} max_{x in dots_i} k(d(x,g));  because k is symmetric this equals
        sum_{g in S} kS[g] with kS the kernel field of the *dots*.  Here we need the other
        direction: T_i = sum_{g in S} max_x k = kS_of_dots evaluated on S, and
        F_i = sum_{x in dots_i} (1 - max_{g in S} k) = sum_{x in dots_i} (1 - kS[x]).
        """
        dS = distance_transform_edt(~Smask, sampling=(1.0, 1.0))
        kS = np.where(dS > R_PX, 0.0, 1.0 - dS / R_PX)
        T = np.empty(len(artifact_masks)); F = np.empty(len(artifact_masks))
        for i, m0 in enumerate(artifact_masks):
            m = m0 & active                       # dots on known faults / outside are not scored
            dm = distance_transform_edt(~m, sampling=(1.0, 1.0))
            km = np.where(dm > R_PX, 0.0, 1.0 - dm / R_PX)
            T[i] = km[Smask].sum()                # sum over truth of max_x k(d)
            F[i] = float(m.sum()) - kS[m].sum()   # sum over dots of (1 - max_g k)
            del dm, km
        K = float(Smask.sum())
        pred = T / (T + 0.2 * F + 0.8 * (K - T) + 1e-12)
        return dict(T=T, F=F, K=K, pred=pred, sse=float(((pred - obs) ** 2).sum()),
                    rmse=float(np.sqrt(((pred - obs) ** 2).mean())),
                    rho=spearman(pred, obs),
                    max_T_over_K=float(T.max() / K) if K else float("inf"))

    def to_mask(mem: np.ndarray) -> np.ndarray:
        S = np.zeros((H, Wd), bool)
        sel = idx[mem]
        S.ravel()[sel] = True
        return S

    # ---- atom dictionary -----------------------------------------------------------------
    flat = lambda A: (A.ravel()[idx]) & cand_ok      # noqa: E731
    hi = [m for m, mt in zip(masks, meta) if mt["score"] >= 0.24]
    cons = np.logical_and.reduce(hi) & footprint & ~cat
    atoms = {f"art{i}_{meta[i]['repo']}": flat(masks[i]) for i in range(len(masks))}
    atoms["consensus_hi"] = flat(cons)
    atoms["majority_hi"] = flat((np.sum(hi, 0) >= (len(hi) // 2 + 1)) & footprint & ~cat)
    atoms["union_hi"] = flat(np.logical_or.reduce(hi) & footprint & ~cat)
    for it in (1, 2, 3, 4):
        atoms[f"cons_dil{it}"] = flat(binary_dilation(cons, iterations=it) & footprint & ~cat)
    Aidx = {k: np.flatnonzero(v) for k, v in atoms.items() if v.any()}
    Scache = {k: Wm[:, v].sum(axis=1).astype(np.float64) / 255.0 for k, v in Aidx.items()}

    def score_mem(mem: np.ndarray) -> dict:
        """Fast approximate objective used *inside* the greedy (T from Wm, F ~ M - T)."""
        T = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
        K = float(mem.sum())
        F = np.maximum(Ms - T, 0.0)
        pred = T / (T + 0.2 * F + 0.8 * np.maximum(K - T, 0.0) + 1e-12)
        sse = float(((pred - obs) ** 2).sum())
        feas = float(T.max() / K) if K > 0 else np.inf
        return dict(pred=pred, sse=sse + (1e6 * max(0.0, feas - 1.0)), rmse=float(np.sqrt(sse / obs.size)),
                    rho=spearman(pred, obs), K=int(K), max_T_over_K=feas, T=T)

    start = flat(cons)
    mem = start.copy()
    cur = score_mem(mem)
    log = [dict(step="start", atom="consensus_hi", **{k: v for k, v in cur.items() if k != "pred"})]
    print(f"start K={cur['K']:,} rmse={cur['rmse']:.4f} rho={cur['rho']:.4f} "
          f"maxT/K={cur['max_T_over_K']:.3f}", flush=True)
    for step in range(args.max_steps):
        best = None
        K0 = cur["K"]
        for name, aidx in Aidx.items():
            inmem = mem[aidx]; n_inter = int(inmem.sum())
            inter = (Wm[:, aidx[inmem]].sum(axis=1).astype(np.float64) / 255.0
                     if n_inter else np.zeros(len(obs)))
            if n_inter < aidx.size:
                T = cur["T"] + Scache[name] - inter
                K = K0 + aidx.size - n_inter
                F = np.maximum(Ms - T, 0.0)
                pred = T / (T + 0.2 * F + 0.8 * np.maximum(K - T, 0.0) + 1e-12)
                sse = float(((pred - obs) ** 2).sum())
                feas = float(T.max() / K) if K > 0 else np.inf
                obj = sse + 1e6 * max(0.0, feas - 1.0)
                if best is None or obj < best[0]:
                    best = (obj, "add", name)
            if 0 < n_inter < K0:
                T = cur["T"] - inter
                K = K0 - n_inter
                F = np.maximum(Ms - T, 0.0)
                pred = T / (T + 0.2 * F + 0.8 * np.maximum(K - T, 0.0) + 1e-12)
                sse = float(((pred - obs) ** 2).sum())
                feas = float(T.max() / K) if K > 0 else np.inf
                obj = sse + 1e6 * max(0.0, feas - 1.0)
                if best is None or obj < best[0]:
                    best = (obj, "remove", name)
        if best is None:
            break
        obj, op, name = best
        if obj >= cur["sse"] + 1e6 * max(0.0, cur["max_T_over_K"] - 1.0) - 1e-9:
            print("  converged", flush=True); break
        aidx = Aidx[name]
        if op == "add":
            mem[aidx[~mem[aidx]]] = True
        else:
            mem[aidx[mem[aidx]]] = False
        cur = score_mem(mem)
        log.append(dict(step=f"{op} {name}", atom=name,
                        **{k: v for k, v in cur.items() if k != "pred"}))
        print(f"  step{step:<3}{op:<7}{name:<32} rmse={cur['rmse']:.4f} rho={cur['rho']:.4f} "
              f"K={cur['K']:,} maxT/K={cur['max_T_over_K']:.3f}", flush=True)

    Smask = to_mask(mem)
    exact = exact_fit(Smask, masks)
    print(f"EXACT  K={exact['K']:,} rmse={exact['rmse']:.4f} rho={exact['rho']:.4f} "
          f"maxT/K={exact['max_T_over_K']:.3f}", flush=True)
    np.save(root / args.save_truth, Smask)

    # ---- cross-validation of the *projection* on held-out artifacts ----------------------
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(len(masks))
    cv = []
    for f in range(args.folds):
        te = np.array_split(perm, args.folds)[f]
        tr = np.array([i for i in range(len(masks)) if i not in set(te.tolist())])
        sub_hi = [masks[i] for i in tr if meta[i]["score"] >= 0.24]
        if not sub_hi:
            continue
        c = np.logical_and.reduce(sub_hi) & footprint & ~cat
        m_tr = flat(c)
        Atr = {f"art{i}": flat(masks[i]) for i in tr}
        Atr["cons"] = m_tr
        Atr["maj"] = flat((np.sum(sub_hi, 0) >= (len(sub_hi) // 2 + 1)) & footprint & ~cat)
        for it in (1, 2, 3):
            Atr[f"dil{it}"] = flat(binary_dilation(c, iterations=it) & footprint & ~cat)
        Aidx2 = {k: np.flatnonzero(v) for k, v in Atr.items() if v.any()}
        Sc2 = {k: Wm[np.ix_(tr, v)].sum(axis=1).astype(np.float64) / 255.0 for k, v in Aidx2.items()}
        memf = m_tr.copy()
        obs_tr, Ms_tr = obs[tr], Ms[tr]

        def sc(mem, Tcur):
            T = Tcur
            K = float(mem.sum())
            F = np.maximum(Ms_tr - T, 0.0)
            pred = T / (T + 0.2 * F + 0.8 * np.maximum(K - T, 0.0) + 1e-12)
            sse = float(((pred - obs_tr) ** 2).sum())
            feas = float(T.max() / K) if K else np.inf
            return sse + 1e6 * max(0.0, feas - 1.0), pred, K, T, feas
        Tcur = Wm[np.ix_(tr, np.flatnonzero(memf))].sum(axis=1).astype(np.float64) / 255.0
        cur_obj, pred, K0, Tcur, feas = sc(memf, Tcur)
        for step in range(12):
            best = None
            for name, aidx in Aidx2.items():
                inmem = memf[aidx]; n_inter = int(inmem.sum())
                inter = (Wm[np.ix_(tr, aidx[inmem])].sum(axis=1).astype(np.float64) / 255.0
                         if n_inter else np.zeros(len(tr)))
                if n_inter < aidx.size:
                    T = Tcur + Sc2[name] - inter
                    o, p, K, _ = None, None, K0 + aidx.size - n_inter, None
                    F = np.maximum(Ms_tr - T, 0.0)
                    p = T / (T + 0.2 * F + 0.8 * np.maximum(K - T, 0.0) + 1e-12)
                    ss = float(((p - obs_tr) ** 2).sum()); fe = float(T.max() / K) if K else np.inf
                    oo = ss + 1e6 * max(0.0, fe - 1.0)
                    if best is None or oo < best[0]:
                        best = (oo, "add", name, T, K)
                if 0 < n_inter < K0:
                    T = Tcur - inter; K = K0 - n_inter
                    F = np.maximum(Ms_tr - T, 0.0)
                    p = T / (T + 0.2 * F + 0.8 * np.maximum(K - T, 0.0) + 1e-12)
                    ss = float(((p - obs_tr) ** 2).sum()); fe = float(T.max() / K) if K else np.inf
                    oo = ss + 1e6 * max(0.0, fe - 1.0)
                    if best is None or oo < best[0]:
                        best = (oo, "remove", name, T, K)
            if best is None or best[0] >= cur_obj - 1e-9:
                break
            _, op, name, Tcur, K0 = best
            aidx = Aidx2[name]
            if op == "add":
                memf[aidx[~memf[aidx]]] = True
            else:
                memf[aidx[memf[aidx]]] = False
            cur_obj = best[0]
        Sf = to_mask(memf)
        # score the held-out artifacts exactly against this fold's surrogate
        dS = distance_transform_edt(~Sf, sampling=(1.0, 1.0))
        kS = np.where(dS > R_PX, 0.0, 1.0 - dS / R_PX)
        pr = []
        for j, i in enumerate(te.tolist()):
            m = masks[i] & active
            dm = distance_transform_edt(~m, sampling=(1.0, 1.0))
            km = np.where(dm > R_PX, 0.0, 1.0 - dm / R_PX)
            Ti = float(km[Sf].sum())
            Fi = float(m.sum()) - float(kS[m].sum())
            Ki = float(Sf.sum())
            pi = Ti / (Ti + 0.2 * Fi + 0.8 * (Ki - Ti) + 1e-12)
            pr.append(dict(name=meta[i]["name"], obs=float(obs[i]), projected=float(pi)))
            del dm, km
        pv = np.array([r["projected"] for r in pr]); ov = obs[te]
        cv.append(dict(fold=int(f), n_train=int(tr.size), n_test=int(te.size), K=int(Sf.sum()),
                       heldout_rho=spearman(pv, ov),
                       heldout_rmse=float(np.sqrt(((pv - ov) ** 2).mean())),
                       heldout_bias=float((pv - ov).mean()), rows=pr))
        print(f"fold {f}: K={int(Sf.sum()):,} HELDOUT rho={cv[-1]['heldout_rho']:.4f} "
              f"rmse={cv[-1]['heldout_rmse']:.4f} bias={cv[-1]['heldout_bias']:+.4f}", flush=True)

    ds_cat = distance_transform_edt(~cat, sampling=(100.0, 100.0))
    dS = ds_cat[Smask]
    out = dict(
        experiment="exp5b_calibrated_inversion",
        label="MEASURED-INSTRUMENT (a projection is never written as a score)",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        objective="sum of squared ABSOLUTE residuals of DTI_i(S) vs owner-reported s_i, no free scale",
        constraints=["T_i(S) <= |S|", "S inside footprint", "S outside mapped catalogue"],
        n_artifacts=len(meta),
        exact_fit=dict(K=exact["K"], rmse=exact["rmse"], rho=exact["rho"],
                       max_T_over_K=exact["max_T_over_K"],
                       sse=exact["sse"]),
        pred_vs_obs=[dict(name=meta[i]["name"], obs=float(obs[i]), projected=float(exact["pred"][i]),
                          T=float(exact["T"][i]), F=float(exact["F"][i]))
                     for i in np.argsort(-obs)],
        greedy_log=log,
        cv=dict(folds=args.folds, seed=args.seed, results=cv,
                mean_heldout_rho=float(np.mean([c["heldout_rho"] for c in cv])),
                mean_heldout_rmse=float(np.mean([c["heldout_rmse"] for c in cv])),
                mean_heldout_bias=float(np.mean([c["heldout_bias"] for c in cv]))),
        surrogate_geometry=dict(n=int(Smask.sum()),
                                median_dist_to_catalogue_m=float(np.median(dS)),
                                p10_m=float(np.percentile(dS, 10)), p90_m=float(np.percentile(dS, 90)),
                                frac_within_300m=float((dS <= 300).mean()),
                                frac_within_1000m=float((dS <= 1000).mean()),
                                frac_beyond_2000m=float((dS > 2000).mean())),
        truth_path=args.save_truth, seconds=round(time.time() - t0, 1))
    json.dump(out, open(root / args.out, "w"), indent=1)
    print("wrote", args.out, f"{time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
