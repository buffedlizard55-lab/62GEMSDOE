#!/usr/bin/env python3
"""EXPERIMENT 11 - close the one axis on which the exp9 field deviates from the top family.

Experiment 10 measured the arrangement of every distinct scored field.  At the mass of the top band
(M = 37,654-44,090) the fields that scored 0.26-0.2778 all carry

    dens21 (other dots in a 2.1 km box around a dot) = 8.75-9.62
    coh21  (structure-tensor coherence of the 2.1 km dot-density field) = 0.307-0.336

while the exp9 winner carries dens21 = 4.56 and coh21 = 0.1595 - i.e. it is nearly UNIFORM, whereas
the top family is 2.7x locally concentrated (uniform expectation at M = 40,000 is 3.42).  Truth is
concentrated in corridors, so a uniform field spends mass where nothing is.

This script applies one spatial concentration transform to the same priority surface and re-measures
everything.  PRE-REGISTERED DECISION RULE (fixed before the numbers were seen):

    prefer the concentrated variant iff it satisfies all seven exp9 constraints AND
    dens21 in [7.0, 12.0] AND coh21 >= 0.25 ; otherwise ship the exp9 winner unchanged.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.ndimage import distance_transform_edt as edt

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util                                              # noqa: E402

for mod, path in (("exp6", "scripts/exp6_detector_blocked.py"), ("exp8", "scripts/exp8_reward_model.py"),
                  ("exp9", "scripts/exp9_profile_matched_emission.py"),
                  ("exp10", "scripts/exp10_linearity.py")):
    sp = importlib.util.spec_from_file_location(mod, ROOT / path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    globals()[mod] = m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oof", default="build/oof_surface.npy")
    ap.add_argument("--exp9", default="evidence/exp9_profile_matched_emission.json")
    ap.add_argument("--out", default="evidence/exp11_concentration.json")
    ap.add_argument("--save", default="build/final_choice.npz")
    ap.add_argument("--mass", type=int, default=40000)
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
    with rasterio.open(ROOT / "build/ext/derived_sgmc_faults_100m.tif") as ds:
        sgmc = (ds.read(1) > 0) & footprint
    d_sgmc = edt(~(sgmc & ~cat3)).astype(np.float32)
    d_cat_px = edt(~cat).astype(np.float32)
    d_cat_m = d_cat_px * 100.0
    with rasterio.open(ROOT / "build/ext/lidar_scarp_features_u8.tif") as ds:
        lidar = ds.read(1).astype(np.float32) / 255.0
    with rasterio.open(ROOT / "build/ext/geodawn_dem_a2_100m.tif") as ds:
        dem100 = ds.read(1).astype(np.float32); nod = ds.nodata
    dem100[~np.isfinite(dem100)] = np.nan
    if nod is not None:
        dem100[dem100 == nod] = np.nan
    gz, gx = np.gradient(np.nan_to_num(dem100, nan=0.0))
    slope = np.degrees(np.arctan(np.hypot(gx, gz) / 100.0)).astype(np.float32)
    m1 = ndi.uniform_filter(np.nan_to_num(dem100, nan=0.0), 5)
    m2 = ndi.uniform_filter(np.nan_to_num(dem100, nan=0.0) ** 2, 5)
    topo_std = np.sqrt(np.maximum(m2 - m1 * m1, 0)).astype(np.float32)
    ctx = dict(d_sgmc=d_sgmc, d_cat=d_cat_px, lidar=(lidar * 255.0), topo_std=topo_std,
               slope=slope, mask=None)

    e9 = json.load(open(ROOT / args.exp9))
    champ = e9["candidates"][0]
    b_chosen = e9["chosen"]["b"]; s_chosen = int(e9["chosen"]["standoff_m"])
    oof = np.load(ROOT / args.oof)
    oof_n = np.clip(np.nan_to_num(oof, nan=0.0), 0.0, None)
    oof_n = oof_n / max(float(oof_n.max()), 1e-12)
    elig = active & (d_cat_m >= s_chosen) if s_chosen else active
    base = np.where(elig, oof_n * ((lidar + 0.05) ** b_chosen), -1.0).astype(np.float32)
    thr = float(np.quantile(base[elig], 0.90))
    hot = (base >= thr) & elig
    dens = ndi.uniform_filter(hot.astype(np.float32), size=21)
    dens_n = dens / max(float(dens.max()), 1e-12)

    results = []
    for gamma in (0.0, 1.0, 2.0, 3.0):
        pri = base * ((0.25 + dens_n) ** gamma) if gamma else base
        keep = exp6.hard_core_local_maxima(np.where(elig, pri, -1.0).astype(np.float32), elig,
                                           args.mass, seed=args.seed + int(gamma * 10))
        n = int(keep.sum())
        if n < 0.9 * args.mass:
            print(f"  gamma={gamma}: only {n:,} maxima - skipped", flush=True)
            continue
        ctx["mask"] = keep
        f = exp8.field_features(keep, ctx)
        f.update(exp10.arrangement(keep))
        f.update(name=f"oofL{b_chosen}_s{s_chosen}_g{gamma}_M{n}", gamma=gamma, M=n)
        n_ok, bad = exp9.feasible(f)
        f["constraints_satisfied"] = n_ok
        f["constraints_failed"] = bad
        results.append((f, keep))
        print(f"  gamma={gamma:<4} M={n:>7,} dens21={f['dens21']:6.2f} coh21={f['coh21']:.4f} "
              f"self_k={f['self_kernel']:.4f} even={f['evenness_cells']:.0f} "
              f"ccat={f['credit_cat']:.4f} lidar={f['lidar_scarp_mean']:.2f} "
              f"csgmc={f['credit_sgmc']:.4f} ok={n_ok}/7", flush=True)

    e9c = e9["chosen"]
    conc = [f for f, _ in results if f["gamma"] > 0 and f["constraints_satisfied"] == 7
            and 7.0 <= f["dens21"] <= 12.0 and f["coh21"] >= 0.25]
    if conc:
        best = max(conc, key=lambda f: (f["coh21"], f["credit_sgmc"]))
        chosen_from = "concentrated variant (pre-registered rule satisfied)"
        src = "exp11"
    else:
        best = e9c
        chosen_from = ("exp9 winner - the pre-registered concentration rule was NOT satisfied "
                       f"(feasible concentrated variants: {len(conc)})")
        src = "exp9"
    print(f"\nCHOSEN {best['name']} from {src}: {chosen_from}", flush=True)

    if src == "exp11":
        keep = dict((f["name"], k) for f, k in results)[best["name"]]
    else:
        pri = base
        keep = exp6.hard_core_local_maxima(np.where(elig, pri, -1.0).astype(np.float32), elig,
                                           args.mass, seed=args.seed + int(b_chosen * 10) + s_chosen)
        assert int(keep.sum()) == best["M"], (int(keep.sum()), best["M"])
    np.savez_compressed(ROOT / args.save, keep=np.packbits(keep.ravel()),
                        shape=np.array(keep.shape), name=best["name"], source=src)
    out = dict(experiment="exp11_concentration", label="MEASURED (no number here is a score)",
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               rule=__doc__.split("PRE-REGISTERED DECISION RULE")[1].strip(),
               base_config=dict(b=b_chosen, standoff_m=s_chosen, mass=args.mass),
               candidates=[f for f, _ in results], chosen=best, chosen_source=src,
               chosen_reason=chosen_from,
               top_family_arrangement=dict(dens21=[8.75, 9.62], coh21=[0.307, 0.336],
                                           source="evidence/exp10_linearity.json"),
               seconds=round(time.time() - t0, 1))
    json.dump(out, open(ROOT / args.out, "w"), indent=1, default=float)
    print("wrote", args.out, f"({time.time()-t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
