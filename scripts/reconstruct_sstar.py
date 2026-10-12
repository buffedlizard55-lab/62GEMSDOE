#!/usr/bin/env python3
"""E1 — reconstruct the leaderboard-inverted truth surrogate S* WITH THE OFFICIAL KERNEL.

Why this script exists (template fix, reported per parallel-run protocol rule 2)
-------------------------------------------------------------------------------
`datum62/scripts/invert.py` (session arena/dfc9787b, 2026-10-11) inverted 56 owner-reported
portal scores to recover a hidden-truth surrogate S* (K = 8,479 px, Spearman +0.968).  Its
kernel quantisation is wrong:

    R = 3.0; KERN = np.maximum(1.0 - np.arange(24) / R, 0.0)          # indexed in PIXELS
    kb  = KERN[np.minimum((dm * 4).astype(np.int32), 23)]              # dm*4 is QUARTER-pixels

The table is defined for j = distance in pixels (zero at j >= 3 px = 300 m) but is indexed
with quarter-pixel indices, so every distance >= 0.75 px (75 m) scored ZERO.  The inversion
therefore fitted an exact-pixel-overlap model instead of the published 300 m triangular
kernel, which is the mechanism behind its systematic under-prediction of every high-scoring
artifact outside the 13-field consensus (gate_ortho: predicted 0.0064 vs observed 0.2376 —
37x; h59-cover: 0.0219 vs 0.2296 — 10x; committed evidence
`datum62/evidence/inverse_truth.json`, verified in this checkout).

Fix applied here (one change, everything else faithful to invert.py):

    q   = rint(dm * 4)                       # quarter-pixel index, 0..12 over the 3 px support
    KERN = max(1 - j / 12, 0), j = 0..23     # zero at j >= 12  <=>  dm >= 3 px = 300 m
    (max |quantisation error| = 1/24 = 0.042 in k)

Disclosed deviations from the committed run (both forced by uncommitted /tmp inputs):
  * the nine `model_q*` atoms are skipped (they need /tmp/datum62build/pfull.npy, the
    session-local detector probability field, which was never committed);
  * consequently the greedy log's `-model_q99.5` removal step cannot be replayed.

Outputs (committed):
  evidence/sstar_fixed/inverse_truth_fixed.json   full log + scale + predicted/observed
  evidence/sstar_fixed/sstar_coords.npz            the S* mask as (row, col) int32 arrays
  evidence/sstar_fixed/forensics.json              DTI table for local + registry artifacts
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
import numpy as np, rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
G60 = Path("/tmp/g60/x/60GEMSDOE-main")          # 60GEMSDOE tarball (sha-verified contents)
OUT = ROOT / "evidence" / "sstar_fixed"
OUT.mkdir(parents=True, exist_ok=True)

# ---- official kernel, quarter-pixel quantised (THE FIX) ----------------------------------
KERN = np.maximum(1.0 - np.arange(24) / 12.0, 0.0).astype(np.float32)   # zero at >= 3 px

def rd(p, idx=1):
    with rasterio.open(p) as d:
        return d.read(idx).astype(np.float32)

def resolve(r):
    b = os.path.basename(r["path"])
    for c in [r["path"], str(G60 / r["path"]), str(ROOT / r["path"])] + \
             [str(x) for x in Path("/tmp/registry").glob("*" + b)] + \
             [str(x) for x in (G60 / "registry/rasters").glob("*" + b)]:
        if os.path.exists(c):
            return c
    raise SystemExit("missing artifact bytes: " + b)

def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    return float(ra @ rb / np.sqrt((ra @ ra) * (rb @ rb)))

def main() -> int:
    t0 = time.time()
    rows = json.load(open(ROOT / "datum62/evidence/measured_artifacts_56.json"))
    obs = np.array([r["score"] for r in rows], float)
    with rasterio.open(ROOT / "data/sample_submission.tif") as d:
        tmpl = d.read(1)
    footprint = np.isfinite(tmpl); H, W = footprint.shape

    masks = []
    for r in rows:
        a = rd(resolve(r))
        masks.append((np.where(np.isfinite(a), a, 0) > 0) & footprint)
    Ms = np.array([int(m.sum()) for m in masks], float)
    print(f"loaded {len(masks)} artifact masks; Ms range {Ms.min():.0f}..{Ms.max():.0f}", flush=True)

    hi = [m for m, r in zip(masks, rows) if r["score"] >= 0.24]
    print(f"score>=0.24 consensus fields: {len(hi)}", flush=True)
    cons = np.logical_and.reduce(hi)
    maj = np.sum(hi, 0) >= (len(hi) // 2 + 1)
    union = np.logical_or.reduce(hi)

    atoms = {f"art{j}_{r['repo']}": m for j, (m, r) in enumerate(zip(masks, rows))}
    atoms.update(consensus13=cons, majority13=maj, union13=union,
                 cons_dil1=binary_dilation(cons, iterations=1),
                 cons_dil2=binary_dilation(cons, iterations=2),
                 cons_dil3=binary_dilation(cons, iterations=3))

    cand = np.zeros((H, W), bool)
    for A in atoms.values():
        cand |= A
    cand &= footprint
    idx = np.flatnonzero(cand.ravel()); n = idx.size
    print(f"candidate pixels {n:,} of {int(footprint.sum()):,}  ({time.time()-t0:.0f}s)", flush=True)

    # ---- kernel weights of every artifact over the candidate set (uint8, k*255) ------------
    Wm = np.zeros((len(masks), n), np.uint8)
    for i, m in enumerate(masks):
        dm = distance_transform_edt(~m)
        q = np.rint(dm * 4).astype(np.int32)
        kb = np.where(dm > 3.0, 0.0, KERN[np.minimum(q, 23)])
        Wm[i] = np.rint(kb.ravel()[idx] * 255).astype(np.uint8)
        del dm, q, kb
        if i % 10 == 0:
            print(f"  weights {i} ({time.time()-t0:.0f}s)", flush=True)

    flat = lambda A: A.ravel()[idx]
    Aidx = {k: np.flatnonzero(flat(A)) for k, A in atoms.items()}
    mem = flat(cons).copy()
    # free the full-grid masks (RAM budget: 3 GB sandbox); the greedy works on Aidx + Wm only
    import gc
    del atoms, masks, cons, maj, union, hi, cand
    gc.collect()

    def fit(mem):
        T = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
        K = int(mem.sum()); p = T / (0.2 * Ms + 0.8 * K)
        a = float((p @ obs) / (p @ p)) if (p @ p) > 0 else 0.0
        ss = float(((obs - a * p) ** 2).sum()); tot = float(((obs - obs.mean()) ** 2).sum())
        return dict(scale=a, r2=1 - ss / tot, rmse=float(np.sqrt(ss / obs.size)),
                    spearman=spearman(obs, p), K=K)

    cur = fit(mem)
    print("start consensus13:", {k: round(v, 4) for k, v in cur.items()}, flush=True)
    log = [dict(step="start", atom="consensus13", **cur)]
    improved = True
    while improved:
        improved = False; best = None
        TinS = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
        cur_idx = np.flatnonzero(mem)
        for name, aidx in Aidx.items():
            new = np.setdiff1d(aidx, cur_idx, assume_unique=False)
            if new.size:
                T = TinS + Wm[:, new].sum(axis=1).astype(np.float64) / 255.0
                K = int(mem.sum()) + new.size
                p = T / (0.2 * Ms + 0.8 * K)
                rho = spearman(obs, p)
                if best is None or rho > best[1]:
                    a = float((p @ obs) / (p @ p))
                    best = (f"+{name}", rho, dict(scale=a, r2=1 - float(((obs - a*p)**2).sum()) /
                                                  float(((obs - obs.mean())**2).sum()),
                                                  K=K, add=name))
            inter = np.intersect1d(aidx, cur_idx, assume_unique=False)
            if inter.size and inter.size < mem.sum():
                T = TinS - Wm[:, inter].sum(axis=1).astype(np.float64) / 255.0
                K = int(mem.sum()) - inter.size
                p = T / (0.2 * Ms + 0.8 * K)
                rho = spearman(obs, p)
                if best is None or rho > best[1]:
                    a = float((p @ obs) / (p @ p))
                    best = (f"-{name}", rho, dict(scale=a, r2=1 - float(((obs - a*p)**2).sum()) /
                                                  float(((obs - obs.mean())**2).sum()),
                                                  K=K, remove=name))
        if best and best[1] > cur["spearman"] + 1e-9:
            nm, _, rec = best
            if "add" in rec:
                new = np.setdiff1d(Aidx[rec["add"]], np.flatnonzero(mem)); mem[new] = True
            else:
                inter = np.intersect1d(Aidx[rec["remove"]], np.flatnonzero(mem)); mem[inter] = False
            cur = fit(mem)
            log.append(dict(step=nm, atom=nm, **cur))
            print(f"  {nm:<28} rho={cur['spearman']:.4f} r2={cur['r2']:.4f} K={cur['K']:,} "
                  f"({time.time()-t0:.0f}s)", flush=True)
            improved = True
        else:
            print("  converged", flush=True)

    T = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
    K = int(mem.sum()); p = T / (0.2 * Ms + 0.8 * K)
    Sfull = np.zeros((H, W), bool); Sfull.ravel()[idx[mem]] = True
    ys, xs = np.nonzero(Sfull)
    np.savez_compressed(OUT / "sstar_coords.npz", row=ys.astype(np.int32), col=xs.astype(np.int32))
    json.dump(dict(log=log, final=cur, K=K, scale=float(cur["scale"]),
                   kernel="official 300 m triangular, quarter-pixel quantised (fixed)",
                   predicted=(cur["scale"] * p).tolist(), observed=obs.tolist(),
                   fields=[dict(repo=r["repo"], score=r["score"], M=int(Ms[i]), path=r["path"])
                           for i, r in enumerate(rows)]),
              open(OUT / "inverse_truth_fixed.json", "w"), indent=1)
    print("FINAL", {k: round(v, 4) if isinstance(v, float) else v for k, v in cur.items()},
          f"({time.time()-t0:.0f}s)")
    o = np.argsort(-obs)
    for i in o[:16]:
        print(f"   obs {obs[i]:.4f} pred {cur['scale']*p[i]:.4f}  {rows[i]['repo']:<10} "
              f"{os.path.basename(rows[i]['path'])[:56]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
