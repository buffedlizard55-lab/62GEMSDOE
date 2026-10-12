#!/usr/bin/env python3
"""EXPERIMENT 10 - does the ARRANGEMENT of the dots (linear coherence) separate 0.2778 from 0.0778?

`h34-scatter-q50-arr-matched` (M = 37,654, credit_sgmc 0.0662, owner-reported 0.0778) and
`h33-2-b2` (M = 37,654, credit_sgmc 0.0655, owner-reported 0.2778) have the same mass and the same
per-dot credit against the one off-catalogue compilation this sandbox has.  They differ by 3.6x in
score.  The hypothesis tested here is that what differs is the ARRANGEMENT: the winners put dots
along coherent linear corridors, the loser scattered them.

Two arrangement statistics, both computable from the dots alone:
  dens21   mean number of other dots in a 2.1 km box around each dot  (chaininess)
  coh21    structure-tensor coherence of the 2.1 km dot-density field, sampled at the dots
           (1 = perfectly linear corridor, 0 = isotropic blob)
Reported with Spearman against the owner-reported scores over the de-duplicated registry, and for
this session's candidate emissions.
"""
from __future__ import annotations
import json, os, pathlib, sys, time
import numpy as np, rasterio
from scipy import ndimage as ndi

ROOT = pathlib.Path(__file__).resolve().parents[1]


def spearman(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b); a, b = a[ok], b[ok]
    if a.size < 4: return float("nan")
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    d = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / d) if d > 0 else float("nan")


def arrangement(mask):
    ys, xs = np.nonzero(mask)
    if ys.size == 0: return dict(dens21=0.0, coh21=0.0, n=0)
    dens = ndi.uniform_filter(mask.astype(np.float32), size=21) * 441.0     # count in the box
    gz, gx = np.gradient(dens)
    Jxx = ndi.uniform_filter(gx * gx, size=21); Jyy = ndi.uniform_filter(gy2 := (gz * gz), size=21)
    Jxy = ndi.uniform_filter(gx * gz, size=21)
    coh = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-18)
    return dict(n=int(ys.size), dens21=float(dens[ys, xs].mean() - 1.0),
                dens21_p90=float(np.percentile(dens[ys, xs], 90) - 1.0),
                coh21=float(coh[ys, xs].mean()), coh21_p10=float(np.percentile(coh[ys, xs], 10)))


def main() -> int:
    t0 = time.time()
    with rasterio.open(ROOT / "data/sample_submission.tif") as ds: tmpl = ds.read(1)
    fp = np.isfinite(tmpl); H, W = fp.shape
    rows = json.load(open(ROOT / "research/registry_index.json"))
    seen = {}
    for r in rows:
        k = (r["repo"], os.path.basename(r["path"]))
        if k not in seen or r["score"] > seen[k]["score"]: seen[k] = r
    out = []
    for r in sorted(seen.values(), key=lambda z: -z["score"]):
        p = pathlib.Path("/tmp/reg/tif") / f"{r['repo']}__{os.path.basename(r['path'])}"
        if not p.exists(): continue
        with rasterio.open(p) as ds: a = ds.read(1).astype(np.float32)
        if a.shape != (H, W): continue
        m = (np.where(np.isfinite(a), a, 0) > 0) & fp
        if m.sum() == 0: continue
        f = arrangement(m); f.update(kind="registry", score=float(r["score"]), M=int(m.sum()),
                                     name=f"{r['repo']}__{os.path.basename(r['path'])[:56]}")
        out.append(f); del a, m
    # de-duplicate identical arrangements
    dedup = {}
    for f in out: dedup.setdefault((f["M"], round(f["dens21"], 4), round(f["coh21"], 5)), f)
    dd = list(dedup.values())
    sc = np.array([f["score"] for f in dd])
    print(f"registry {len(out)} rows -> {len(dd)} distinct arrangements  t={time.time()-t0:.0f}s")
    print(f"Spearman(score, dens21) = {spearman(sc, [f['dens21'] for f in dd]):.4f}")
    print(f"Spearman(score, coh21)  = {spearman(sc, [f['coh21'] for f in dd]):.4f}")
    print(f"Spearman(score, M)      = {spearman(sc, [f['M'] for f in dd]):.4f}")
    print(f"\n{'score':>7} {'M':>8} {'dens21':>8} {'coh21':>7}  name")
    for f in sorted(dd, key=lambda z: -z["score"])[:12]:
        print(f"{f['score']:7.4f} {f['M']:8,d} {f['dens21']:8.2f} {f['coh21']:7.4f}  {f['name'][:50]}")
    print("  ...")
    for f in sorted(dd, key=lambda z: -z["score"])[-6:]:
        print(f"{f['score']:7.4f} {f['M']:8,d} {f['dens21']:8.2f} {f['coh21']:7.4f}  {f['name'][:50]}")
    # this session's chosen candidate
    z = np.load(ROOT / "build/final_choice.npz")
    keep = np.unpackbits(z["keep"]).astype(bool).reshape(tuple(z["shape"]))
    f = arrangement(keep); f.update(kind="candidate", name=str(z["name"]), M=int(keep.sum()))
    print(f"\nCANDIDATE {f['name']}: M={f['M']:,} dens21={f['dens21']:.2f} coh21={f['coh21']:.4f} "
          f"dens21_p90={f['dens21_p90']:.2f} coh21_p10={f['coh21_p10']:.4f}")
    champ = [x for x in dd if x["score"] == max(sc)][0]
    print(f"CHAMPION  {champ['name'][:40]}: M={champ['M']:,} dens21={champ['dens21']:.2f} "
          f"coh21={champ['coh21']:.4f}")
    json.dump(dict(experiment="exp10_linearity", label="MEASURED",
                   generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   n_registry_rows=len(out), n_distinct=len(dd),
                   spearman=dict(dens21=spearman(sc, [f["dens21"] for f in dd]),
                                 coh21=spearman(sc, [f["coh21"] for f in dd]),
                                 dens21_p90=spearman(sc, [f["dens21_p90"] for f in dd]),
                                 M=spearman(sc, [f["M"] for f in dd])),
                   distinct=dd, candidate=f, champion=champ,
                   seconds=round(time.time() - t0, 1)),
              open(ROOT / "evidence/exp10_linearity.json", "w"), indent=1, default=float)
    print("wrote evidence/exp10_linearity.json", f"{time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
