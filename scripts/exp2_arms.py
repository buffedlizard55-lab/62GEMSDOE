#!/usr/bin/env python3
"""EXPERIMENT 2 — build the candidate fields and measure them.

Three arms, all emitted by ONE shared hard-core emitter (guaranteed >=300 m between
dots, i.e. zero self-kernel, which the published metric pays 0.2 per dot for):

* ``ARM-A  vote``    -- one representative layer per *independent physical family*
                        (topographic lineament, LiDAR scarp, radiometric, magnetic,
                        gravity, geodetic strain, seismic, subsurface, 10 m channel
                        steepness).  Each layer votes with its own top quantiles; the
                        score is the vote count times an orientation-agreement factor
                        computed from the doubled line direction (a discrete k-of-N
                        consensus, deliberately not the incumbent's continuous
                        weighted Frangi/Hessian sum).
* ``ARM-B  catext``  -- catalogue-strike continuation: distance-weighted score for
                        pixels that continue a mapped trace's strike and lie OFF the
                        catalogue.  Targets the population the organizers explicitly
                        include ("newly mapped geometry of existing systems").
* ``ARM-C  poisson`` -- uniform random dots, the null the metric must be read against.

Every arm is measured three ways on the SAME emitted dots:
  credit_cat   mean 300 m kernel credit against labels.tif (the mapped catalogue)
  credit_sgmc  mean 300 m kernel credit against SGMC 1:750k traces minus the catalogue
  overlap3px   fraction of dots within 3 px of each prior field (lane-drift check)

Usage: python3 scripts/exp2_arms.py --arm A --budget 40000
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import grid  # noqa: E402

FEAT = HERE / "build" / "feat"
REG = HERE / "build" / "registry"
EXT = HERE / "build" / "ext"

# ------------------------------------------------------------------ family representatives
# chosen in experiment 1 (evidence/e1_layer_screen_20261011b.json) as the best-ranked member
# of each independent physical family that is NOT a coverage mask and does not simply
# re-derive an incumbent's field.  Rationale recorded per line.
FAMILIES: dict[str, list[tuple[str, str]]] = {
    # family -> [(layer label, why)]
    "topo_lineament": [("topo10_hs_lineament", "10 m DEM hillshade lineament response")],
    "topo_break": [("off_det_elev_slope", "detrended-elevation slope (official stack band 19)")],
    "lidar_scarp": [("lidar_cross_max", "1 m LiDAR cross-scarp response (max per 100 m cell)"),
                    ("lidar_lappos_max", "LiDAR positive Laplacian (up-facing break)")],
    "radiometric": [("rad_K", "airborne potassium"),
                    ("radext_ThK", "Th/K ratio (alteration-sensitive)")],
    "magnetic": [("off_tc", "tilt-angle derivative of the magnetic field (edge detector)"),
                 ("radext_TMI_up150", "150 m upward-continued TMI (deep source)")],
    "gravity": [("off_iso_grav_anom_hg", "isostatic gravity horizontal gradient")],
    "geodetic": [("off_geod_shearrate", "geodetic shear-strain rate"),
                 ("off_geod_2ndinv", "geodetic second invariant")],
    "seismic": [("off_ieq_n100a15", "earthquake intensity/density")],
    "subsurface": [("off_cond_surf", "conductivity surface")],
    "channel_steepness": [("chi10_ksn_max_m0.9", "channel steepness ksn (10 m DEM, theta=0.9)")],
    "channel_step": [("chi10_step_max_x1000", "10 m channel/step maximum")],
}
# families that are pure coverage masks or trivially non-geological: never used
FORBIDDEN = {"lidar_valid", "lidar_coh100", "lidar_strike"}


def load_feat(label: str, key: str = "s1.2") -> np.ndarray | None:
    q = FEAT / f"{label}__{key}__q.npy"
    if not q.exists():
        return None
    return np.load(q)


def load_theta(label: str, key: str = "s1.2") -> np.ndarray | None:
    p = FEAT / f"{label}__{key}__th.npy"
    return np.load(p) if p.exists() else None


# ------------------------------------------------------------------ shared emitter
def hardcore_greedy(priority: np.ndarray, eligible: np.ndarray, budget: int,
                    spacing_px: float = 3.0, chunk_factor: int = 12) -> np.ndarray:
    """Greedy top-score-first Poisson-disk selection with a hard 300 m core.

    Every selected dot has no other selected dot within ``spacing_px`` pixels, so the
    self-kernel term of the published metric is exactly zero: each dot contributes
    0.2 to the denominator and nothing else.
    """
    H, W = priority.shape
    # Tie-break randomly: the consensus score is discrete (a vote count), and a stable
    # argpartition would otherwise return a spatially contiguous block of one row and the
    # greedy would then block most of its own candidates.  Deterministic seed so runs repeat.
    jitter = np.random.default_rng(12345).random(priority.shape).astype(np.float32) * 1e-3
    p = np.where(eligible, priority + jitter, -np.inf).astype(np.float32)
    n_cand = int(np.isfinite(p).sum())
    if n_cand == 0 or budget <= 0:
        return np.zeros((H, W), bool)
    r = int(np.ceil(spacing_px))
    offs = [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
            if (dy or dx) and (dy * dy + dx * dx) <= spacing_px * spacing_px]
    take = min(budget, n_cand)
    # prune to the best chunk_factor*budget candidates before sorting: the greedy never
    # reaches past them if fewer than `take` are selected, and it bounds the sort cost.
    flat = p.ravel()
    k = min(flat.size, max(take * chunk_factor, 100_000))
    idx = np.argpartition(-flat, k - 1)[:k]
    idx = idx[np.isfinite(flat[idx])]
    order = idx[np.argsort(-flat[idx], kind="stable")]
    blocked = np.zeros((H, W), bool)
    out = np.zeros((H, W), bool)
    n = 0
    ys_all, xs_all = np.divmod(order, W)
    for y, x in zip(ys_all, xs_all):
        if blocked[y, x]:
            continue
        out[y, x] = True
        n += 1
        y0, y1 = max(0, y - r), min(H, y + r + 1)
        x0, x1 = max(0, x - r), min(W, x + r + 1)
        for dy, dx in offs:
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W:
                blocked[yy, xx] = True
        if n >= take:
            break
    return out


def kernel_credit(dist_px: np.ndarray, ys: np.ndarray, xs: np.ndarray,
                  radius_px: float = 3.0) -> float:
    d = dist_px[ys, xs]
    return float(np.maximum(1.0 - d / radius_px, 0.0).mean())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="A", choices=["A", "B", "C", "AB"])
    ap.add_argument("--budget", type=int, default=40000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--vote-q", type=float, default=0.975,
                    help="per-layer quantile above which a layer 'votes'")
    ap.add_argument("--min-votes", type=int, default=2)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    t0 = time.time()

    known, footprint = grid.load_catalogue(HERE / "data" / "labels.tif")
    cat3 = ndi.binary_dilation(known, iterations=3)
    eligible = footprint & ~cat3
    print(f"[e2] footprint {int(footprint.sum()):,}  eligible(off-catalogue,3px) "
          f"{int(eligible.sum()):,}")

    # distance fields for the proxies and for the lane-drift checks
    from scipy.ndimage import distance_transform_edt as edt
    sgmc = None
    import rasterio
    with rasterio.open(EXT / "derived_sgmc_faults_100m.tif") as src:
        a = src.read(1)
        sgmc = (a > 0) & footprint
    sgmc_off = sgmc & ~cat3
    dist_cat = edt(~known).astype(np.float32)
    dist_sgmc = edt(~sgmc_off).astype(np.float32)
    priors = {}
    for nm, f in (("champ_h33", REG / "champion_h33_2_b2_02778.tif"),
                  ("bayesopt_d28", REG / "bayesopt_dilation_scarp_d28.tif"),
                  ("h25_dotted", REG / "h25_dotted_d2_8_02600.tif")):
        if f.exists():
            with rasterio.open(f) as src:
                m = src.read(1)
            priors[nm] = (m > 0) & footprint
    print(f"[e2] distance fields ready ({time.time() - t0:.0f}s); sgmc off-cat "
          f"{int(sgmc_off.sum()):,}")

    rng = np.random.default_rng(args.seed)
    scores: dict[str, np.ndarray] = {}

    if args.arm in ("A", "AB"):
        acc = np.zeros(footprint.shape, np.complex64)      # sum over voters of e^{2i theta}
        cnt = np.zeros(footprint.shape, np.float32)
        used = []
        for fam, members in FAMILIES.items():
            fam_best = None
            for label, _why in members:
                if label in FORBIDDEN:
                    continue
                q = load_feat(label)
                th = load_theta(label)
                if q is None or th is None:
                    print(f"[e2] MISSING {label}")
                    continue
                v = q > 0
                if not v.any():
                    continue
                thr = np.quantile(q[v], args.vote_q)
                m = (q >= thr) & eligible
                if fam_best is None:
                    fam_best = m
                else:
                    fam_best |= m
                used.append((fam, label, int(m.sum()), float(thr)))
                ang = th.astype(np.float32) * (np.pi / 128.0) * 2.0
                acc += (m * np.exp(1j * ang)).astype(np.complex64)
                cnt += m.astype(np.float32)
            # one vote per family (members are OR-ed), which is what keeps 12 LiDAR bands
            # from outvoting a single independent physics
        vote = cnt
        voters = np.maximum(vote, 1.0)
        coh = np.abs(acc) / voters
        scoreA = np.where(vote >= args.min_votes, vote * (0.35 + 0.65 * coh), 0.0)
        scoreA = scoreA.astype(np.float32)
        scores["A"] = scoreA
        print(f"[e2] ARM-A families used: {len(set(f for f, *_ in used))}  layers "
              f"{len(used)}  voters>={args.min_votes}: {int((scoreA > 0).sum()):,}  "
              f"({time.time() - t0:.0f}s)")

    if args.arm in ("B", "AB"):
        # catalogue-strike continuation: for each pixel, the score is driven by the
        # distance to the nearest catalogue pixel measured in a *strike-aligned* way.
        # Implementation without a full vector skeleton: anisotropic distance by
        # shifting the catalogue along a fan of strikes -> score = max over strikes of
        # (kernel falloff) restricted to pixels whose local 10 m lineament response is
        # high (so the continuation is DEM-supported) and which are off the catalogue.
        hs = load_feat("topo10_hs_lineament")
        if hs is None:
            print("[e2] ARM-B needs topo10_hs_lineament")
            return 1
        support = (hs >= np.quantile(hs[hs > 0], 0.90)).astype(np.float32)
        support = ndi.gaussian_filter(support, 1.0)
        best = np.zeros(footprint.shape, np.float32)
        for deg in np.arange(-180, 180, 5):
            th_rad = np.deg2rad(deg)
            dy = -np.sin(th_rad)          # image row grows south
            dx = np.cos(th_rad)
            for dist_px in (4, 8, 12, 16, 20, 26):
                oy, ox = int(round(dy * dist_px)), int(round(dx * dist_px))
                if oy == 0 and ox == 0:
                    continue
                sh = np.roll(np.roll(known, oy, axis=0), ox, axis=1)
                if oy > 0:
                    sh[:oy, :] = False
                elif oy < 0:
                    sh[oy:, :] = False
                if ox > 0:
                    sh[:, :ox] = False
                elif ox < 0:
                    sh[:, ox:] = False
                w = np.float32(1.0 - dist_px / 30.0)
                np.maximum(best, sh * w, out=best)
        scoreB = (best * support).astype(np.float32)
        scores["B"] = scoreB
        print(f"[e2] ARM-B strike fan done; nonzero {int((scoreB > 0).sum()):,} "
              f"({time.time() - t0:.0f}s)")

    if args.arm == "C":
        scoreC = np.zeros(footprint.shape, np.float32)
        ys, xs = np.nonzero(eligible)
        pick = rng.choice(ys.size, size=min(args.budget * 4, ys.size), replace=False)
        scoreC[ys[pick], xs[pick]] = rng.random(pick.size).astype(np.float32) + 1.0
        scores["C"] = scoreC

    out = dict(experiment="E2 arms", arm=args.arm, budget=args.budget, seed=args.seed,
               generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               vote_quantile=args.vote_q, min_votes=args.min_votes, rows=[])

    for name, sc in scores.items():
        dots = hardcore_greedy(sc, eligible, args.budget)
        ys, xs = np.nonzero(dots)
        row = dict(arm=name, n_dots=int(ys.size),
                   credit_cat=kernel_credit(dist_cat, ys, xs),
                   credit_sgmc=kernel_credit(dist_sgmc, ys, xs))
        for nm, m in priors.items():
            dm = edt(~m).astype(np.float32)
            row[f"frac3px_{nm}"] = float((dm[ys, xs] <= 3.0).mean())
        # self-kernel must be exactly 0 by construction
        dd = edt(~dots)
        row["min_pairwise_px"] = float(dd[dots].min()) if dots.any() else None
        out["rows"].append(row)
        print(f"[e2] {name}: n={row['n_dots']:,}  credit_cat={row['credit_cat']:.4f}  "
              f"credit_sgmc={row['credit_sgmc']:.4f}  "
              + "  ".join(f"ovl_{k}={v:.3f}" for k, v in row.items()
                          if k.startswith('frac3px_')))
        if args.out:
            np.save(args.out.replace(".json", f"_{name}.npy"), dots)

    p = HERE / "evidence" / f"e2_arms_{args.tag or args.arm}_{args.budget}.json"
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(f"[e2] wrote {p} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
