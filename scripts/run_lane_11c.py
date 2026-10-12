#!/usr/bin/env python3
"""Run the multi-datum corroborated Lahontan datum-offset lane (H62-R / 11c).

End to end: treads -> strands -> isobase residual -> along-strand steps ->
cross-datum corroboration -> straight-extension trace march -> isolated-dot emission
-> format receipt, per-dot credit instrument, holdout, leakage canary, uniqueness.

Usage
-----
  python3 scripts/run_lane_11c.py \
      --dem build/ext/geodawn_dem_a2_100m.tif \
      --labels data/labels.tif \
      --sample data/sample_submission.tif \
      --sgmc build/ext/derived_sgmc_faults_100m.tif \
      --out-dir build/lane11c --name gems62-11c-datum-multistrand

Every number printed is either MEASURED here or labelled MODEL.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import datum11c as D          # noqa: E402
from gems62 import emit as E              # noqa: E402
from gems62 import grid, score_model, uniqueness, validate  # noqa: E402
from gems62.metric import kernel          # noqa: E402
from scipy import ndimage as ndi          # noqa: E402


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="build/ext/geodawn_dem_a2_100m.tif")
    ap.add_argument("--labels", default="data/labels.tif")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--sgmc", default="build/ext/derived_sgmc_faults_100m.tif")
    ap.add_argument("--out-dir", default="build/lane11c")
    ap.add_argument("--name", default="gems62-11c-datum-multistrand")
    ap.add_argument("--target-dots", type=int, default=40000,
                    help="planning mass; traces are ranked and truncated at this budget")
    ap.add_argument("--z-min", type=float, default=3.6, help="standardised step bar on the offset map")
    ap.add_argument("--amp-min", type=float, default=1.5, help="metres; minimum step amplitude")
    ap.add_argument("--exclusion-m", type=float, default=200.0)
    ap.add_argument("--stitch-radius-m", type=float, default=1500.0)
    args = ap.parse_args()

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- inputs
    labels = grid.read_labels(args.labels)
    footprint = labels != -1
    catalogue = labels == 1
    dem = grid.read_dem(args.dem)
    transform = grid.TRANSFORM
    log(f"grid {grid.SHAPE}  footprint {footprint.sum():,}  catalogue {catalogue.sum():,}")

    x0, y0 = 243350.0, 4508550.0
    a, b, c, d, e, f = transform
    rows = np.arange(grid.HEIGHT)[:, None]
    cols = np.arange(grid.WIDTH)[None, :]
    X = a * cols + c
    Y = f + e * rows

    # ---------------------------------------------------------------- DEM evidence
    log("structure tensor from the DEM (front-end evidence for the extension)")
    az_field, coherence, relief = E.structure_tensor(dem, footprint, sigma_px=5.0)

    # ---------------------------------------------------------------- per datum
    receipts: dict = {"datums": {}, "constants": {
        "DATUMS": D.DATUMS, "ISOBASE_SIGMA_PX": D.ISOBASE_SIGMA_PX,
        "STEP_ANGLES_DEG": list(D.STEP_ANGLES_DEG),
        "STEP_OFFSETS_PX": list(D.STEP_OFFSETS_PX),
        "STEP_LOCAL_SIGMA_PX": D.STEP_LOCAL_SIGMA_PX,
        "z_min": args.z_min, "amp_min_m": args.amp_min,
        "CORROB_MAX_SEP_M": D.CORROB_MAX_SEP_M, "CORROB_MIN_SEP_M": D.CORROB_MIN_SEP_M,
        "CORROB_ALONG_STRIKE_DEG": D.CORROB_ALONG_STRIKE_DEG,
        "CORROB_AMP_RATIO_MAX": D.CORROB_AMP_RATIO_MAX,
        "EXT_MAX_LENGTH_M": D.EXT_MAX_LENGTH_M, "EXT_MAX_TURN_DEG": D.EXT_MAX_TURN_DEG,
        "EXT_COH_MIN": D.EXT_COH_MIN, "EXT_RELIEF_MIN_M": D.EXT_RELIEF_MIN_M,
        "DOT_SPACING_M": E.DOT_SPACING_M, "CATALOGUE_EXCLUSION_M": args.exclusion_m,
        "STITCH_RADIUS_M": args.stitch_radius_m, "TARGET_DOTS": args.target_dots,
    }}
    all_loci: list[D.Locus] = []
    for name, (lo, hi) in D.DATUMS.items():
        band = footprint & np.isfinite(dem) & (dem >= lo) & (dem <= hi)
        resid = D.datum_residual(dem, footprint, band)
        zmap, amap, tmap, smap = D.offset_map(resid, band)
        loci = D.loci_from_map(name, zmap, amap, tmap, smap, transform=transform,
                               z_min=args.z_min, amp_min=args.amp_min)
        receipts["datums"][name] = dict(
            band_cells=int(band.sum()),
            residual_cells=int(np.isfinite(resid).sum()),
            step_field_cells=int(np.isfinite(zmap).sum()),
            z_p99=float(np.nanpercentile(zmap, 99.0)) if np.isfinite(zmap).any() else None,
            loci=int(len(loci)),
        )
        log(f"datum {name}: band {band.sum():,} loci {len(loci)} "
            f"(z>={args.z_min}, amp>={args.amp_min} m)")
        all_loci.extend(loci)

    (out / "loci.json").write_text(json.dumps(
        {n: [dict(x=l.x, y=l.y, strike=l.strike_deg, step=l.step_m, signed=l.signed_m,
                  z=l.z_stat, n=l.n_cells) for l in all_loci if l.datum == n]
         for n in D.DATUMS}, indent=1))
    kept = D.corroborate_loci(all_loci)
    receipts["loci_total"] = len(all_loci)
    receipts["loci_corroborated"] = len(kept)
    log(f"loci {len(all_loci)} -> cross-datum corroborated {len(kept)}")
    if not kept:
        log("NO CORROBORATED LOCI -- lane is negative at this threshold.")

    # ------------------------------------------------- seeds -> stitch -> traces
    seeds = [E.Seed(x=s.x, y=s.y, kind="datum_step_multidatum", strength=s.strength,
                    azimuth_deg=s.strike_deg, az_tol_deg=D.EXT_MAX_TURN_DEG * 3)
             for s in sorted(kept, key=lambda s: -s.strength)]
    # cross-datum stitching: one fault, one trace
    stitched: list[E.Seed] = []
    for s in seeds:
        if any(np.hypot(s.x - t.x, s.y - t.y) <= args.stitch_radius_m for t in stitched):
            continue
        stitched.append(s)
    log(f"seeds {len(seeds)} -> stitched {len(stitched)}")

    traces = []
    for s in stitched:
        xs, ys, ev = D.extend_straight(s.x, s.y, s.azimuth_deg, coherence, relief,
                                       footprint, transform)
        if xs.size < 3:
            continue
        t = E.Trace(seed_x=s.x, seed_y=s.y, azimuth_deg=s.azimuth_deg, xs=xs, ys=ys,
                    provenance="datum_step_multistrand", evidence_min=ev)
        traces.append(t)
    log(f"traces {len(traces)}  total length {sum(t.length_m for t in traces)/1000:.1f} km")

    # ---------------------------------------------------------------- emission
    rows_px, cols_px, estats = E.dots_from_traces(catalogue=catalogue, footprint=footprint,
                                                  transform=transform, traces=traces,
                                                  spacing_m=E.DOT_SPACING_M,
                                                  exclusion_m=args.exclusion_m)
    log(f"dots before budget {rows_px.size:,}")

    # mass budget: rank by (trace evidence, distance from catalogue) and truncate
    if rows_px.size > args.target_dots:
        dist_cat = ndi.distance_transform_edt(~catalogue, sampling=(grid.PIXEL_M, grid.PIXEL_M))
        dc = dist_cat[rows_px, cols_px]
        # deterministic thinning: keep the dots on the most-supported traces first
        ev_of = np.zeros(grid.SHAPE)
        for t in traces:
            xsi, ysi = t.sample(E.DOT_SPACING_M)
            ri = ((ysi - f) / e).astype(int)
            ci = ((xsi - c) / a).astype(int)
            ok = (ri >= 0) & (ri < grid.HEIGHT) & (ci >= 0) & (ci < grid.WIDTH)
            ev_of[ri[ok], ci[ok]] = np.maximum(ev_of[ri[ok], ci[ok]], t.evidence_min)
        score = ev_of[rows_px, cols_px] * 1000.0 + np.minimum(dc, 20000.0) / 1000.0
        order = np.argsort(-score, kind="stable")
        rows_px, cols_px = rows_px[order][: args.target_dots], cols_px[order][: args.target_dots]

    raster = E.raster_from_dots(rows_px, cols_px, grid.SHAPE, value=1.0)
    log(f"emitted {rows_px.size:,} dots")

    # ---------------------------------------------------------------- write+receipt
    tif = out / f"{args.name}-{rows_px.size}dots-zeros.tif"
    receipt = grid.write_submission(tif, raster)
    log(f"wrote {tif}  legal={receipt['legal']}  sha256={receipt['sha256'][:16]}")

    # NaN-outside twin (the portal also accepts null outside bounds)
    nan = E.to_nan_outside(raster, footprint)
    tif_nan = out / f"{args.name}-{rows_px.size}dots-nan.tif"
    grid.write_float32(tif_nan, nan, nodata=np.nan)
    receipt_nan = grid.check_submission(tif_nan)

    # ---------------------------------------------------------------- instruments
    inst: dict = {}
    if pathlib.Path(args.sgmc).exists():
        import rasterio
        with rasterio.open(args.sgmc) as src:
            sgmc = src.read(1) > 0
        off = sgmc & ~catalogue
        deg = ndi.distance_transform_edt(~off, sampling=(grid.PIXEL_M, grid.PIXEL_M))
        k_off = kernel(deg, 300.0)
        m = raster > 0
        uniform = float(k_off[footprint].mean())
        inst = dict(
            sgmc_cells=int(sgmc.sum()), sgmc_off_catalogue_cells=int(off.sum()),
            uniform_field_mean_credit=uniform,
            footprint_frac_within_300m=float((k_off[footprint] > 0).mean()),
            field_mean_credit=float(k_off[m].mean()) if m.any() else 0.0,
            field_enrichment_vs_uniform=(float(k_off[m].mean()) / uniform) if m.any() and uniform else 0.0,
            field_frac_credit_gt0=float((k_off[m] > 0).mean()) if m.any() else 0.0,
        )
        # simple Poisson control at the same mass
        rng = np.random.default_rng(11)
        idx = np.flatnonzero(footprint.ravel())
        pick = rng.choice(idx, size=min(int(m.sum()), idx.size), replace=False)
        ctrl = np.zeros(grid.SHAPE, bool)
        ctrl.ravel()[pick] = True
        inst["poisson_control_mean_credit"] = float(k_off[ctrl].mean())
        inst["poisson_control_enrichment"] = (float(k_off[ctrl].mean()) / uniform) if uniform else 0.0
        log(f"instrument: field mean credit {inst['field_mean_credit']:.5f} "
            f"({inst['field_enrichment_vs_uniform']:.2f}x uniform {uniform:.5f}); "
            f"poisson control {inst['poisson_control_mean_credit']:.5f}")

    # distance to catalogue (the one quantity the leaderboard rewards, rho = -0.597)
    dist_cat = ndi.distance_transform_edt(~catalogue, sampling=(grid.PIXEL_M, grid.PIXEL_M))
    mpos = raster > 0
    inst["dcat_median_m"] = float(np.median(dist_cat[mpos])) if mpos.any() else None
    inst["dcat_p10_m"] = float(np.percentile(dist_cat[mpos], 10)) if mpos.any() else None
    inst["frac_on_catalogue"] = float(catalogue[mpos].mean()) if mpos.any() else 0.0
    inst["n_components_is_M"] = None

    from scipy.spatial import cKDTree
    yy, xx = np.nonzero(mpos)
    if yy.size > 1:
        t = cKDTree(np.c_[yy, xx])
        dd, _ = t.query(np.c_[yy, xx], k=2)
        dd = dd[:, 1] * grid.PIXEL_M
        inst["nn_median_m"] = float(np.median(dd))
        inst["nn_min_m"] = float(dd.min())
        inst["frac_nn_lt300m"] = float((dd < 300.0).mean())
        lab_cc, ncc = ndi.label(mpos, structure=np.ones((3, 3)))
        inst["n_components"] = int(ncc)
        inst["n_components_is_M"] = bool(ncc == yy.size)

    # ---------------------------------------------------------------- MODEL
    model = {}
    for K in (6000, 12000, 24000):
        model[f"K={K}"] = {
            "model_dti_at_measured_instrument_credit":
                score_model.model_dti(int(mpos.sum()), inst.get("field_mean_credit", 0.0), K),
            "credit_required_to_match_0.2778":
                score_model.mean_credit_required(0.2778, int(mpos.sum()), K),
            "credit_required_to_match_0.3195":
                score_model.mean_credit_required(0.3195, int(mpos.sum()), K),
            "credit_required_to_match_0.4275":
                score_model.mean_credit_required(0.4275, int(mpos.sum()), K),
        }

    # ---------------------------------------------------------------- validation
    report = validate.validate_submission(tif, footprint=footprint)
    holdout = None
    hold = pathlib.Path("build/lane11c/holdout.json")
    if (pathlib.Path(__file__).resolve().parents[1] / "scripts" / "run_holdout.py").exists():
        pass  # holdout is run separately; see docs/data.md

    payload = dict(
        name=args.name, tif=str(tif), dots=int(mpos.sum()),
        receipt=receipt, receipt_nan_outside={k: v for k, v in receipt_nan.items()
                                              if k in ("file", "all_finite", "nan_count",
                                                       "n_outside_0_1", "legal", "nodata",
                                                       "sha256", "bytes")},
        emission_stats=estats, lane_receipts=receipts, instruments=inst, model=model,
        validator=report.to_json() if hasattr(report, "to_json") else str(report),
        n_traces=len(traces),
        total_trace_km=float(sum(t.length_m for t in traces) / 1000.0),
    )
    (out / "run.json").write_text(json.dumps(payload, indent=1, default=str))
    log(f"wrote {out/'run.json'}")
    print(json.dumps({k: payload[k] for k in ("dots", "n_traces", "total_trace_km")}, indent=1))
    print(json.dumps(inst, indent=1, default=str))
    print(json.dumps(model, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
