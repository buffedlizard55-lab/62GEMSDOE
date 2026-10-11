"""Run the datum-offset lane end to end and write the submission GeoTIFF.

Pipeline
--------
1. Load the competition grid (labels, DEM) and the official feature stack.
2. Map the Lahontan highstand datum: wave-planed cells inside the published
   deformed-elevation window, reduced to one observation per bench.
3. Fit a robust smooth isobase (2-D polynomial) to the bench elevations.
4. Flag abrupt steps and lateral deflections of the datum.
5. Seed a trace at each flagged offset and extend it while DEM lineament
   evidence supports it.
6. Emit kernel-matched unit dots with a catalogue exclusion.
7. Validate the raster, check lane uniqueness against the registry, write the
   run card, profiles and diagnostics.

Usage:
    python scripts/run_lane.py --data /tmp/gems/data --registry /tmp/gems/registry \
        --out docs/downloads
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems62 import emit, lahontan, validate  # noqa: E402
from gems62.grid import (  # noqa: E402
    CATALOGUE_CELLS,
    FOOTPRINT_CELLS,
    TRANSFORM,
    load_scene,
    write_float32,
)
from gems62 import holdout as holdout_mod  # noqa: E402
from gems62 import score_model  # noqa: E402
from gems62.uniqueness import compare, dump as dump_uniqueness, verdict  # noqa: E402

RUN_NAME = "gems62-lahontan-isobase"


def save_profile_png(rows: list[dict], out: Path, title: str,
                     label: str = "") -> None:
    """Render the elevation-versus-distance profile (main deliverable figure)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # pragma: no cover
        return
    W, H = 1400, 720
    img = Image.new("RGB", (W, H), (12, 14, 20))
    d = ImageDraw.Draw(img)
    L, R, T, B = 90, W - 60, 70, H - 110
    if not rows:
        d.text((L, T), "no benches survived the datum filters", fill=(230, 120, 120))
        img.save(out)
        return
    xs = np.array([r["distance_track_m"] for r in rows], dtype=float)
    zs = np.array([r["elevation_m"] for r in rows], dtype=float)
    ib = np.array([r["isobase_m"] for r in rows], dtype=float)
    res = np.array([r["residual_m"] for r in rows], dtype=float)
    x0, x1 = 0.0, max(xs.max(), 1.0)
    lo = float(min(zs.min(), ib.min())) - 3.0
    hi = float(max(zs.max(), ib.max())) + 3.0

    def px(v):
        return L + (v - x0) / max(x1 - x0, 1e-9) * (R - L)

    def py(v):
        return B - (v - lo) / max(hi - lo, 1e-9) * (B - T)

    # grid
    for i in range(6):
        v = lo + (hi - lo) * i / 5
        y = py(v)
        d.line([(L, y), (R, y)], fill=(38, 42, 54))
        d.text((10, y - 6), f"{v:8.1f} m", fill=(150, 160, 175))
    n_ticks = 10
    for i in range(n_ticks + 1):
        v = x0 + (x1 - x0) * i / n_ticks
        x = px(v)
        d.line([(x, T), (x, B)], fill=(28, 32, 42))
        d.text((x - 18, B + 8), f"{v/1000:5.1f}", fill=(150, 160, 175))
    d.text(((L + R) / 2 - 70, B + 40), "along-shoreline distance (km)", fill=(200, 208, 220))
    d.text((10, 20), title, fill=(235, 240, 250))
    if label:
        d.text((10, 40), label, fill=(150, 160, 175))

    order = np.argsort(xs)
    ib_line = [(px(xs[i]), py(ib[i])) for i in order]
    if len(ib_line) > 1:
        d.line(ib_line, fill=(90, 170, 240))
    for i in order:
        col = (240, 200, 90) if abs(res[i]) >= lahontan.ELEVATION_RESOLUTION_M else (120, 210, 150)
        d.ellipse([px(xs[i]) - 3, py(zs[i]) - 3, px(xs[i]) + 3, py(zs[i]) + 3], fill=col)
    d.text((R - 300, T + 6), "isobase (smooth, robust)", fill=(90, 170, 240))
    d.text((R - 300, T + 22), "bench datum (residual < 3 m)", fill=(120, 210, 150))
    d.text((R - 300, T + 38), "FLAGGED step (residual >= 3 m)", fill=(240, 200, 90))
    img.save(out)


def save_map_png(dem, footprint, catalogue, band, dots, out: Path) -> None:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        return
    H, W = dem.shape
    def norm(a, lo, hi, bg=40):
        a = np.asarray(a, dtype=float)
        o = np.clip((a - lo) / (hi - lo), 0, 1)
        o[~np.isfinite(a)] = 0.0
        return o
    shade = norm(dem, 1050, 2200)
    rgb = np.stack([shade, shade, shade], axis=-1)
    rgb[band & footprint] = rgb[band & footprint] * 0.35 + np.array([0.15, 0.45, 0.85]) * 0.65
    rgb[catalogue] = np.array([0.95, 0.25, 0.25])
    rgb[dots] = np.array([1.0, 0.85, 0.10])
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    img = img.resize((W // 4, H // 4), Image.BILINEAR)
    img.save(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/gems/data")
    ap.add_argument("--registry", default="/tmp/gems/registry")
    ap.add_argument("--out", default="docs/downloads")
    ap.add_argument("--evidence", default="evidence")
    ap.add_argument("--isobase-order", type=int, default=3)
    ap.add_argument("--bench-slope-max-deg", type=float, default=lahontan.BENCH_SLOPE_MAX_DEG)
    ap.add_argument("--bench-min-cells", type=int, default=4)
    ap.add_argument("--step-threshold-m", type=float, default=lahontan.ELEVATION_RESOLUTION_M)
    ap.add_argument("--max-trace-length-m", type=float, default=emit.MAX_TRACE_LENGTH_M)
    ap.add_argument("--exclusion-m", type=float, default=emit.CATALOGUE_EXCLUSION_M)
    ap.add_argument("--spacing-m", type=float, default=emit.DOT_SPACING_M)
    ap.add_argument("--coherence-min", type=float, default=emit.COHERENCE_MIN)
    ap.add_argument("--deflection-min-deg", type=float, default=lahontan.DEFLECTION_MIN_DEG)
    ap.add_argument("--min-trace-length-m", type=float, default=400.0)
    ap.add_argument("--relief-min-m", type=float, default=emit.RELIEF_MIN_M)
    ap.add_argument("--name", default=RUN_NAME)
    ap.add_argument("--holdout-bootstrap", type=int, default=0,
                    help="cluster-bootstrap replicates over withheld segments (0 = off)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ev = Path(args.evidence)
    ev.mkdir(parents=True, exist_ok=True)

    print("[1/7] loading competition grid")
    scene = load_scene(args.data)
    footprint, catalogue, dem = scene.footprint, scene.catalogue, scene.dem
    assert int(footprint.sum()) == FOOTPRINT_CELLS, int(footprint.sum())
    assert int(catalogue.sum()) == CATALOGUE_CELLS, int(catalogue.sum())

    print("[2/7] mapping the highstand datum")
    band = lahontan.bench_cells(dem, footprint)
    benches = lahontan.describe_benches(
        dem, footprint, TRANSFORM,
        slope_max_deg=args.bench_slope_max_deg,
        min_cells=args.bench_min_cells,
    )
    print(f"      wave-planed datum cells = {int(band.sum()):,}; benches = {len(benches):,}")
    if len(benches) < 30:
        print("      too few benches; aborting", file=sys.stderr)
        return 2

    print("[3/7] fitting the smooth isobase (global dome, then local strand)")
    coef, info = lahontan.fit_isobase(benches, order=args.isobase_order)
    bx = np.array([b.x for b in benches])
    by = np.array([b.y for b in benches])
    bz = np.array([b.z for b in benches])
    bn = np.array([b.n_cells for b in benches], dtype=float)
    ib = lahontan.isobase_at(coef, info["terms"], info["x0"], info["y0"], bx, by)
    residual_global = bz - ib
    keep, levels = lahontan.dominant_strand_mask(residual_global, bn)
    print(f"      global isobase sigma = {info['residual_sigma_m']:.2f} m; "
          f"levels = {[round(m['value_m'],1) for m in levels['modes']]}")
    print(f"      dominant strand at {levels['dominant_m']:+.2f} m "
          f"-> {levels['strand_benches']} benches / {levels['strand_cells']:,} cells")
    if levels["strand_benches"] < 20:
        print("      dominant strand too sparse; aborting", file=sys.stderr)
        return 2

    idx = np.nonzero(keep)[0]
    benches = [benches[i] for i in idx]
    residual_g = residual_global[idx]
    rho, info_local = lahontan.local_isobase(benches, residual_g)
    residual = residual_g - rho
    print(f"      local strand isobase sigma = {info_local['residual_sigma_m']:.2f} m "
          f"(published elevation resolution = {lahontan.ELEVATION_RESOLUTION_M} m)")

    print("[4/7] flagging datum offsets")
    steps = lahontan.flag_steps(benches, residual, threshold_m=args.step_threshold_m)
    defl = lahontan.flag_deflections(benches)
    print(f"      step flags = {len(steps):,}; deflection flags = {len(defl):,}")

    print("[5/7] seeding and extending traces on DEM evidence")
    az_f, coh_f, rel_f = emit.structure_tensor(dem, footprint)
    seeds = emit.seeds_from_flags(
        steps, defl, benches,
        min_abs_jump_m=args.step_threshold_m,
        min_az_change_deg=args.deflection_min_deg,
    )
    print(f"      seeds = {len(seeds):,} "
          f"({sum(1 for s in seeds if s.kind == 'elevation_step')} step, "
          f"{sum(1 for s in seeds if s.kind == 'lateral_deflection')} deflection)")
    traces = emit.traces_from_flags(
        seeds, az_f, coh_f, rel_f, footprint, TRANSFORM,
        min_evidence_coherence=args.coherence_min,
        min_length_m=args.min_trace_length_m,
    )
    print(f"      traces = {len(traces):,}  "
          f"mean length {np.mean([t.length_m for t in traces]) if traces else 0:.0f} m")

    print("[6/7] emitting kernel-matched unit dots")
    rows, cols, estats = emit.dots_from_traces(
        traces, catalogue, footprint, TRANSFORM,
        spacing_m=args.spacing_m, exclusion_m=args.exclusion_m,
    )
    print(f"      dots = {estats['n_dots']:,}")
    raster = emit.raster_from_dots(rows, cols, footprint.shape)
    nan_raster = emit.to_nan_outside(raster, footprint)

    tag = f"{args.name}-{estats['n_dots']}dots"
    primary = out / f"{tag}-zeros.tif"
    nanfile = out / f"{tag}-nan.tif"
    write_float32(primary, raster)
    write_float32(nanfile, nan_raster, nodata=np.nan)

    print("[7/7] validating, checking lane, writing receipts")
    print("      holdout: whole withheld catalogue segments, pooled DTI")
    ho = holdout_mod.evaluate(raster, catalogue, footprint,
                              bootstrap_n=args.holdout_bootstrap)
    print(f"      HOLDOUT-DTI = {ho.pooled_dti:.6f} "
          f"({ho.withheld_segments_total:,} segments / {ho.withheld_cells_total:,} cells)"
          + (f" CI95 [{ho.ci95[0]:.6f}, {ho.ci95[1]:.6f}]" if ho.ci95 else ""))
    (ev / f"{tag}-holdout.json").write_text(ho.to_json())
    pv = validate.validate_submission(primary, footprint)
    nv = validate.validate_submission(nanfile, footprint, expected_positive_values=(1.0,))

    reg_paths = {p.stem: p for p in sorted(Path(args.registry).glob("*.tif"))}
    entries = compare(raster, reg_paths, footprint) if reg_paths else []
    lane = verdict(entries) if entries else {"verdict": "NO REGISTRY", "passed": None}
    dump_uniqueness(entries, ev / f"{tag}-lane.json")

    # The rule has two halves, and this is the half that runs BEFORE placement:
    # the datum-offset surface itself (and its flagged-evidence subset), compared
    # with the same machinery.  Recording only the final-dots half would leave
    # the receipt incomplete.
    surf_full, surf_ev = lahontan.datum_offset_surface(
        benches, residual, footprint.shape, step_threshold_m=args.step_threshold_m)
    surface_receipts = {}
    for variant, surf in (("full", surf_full), ("evidence", surf_ev)):
        se = compare(surf, reg_paths, footprint) if reg_paths else []
        sv = verdict(se) if se else {"verdict": "NO REGISTRY", "passed": None}
        dump_uniqueness(se, ev / f"{tag}-lane-surface-{variant}.json")
        surface_receipts[variant] = {
            "cells": int((surf > 0).sum()),
            "max_abs_rho": sv.get("max_abs_rho"),
            "max_frac3px_non_vacuous": sv.get("max_frac3px_non_vacuous"),
            "rho_limit": sv.get("rho_limit"), "overlap_limit": sv.get("overlap_limit"),
            "n_registry": sv.get("n_registry"), "n_vacuous": sv.get("n_vacuous"),
            "closest_non_vacuous": sv.get("closest_non_vacuous"),
            "passed": sv.get("passed"), "verdict": sv.get("verdict"),
        }
        print(f"      surface/{variant:8s} cells={surface_receipts[variant]['cells']:,} "
              f"max|rho|={sv.get('max_abs_rho'):.6f} "
              f"max3px={sv.get('max_frac3px_non_vacuous'):.4f}")
    surface_ok = all(v["passed"] for v in surface_receipts.values())

    track_azimuth = float(np.median([b.azimuth_deg for b in benches if b.is_elongated])) \
        if any(b.is_elongated for b in benches) else 0.0
    profiles = lahontan.shoreline_profile(benches, residual, track_deg=track_azimuth)

    save_profile_png(profiles, ev / f"{tag}-profile.png",
                     "Lake Lahontan highstand datum: elevation vs along-shoreline distance",
                     f"track azimuth {track_azimuth:.1f} deg | {len(benches)} benches | "
                     f"isobase residual sigma {info['residual_sigma_m']:.2f} m")
    save_map_png(dem, footprint, catalogue, band, raster > 0, ev / f"{tag}-map.png")

    card = {
        "run_card_version": "parallel-run protocol v1",
        "slug": tag,
        "lane": "datum-offset: Lake Lahontan shorelines as a strain gauge",
        "hypothesis": (
            "The Lahontan highstand shoreline is an isochronous near-level datum formed "
            "immediately prior to 13.07 +/- 0.06 ka. After removing a smooth isobase "
            "(isostatic rebound + regional tilt), abrupt steps and lateral deflections of "
            "that datum mark faults that displace the shoreline. The competition's hidden "
            "labels are expert-identified faults absent from the USGS/INGENIOUS catalogue, "
            "and a shoreline offset is exactly the surface expression an expert maps."
        ),
        "mechanism": (
            "Wave-planed highstand benches are mapped in the DEM inside the published "
            "deformed-elevation window (1313.5-1345.8 m); a robust 2-D polynomial isobase "
            "is fitted to the bench elevations; residuals above the published 3 m elevation "
            "resolution, and azimuth changes above 35 deg between nearby elongated benches, "
            "are flagged; a trace is seeded at each flag and extended while the local "
            "structure tensor (coherence >= 0.15, cross-strike relief >= 4 m) supports it; "
            "unit dots are emitted at 300 m kernel-matched spacing with a 200 m catalogue "
            "exclusion."
        ),
        "named_non_fault_process_that_could_mimic_it": (
            "(a) Beach-ridge constructional scatter -- crests build 1-3 m above still water, "
            "which is why the step threshold defaults to the published 3 m resolution; "
            "(b) fluvial and deltaic terraces graded to lower still-water levels, which sit "
            "inside the elevation window without being the highstand datum; (c) alluvial-fan "
            "and bajada construction surfaces that are flat enough to pass the slope gate; "
            "(d) eolian (dune) crests; (e) differential rebound and sediment compaction "
            "producing steps at the lake-margin sediment/bedrock contact with no fault."
        ),
        "holdout": {
            "label": "HOLDOUT-DTI",
            "evaluator": ho.evaluator,
            "withheld_segments": ho.withheld_segments_total,
            "withheld_positive_cells": ho.withheld_cells_total,
            "design": "4 spatial quadrants; whole 8-connected catalogue segments withheld per fold; visible faults masked pixel-exactly out of the scored footprint; a 300 m gap around visible faults is excluded from false-positive accounting; truth is never dilated",
            "leak_free_reason": "the lane does not read the catalogue for placement (the only catalogue term is an exclusion gate that can only remove mass), so withheld positives cannot help it",
            "pooled_dti": ho.pooled_dti,
            "ci95_cluster_bootstrap_whole_segments": list(ho.ci95) if ho.ci95 else None,
            "bootstrap_n": ho.bootstrap_n,
            "validity_note": ho.note,
        },
        "raster_sha256": pv.sha256,
        "raster_bytes": pv.bytes,
        "raster_path": str(primary),
        "nan_twin_sha256": nv.sha256,
        "nan_twin_path": str(nanfile),
        "validator_output": {
            "passed": pv.passed,
            "failures": pv.failures,
            "notes": pv.notes,
            "detail": json.loads(pv.to_json()),
        },
        "isobase": {"global": info, "levels": levels, "local_strand": info_local},
        "emission": estats,
        "counts": {
            "benches": len(benches),
            "datum_cells": int(band.sum()),
            "step_flags": len(steps),
            "deflection_flags": len(defl),
            "traces": len(traces),
            "dots": int(rows.size),
            "traces_longer_than_1km": int(sum(1 for t in traces if t.length_m >= 1000)),
            "mean_trace_length_m": float(np.mean([t.length_m for t in traces])) if traces else 0.0,
        },
        "correlation_overlap_vs_registry": lane,
        "correlation_overlap_vs_registry_surface_before_placement": surface_receipts,
        "score_model": {
            **score_model.comparison_table(0.3195),
            "in_family_check": {
                "note": "the algebra reproduces the two owner-reported rows of the "
                        "same artifact family to within 0.02 % (c=0.122, N=40,199 -> "
                        "0.27802 vs owner-reported 0.2778); the fit is not a score, it "
                        "is the reason the model is believed for the ranking question",
                "reproduced_02778": score_model.model_dti(40199, 0.122, 12000),
                "reproduced_02600": score_model.model_dti(44090, 0.122, 12000),
            },
            "this_artifact_ceiling": score_model.perfect_placement_ceiling(int(rows.size)),
            "this_artifact_ceiling_note": (
                "hard upper bound on this file: even with EVERY dot landing on a truth "
                "pixel the index cannot exceed this value, because FN_w is charged "
                "0.8 per missing truth cell and only 0.2 per emitted cell"
            ),
        },
        "safe_to_upload": False,
        "upload_decision": (
            "DO NOT SPEND A WEEKLY SLOT. The file is unique and format-valid, and it is "
            "OK TO DOWNLOAD for inspection, but its hard upper bound (perfect placement, "
            f"{int(rows.size)} dots, |G|=12,000) is {score_model.perfect_placement_ceiling(int(rows.size)):.4f}. "
            "The protocol gate 'do not spend a submission slot on an idea that has not beaten "
            "the current holdout best' is not met. Use it as evidence for the Phase-2 "
            "defensibility case, not as an initial-round scorer."
        ),
        "verdict": "negative",
    }
    (ev / f"{tag}-runcard.json").write_text(json.dumps(card, indent=1, default=str))

    profiles_path = ev / f"{tag}-profile.json"
    profiles_path.write_text(json.dumps({
        "track_azimuth_deg": track_azimuth,
        "isobase": {"global": info, "levels": levels, "local_strand": info_local},
        "rows": profiles,
    }, indent=1, default=str))

    print()
    print(f"  primary : {primary}  ({pv.bytes:,} B)  sha256 {pv.sha256[:16]}...")
    print(f"  nan twin: {nanfile}  sha256 {nv.sha256[:16]}...")
    print(f"  format  : {'PASS' if pv.passed else 'FAIL'}   lane: {lane['verdict']} "
          f"(max|rho| {lane.get('max_abs_rho')}, max 3px overlap {lane.get('max_frac3px_non_vacuous')})")
    print(f"  run card: {ev / f'{tag}-runcard.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
