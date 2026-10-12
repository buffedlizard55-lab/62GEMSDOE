#!/usr/bin/env python3
"""EXPERIMENT 6 - primary-data detector for the calibrated consensus surrogate, blocked, out-of-fold.

Inputs (all byte-verified this session)
--------------------------------------
* `/tmp/stack/training_features.tif` - the organiser's own 19-band numerical feature stack,
  sha256 `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5`, 418,912,844 B,
  reassembled from the five public bridge parts of `buffedlizard55-lab/GEMSDOE` and matched against
  `data/bridge/manifest.json` (which pins the official Dropbox mirror on the competition data tab).
* `data/sample_submission.tif` (sha256 `2176d08e...`) -> the scored footprint.
* `data/labels.tif` == the bridge's `existing_faults.tif` (sha256 `7ba308cc...`) -> the mapped
  USGS/INGENIOUS catalogue, which the organiser excludes from evaluation (forum thread 11516).
* `build/vote_surface_cand.npy` - the score-weighted vote V from `exp5c_vote_inversion.py`, whose
  nested quantiles give three calibrated truth surrogates (K = 2,659 / 5,318 / 13,294).
* `evidence/dem/lahontan_dem_utm11.tif` - USGS 3DEP 25 m DEM (partial footprint coverage), used for
  this lane's own datum features: the fitted Lahontan isobase of
  `evidence/gems62-lahontan-isobase-99dots-runcard.json` (coefficients read, not refitted).

Method
------
Six spatial blocks (3 x 2).  For each fold the model sees only the other five blocks; predictions are
stitched into one out-of-fold (OOF) surface, so every pixel is scored by a model that never saw its
block.  Per-feature single AUC is printed as the leakage canary required by the brief (>0.90 =>
leakage until proven otherwise).  The OOF surface is then turned into hard-core emissions of several
masses and each is scored with the EXACT published index against all three surrogates, next to the
same numbers for every registry artifact - including the 0.2778 champion - so the comparison is
apples to apples on one instrument.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi

R_PX = 3.0
PIX_M = 100.0


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    d = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / d) if d > 0 else float("nan")


def kernel_field(mask: np.ndarray) -> np.ndarray:
    d = ndi.distance_transform_edt(~mask, sampling=(1.0, 1.0))
    k = np.where(d > R_PX, 0.0, 1.0 - d / R_PX).astype(np.float32)
    return k


def dti_binary_fast(field: np.ndarray, S_kernels: dict, active: np.ndarray) -> dict:
    """Exact published index for a BINARY field against several pre-computed truth kernel fields.

    For a binary dot field A (values 0/1) restricted to `active`:
        T = sum_{g in S} max_{x in A} k(d(x,g)) = sum_{g in S} kA[g]      (kA = kernel field of A)
        F = sum_{x in A} (1 - max_{g in S} k(d(x,g))) = |A| - sum_{x in A} kS[x]
        DTI = T / (T + 0.2 F + 0.8 (|S| - T))
    kS is pre-computed once per surrogate; kA needs one EDT per field.  The identity against the
    shift-based transcription in `src/gems62/metric.py` is asserted in `tests/test_exp6_dti.py`.
    """
    A = (np.where(active, np.nan_to_num(field, nan=0.0), 0.0) > 0)
    M = float(A.sum())
    out = dict(M=M)
    if M == 0:
        for name, (kS, S, K) in S_kernels.items():
            out[name] = dict(T=0.0, F=0.0, K=K, dti=0.0)
        return out
    kA = kernel_field(A)
    for name, (kS, S, K) in S_kernels.items():
        T = float(kA[S].sum())
        F = M - float(kS[A].sum())
        out[name] = dict(T=T, F=F, K=K, dti=T / (T + 0.2 * F + 0.8 * (K - T) + 1e-12))
    return out


def hard_core_local_maxima(score: np.ndarray, elig: np.ndarray, n_want: int,
                           eps_frac: float = 1e-4, seed: int = 20261012) -> np.ndarray:
    """Vectorised hard-core thinning: keep only strict local maxima of the (tie-jittered) score in a
    7x7 window, then take the `n_want` highest.  Two strict local maxima of a 7x7 window are at
    Chebyshev distance >= 4 px, i.e. >= 400 m apart, so no two emitted dots share a 300 m kernel."""
    rng = np.random.default_rng(seed)
    lo, hi = np.nanpercentile(score[elig], [1, 99]) if elig.any() else (0.0, 1.0)
    eps = max(float(hi - lo), 1e-12) * eps_frac
    jit = rng.random(score.shape, dtype=np.float32)
    s = np.where(elig, score + eps * jit, -np.inf).astype(np.float32)
    loc = (s == ndi.maximum_filter(s, size=7, mode="nearest")) & elig
    n_loc = int(loc.sum())
    if n_loc <= n_want:
        return loc
    flat = np.flatnonzero(loc.ravel())
    vals = s.ravel()[flat]
    take = np.argpartition(-vals, n_want)[:n_want]
    keep = np.zeros(score.shape, bool)
    keep.ravel()[flat[take]] = True
    return keep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", default="/tmp/stack/training_features.tif")
    ap.add_argument("--stack-sha", default="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--catalogue", default="data/labels.tif")
    ap.add_argument("--vote", default="build/vote_surface_cand.npy")
    ap.add_argument("--cand", default="build/cand_idx.npy")
    ap.add_argument("--dem", default="evidence/dem/lahontan_dem_utm11.tif")
    ap.add_argument("--runcard", default="evidence/gems62-lahontan-isobase-99dots-runcard.json")
    ap.add_argument("--registry", default="/tmp/reg/tif")
    ap.add_argument("--index", default="research/registry_index.json")
    ap.add_argument("--featdir", default="build/features")
    ap.add_argument("--oof", default="build/oof_surface.npy")
    ap.add_argument("--out", default="evidence/exp6_detector_blocked.json")
    ap.add_argument("--n-neg", type=int, default=60000)
    ap.add_argument("--max-iter", type=int, default=260)
    ap.add_argument("--seed", type=int, default=20261012)
    ap.add_argument("--masses", default="10000,20000,30000,40000,50000,60000,80000,100000,120000")
    args = ap.parse_args()
    t0 = time.time()
    root = pathlib.Path(__file__).resolve().parents[1]
    import hashlib
    sha = hashlib.sha256()
    with open(args.stack, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            sha.update(chunk)
    stack_sha = sha.hexdigest()
    print(f"stack sha256 {stack_sha}  match={stack_sha == args.stack_sha}", flush=True)
    if stack_sha != args.stack_sha:
        raise SystemExit("feature stack hash does not match the manifest pin")

    with rasterio.open(root / args.sample) as ds:
        tmpl = ds.read(1)
    footprint = np.isfinite(tmpl)
    H, Wd = footprint.shape
    with rasterio.open(root / args.catalogue) as ds:
        cat = (ds.read(1) == 1) & footprint
    active = footprint & ~cat
    print(f"footprint {int(footprint.sum()):,}  catalogue {int(cat.sum()):,}  "
          f"active {int(active.sum()):,}", flush=True)

    # ---- surrogates from the exp5c vote ---------------------------------------------------
    idx = np.load(root / args.cand)
    V = np.load(root / args.vote).astype(np.float64)
    adm = active.ravel()[idx]
    pos = V[adm & (V > 0)]
    sur = {}
    for name, q in (("S_core", 0.999), ("S_mid", 0.998), ("S_wide", 0.995)):
        thr = float(np.quantile(pos, q))
        mem = (V >= thr) & adm
        S = np.zeros((H, Wd), bool)
        S.ravel()[idx[mem]] = True
        sur[name] = dict(q=q, thresh=thr, K=int(S.sum()), mask=S)
        print(f"  surrogate {name}: q={q} K={int(S.sum()):,}", flush=True)

    # ---- feature construction -------------------------------------------------------------
    fdir = root / args.featdir
    fdir.mkdir(parents=True, exist_ok=True)
    names: list[str] = []

    def put(name: str, arr: np.ndarray):
        names.append(name)
        np.save(fdir / f"{len(names)-1:02d}_{name}.npy", arr.astype(np.float32))
        print(f"  feat {len(names)-1:02d} {name:<26} finite={float(np.isfinite(arr[footprint]).mean()):.4f}"
              f"  t={time.time()-t0:.0f}s", flush=True)

    bands = {}
    with rasterio.open(args.stack) as ds:
        for i in range(1, ds.count + 1):
            bn = ds.tags(i)["band_name"]
            a = ds.read(i).astype(np.float32)
            a[~np.isfinite(a) | (a < -1e37)] = np.nan
            a[~footprint] = np.nan
            bands[bn] = a
            put(bn, a)

    def grad(bn):
        z = bands[bn]
        gz, gx = np.gradient(np.nan_to_num(z, nan=0.0))
        m = np.isfinite(z)
        gx[~m] = np.nan; gz[~m] = np.nan
        return gx, gz

    def coherence(bn, size=5):
        gx, gy = grad(bn)
        gx = np.nan_to_num(gx, nan=0.0); gy = np.nan_to_num(gy, nan=0.0)
        Jxx = ndi.uniform_filter(gx * gx, size=size)
        Jyy = ndi.uniform_filter(gy * gy, size=size)
        Jxy = ndi.uniform_filter(gx * gy, size=size)
        num = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2)
        return (num / (Jxx + Jyy + 1e-9)).astype(np.float32)

    put("coh_det_elev", coherence("det_elev"))
    put("coh_tmi_hg", coherence("tmi_hg"))
    put("coh_iso_grav_hg", coherence("iso_grav_anom_hg"))

    gx, gy = grad("det_elev")
    mag = np.hypot(np.nan_to_num(gx, nan=0.0), np.nan_to_num(gy, nan=0.0))
    put("detelev_gradmag", mag)
    put("detelev_gradmag_max5", ndi.maximum_filter(np.nan_to_num(mag, nan=0.0), size=5))
    z = np.nan_to_num(bands["det_elev"], nan=0.0)
    m1 = ndi.uniform_filter(z, size=5); m2 = ndi.uniform_filter(z * z, size=5)
    put("detelev_std5", np.sqrt(np.maximum(m2 - m1 * m1, 0.0)))
    put("detelev_range3", ndi.maximum_filter(z, 3) - ndi.minimum_filter(z, 3))
    put("tc_max5", ndi.maximum_filter(np.nan_to_num(bands["tc"], nan=0.0), size=5))
    put("isogravhg_absmax5",
        ndi.maximum_filter(np.abs(np.nan_to_num(bands["iso_grav_anom_hg"], nan=0.0)), size=5))
    put("depthbase_std7",
        np.sqrt(np.maximum(ndi.uniform_filter(np.nan_to_num(bands["depth_to_base_surf"], nan=0.0) ** 2, 7)
                           - ndi.uniform_filter(np.nan_to_num(bands["depth_to_base_surf"], nan=0.0), 7) ** 2, 0)))

    # catalogue geometry
    dcat = ndi.distance_transform_edt(~cat, sampling=(PIX_M, PIX_M)).astype(np.float32)
    put("dist_to_catalogue_m", dcat)
    nb = ndi.convolve(cat.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - cat.astype(np.uint8)
    tips = cat & (nb <= 2)
    if tips.sum() < 10:
        tips = cat & (nb <= 3)
    dtip = ndi.distance_transform_edt(~tips, sampling=(PIX_M, PIX_M)).astype(np.float32)
    put("dist_to_catalogue_tip_m", dtip)
    print(f"  catalogue tips {int(tips.sum()):,}", flush=True)

    # ---- this lane's datum features (isobase coefficients READ from the committed run card) --
    rc = json.load(open(root / args.runcard))
    iso = rc["isobase"]["global"]
    x0, y0, terms, coef = iso["x0"], iso["y0"], iso["terms"], iso["coef"]
    dom = rc["isobase"]["levels"]["dominant_m"]
    tol = rc["isobase"]["levels"]["strand_tolerance_m"]
    with rasterio.open(root / args.dem) as ds:
        dem = ds.read(1).astype(np.float32)
        dtr = ds.transform
        dnod = ds.nodata
    dem[dem <= -32000] = np.nan
    med = float(np.nanmedian(dem))
    scale = 0.1 if med > 5000 else 1.0        # the 3DEP int16 product is decimetres
    dem *= scale
    print(f"  DEM median {med:.1f} -> scale {scale}; coverage of footprint: ", end="", flush=True)
    # resample 25 m -> 100 m by block mean, aligned on the competition transform
    with rasterio.open(root / args.sample) as ds:
        strans = ds.transform
    dem100 = np.full((H, Wd), np.nan, np.float32)
    col0 = int(round((dtr.c - strans.c) / 100.0))
    row0 = int(round((strans.f - dtr.f) / 100.0))
    bs = 4
    hh, ww = dem.shape[0] // bs, dem.shape[1] // bs
    blk = np.nanmean(np.nan_to_num(dem[:hh * bs, :ww * bs], nan=0.0).reshape(hh, bs, ww, bs), axis=(1, 3))
    cnt = np.isfinite(dem[:hh * bs, :ww * bs]).reshape(hh, bs, ww, bs).mean(axis=(1, 3))
    blk[cnt < 0.5] = np.nan
    r0, r1 = max(0, row0), min(H, row0 + hh)
    c0, c1 = max(0, col0), min(Wd, col0 + ww)
    if r1 > r0 and c1 > c0:
        dem100[r0:r1, c0:c1] = blk[r0 - row0:r1 - row0, c0 - col0:c1 - col0]
    cov = float(np.isfinite(dem100[footprint]).mean())
    print(f"{cov:.4f}", flush=True)
    yy, xx = np.mgrid[0:H, 0:Wd].astype(np.float64)
    X = (strans.c + (xx + 0.5) * strans.a) - x0
    Y = (strans.f + (yy + 0.5) * strans.e) - y0
    iso_surf = np.zeros((H, Wd))
    for (i, j), c in zip(terms, coef):
        iso_surf += c * (X ** i) * (Y ** j)
    resid = dem100 - iso_surf.astype(np.float32)
    put("datum_isobase_resid_m", resid)
    put("datum_band", np.where(np.isfinite(resid), (np.abs(resid - dom) <= tol).astype(np.float32), np.nan))
    put("datum_abs_resid", np.abs(resid))
    del dem, dem100, blk, cnt, X, Y, iso_surf

    Sker = {k: (kernel_field(v["mask"]), v["mask"], float(v["K"])) for k, v in sur.items()}
    F = len(names)
    print(f"features {F}", flush=True)

    # ---- spatial blocks -------------------------------------------------------------------
    rows = np.linspace(0, H, 3).astype(int)
    cols = np.linspace(0, Wd, 4).astype(int)
    block = np.full((H, Wd), -1, np.int8)
    for bi in range(2):
        for bj in range(3):
            block[rows[bi]:rows[bi + 1], cols[bj]:cols[bj + 1]] = bi * 3 + bj
    blocks = [b for b in range(6)]
    print(f"block sizes {[int((block == b_).sum()) for b_ in blocks]}", flush=True)

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    train_pos = sur["S_mid"]["mask"]
    rng = np.random.default_rng(args.seed)
    oof = np.full((H, Wd), np.nan, np.float32)
    fold_report, per_feature_auc = [], {}
    fp_idx = np.flatnonzero(footprint.ravel())
    for b in blocks:
        te = (block == b)
        tr = ~te
        ptr = np.flatnonzero((train_pos & tr & footprint).ravel())
        ntr = np.flatnonzero((active & tr & ~train_pos).ravel())
        nte_pos = np.flatnonzero((train_pos & te & footprint).ravel())
        nte_neg = np.flatnonzero((active & te & ~train_pos).ravel())
        if ptr.size == 0 or nte_pos.size == 0:
            print(f"  block {b}: no positives in train or test - skipped", flush=True)
            continue
        neg_take = rng.choice(ntr, size=min(args.n_neg, ntr.size), replace=False)
        neg_te = rng.choice(nte_neg, size=min(20000, nte_neg.size), replace=False)
        tr_idx = np.concatenate([ptr, neg_take])
        te_idx = np.concatenate([nte_pos, neg_te])
        Xtr = np.empty((tr_idx.size, F), np.float32)
        Xte = np.empty((te_idx.size, F), np.float32)
        for j in range(F):
            a = np.load(fdir / f"{j:02d}_{names[j]}.npy", mmap_mode="r")
            Xtr[:, j] = np.asarray(a).ravel()[tr_idx]
            Xte[:, j] = np.asarray(a).ravel()[te_idx]
        ytr = np.zeros(tr_idx.size, np.int8)
        ytr[:ptr.size] = 1
        yte = np.zeros(te_idx.size, np.int8)
        yte[:nte_pos.size] = 1
        w = np.ones(tr_idx.size)
        w[:ptr.size] = float(neg_take.size) / max(ptr.size, 1)
        clf = HistGradientBoostingClassifier(
            max_iter=args.max_iter, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=40, l2_regularization=1.0, early_stopping=False,
            random_state=args.seed)
        clf.fit(Xtr, ytr, sample_weight=w)
        pte = clf.predict_proba(Xte)[:, 1]
        auc = float(roc_auc_score(yte, pte))
        # leakage canary: each feature alone
        if b == blocks[0]:
            for j in range(F):
                col = Xte[:, j]
                ok = np.isfinite(col)
                per_feature_auc[names[j]] = (float(roc_auc_score(yte[ok], col[ok]))
                                             if ok.sum() > 100 and len(np.unique(yte[ok])) > 1
                                             else None)
        # OOF prediction over the whole block, in row chunks
        r_lo, r_hi = int(np.flatnonzero(te.any(axis=1)).min()), int(np.flatnonzero(te.any(axis=1)).max()) + 1
        for r0c in range(r_lo, r_hi, 256):
            r1c = min(r_hi, r0c + 256)
            sub = te[r0c:r1c]
            sel = np.flatnonzero(sub.ravel())
            if sel.size == 0:
                continue
            Xc = np.empty((sel.size, F), np.float32)
            base = r0c * Wd
            for j in range(F):
                a = np.load(fdir / f"{j:02d}_{names[j]}.npy", mmap_mode="r")
                Xc[:, j] = np.asarray(a).ravel()[base:base + sub.size][sel]
            pc = clf.predict_proba(Xc)[:, 1]
            flat = oof[r0c:r1c].ravel()
            flat[sel] = pc
            oof[r0c:r1c] = flat.reshape(-1, sub.shape[1])
            del Xc
        fold_report.append(dict(block=int(b), n_train_pos=int(ptr.size), n_train_neg=int(neg_take.size),
                                n_test_pos=int(nte_pos.size), n_test_neg=int(neg_te.size), auc=auc))
        print(f"  block {b}: train+ {ptr.size:,} test+ {nte_pos.size:,} AUC={auc:.4f} "
              f"t={time.time()-t0:.0f}s", flush=True)
        del Xtr, Xte
    np.save(root / args.oof, oof)
    mean_auc = float(np.mean([f["auc"] for f in fold_report]))
    print(f"MEAN BLOCKED AUC {mean_auc:.4f}", flush=True)

    # ---- instrument table: every registry artifact + this session's OOF emissions ----------
    rows_out = []
    idxr = json.load(open(root / args.index))
    seen = {}
    for r in idxr:
        k = (r["repo"], os.path.basename(r["path"]))
        if k not in seen or r["score"] > seen[k]["score"]:
            seen[k] = r
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
        row = dict(name=f"{r['repo']}__{os.path.basename(r['path'])[:60]}", obs=float(r["score"]),
                   M=int((m & active).sum()), kind="registry")
        res = dti_binary_fast(m.astype(np.float64), Sker, active)
        for sname in sur:
            row[f"dti_{sname}"] = res[sname]["dti"]
        rows_out.append(row)
        del a, m
    print(f"instrument table: {len(rows_out)} registry artifacts  t={time.time()-t0:.0f}s", flush=True)

    # emissions from the OOF surface, at several masses, with a catalogue standoff sweep
    pv = np.where(active & np.isfinite(oof), oof, -1.0)
    masses = [int(x) for x in args.masses.split(",")]
    emit_rows = []
    keep_masks = {}
    for standoff in (0, 300, 600):
        elig = active.copy()
        if standoff:
            elig &= dcat >= standoff
        for M in masses:
            t1 = time.time()
            keep = hard_core_local_maxima(pv, elig, M, seed=args.seed + standoff)
            n = int(keep.sum())
            if n < M * 0.9:
                print(f"  emit standoff={standoff} M={M}: only {n:,} local maxima - skipped",
                      flush=True)
                continue
            row = dict(kind="emission", standoff_m=standoff, M_target=M, M_actual=n,
                       name=f"oof_standoff{standoff}_M{M}")
            res = dti_binary_fast(keep.astype(np.float64), Sker, active)
            for sname in sur:
                row[f"dti_{sname}"] = res[sname]["dti"]
                row[f"credit_{sname}"] = res[sname]["T"] / max(n, 1)
            emit_rows.append(row)
            if standoff == 300:
                keep_masks[M] = keep
            print(f"  emit standoff={standoff} M={n:,} " +
                  " ".join(f"{k.replace('dti_','')}={row[k]:.4f}" for k in row if k.startswith("dti_")) +
                  f"  ({time.time()-t1:.0f}s)", flush=True)
    np.save(root / "build" / "keep_masks.npy",
            np.array([keep_masks[m].ravel() for m in sorted(keep_masks)]))
    json.dump(dict(masses=sorted(keep_masks)), open(root / "build" / "keep_masks_index.json", "w"))

    out = dict(
        experiment="exp6_detector_blocked",
        label="MEASURED-INSTRUMENT + MODEL (no projection here is written as a score)",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        stack_sha256=stack_sha, stack_sha_matches_manifest=stack_sha == args.stack_sha,
        n_features=F, feature_names=names, dem_coverage_of_footprint=cov,
        surrogates={k: dict(q=v["q"], thresh=v["thresh"], K=v["K"]) for k, v in sur.items()},
        folds=fold_report, mean_blocked_auc=mean_auc,
        per_feature_auc_block0=per_feature_auc,
        leakage_flags=[k for k, v in per_feature_auc.items() if v is not None and v > 0.90],
        registry_on_surrogates=rows_out, emissions=emit_rows,
        seconds=round(time.time() - t0, 1))
    json.dump(out, open(root / args.out, "w"), indent=1)
    print("wrote", args.out, f"{time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
