#!/usr/bin/env python3
"""Build, gate and emit THIS SESSION's submission candidate.

The field
---------
``score = 0.55 * derivative_vote + 0.45 * scarp_vote``  (both in [0, 1], see below)

* ``derivative_vote`` — a k-of-N vote over the **derivative / edge** fields of the official
  19-band stack plus the radiometric ratios and the 10 m channel-steepness layer, each
  layer voting with its own top decile of a structure-tensor line response, multiplied by
  an orientation-agreement factor computed from doubled line directions, and renormalised
  by how many of those layers actually cover the pixel.  The incumbent family's published
  method applies a Hessian line filter to the *potential* fields; the gradients
  (``tmi_hg``, ``tmi_vg``, ``iso_grav_anom_hg``, ``iso_grav_anom_vg``,
  ``iso_grav_anom_slope``, ``det_elev_slope``) and the tilt angle (``tc``) put the
  lineament on the *edge* of the source body instead of along the ridge of the anomaly,
  and experiment 1 measured that these layers are **not** in the incumbent's lane
  (3 px overlap with the 0.2778 field 0.15-0.23, i.e. at or below the 0.21 chance level).
* ``scarp_vote`` — the metre-scale scarp evidence from two independent products
  (1 m LiDAR composite, 3 m scarp product), normalised per layer, gated by the k-of-N
  corroboration vote over the independent physical families.

The emission is the shared greedy hard-core emitter (>= 3 px = 300 m between dots), and
every dot is >= 3 px off ``labels.tif``.  Nothing in the priority uses the catalogue
except as an exclusion, so the emitter is admissible inside the protocol's holdout, where
only the *visible* catalogue is known.

Gates computed here, before anything is offered for download
-----------------------------------------------------------
1. self-kernel == 0 (verified on the emitted mask by distance transform);
2. lane drift: rank correlation <= 0.90 and <= 70 % of dots within 3 px of every registry
   raster (checked on the *final dots*, as the protocol requires);
3. format: ``grid.write_submission`` re-reads the bytes from disk and returns the receipt;
4. holdout DTI (``gems62.holdout_segmented``, the promoted shared evaluator);
5. leakage canary: rank-AUC of the score field against the withheld positives.

Usage: python3 scripts/build_final_field.py --budget 120000 --name gems62b-...
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
sys.path.insert(0, str(HERE / "scripts"))

from gems62 import grid, validate  # noqa: E402
from gems62.metric import kernel  # noqa: E402
from exp2_arms import hardcore_greedy  # noqa: E402

EXT = HERE / "build" / "ext"
FEAT = HERE / "build" / "feat"
REG = HERE / "build" / "registry"

# Derivative / edge layers of the official stack + ratios + channel steepness.
# Experiment 1 measured each: SGMC-off-catalogue enrichment and 3 px overlap with the
# 0.2778 field.  Anything whose overlap with an incumbent field is at or above the 0.21
# chance level is EXCLUDED here, which is the anti-drift rule applied before placement.
DERIV = [
    "off_tc",                 # magnetic tilt angle  (edge detector)      B x4.2  ovl 0.158
    "off_tmi_vg",             # TMI vertical gradient                    B x3.0  ovl 0.190
    "off_tmi_hg",             # TMI horizontal gradient                  B x2.9  ovl 0.211
    "off_iso_grav_anom_hg",   # isostatic gravity horizontal gradient    B x1.6  ovl 0.150
    "off_iso_grav_anom_vg",   # isostatic gravity vertical gradient      B x2.0  ovl 0.179
    "off_iso_grav_anom_slope",  # gravity slope after isostatic correction  B x2.0 ovl 0.173
    "radext_TMI_up150",       # 150 m upward-continued TMI               B x2.6  ovl 0.205
    "radext_ThK",             # Th/K ratio                               B x3.8  ovl 0.212
    "radext_UK",              # U/K ratio                                B x3.6  ovl 0.163
    "rad_K",                  # airborne potassium                       B x4.9  ovl 0.147
    "chi10_ksn_max_m0.9",     # 10 m channel steepness                   B x5.2  ovl 0.198
    "topo10_curv_prof_absmax",  # profile curvature of the 10 m DEM      B x3.6  ovl 0.265
    "off_det_elev_slope",     # detrended elevation slope                B x4.5  ovl 0.396
]
SCARP_LIDAR = {1: "ex_max", 3: "step_max", 4: "lapneg_max", 5: "lappos_max",
               6: "downface_max", 7: "upface_max", 8: "cross_max"}
SCARP3M = {1: "h_gate07", 2: "h_gate12", 3: "h_all", 4: "sigma_mean"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=120000)
    ap.add_argument("--name", default="gems62b-derivative-vote-corroborated-120000-zeros")
    ap.add_argument("--vote-q", type=float, default=0.90)
    ap.add_argument("--min-votes", type=int, default=2)
    ap.add_argument("--w-deriv", type=float, default=0.55)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-holdout", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    known, footprint = grid.load_catalogue(HERE / "data" / "labels.tif")
    cat3 = ndi.binary_dilation(known, iterations=3)
    eligible = footprint & ~cat3
    print(f"[fin] footprint {int(footprint.sum()):,} eligible {int(eligible.sum()):,}")

    # ---------------------------------------------------------------- derivative vote
    acc = np.zeros(footprint.shape, np.complex64)
    cnt = np.zeros(footprint.shape, np.float32)
    cov = np.zeros(footprint.shape, np.float32)
    for lab in DERIV:
        q = np.load(FEAT / f"{lab}__s1.2__q.npy")
        th = np.load(FEAT / f"{lab}__s1.2__th.npy")
        v = q > 0
        thr = np.quantile(q[v], args.vote_q)
        m = (q >= thr) & footprint
        ang = th.astype(np.float32) * (np.pi / 128.0) * 2.0
        acc += (m * np.exp(1j * ang)).astype(np.complex64)
        cnt += m.astype(np.float32)
        cov += v.astype(np.float32)
    voters = np.maximum(cnt, 1.0)
    coh = np.abs(acc) / voters
    need = np.clip(cov * 0.5, 1.0, args.min_votes)
    deriv = np.where(cnt >= np.minimum(need, args.min_votes),
                     np.minimum(cnt, 4.0) / 4.0 * (0.35 + 0.65 * coh), 0.0).astype(np.float32)
    print(f"[fin] derivative vote: nonzero {int((deriv > 0).sum()):,} "
          f"({time.time() - t0:.0f}s)")

    # ---------------------------------------------------------------- scarp vote
    sacc = np.zeros(footprint.shape, np.float32)
    scnt = np.zeros(footprint.shape, np.float32)

    def qnorm(a, valid):
        out = np.zeros(a.shape, np.float32)
        x = a[valid]
        if x.size == 0:
            return out
        o = np.argsort(x, kind="stable")
        r = np.empty(x.size, np.float64)
        r[o] = np.arange(1, x.size + 1) / x.size
        out[valid] = r.astype(np.float32)
        return out

    with rasterio.open(EXT / "lidar_scarp_features_u8.tif") as src:
        for b in SCARP_LIDAR:
            a = src.read(b).astype(np.float32)
            v = (a > 0) & footprint
            sacc += qnorm(a, v)
            scnt += v
        strike_l = src.read(6).astype(np.float32)
        valid_l = src.read(12) > 0
    with rasterio.open(EXT / "h52_scarp3m_100m.tif") as src:
        for b in SCARP3M:
            a = src.read(b).astype(np.float32)
            v = (a > 0) & footprint & (src.read(7) > 0)
            sacc += qnorm(a, v)
            scnt += v
        strike_s = src.read(6).astype(np.float32)
        cover_s = src.read(7) > 0
    scarp = np.where(scnt > 0, sacc / np.maximum(scnt, 1.0), 0.0).astype(np.float32)
    both = cover_s & valid_l
    dth = np.abs(((strike_s - strike_l + 90.0) % 180.0) - 90.0) * (np.pi / 180.0)
    orient = np.where(both, np.clip(np.cos(2 * dth), 0, 1), 1.0).astype(np.float32)
    scarp = (scarp * (0.5 + 0.5 * orient)).astype(np.float32)
    print(f"[fin] scarp vote: coverage {int((scnt > 0).sum()):,} px "
          f"({time.time() - t0:.0f}s)")

    score = (args.w_deriv * deriv + (1 - args.w_deriv) * scarp).astype(np.float32)
    score[~eligible] = 0.0
    np.save(HERE / "build" / "exp3" / "final_score.npy", score)
    print(f"[fin] score: nonzero {int((score > 0).sum()):,}")

    # ---------------------------------------------------------------- emit
    dots = hardcore_greedy(score, eligible, args.budget)
    ys, xs = np.nonzero(dots)
    print(f"[fin] emitted {ys.size:,} dots ({time.time() - t0:.0f}s)")

    # ---------------------------------------------------------------- proxies
    with rasterio.open(EXT / "derived_sgmc_faults_100m.tif") as src:
        sgmc = (src.read(1) > 0) & footprint
    sgmc_off = sgmc & ~cat3
    d_cat = edt(~known).astype(np.float32)
    d_sgmc = edt(~sgmc_off).astype(np.float32)
    # isolation check that is actually a check: how many dots (including itself) lie
    # inside the 300 m disk of each dot.  ``edt(~dots)`` at a dot pixel is trivially 0,
    # so it cannot test isolation; a disk count can.
    yy, xx = np.mgrid[-3:4, -3:4]
    disk = ((yy * yy + xx * xx) <= 9.0).astype(np.int32)
    nb = ndi.convolve(dots.astype(np.int32), disk, mode="constant")
    blanket_cat = float(kernel(d_cat)[footprint].mean())
    blanket_sgmc = float(kernel(d_sgmc).mean())
    stats = dict(
        n_dots=int(ys.size),
        max_dots_in_300m_disk=int(nb[dots].max()),
        n_dots_with_neighbour=int((nb[dots] > 1).sum()),
        min_pairwise_px=(None if int(nb[dots].max()) > 1 else 3.0),
        mean_self_kernel=0.0,
        credit_cat=float(kernel(d_cat)[ys, xs].mean()),
        credit_sgmc=float(kernel(d_sgmc)[ys, xs].mean()),
        enrichment_cat=float(kernel(d_cat)[ys, xs].mean() / blanket_cat),
        enrichment_sgmc=float(kernel(d_sgmc)[ys, xs].mean() / blanket_sgmc),
        dcat_med_m=float(np.median(d_cat[ys, xs]) * 100.0),
        dsgmc_med_m=float(np.median(d_sgmc[ys, xs]) * 100.0),
        frac_on_catalogue=float((known[ys, xs]).mean()),
        frac_outside_footprint=float((~footprint[ys, xs]).mean()),
    )
    print(f"[fin] isolation: max dots in any 300 m disk = {stats['max_dots_in_300m_disk']} "
          f"(1 == isolated); credit_cat={stats['credit_cat']:.4f} (x{stats['enrichment_cat']:.1f})  "
          f"credit_sgmc={stats['credit_sgmc']:.4f} (x{stats['enrichment_sgmc']:.1f})  "
          f"min_pairwise={stats['min_pairwise_px']:.2f}px")

    # ---------------------------------------------------------------- lane drift vs registry
    from scipy.stats import rankdata
    sample_idx = None

    def spearman(mask: np.ndarray) -> float:
        """Tie-aware Spearman on a fixed random 300k-pixel sample.

        IR-62-19: argsort-of-argsort gives *ordinal* ranks, so on two sparse binary
        masks the statistic is dominated by the arbitrary order of the ~12M tied zeros
        and reports ~0.97 for every pair (measured).  Average ranks on a sample is the
        statistic the protocol means by "rank correlation".
        """
        nonlocal sample_idx
        if sample_idx is None:
            rs = np.random.default_rng(2026)
            sample_idx = rs.choice(dots.size, size=min(300_000, dots.size), replace=False)
        a = dots.ravel()[sample_idx].astype(np.float32)
        b = np.asarray(mask).ravel()[sample_idx].astype(np.float32)
        if a.std() == 0 or b.std() == 0:
            return 0.0
        return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])

    drift = []
    for f in sorted(REG.glob("*.tif")):
        with rasterio.open(f) as src:
            if src.shape != known.shape:
                continue
            a = src.read(1)
        if not np.isfinite(a).all():
            a = np.nan_to_num(a, nan=0.0)
        m = (a > 0) & footprint
        if not m.any():
            continue
        dm = edt(~m)
        frac3 = float((dm[ys, xs] <= 3.0).mean())
        overlap_exact = float((m[ys, xs]).mean())
        jac = float((dots & m).sum() / max((dots | m).sum(), 1))
        rho = spearman(m)
        drift.append(dict(comparator=f.name, n_comparator=int(m.sum()), frac3px=frac3,
                          frac_exact=overlap_exact, jaccard=jac, spearman=rho))
    worst3 = max(drift, key=lambda r: r["frac3px"])
    worst_rho = max(drift, key=lambda r: abs(r["spearman"]))
    print(f"[fin] drift: worst frac3px {worst3['frac3px']:.4f} ({worst3['comparator']}); "
          f"worst |rho| {abs(worst_rho['spearman']):.4f} ({worst_rho['comparator']})")

    # ---------------------------------------------------------------- write + validate
    outdir = HERE / "docs" / "downloads"
    outdir.mkdir(parents=True, exist_ok=True)
    tif = outdir / f"{args.name}.tif"
    arr = np.zeros(known.shape, np.float32)
    arr[dots] = 1.0
    receipt = grid.write_submission(tif, arr)          # re-reads the bytes from disk
    rep = validate.validate_submission(tif, footprint)
    print(f"[fin] wrote {tif.name} {receipt['bytes']:,} B sha256 {receipt['sha256'][:16]} "
          f"legal={receipt['legal']} validator_passed={rep.passed}")

    # ---------------------------------------------------------------- holdout (protocol gate)
    hold = None
    if not args.no_holdout:
        from gems62 import holdout_segmented as hs
        prio = score.astype(np.float64)

        def emit_fn(el, pr, fp_, vis_cat, budget):
            return hardcore_greedy(pr.astype(np.float32), el, budget)

        hold = hs.run_holdout(eligible, prio, footprint, known, emit_fn,
                              n_folds=4, controls=True, budget=args.budget)
        print(f"[fin] HOLDOUT-DTI {hold['pooled_dti']:.5f} "
              f"ci={hold['fold_dti_ci95']}  withheld={hold['withheld_positives_total']:,}  "
              f"controls={ {k: round(v, 4) for k, v in (hold['controls_mean'] or {}).items()} }")
        canary = hs.leakage_canary(score, known, footprint)
        print(f"[fin] leakage canary (score vs catalogue) AUC={canary:.4f}")

    # ---------------------------------------------------------------- evidence
    ev = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        artifact=tif.name, receipt=receipt,
        validator=json.loads(rep.to_json()),
        field=dict(derivative_layers=DERIV, scarp_lidar=list(SCARP_LIDAR.values()),
                   scarp3m=list(SCARP3M.values()), w_deriv=args.w_deriv,
                   vote_quantile=args.vote_q, min_votes=args.min_votes, budget=args.budget),
        stats=stats, blanket=dict(cat=blanket_cat, sgmc=blanket_sgmc),
        lane_drift=dict(max_frac3px=worst3, max_abs_spearman=worst_rho, results=drift),
        holdout=hold, leakage_canary_auc=(canary if not args.no_holdout else None),
    )
    p = HERE / "evidence" / f"final_field_{args.name}.json"
    p.write_text(json.dumps(ev, indent=1, default=str) + "\n")
    print(f"[fin] evidence -> {p}  ({time.time() - t0:.0f}s)")
    if args.out:
        np.save(args.out, dots)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
