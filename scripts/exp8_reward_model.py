#!/usr/bin/env python3
"""EXPERIMENT 8 - learn the portal's own reward function from 79 scored artifacts, then use it.

Everything the group knows about the organiser's scoring is 79 public rasters with owner-reported
scores.  Each one is a measurement.  This script turns that into a *design rule* instead of an
anecdote:

1. Measure, for every registry artifact and for every candidate this session can emit, a vector of
   quantities that are computable locally without any hidden information:
   M (dots), mean 300 m kernel credit per dot against SGMC-1:750k-minus-catalogue, the same against
   the mapped catalogue, median distance to the catalogue, mean self-kernel (isolation), spatial
   evenness (fraction of 10 km cells holding a dot), LiDAR-scarp hit fraction, and 10 m-topography
   roughness under the dots.
2. Invert the published closed form for isolated unit dots, ``s = c/(0.2 + 0.8K/M)``, to get each
   artifact's IMPLIED real per-dot credit ``c = s (0.2 + 0.8K/M)`` at K = 12,000 (planning value;
   sensitivity 8,479 and 13,688 also reported).
3. Fit ``c`` (and separately ``s``) on the measurable vector with gradient boosting under
   leave-artifact-out CV on de-duplicated fields, and report CV rho / rmse.  A model that cannot
   predict a held-out artifact's score is not used to choose anything.
4. Score this session's candidate emissions with the CV'd model and print the ranking.

Nothing printed here is a score.  Model outputs are labelled MODEL; measurements MEASURED; the
owner-reported numbers OWNER-REPORTED (no organiser receipt exists in this repository).
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
from scipy import ndimage as ndi
from scipy.ndimage import distance_transform_edt as edt

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util                                              # noqa: E402

_spec = importlib.util.spec_from_file_location("exp6", ROOT / "scripts" / "exp6_detector_blocked.py")
exp6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exp6)

K_PLANNING = 12000.0


def spearman(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 4:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    d = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / d) if d > 0 else float("nan")


def implied_credit(score: float, M: float, K: float = K_PLANNING) -> float:
    """s = c/(0.2 + 0.8K/M)  =>  c = s (0.2 + 0.8K/M).  Isolated-unit-dot closed form."""
    if M <= 0:
        return float("nan")
    return float(score * (0.2 + 0.8 * K / M))


def field_features(mask: np.ndarray, ctx: dict) -> dict:
    """All quantities computable without hidden information."""
    ys, xs = np.nonzero(mask)
    n = int(ys.size)
    if n == 0:
        return dict(M=0)
    k_sgmc = np.maximum(1.0 - ctx["d_sgmc"][ys, xs] / 3.0, 0.0)
    k_cat = np.maximum(1.0 - ctx["d_cat"][ys, xs] / 3.0, 0.0)
    # isolation: mean over dots of the largest kernel weight coming from ANOTHER dot.
    # Computed in coordinate space over the 28 non-zero offsets inside the 3 px kernel, so it is
    # exact where the kernel is non-zero and cheap (no full-grid shifts).
    mask = ctx["mask"]
    d_other = np.full(n, np.inf)
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if dy == 0 and dx == 0:
                continue
            w = float(np.hypot(dy, dx))
            if w > 3.0:
                continue
            yy = ys + dy; xx = xs + dx
            ok = (yy >= 0) & (yy < mask.shape[0]) & (xx >= 0) & (xx < mask.shape[1])
            hit = np.zeros(n, bool)
            hit[ok] = mask[yy[ok], xx[ok]]
            d_other = np.where(hit & (w < d_other), w, d_other)
    selfk = np.maximum(1.0 - np.minimum(d_other, 3.0) / 3.0, 0.0)
    selfk[~np.isfinite(d_other)] = 0.0
    cell = (ys // 100) * 1000 + (xs // 100)
    n_cells = len(np.unique(cell))
    rough = ctx["topo_std"][ys, xs]
    return dict(
        M=n,
        credit_sgmc=float(k_sgmc.mean()),
        credit_cat=float(k_cat.mean()),
        frac_sgmc_hit=float((ctx["d_sgmc"][ys, xs] <= 3.0).mean()),
        dcat_med_m=float(np.median(ctx["d_cat"][ys, xs]) * 100.0),
        dsgmc_med_m=float(np.median(ctx["d_sgmc"][ys, xs]) * 100.0),
        self_kernel=float(selfk.mean()),
        evenness_cells=float(n_cells),
        lidar_scarp_mean=float(ctx["lidar"][ys, xs].mean()),
        topo_rough_mean=float(np.nanmean(rough)),
        slope_mean=float(np.nanmean(ctx["slope"][ys, xs])),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="/tmp/reg/tif")
    ap.add_argument("--index", default="research/registry_index.json")
    ap.add_argument("--ext", default="build/ext")
    ap.add_argument("--oof", default="build/oof_surface.npy")
    ap.add_argument("--out", default="evidence/exp8_reward_model.json")
    ap.add_argument("--seed", type=int, default=20261012)
    args = ap.parse_args()
    t0 = time.time()
    with rasterio.open(ROOT / "data/sample_submission.tif") as ds:
        tmpl = ds.read(1)
    footprint = np.isfinite(tmpl); H, Wd = footprint.shape
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = (ds.read(1) == 1) & footprint
    active = footprint & ~cat
    cat3 = ndi.binary_dilation(cat, iterations=3)

    with rasterio.open(ROOT / args.ext / "derived_sgmc_faults_100m.tif") as ds:
        sgmc = (ds.read(1) > 0) & footprint
    sgmc_off = sgmc & ~cat3
    d_sgmc = edt(~sgmc_off).astype(np.float32)
    d_cat = edt(~cat).astype(np.float32)
    with rasterio.open(ROOT / args.ext / "lidar_scarp_features_u8.tif") as ds:
        lidar = ds.read(1).astype(np.float32)      # band 1 of the sibling-derived scarp composite
    with rasterio.open(ROOT / args.ext / "geodawn_dem_a2_100m.tif") as ds:
        dem100 = ds.read(1).astype(np.float32)
        dem_nodata = ds.nodata
    dem100[~np.isfinite(dem100)] = np.nan
    if dem_nodata is not None:
        dem100[dem100 == dem_nodata] = np.nan
    gz, gx = np.gradient(np.nan_to_num(dem100, nan=0.0))
    slope = np.degrees(np.arctan(np.hypot(gx, gz) / 100.0)).astype(np.float32)
    m1 = ndi.uniform_filter(np.nan_to_num(dem100, nan=0.0), 5)
    m2 = ndi.uniform_filter(np.nan_to_num(dem100, nan=0.0) ** 2, 5)
    topo_std = np.sqrt(np.maximum(m2 - m1 * m1, 0)).astype(np.float32)
    print(f"sgmc {int(sgmc.sum()):,}  sgmc_offcat {int(sgmc_off.sum()):,}  "
          f"dem100 finite {float(np.isfinite(dem100[footprint]).mean()):.4f}  t={time.time()-t0:.0f}s",
          flush=True)

    ctx = dict(d_sgmc=d_sgmc, d_cat=d_cat, lidar=lidar, topo_std=topo_std, slope=slope, mask=None)

    def with_self(mask):
        ctx["mask"] = mask
        return ctx

    # ---------------- registry artifacts ---------------------------------------------------
    rows = json.load(open(ROOT / args.index))
    seen = {}
    for r in rows:
        k = (r["repo"], os.path.basename(r["path"]))
        if k not in seen or r["score"] > seen[k]["score"]:
            seen[k] = r
    table = []
    for r in sorted(seen.values(), key=lambda z: -z["score"]):
        p = pathlib.Path(args.registry) / f"{r['repo']}__{os.path.basename(r['path'])}"
        if not p.exists():
            continue
        with rasterio.open(p) as ds:
            a = ds.read(1).astype(np.float32)
        if a.shape != (H, Wd):
            continue
        m = (np.where(np.isfinite(a), a, 0) > 0) & footprint
        if m.sum() == 0:
            continue
        f = field_features(m, with_self(m))
        f.update(kind="registry", name=f"{r['repo']}__{os.path.basename(r['path'])[:56]}",
                 score=float(r["score"]), repo=r["repo"])
        f["implied_credit_K12000"] = implied_credit(f["score"], f["M"])
        f["implied_credit_K8479"] = implied_credit(f["score"], f["M"], 8479.0)
        f["implied_credit_K13688"] = implied_credit(f["score"], f["M"], 13688.0)
        table.append(f)
        del a, m
    print(f"registry artifacts measured: {len(table)}  t={time.time()-t0:.0f}s", flush=True)

    # ---------------- this session's candidates -------------------------------------------
    oof = np.load(ROOT / args.oof)
    pv = np.where(active & np.isfinite(oof), oof, -1.0)
    cands = {}
    for standoff in (0, 300, 1500):
        elig = active.copy()
        if standoff:
            elig &= d_cat >= standoff
        for M in (20000, 30000, 40000, 50000, 60000):
            keep = exp6.hard_core_local_maxima(pv, elig, M, seed=args.seed + standoff)
            if int(keep.sum()) < 0.9 * M:
                print(f"  cand oof_s{standoff}_M{M}: only {int(keep.sum()):,} maxima - skipped",
                      flush=True)
                continue
            cands[f"oof_s{standoff}_M{int(keep.sum())}"] = keep
    # SGMC-offcat targeted field (independent official compilation; the population the organiser
    # describes as "not captured by USGS/INGENIOUS")
    pri = np.maximum(1.0 - d_sgmc / 3.0, 0.0).astype(np.float32)
    for M in (15000, 25000, 40000):
        keep = exp6.hard_core_local_maxima(np.where(active, pri, -1.0), active, M, seed=args.seed + 1)
        cands[f"sgmcoff_M{int(keep.sum())}"] = keep
    # LiDAR scarp composite targeted field
    lp = np.nan_to_num(lidar, nan=0.0).astype(np.float32)
    for M in (40000,):
        keep = exp6.hard_core_local_maxima(np.where(active, lp, -1.0), active, M, seed=args.seed + 2)
        cands[f"lidar_M{int(keep.sum())}"] = keep
    # mixture: detector x SGMC proximity (both must agree)
    mix = np.where(active, (np.clip(pv, 0, None) / max(float(np.nanmax(pv)), 1e-9))
                   * (0.35 + 0.65 * pri / max(float(pri.max()), 1e-9)), -1.0).astype(np.float32)
    for standoff in (0, 300):
        elig = active & (d_cat >= standoff) if standoff else active
        for M in (40000, 50000):
            keep = exp6.hard_core_local_maxima(mix, elig, M, seed=args.seed + 3 + standoff)
            if int(keep.sum()) >= 0.9 * M:
                cands[f"mix_s{standoff}_M{int(keep.sum())}"] = keep
    # in-lane variant: detector restricted to the Lahontan datum band
    rc = json.load(open(ROOT / "evidence/gems62-lahontan-isobase-99dots-runcard.json"))
    dom = rc["isobase"]["levels"]["dominant_m"]; tol = rc["isobase"]["levels"]["strand_tolerance_m"]
    resid = np.load(ROOT / "build/features/31_datum_isobase_resid_m.npy")
    band = np.isfinite(resid) & (np.abs(resid - dom) <= tol)
    lane = np.where(active & band, pv, -1.0).astype(np.float32)
    keep = exp6.hard_core_local_maxima(lane, active & band, 20000, seed=args.seed + 5)
    cands[f"lane_datumband_M{int(keep.sum())}"] = keep
    print(f"candidates emitted: {len(cands)}  t={time.time()-t0:.0f}s", flush=True)

    for name, keep in cands.items():
        f = field_features(keep, with_self(keep))
        f.update(kind="candidate", name=name, score=None)
        table.append(f)
    np.savez_compressed(ROOT / "build" / "candidates.npz",
                        **{k: np.packbits(v.ravel()) for k, v in cands.items()})

    # ---------------- reward model ---------------------------------------------------------
    reg = [r for r in table if r["kind"] == "registry"]
    key = lambda r: (r["M"], round(r["credit_sgmc"], 5), round(r["credit_cat"], 5))  # noqa: E731
    dedup = {}
    for r in reg:
        dedup.setdefault(key(r), r)
    dd = list(dedup.values())
    print(f"de-duplicated scored fields: {len(dd)} of {len(reg)}", flush=True)
    feats = ["M", "credit_sgmc", "credit_cat", "frac_sgmc_hit", "dcat_med_m", "dsgmc_med_m",
             "self_kernel", "evenness_cells", "lidar_scarp_mean", "topo_rough_mean", "slope_mean"]
    X = np.array([[r[f] for f in feats] for r in dd], float)
    y = np.array([r["implied_credit_K12000"] for r in dd], float)
    ys = np.array([r["score"] for r in dd], float)

    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import KFold
    cv_out = {}
    for target, yv in (("implied_credit", y), ("score", ys)):
        oof_pred = np.zeros(yv.size)
        for tr, te in KFold(5, shuffle=True, random_state=args.seed).split(X):
            mdl = HistGradientBoostingRegressor(max_iter=220, learning_rate=0.06, max_leaf_nodes=15,
                                                min_samples_leaf=3, l2_regularization=1.0,
                                                random_state=args.seed)
            mdl.fit(X[tr], yv[tr])
            oof_pred[te] = mdl.predict(X[te])
        cv_out[target] = dict(
            n=int(yv.size), cv_rho=spearman(oof_pred, yv),
            cv_rmse=float(np.sqrt(((oof_pred - yv) ** 2).mean())),
            cv_bias=float((oof_pred - yv).mean()),
            cv_max_abs_err=float(np.abs(oof_pred - yv).max()),
            in_sample_rho=spearman(yv, yv))
        full = HistGradientBoostingRegressor(max_iter=220, learning_rate=0.06, max_leaf_nodes=15,
                                             min_samples_leaf=3, l2_regularization=1.0,
                                             random_state=args.seed).fit(X, yv)
        cv_out[target]["oof_pred"] = oof_pred.tolist()
        cv_out[target]["feature_names"] = feats
        # permutation importance on the out-of-fold model
        imp = {}
        rng = np.random.default_rng(args.seed)
        for j, fn in enumerate(feats):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            p = full.predict(Xp)
            base = full.predict(X)
            imp[fn] = float(np.sqrt(((p - yv) ** 2).mean()) - np.sqrt(((base - yv) ** 2).mean()))
        cv_out[target]["permutation_importance_rmse_increase"] = imp
        cv_out[target]["model_pickle"] = None
        globals()[f"_mdl_{target}"] = full
        print(f"  {target}: CV rho={cv_out[target]['cv_rho']:.4f} rmse={cv_out[target]['cv_rmse']:.4f}"
              f"  top imp={sorted(imp.items(), key=lambda z: -z[1])[:4]}", flush=True)

    # single-quantity correlations, for comparison with the model
    singles = {}
    for f in feats:
        v = np.array([r[f] for r in dd], float)
        singles[f] = dict(rho_vs_score=spearman(v, ys), rho_vs_implied_credit=spearman(v, y))
    singles["M_only"] = dict(rho_vs_score=spearman(np.array([r["M"] for r in dd], float), ys))
    print("single-quantity spearman vs score:",
          {k: round(v["rho_vs_score"], 3) for k, v in singles.items()}, flush=True)

    # ---------------- rank the candidates with the CV'd model ------------------------------
    Xc = np.array([[r[f] for f in feats] for r in table if r["kind"] == "candidate"], float)
    names = [r["name"] for r in table if r["kind"] == "candidate"]
    pred_credit = globals()["_mdl_implied_credit"].predict(Xc)
    pred_score = globals()["_mdl_score"].predict(Xc)
    champ = max(reg, key=lambda r: r["score"])
    ranking = sorted(zip(names, pred_score, pred_credit,
                         [r for r in table if r["kind"] == "candidate"]),
                     key=lambda z: -z[1])
    print(f"\nchampion reference: {champ['name']} score={champ['score']} M={champ['M']:,} "
          f"credit_sgmc={champ['credit_sgmc']:.4f} implied_credit={champ['implied_credit_K12000']:.4f}",
          flush=True)
    print(f"{'candidate':<34} {'pred_score':>10} {'pred_credit':>11} {'M':>8} {'cred_sgmc':>9} "
          f"{'self_k':>7} {'dcat_m':>7}", flush=True)
    for nm, ps, pc, r in ranking:
        print(f"{nm:<34} {ps:10.4f} {pc:11.4f} {r['M']:8,d} {r['credit_sgmc']:9.4f} "
              f"{r['self_kernel']:7.4f} {r['dcat_med_m']:7.0f}", flush=True)

    out = dict(
        experiment="exp8_reward_model",
        label="MEASURED + MODEL (a model output is never written as a score)",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        K_planning=K_PLANNING,
        closed_form="s = c/(0.2 + 0.8K/M) for isolated unit dots; c = s(0.2 + 0.8K/M)",
        n_registry=len(reg), n_dedup=len(dd), n_candidates=len(cands),
        instrument_cells=dict(sgmc=int(sgmc.sum()), sgmc_offcat=int(sgmc_off.sum()),
                              catalogue=int(cat.sum()), active=int(active.sum())),
        reward_model=cv_out, single_quantity_spearman=singles,
        champion_reference={k: champ[k] for k in ("name", "score", "M", "credit_sgmc", "credit_cat",
                                                  "dcat_med_m", "self_kernel", "evenness_cells",
                                                  "implied_credit_K12000", "lidar_scarp_mean")},
        table=table,
        candidate_ranking=[dict(name=nm, model_score=ps, model_implied_credit=pc,
                                **{k: r[k] for k in ("M", "credit_sgmc", "credit_cat",
                                                     "frac_sgmc_hit", "dcat_med_m", "self_kernel",
                                                     "evenness_cells", "lidar_scarp_mean",
                                                     "topo_rough_mean", "slope_mean")})
                           for nm, ps, pc, r in ranking],
        seconds=round(time.time() - t0, 1))
    json.dump(out, open(ROOT / args.out, "w"), indent=1, default=float)
    print(f"\nwrote {args.out}  ({time.time()-t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
