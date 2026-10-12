#!/usr/bin/env python3
"""EXPERIMENT 3 — the emission: scarp-primary field, corroborated, hard-core isolated.

Design, and why each part is in it:

1. **Primary locator = scarp evidence** from the two independent metre-scale scarp
   products (the 1 m LiDAR composite, 12 bands, and the 3 m scarp product, 7 bands).
   Rationale that does not depend on any local proxy: the organizer's target is
   *newly identified faults*, and the only fault population that a 1:750 k-1:24 k
   compilation systematically misses is the young, small-slip, surficial scarp
   population.  Both products are metre-scale topography, i.e. they resolve the
   2-10 m scarps a 100 m DEM cannot.
2. **Corroboration gate = k-of-N vote over independent physical families** (gravity,
   magnetics, radiometrics, geodetic strain, seismicity, conductivity, channel
   steepness, hillshade lineaments).  A scarp pixel that no independent physics
   supports is more likely a fluvial cut, a road grade, or a survey edge.
3. **Orientation agreement** between the two scarp products' strike bands, where both
   cover.  A real fault scarp has one strike; two independent products that disagree
   are looking at different features.
4. **Hard-core emission** (>=3 px = 300 m apart, greedy by score).  The published
   metric pays 0.2 per unit dot, so a second dot inside the first dot's kernel is a
   pure loss; this emitter makes that impossible by construction, then verifies it by
   distance transform on the written mask.
5. **Off-catalogue restriction**: every dot is >= 3 px from labels.tif, because the
   metric's known-fault pixels are masked out of scoring and the task is to find
   *unmapped* structures.

The script writes the profile of the credit-versus-mass curve on BOTH local proxies
(mapped catalogue, and SGMC 1:750 k minus catalogue) so the operating point is chosen
from a measured curve rather than from a preference.

Usage: python3 scripts/exp3_emit.py --budgets 20000 40000 80000 120000 200000 300000
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

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
from gems62 import grid  # noqa: E402
from gems62.metric import kernel, RADIUS_PX  # noqa: E402

EXT = HERE / "build" / "ext"
FEAT = HERE / "build" / "feat"

LIDAR = EXT / "lidar_scarp_features_u8.tif"
SCARP3M = EXT / "h52_scarp3m_100m.tif"

# non-scarp corroborating families (one representative each; from E1)
CORROBORATORS = [
    "off_iso_grav_anom_hg",     # gravity horizontal gradient
    "off_tc",                   # magnetic tilt angle
    "radext_TMI_up150",         # upward-continued TMI
    "rad_K",                    # airborne potassium
    "radext_ThK",               # Th/K ratio
    "off_geod_shearrate",       # geodetic shear rate
    "off_ieq_n100a15",          # seismicity intensity
    "off_cond_surf",            # conductivity surface
    "chi10_ksn_max_m0.9",       # channel steepness
    "topo10_hs_lineament",      # 10 m hillshade lineaments
]


def q_norm(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Rank -> [0,1] within the valid mask; 0 outside."""
    out = np.zeros(a.shape, np.float32)
    x = a[valid]
    if x.size == 0:
        return out
    order = np.argsort(x, kind="stable")
    r = np.empty(x.size, np.float64)
    r[order] = np.arange(1, x.size + 1) / x.size
    out[valid] = r.astype(np.float32)
    return out


def load_u8(path: pathlib.Path, band: int) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as src:
        a = src.read(band).astype(np.float32)
        nodata = src.nodata
    valid = np.isfinite(a)
    if nodata is not None:
        valid &= (a != np.float32(nodata))
    valid &= (a > 0) if "scarp3m" in path.name and band == 7 else valid
    return a, valid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", type=int, nargs="+",
                    default=[20000, 40000, 80000, 120000, 200000, 300000])
    ap.add_argument("--vote-q", type=float, default=0.90)
    ap.add_argument("--out-dir", default="build/exp3")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()
    t0 = time.time()
    outdir = HERE / args.out_dir
    outdir.mkdir(parents=True, exist_ok=True)

    known, footprint = grid.load_catalogue(HERE / "data" / "labels.tif")
    cat3 = ndi.binary_dilation(known, iterations=3)
    eligible = footprint & ~cat3
    print(f"[e3] footprint {int(footprint.sum()):,}  eligible {int(eligible.sum()):,}")

    # ---------------------------------------------------------------- proxies
    with rasterio.open(EXT / "derived_sgmc_faults_100m.tif") as src:
        sgmc = (src.read(1) > 0) & footprint
    sgmc_off = sgmc & ~cat3
    dist_cat = edt(~known).astype(np.float32)
    dist_sgmc = edt(~sgmc_off).astype(np.float32)
    blanket_cat = float(kernel(dist_cat)[footprint].mean())
    blanket_sgmc = float(kernel(dist_sgmc).mean())
    print(f"[e3] blanket credit: cat {blanket_cat:.5f} (in footprint)  sgmc {blanket_sgmc:.5f}")

    # ---------------------------------------------------------------- scarp score
    acc = np.zeros(footprint.shape, np.float32)
    cnt = np.zeros(footprint.shape, np.float32)
    used = []
    LIDAR_BANDS = {1: "ex_max", 3: "step_max", 4: "lapneg_max", 5: "lappos_max",
                   6: "downface_max", 7: "upface_max", 8: "cross_max"}
    with rasterio.open(LIDAR) as src:
        for b, nm in LIDAR_BANDS.items():
            a, v = load_u8(LIDAR, b)
            q = q_norm(a, v & footprint)
            acc += q
            cnt += (v & footprint)
            used.append(f"lidar:{nm}")
        strike_l = src.read(6).astype(np.float32)
        valid_l = (src.read(12) > 0)
    with rasterio.open(SCARP3M) as src:
        for b, nm in ((1, "h_gate07"), (2, "h_gate12"), (3, "h_all"), (4, "sigma_mean")):
            a, v = load_u8(SCARP3M, b)
            q = q_norm(a, v & footprint)
            acc += q
            cnt += (v & footprint)
            used.append(f"scarp3m:{nm}")
        strike_s = src.read(6).astype(np.float32)
        cover_s = (src.read(7) > 0)
    scarp = np.where(cnt > 0, acc / np.maximum(cnt, 1.0), 0.0).astype(np.float32)

    # orientation agreement between the two products, where both cover
    both = cover_s & valid_l
    dtheta = np.abs(((strike_s - strike_l + 90.0) % 180.0) - 90.0) * (np.pi / 180.0)
    orient = np.where(both, np.cos(2.0 * dtheta).clip(0, 1), 1.0).astype(np.float32)

    # ---------------------------------------------------------------- corroboration vote
    vote = np.zeros(footprint.shape, np.float32)
    cov_fam = np.zeros(footprint.shape, np.float32)
    for lab in CORROBORATORS:
        q = np.load(FEAT / f"{lab}__s1.2__q.npy")
        v = q > 0
        if not v.any():
            continue
        thr = np.quantile(q[v], args.vote_q)
        vote += ((q >= thr) & footprint).astype(np.float32)
        cov_fam += v.astype(np.float32)
    print(f"[e3] corroborators with coverage: {int((cov_fam > 0).sum()):,} px "
          f"({time.time() - t0:.0f}s)")
    need = np.minimum(np.maximum(cov_fam * 0.5, 1.0), 2.0)   # >=1 vote where 1 family covers
    gate = np.clip(vote / need, 0.0, 1.0)

    score = (scarp * (0.35 + 0.65 * orient) * (0.40 + 0.60 * gate)).astype(np.float32)
    score[~eligible] = 0.0
    np.save(outdir / "score.npy", score)
    np.save(outdir / "scarp.npy", scarp)
    np.save(outdir / "gate.npy", gate)
    print(f"[e3] score ready: nonzero {int((score > 0).sum()):,}  "
          f"scarp>0 {int((scarp > 0).sum()):,} ({time.time() - t0:.0f}s)")

    # ---------------------------------------------------------------- emit + profile
    # import the shared emitter from exp2 (same object, not a copy)
    sys.path.insert(0, str(HERE / "scripts"))
    from exp2_arms import hardcore_greedy  # noqa: E402

    rows = []
    prev = 0
    for b in sorted(args.budgets):
        dots = hardcore_greedy(score, eligible, b)
        ys, xs = np.nonzero(dots)
        kk = kernel(dist_cat)[ys, xs].mean()
        ks = kernel(dist_sgmc)[ys, xs].mean()
        row = dict(budget=b, n_dots=int(ys.size), credit_cat=float(kk),
                   credit_sgmc=float(ks),
                   enrichment_cat=float(kk / blanket_cat),
                   enrichment_sgmc=float(ks / blanket_sgmc),
                   dcat_med_m=float(np.median(dist_cat[ys, xs]) * 100.0))
        rows.append(row)
        print(f"[e3] budget {b:>7,}: n={row['n_dots']:>7,}  credit_cat={kk:.4f} "
              f"(x{row['enrichment_cat']:.1f})  credit_sgmc={ks:.4f} "
              f"(x{row['enrichment_sgmc']:.1f})  dcat_med={row['dcat_med_m']:.0f}m  "
              f"({time.time() - t0:.0f}s)", flush=True)
        if args.name:
            np.save(outdir / f"{args.name}_{b}.npy", dots)
        prev = int(ys.size)

    prof = dict(experiment="E3 emission profile", generated_utc=time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        vote_q=args.vote_q, corroborators=CORROBORATORS, scarp_layers=used,
        blanket_credit=dict(cat=blanket_cat, sgmc=blanket_sgmc),
        rows=rows)
    p = HERE / "evidence" / "e3_emission_profile_20261011b.json"
    p.write_text(json.dumps(prof, indent=1) + "\n")
    print(f"[e3] wrote {p} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
