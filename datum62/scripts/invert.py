#!/usr/bin/env python3
"""EXPERIMENT 3 - invert the public leaderboard: estimate the hidden truth SET (memory-safe).

s_i(S) = T_i(S)/(0.2*M_i + 0.8*|S|),  T_i(S) = sum_{g in S} k(dist(g, dots_i)).
Weights are quantised to uint8 (k*255) and only the candidate pixel set is materialised.
Greedy forward/backward selection over a dictionary of atoms.
"""
from __future__ import annotations
import glob, json, os, sys
from pathlib import Path
import numpy as np, rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt
ROOT = Path(__file__).resolve().parents[2]
G60 = Path("/tmp/g60/x/60GEMSDOE-main"); BUILD = Path("/tmp/datum62build")
OUT = ROOT / "datum62" / "evidence"
R = 3.0  # px; official kernel support = 300 m at 100 m pixels
# FIX 2026-10-12 (session arena/778884cc, IR-62-25): the table below was defined in PIXEL units
# (zero at j >= 3) but indexed with QUARTER-pixel indices (dm*4), shrinking the effective kernel
# to 75 m and zeroing every contribution beyond 0.75 px.  The table is now defined on the same
# quarter-pixel grid used for indexing (zero at j >= 12  <=>  dm >= 3 px = 300 m).  The committed
# evidence (datum62/evidence/inverse_truth.json) was produced with the buggy kernel; the corrected
# reconstruction is scripts/reconstruct_sstar.py -> evidence/sstar_fixed/.
KERN = np.maximum(1.0 - np.arange(24) / (R * 4), 0.0).astype(np.float32)
def rd(p, idx=1):
    with rasterio.open(p) as d: return d.read(idx).astype(np.float32)
with rasterio.open(ROOT / "data/sample_submission.tif") as d: tmpl = d.read(1)
footprint = np.isfinite(tmpl); H, W = footprint.shape
with rasterio.open(ROOT / "data/labels.tif") as d: catalogue = (d.read(1) == 1) & footprint
def resolve(r):
    b = os.path.basename(r["path"])
    for c in [r["path"], str(G60 / r["path"])] + glob.glob("/tmp/reg/tif/*" + b):
        if os.path.exists(c): return c
    raise SystemExit("missing " + b)
rows = json.load(open("/tmp/reg/measured.json")); obs = np.array([r["score"] for r in rows])
masks = []
for r in rows:
    a = rd(resolve(r)); masks.append((np.where(np.isfinite(a), a, 0) > 0))
Ms = np.array([int(m.sum()) for m in masks], float)
hi = [m for m, r in zip(masks, rows) if r["score"] >= 0.24]
cons = np.logical_and.reduce(hi); maj = np.sum(hi, 0) >= (len(hi)//2+1); union = np.logical_or.reduce(hi)
pf = np.load(BUILD / "pfull.npy")
atoms = {f"art{j}_{r['repo']}": (m & footprint) for j, (m, r) in enumerate(zip(masks, rows))}
atoms.update(consensus13=cons, majority13=maj, union13=union,
             cons_dil1=binary_dilation(cons, iterations=1), cons_dil2=binary_dilation(cons, iterations=2),
             cons_dil3=binary_dilation(cons, iterations=3))
for q in (99.9, 99.7, 99.5, 99.0, 98.0, 96.0, 92.0, 85.0, 70.0):
    atoms[f"model_q{q}"] = (pf >= float(np.percentile(pf[footprint], q))) & footprint
cand = np.zeros((H, W), bool)
for A in atoms.values(): cand |= A
cand &= footprint
idx = np.flatnonzero(cand.ravel()); n = idx.size
print(f"candidate pixels {n:,} of {int(footprint.sum()):,}", flush=True)
flat = lambda A: A.ravel()[idx]
with rasterio.open(ROOT / "data/sample_submission.tif") as d: _ = d.read(1)
Wm = np.zeros((len(masks), n), np.uint8)
for i, m in enumerate(masks):
    dm = distance_transform_edt(~m)
    kb = np.where(dm > 3, 0.0, KERN[np.minimum((dm*4).astype(np.int32), 23)])
    Wm[i] = np.rint(kb.ravel()[idx]*255).astype(np.uint8); del dm, kb
    if i % 10 == 0: print("  weights", i, flush=True)
np.save(BUILD/"Wm_shape.npy", np.array([len(masks), n]))
Aidx = {k: np.flatnonzero(flat(A)) for k, A in atoms.items()}
def fit(mem):
    """mem: boolean over candidate pixels."""
    T = Wm[:, mem].sum(axis=1).astype(np.float64)/255.0
    K = int(mem.sum()); p = T/(0.2*Ms + 0.8*K)
    a = float((p@obs)/(p@p)); ss = float(((obs-a*p)**2).sum()); tot = float(((obs-obs.mean())**2).sum())
    ra = np.argsort(np.argsort(obs)).astype(float); rb = np.argsort(np.argsort(p)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    return dict(scale=a, r2=1-ss/tot, rmse=float(np.sqrt(ss/obs.size)), spearman=float(ra@rb/np.sqrt((ra@ra)*(rb@rb))), K=K)
mem = flat(cons).copy(); cur = fit(mem)
print("start consensus13:", {k: (round(v,4) if isinstance(v,float) else v) for k,v in cur.items()}, flush=True)
log=[dict(step="start",atom="consensus13",**cur)]
improved=True
while improved:
    improved=False; best=None
    TinS = Wm[:, mem].sum(axis=1).astype(np.float64)/255.0
    for name, aidx in Aidx.items():
        # add
        new = np.setdiff1d(aidx, np.flatnonzero(mem), assume_unique=False)
        if new.size:
            T = TinS + Wm[:, new].sum(axis=1).astype(np.float64)/255.0
            K = int(mem.sum())+new.size
            p = T/(0.2*Ms+0.8*K); a=float((p@obs)/(p@p)); ss=float(((obs-a*p)**2).sum())
            ra=np.argsort(np.argsort(obs)).astype(float); rb=np.argsort(np.argsort(p)).astype(float)
            ra-=ra.mean(); rb-=rb.mean(); rho=float(ra@rb/np.sqrt((ra@ra)*(rb@rb)))
            if best is None or rho>best[1]: best=(f"+{name}", rho, dict(scale=a,r2=1-ss/float(((obs-obs.mean())**2).sum()),K=K,add=name))
        # remove
        keep = np.setdiff1d(aidx, np.flatnonzero(mem), assume_unique=False)
        inter = np.intersect1d(aidx, np.flatnonzero(mem))
        if inter.size and inter.size < mem.sum():
            T = TinS - Wm[:, inter].sum(axis=1).astype(np.float64)/255.0
            K = int(mem.sum())-inter.size
            p = T/(0.2*Ms+0.8*K); a=float((p@obs)/(p@p)); ss=float(((obs-a*p)**2).sum())
            ra=np.argsort(np.argsort(obs)).astype(float); rb=np.argsort(np.argsort(p)).astype(float)
            ra-=ra.mean(); rb-=rb.mean(); rho=float(ra@rb/np.sqrt((ra@ra)*(rb@rb)))
            if best is None or rho>best[1]: best=(f"-{name}", rho, dict(scale=a,r2=1-ss/float(((obs-obs.mean())**2).sum()),K=K,remove=name))
    if best and best[1] > cur["spearman"]+1e-9:
        nm = best[0]; rec = best[2]
        if "add" in rec:
            new = np.setdiff1d(Aidx[rec["add"]], np.flatnonzero(mem)); mem[new]=True
        else:
            inter = np.intersect1d(Aidx[rec["remove"]], np.flatnonzero(mem)); mem[inter]=False
        cur = fit(mem); log.append(dict(step=nm, atom=nm, **cur))
        print(f"  {nm:<26} rho={cur['spearman']:.4f} r2={cur['r2']:.4f} K={cur['K']:,}", flush=True)
        improved=True
    else: print("  converged", flush=True)
T = Wm[:, mem].sum(axis=1).astype(np.float64)/255.0; K=int(mem.sum()); p = T/(0.2*Ms+0.8*K)
Sfull = np.zeros((H,W), bool); Sfull.ravel()[idx[mem]] = True
np.save(BUILD/"truth_est.npy", Sfull)
json.dump(dict(log=log, final=cur, K=int(K), scale=float(cur["scale"]),
               predicted=(cur["scale"]*p).tolist(), observed=obs.tolist(),
               fields=[dict(repo=r["repo"], score=r["score"], M=int(Ms[i]), path=r["path"]) for i,r in enumerate(rows)]),
          open(OUT/"inverse_truth.json","w"), indent=1)
print("FINAL", cur)
o=np.argsort(-obs)
for i in o[:8]: print(f"   obs {obs[i]:.4f} pred {cur['scale']*p[i]:.4f}  {rows[i]['repo']} {os.path.basename(rows[i]['path'])[:50]}")
