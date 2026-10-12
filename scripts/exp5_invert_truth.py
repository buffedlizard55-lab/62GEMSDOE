#!/usr/bin/env python3
"""EXPERIMENT 5 (session 2026-10-12) - rebuild and *cross-validate* the inverted-truth instrument.

Why this exists
---------------
Every submission with a known portal score is one linear measurement of the hidden truth set G:

    s_i = T_i / (T_i + 0.2*F_i + 0.8*(|G| - T_i)),   T_i = sum_{g in G} max_{x in dots_i} p(x) k(d(x,g))

`datum62/scripts/invert.py` (previous session) inverted 56 such measurements and reported a
truth surrogate S* reproducing the owner-reported scores at Spearman +0.968.  That number was
reported **in-sample only**: the atom dictionary contained every scored artifact's own mask, so a
high in-sample rho is exactly what an overfit would also produce.  This script

  (1) rebuilds the surrogate from the 87 score-anchored registry rasters (fetched this session,
      sha256-verified against research/registry_index.json), and
  (2) CROSS-VALIDATES it: for each fold the atom dictionary contains only the training artifacts,
      so a held-out artifact's score is predicted by a surrogate that has never seen its mask.

Nothing here is a score.  Output is labelled MEASURED-INSTRUMENT with its CV rho.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt

R_PX = 3.0
KERNEL = np.maximum(1.0 - np.arange(0, 24) * (100.0 / 300.0) / 1.0, 0.0).astype(np.float32)


def kernel_at(dist_px: np.ndarray) -> np.ndarray:
    """k(d) = max(1 - d/R, 0) with R = 3 px, evaluated on an EDT in pixels."""
    return np.where(dist_px > R_PX, 0.0, np.maximum(1.0 - dist_px / R_PX, 0.0)).astype(np.float32)


def load_masks(reg_dir: pathlib.Path, rows: list[dict], footprint: np.ndarray):
    masks, kept = [], []
    for r in rows:
        name = f"{r['repo']}__{os.path.basename(r['path'])}"
        p = reg_dir / name
        if not p.exists():
            print("missing", name, file=sys.stderr)
            continue
        with rasterio.open(p) as ds:
            a = ds.read(1).astype(np.float32)
        if a.shape != footprint.shape:
            print("shape mismatch", name, a.shape, file=sys.stderr)
            continue
        m = (np.where(np.isfinite(a), a, 0.0) > 0) & footprint
        if m.sum() == 0:
            print("vacuous", name, file=sys.stderr)
            continue
        masks.append(m)
        kept.append(dict(name=name, repo=r["repo"], score=float(r["score"]),
                         path=r["path"], sha256=r.get("sha"),
                         M=int(m.sum()), base=r.get("base")))
    return masks, kept


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    ra -= ra.mean(); rb -= rb.mean()
    d = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / d) if d > 0 else float("nan")


def fit_set(Wm, Ms, obs, mem):
    """Given a boolean membership over candidate pixels, return the fit diagnostics."""
    T = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
    K = int(mem.sum())
    pred_shape = T / (0.2 * Ms + 0.8 * K)
    denom = float(pred_shape @ pred_shape)
    a = float((pred_shape @ obs) / denom) if denom > 0 else 0.0
    resid = obs - a * pred_shape
    ss = float((resid ** 2).sum()); tot = float(((obs - obs.mean()) ** 2).sum())
    return dict(scale=a, r2=1.0 - ss / tot if tot > 0 else float("nan"),
                rmse=float(np.sqrt(ss / obs.size)), rho=spearman(pred_shape, obs),
                K=K, T_sum=float(T.sum()), pred=(a * pred_shape))


def greedy(Wm, Ms, obs, atoms: dict, start: np.ndarray, max_steps: int = 20,
           verbose: bool = True):
    """Forward/backward greedy over atoms, maximising rank correlation of the implied score.

    Cost control: for every atom A the full column sum ``S_A = Wm[:, A].sum(1)`` is cached once.
    At each step only the *intersection* sum has to be recomputed, because

        add A:      T <- T_in + S_A - Wm[:, A & mem].sum(1),  K <- K + |A| - |A & mem|
        remove A:   T <- T_in - Wm[:, A & mem].sum(1),        K <- K - |A & mem|
    """
    mem = start.copy()
    cur = fit_set(Wm, Ms, obs, mem)
    log = [dict(step="start", atom="consensus", **{k: v for k, v in cur.items() if k != "pred"})]
    Aidx = {k: np.flatnonzero(v) for k, v in atoms.items() if v.any()}
    Sfull = {k: Wm[:, v].sum(axis=1).astype(np.float64) / 255.0 for k, v in Aidx.items()}
    for step in range(max_steps):
        best = None
        TinS = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
        K0 = int(mem.sum())
        for name, aidx in Aidx.items():
            inmem = mem[aidx]
            n_inter = int(inmem.sum())
            inter_sum = (Wm[:, aidx[inmem]].sum(axis=1).astype(np.float64) / 255.0
                         if n_inter else np.zeros(Wm.shape[0]))
            if n_inter < aidx.size:                      # ---- add A \ mem
                T = TinS + Sfull[name] - inter_sum
                K = K0 + int(aidx.size) - n_inter
                rho = spearman(T / (0.2 * Ms + 0.8 * K), obs)
                if best is None or rho > best[0]:
                    best = (rho, "add", name, int(aidx.size) - n_inter)
            if 0 < n_inter < K0:                         # ---- remove A & mem
                T = TinS - inter_sum
                K = K0 - n_inter
                if K > 0:
                    rho = spearman(T / (0.2 * Ms + 0.8 * K), obs)
                    if best is None or rho > best[0]:
                        best = (rho, "remove", name, n_inter)
        if best is None or best[0] <= cur["rho"] + 1e-9:
            if verbose:
                print("  converged", flush=True)
            break
        rho, op, name, n = best
        aidx = Aidx[name]
        if op == "add":
            mem[aidx[~mem[aidx]]] = True
        else:
            mem[aidx[mem[aidx]]] = False
        cur = fit_set(Wm, Ms, obs, mem)
        log.append(dict(step=f"{op} {name}", atom=name, n=int(n),
                        **{k: v for k, v in cur.items() if k != "pred"}))
        if verbose:
            print(f"  step{step:<3}{op:<7}{name:<34} rho={cur['rho']:.4f} "
                  f"r2={cur['r2']:.4f} K={cur['K']:,}", flush=True)
    return mem, cur, log


def build_weight_matrix(masks, idx, H, W):
    Wm = np.zeros((len(masks), idx.size), np.uint8)
    for i, m in enumerate(masks):
        dm = distance_transform_edt(~m, sampling=(1.0, 1.0))
        kb = kernel_at(dm)
        Wm[i] = np.rint(kb.ravel()[idx] * 255.0).astype(np.uint8)
        del dm, kb
        if i % 20 == 0:
            print(f"  weights {i}/{len(masks)}", flush=True)
    return Wm


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="/tmp/reg/tif")
    ap.add_argument("--index", default="research/registry_index.json")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--catalogue", default="data/labels.tif")
    ap.add_argument("--out", default="evidence/exp5_inverse_truth_cv.json")
    ap.add_argument("--save-truth", default="build/truth_est_S.npy")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261012)
    ap.add_argument("--max-steps", type=int, default=40)
    args = ap.parse_args()

    t0 = time.time()
    root = pathlib.Path(__file__).resolve().parents[1]
    with rasterio.open(root / args.sample) as ds:
        tmpl = ds.read(1)
        transform = ds.transform
        crs = ds.crs
    footprint = np.isfinite(tmpl)
    H, Wd = footprint.shape
    with rasterio.open(root / args.catalogue) as ds:
        cat = (ds.read(1) == 1) & footprint
    print(f"footprint {int(footprint.sum()):,} cells; catalogue {int(cat.sum()):,}", flush=True)

    rows = json.load(open(root / args.index))
    # de-duplicate identical (repo,basename) rows; keep the highest score per distinct file
    seen = {}
    for r in rows:
        key = (r["repo"], os.path.basename(r["path"]))
        if key not in seen or r["score"] > seen[key]["score"]:
            seen[key] = r
    rows = sorted(seen.values(), key=lambda r: -r["score"])
    masks, meta = load_masks(pathlib.Path(args.registry), rows, footprint)
    Ms = np.array([m["M"] for m in meta], float)
    obs = np.array([m["score"] for m in meta], float)
    print(f"loaded {len(masks)} artifacts, scores {obs.min():.4f}..{obs.max():.4f}", flush=True)

    # ---- candidate pixel set -------------------------------------------------------------
    hi = [mk for mk, mt in zip(masks, meta) if mt["score"] >= 0.24]
    print(f"artifacts scoring >= 0.24: {len(hi)}", flush=True)
    cons = np.logical_and.reduce(hi) & footprint
    maj = (np.sum(hi, 0) >= (len(hi) // 2 + 1)) & footprint
    union = np.logical_or.reduce(hi) & footprint
    cand = union.copy()
    for mk in masks:
        cand |= mk
    cand &= footprint
    idx = np.flatnonzero(cand.ravel())
    print(f"candidate pixels {idx.size:,}  consensus {int(cons.sum()):,}  majority {int(maj.sum()):,}"
          f"  union {int(union.sum()):,}", flush=True)

    flat = lambda A: A.ravel()[idx].copy()  # noqa: E731
    Wm = build_weight_matrix(masks, idx, H, Wd)
    np.save(str(root / "build" / "Wm.npy"), Wm)
    np.save(str(root / "build" / "cand_idx.npy"), idx)
    print(f"weight matrix {Wm.shape} ({Wm.nbytes/1e6:.1f} MB)  t={time.time()-t0:.0f}s", flush=True)

    def atom_dict(subset: list[int]) -> dict[str, np.ndarray]:
        sub_hi = [masks[i] for i in subset if meta[i]["score"] >= 0.24]
        out = {f"art{i}_{meta[i]['repo']}": flat(masks[i]) for i in subset}
        if sub_hi:
            c = np.logical_and.reduce(sub_hi) & footprint
            mj = (np.sum(sub_hi, 0) >= (len(sub_hi) // 2 + 1)) & footprint
            u = np.logical_or.reduce(sub_hi) & footprint
            out["consensus_hi"] = flat(c)
            out["majority_hi"] = flat(mj)
            out["union_hi"] = flat(u)
            for it in (1, 2, 3):
                out[f"cons_dil{it}"] = flat(binary_dilation(c, iterations=it) & footprint)
                out[f"maj_dil{it}"] = flat(binary_dilation(mj, iterations=it) & footprint)
        return out

    all_idx = list(range(len(masks)))
    atoms_full = atom_dict(all_idx)
    mem0 = flat(cons)
    if mem0.sum() == 0:
        mem0 = flat(maj)
    print(f"start set {int(mem0.sum()):,} px", flush=True)
    mem, cur, log = greedy(Wm, Ms, obs, atoms_full, mem0, max_steps=args.max_steps)
    print("FULL FIT", {k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in cur.items() if k != "pred"}, flush=True)

    Sfull = np.zeros((H, Wd), bool)
    Sfull.ravel()[idx[mem]] = True
    np.save(str(root / args.save_truth), Sfull)

    # ---- cross-validation: atoms restricted to training artifacts -------------------------
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(len(masks))
    cv = []
    for f in range(args.folds):
        te = np.array_split(perm, args.folds)[f]
        tr = np.array([i for i in all_idx if i not in set(te.tolist())])
        sub_hi = [masks[i] for i in tr if meta[i]["score"] >= 0.24]
        if not sub_hi:
            continue
        c = np.logical_and.reduce(sub_hi) & footprint
        start = flat(c)
        if start.sum() == 0:
            start = flat((np.sum(sub_hi, 0) >= (len(sub_hi) // 2 + 1)) & footprint)
        atoms_tr = atom_dict(tr.tolist())
        Wtr, Mtr, otr = Wm[tr], Ms[tr], obs[tr]
        memf, curf, logf = greedy(Wtr, Mtr, otr, atoms_tr, start, max_steps=args.max_steps,
                                  verbose=False)
        # predict the held-out artifacts with the fold's surrogate
        T_te = Wm[np.ix_(te, memf)].sum(axis=1).astype(np.float64) / 255.0
        p_te = T_te / (0.2 * Ms[te] + 0.8 * int(memf.sum()))
        rho_te = spearman(p_te, obs[te])
        a = curf["scale"]
        cv.append(dict(fold=int(f), n_train=int(tr.size), n_test=int(te.size),
                       train_rho=curf["rho"], train_r2=curf["r2"], K=curf["K"],
                       scale=a, test_rho=rho_te,
                       test_rmse=float(np.sqrt(((obs[te] - a * p_te) ** 2).mean())),
                       test_rows=[dict(name=meta[i]["name"], obs=float(obs[i]),
                                       pred=float(a * p_te[j]))
                                  for j, i in enumerate(te.tolist())],
                       steps=len(logf) - 1))
        print(f"fold {f}: K={curf['K']:,} train_rho={curf['rho']:.4f} "
              f"HELDOUT_rho={rho_te:.4f} rmse={cv[-1]['test_rmse']:.4f}", flush=True)

    # ---- what is S*, geometrically? ------------------------------------------------------
    ds_cat = distance_transform_edt(~cat, sampling=(100.0, 100.0))
    dS = ds_cat[Sfull]
    on_cat = int((dS == 0).sum())
    dist_stats = dict(n=int(Sfull.sum()), on_catalogue_px=on_cat,
                      median_m=float(np.median(dS)), p10_m=float(np.percentile(dS, 10)),
                      p90_m=float(np.percentile(dS, 90)),
                      frac_within_300m=float((dS <= 300).mean()),
                      frac_within_1000m=float((dS <= 1000).mean()),
                      frac_beyond_2000m=float((dS > 2000).mean()))
    print("S* vs catalogue:", dist_stats, flush=True)

    out = dict(
        experiment="exp5_invert_truth",
        label="MEASURED-INSTRUMENT (not a score, not a projection)",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        n_artifacts=len(masks), n_artifacts_rows_in_index=len(rows),
        score_range=[float(obs.min()), float(obs.max())],
        candidate_pixels=int(idx.size),
        full_fit={k: (v.tolist() if isinstance(v, np.ndarray) else v)
                  for k, v in cur.items() if k != "pred"},
        full_fit_pred_vs_obs=[dict(name=meta[i]["name"], obs=float(obs[i]), pred=float(cur["pred"][i]))
                              for i in np.argsort(-obs)],
        greedy_log=log,
        cv=dict(folds=args.folds, seed=args.seed, results=cv,
                mean_heldout_rho=float(np.mean([c["test_rho"] for c in cv])),
                min_heldout_rho=float(np.min([c["test_rho"] for c in cv]))),
        surrogate_geometry=dist_stats,
        truth_path=args.save_truth,
        seconds=round(time.time() - t0, 1),
    )
    pathlib.Path(root / args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(root / args.out, "w"), indent=1)
    print("wrote", args.out, f"({time.time()-t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
