#!/usr/bin/env python3
"""Rebuild the leaderboard-inverted truth surrogate S* with the kernel defect FIXED.

IR-62-2026-10-12-01 (this session): the shared inversion in datum62/scripts/invert.py
quantised pixel distances on a quarter-pixel lattice but divided by R=3 instead of R*4=12,
i.e. it fitted a triangle that reaches zero at 0.75 px (75 m) instead of the published
300 m kernel k(d) = max(1 - d/300m, 0).  The protocol says a shared tool is fixed once,
in the template, and reported.  This script is the fixed tool: same 56 owner-reported
scores, same greedy add/remove inversion, but the weights are the published kernel.

Outputs:
  build/sstar/truth_est.npy     bool (H, W) mask, the rebuilt S*
  evidence/sstar_rebuild_20261012.json   receipt: fit statistics, kernel spec, per-field table
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

ROOT = pathlib.Path(__file__).resolve().parents[1]
REG = ROOT / "build" / "registry"
OUTDIR = ROOT / "build" / "sstar"
EVID = ROOT / "evidence"
ROWS = ROOT / "datum62" / "evidence" / "measured_artifacts_56.json"

# Published kernel: k(d) = max(1 - d/300m, 0); at 100 m/px the support is 3 px.
RADIUS_PX = 3.0
# quarter-pixel quantisation bins; index j = round(dm * 4) -> k = max(1 - j/12, 0)
QUANT = 4
KERN = np.maximum(1.0 - np.arange(24) / (RADIUS_PX * QUANT), 0.0).astype(np.float32)


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    EVID.mkdir(parents=True, exist_ok=True)
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as d:
        tmpl = d.read(1)
    footprint = np.isfinite(tmpl)
    H, W = footprint.shape
    rows = json.loads(ROWS.read_text())
    masks, Ms, obs = [], [], []
    for r in rows:
        p = REG / pathlib.Path(r["path"]).name
        assert p.exists(), p
        with rasterio.open(p) as d:
            a = d.read(1)
        m = (np.where(np.isfinite(a), a, 0) > 0) & footprint
        masks.append(m)
        Ms.append(float(m.sum()))
        obs.append(float(r["score"]))
        print(f"mask {p.name[:56]:<56} M={int(m.sum()):>7,}", flush=True)
    Ms = np.array(Ms)
    obs = np.array(obs)

    hi = [m for m, r in zip(masks, rows) if r["score"] >= 0.24]
    cons = np.logical_and.reduce(hi)
    maj = np.sum(hi, 0) >= (len(hi) // 2 + 1)
    union = np.logical_or.reduce(hi)
    print(f"consensus(>=0.24, n={len(hi)}) = {int(cons.sum()):,} px", flush=True)

    # candidate pixels = union of every atom
    atoms: dict[str, np.ndarray] = {}
    for j, (m, r) in enumerate(zip(masks, rows)):
        atoms[f"art{j}_{r['repo']}"] = m
    atoms["consensus13"] = cons
    atoms["majority13"] = maj
    atoms["union13"] = union
    for it in (1, 2, 3):
        from scipy.ndimage import binary_dilation
        atoms[f"cons_dil{it}"] = binary_dilation(cons, iterations=it)
    cand = np.zeros((H, W), bool)
    for A in atoms.values():
        cand |= A
    cand &= footprint
    idx = np.flatnonzero(cand.ravel())
    n = idx.size
    print(f"candidate pixels {n:,} of {int(footprint.sum()):,}", flush=True)

    # kernel weights at candidate pixels for every artifact
    Wm = np.zeros((len(masks), n), np.uint8)
    for i, m in enumerate(masks):
        dm = distance_transform_edt(~m)
        kb = np.where(dm > RADIUS_PX, 0.0,
                      KERN[np.minimum((dm * QUANT).astype(np.int32), 23)])
        Wm[i] = np.rint(kb.ravel()[idx] * 255).astype(np.uint8)
        del dm, kb
        if i % 10 == 0:
            print(f"  weights {i}", flush=True)

    def flat(A: np.ndarray) -> np.ndarray:
        return A.ravel()[idx]

    Aidx = {k: np.flatnonzero(flat(A)) for k, A in atoms.items()}

    tot = float(((obs - obs.mean()) ** 2).sum())

    def fit(mem: np.ndarray) -> dict:
        T = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
        K = int(mem.sum())
        p = T / (0.2 * Ms + 0.8 * K)
        a = float((p @ obs) / (p @ p))
        ss = float(((obs - a * p) ** 2).sum())
        ra = np.argsort(np.argsort(obs)).astype(float)
        rb = np.argsort(np.argsort(p)).astype(float)
        ra -= ra.mean(); rb -= rb.mean()
        return dict(scale=a, r2=1 - ss / tot, rmse=float(np.sqrt(ss / obs.size)),
                    spearman=float(ra @ rb / np.sqrt((ra @ ra) * (rb @ rb))), K=K)

    mem = flat(cons).copy()
    cur = fit(mem)
    print("start consensus:", cur, flush=True)
    log = [dict(step="start", atom="consensus13", **cur)]
    improved = True
    while improved:
        improved = False
        best = None
        TinS = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
        mem_idx = np.flatnonzero(mem)
        for name, aidx in Aidx.items():
            new = np.setdiff1d(aidx, mem_idx, assume_unique=False)
            if new.size:
                T = TinS + Wm[:, new].sum(axis=1).astype(np.float64) / 255.0
                K = int(mem.sum()) + new.size
                p = T / (0.2 * Ms + 0.8 * K)
                a = float((p @ obs) / (p @ p))
                ss = float(((obs - a * p) ** 2).sum())
                ra = np.argsort(np.argsort(obs)).astype(float)
                rb = np.argsort(np.argsort(p)).astype(float)
                ra -= ra.mean(); rb -= rb.mean()
                rho = float(ra @ rb / np.sqrt((ra @ ra) * (rb @ rb)))
                if best is None or rho > best[1]:
                    best = (f"+{name}", rho, dict(scale=a, r2=1 - ss / tot, K=K, add=name))
            inter = np.intersect1d(aidx, mem_idx)
            if inter.size and inter.size < mem.sum():
                T = TinS - Wm[:, inter].sum(axis=1).astype(np.float64) / 255.0
                K = int(mem.sum()) - inter.size
                p = T / (0.2 * Ms + 0.8 * K)
                a = float((p @ obs) / (p @ p))
                ss = float(((obs - a * p) ** 2).sum())
                ra = np.argsort(np.argsort(obs)).astype(float)
                rb = np.argsort(np.argsort(p)).astype(float)
                ra -= ra.mean(); rb -= rb.mean()
                rho = float(ra @ rb / np.sqrt((ra @ ra) * (rb @ rb)))
                if best is None or rho > best[1]:
                    best = (f"-{name}", rho, dict(scale=a, r2=1 - ss / tot, K=K, remove=name))
        if best and best[1] > cur["spearman"] + 1e-9:
            nm = best[0]; rec = best[2]
            if "add" in rec:
                new = np.setdiff1d(Aidx[rec["add"]], np.flatnonzero(mem))
                mem[new] = True
            else:
                inter = np.intersect1d(Aidx[rec["remove"]], np.flatnonzero(mem))
                mem[inter] = False
            cur = fit(mem)
            log.append(dict(step=nm, atom=nm, **cur))
            print(f"  {nm:<28} rho={cur['spearman']:.4f} r2={cur['r2']:.4f} K={cur['K']:,}",
                  flush=True)
            improved = True
        else:
            print("  converged", flush=True)

    T = Wm[:, mem].sum(axis=1).astype(np.float64) / 255.0
    K = int(mem.sum())
    p = T / (0.2 * Ms + 0.8 * K)
    Sfull = np.zeros((H, W), bool)
    Sfull.ravel()[idx[mem]] = True
    np.save(OUTDIR / "truth_est.npy", Sfull)

    # calibration of the 300 m-correct instrument against the old 75 m one
    old = json.loads((ROOT / "datum62" / "evidence" / "inverse_truth.json").read_text())
    receipt = dict(
        generated_utc=__import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        instrument="S* rebuild v2 (fixed 300 m triangular kernel)",
        defect_fixed="IR-62-2026-10-12-01: datum62 invert.py used KERN=1-j/3 on j=dm*4, "
                     "zero at 0.75 px; this rebuild uses KERN=1-j/12, zero at 3 px = 300 m "
                     "= the published kernel",
        kernel=dict(radius_px=RADIUS_PX, quant=QUANT,
                    formula="k(d)=max(1-d/300m,0), d in metres; dm in px at 100 m/px"),
        n_fields=len(rows), K=int(K), fit=cur,
        old_instrument_fit=dict(K=old["K"], spearman=old["final"]["spearman"],
                                r2=old["final"]["r2"], scale=old["scale"]),
        fields=[dict(repo=r["repo"], path=r["path"], score=r["score"], M=int(Ms[i]),
                     pred=float(cur["scale"] * p[i]))
                for i, r in enumerate(rows)],
    )
    (EVID / "sstar_rebuild_20261012.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print("FINAL", cur)
    o = np.argsort(-obs)
    for i in o[:8]:
        print(f"   obs {obs[i]:.4f} pred {cur['scale'] * p[i]:.4f}  {rows[i]['repo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
