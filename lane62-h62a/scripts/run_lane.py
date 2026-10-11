#!/usr/bin/env python3
"""H62-A: Lake Lahontan shorelines as a strain gauge -- end-to-end lane run.

Runs, in order and writing a JSON evidence file for each step:

  E0  data verification           sha256 of the three official rasters vs pins
  E1  lane surfaces               benches, isobase fit, residuals, strike, flags
  E2  enrichment + canaries       habitat table; per-feature rank-AUC (< 0.90)
  E3  segmented holdout           hide-and-recover, pooled DTI, equal-budget controls
  E4  first deliverable           shoreline elevation-vs-distance profiles + PNGs
  E5  final emission              dotted artifact at the metric-optimal budget
  E6  format validation           the format checks, re-read from the bytes on disk
  E7  uniqueness                  vs every earlier raster in the registry
  E8  run card                    the single JSON card the protocol requires

Three experiment arms (the protocol's budget is 3):

  A1  lane-faithful     seeds = flagged steps + lateral deflections on the
                        fitted isobase; traces extended on DEM-ridge evidence
  A2  band-only         no isobase: the whole pluvial-lake-margin band ranked by
                        habitat + ridge evidence.  This is the ablation that
                        says whether the isobase step-detection adds anything.
  A3  lane + habitat    A1's traced pixels, but ranked inside the habitat band
                        so the budget is spent where the catalogue says faults
                        actually are.

Usage
-----
    python scripts/run_lane.py --budget 38000 --arms A1 A2 A3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import LANE, LANE_ID, __version__                      # noqa: E402
from gems62 import emission as em                                   # noqa: E402
from gems62 import grid, habitat, holdout, isobase, profiles        # noqa: E402
from gems62 import submission_writer as sw                          # noqa: E402
from gems62 import uniqueness, validate                             # noqa: E402
from gems62.metric import attainable_kernel_weights                 # noqa: E402
from gems62.metric import marginal_inclusion_threshold              # noqa: E402
from gems62 import paths                                            # noqa: E402


def jdump(obj, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    return dest


def norm01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    v = np.asarray(a, float)
    m = mask & np.isfinite(v)
    if not m.any():
        return np.zeros_like(v)
    lo, hi = np.percentile(v[m], [1, 99])
    if hi <= lo:
        return np.zeros_like(v)
    return np.clip((v - lo) / (hi - lo), 0.0, 1.0)


ARM_DESC = {
    "A1": ("lane-faithful: eligible = bench pixels whose isobase residual falls in "
           "the physical shoreline-throw window [15,130) m, plus azimuth-kink "
           "deflections, extended along isobase strike on DEM-ridge evidence. "
           "No catalogue-derived term at all."),
    "A2": ("band-only ablation: eligible = the whole pluvial-lake-margin band, ranked "
           "by habitat + ridge evidence, with no isobase fit. This is the arm that "
           "says whether the isobase step-detection adds anything over 'look at "
           "basin-margin scarps'."),
    "A3": ("lane + habitat: A1's throw-window bench pixels intersected with the "
           "measured fault-rich habitat (enrichment >= 2.0). This is the cell that "
           "measured 3.67x enrichment over 66,163 px."),
}


def build_priority(surf: isobase.LaneSurfaces, arm: str, visible_cat: np.ndarray,
                   footprint: np.ndarray, hab_w: np.ndarray | None = None,
                   hab_min: float = 2.0, traced: np.ndarray | None = None):
    """Ranking used to spend the dot budget.  Catalogue input is `visible_cat` only."""
    if hab_w is None:
        hab_w = habitat.habitat_enrichment(surf.tpi, surf.slope, visible_cat,
                                           footprint & surf.tpi_ok)
    hab = np.clip(hab_w, 0.0, 6.0)
    ev = surf.ridge_evidence
    med = surf.stats.get("resid_median_m") or 0.0
    throw = np.abs(surf.resid - med)

    if arm == "A1":
        # rank inside the physical throw window: closest to the middle of the
        # 15-120 m slip-rate bracket first, then ridge evidence
        lo, hi = surf.stats.get("throw_lo_m", 15.0), surf.stats.get("throw_hi_m", 130.0)
        centre = 0.5 * (lo + min(hi, 120.0))
        p = 0.60 * norm01(-np.abs(throw - centre), footprint) + 0.40 * ev
        elig = footprint & (surf.step_flag | surf.deflect_flag)
    elif arm == "A2":
        p = 0.5 * norm01(hab, footprint) + 0.5 * ev
        elig = footprint & surf.margin
    elif arm == "A3":
        p = (0.40 * norm01(hab, footprint) + 0.35 * ev
             + 0.25 * norm01(-np.abs(throw - 60.0), footprint))
        elig = footprint & surf.step_flag & (hab >= hab_min)
    else:
        raise ValueError(f"unknown arm {arm}")

    # lane steps 4-5 (seed a trace, extend it while DEM-ridge evidence supports
    # it) apply to A1 and A3 only.  A2 is the no-isobase ablation and must not
    # inherit the traced geometry, or the ablation proves nothing.
    if traced is not None and arm in ("A1", "A3"):
        elig = elig | (traced & footprint)
        p = p + 0.35 * traced.astype(float)
    return p, elig


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=38000)
    ap.add_argument("--arms", nargs="*", default=["A1", "A2", "A3"])
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--min-sep", type=int, default=3)
    ap.add_argument("--prune-cat-px", type=float, default=3.0)
    ap.add_argument("--min-evidence", type=float, default=0.55)
    ap.add_argument("--max-len-px", type=int, default=120)
    ap.add_argument("--taper", type=float, default=0.15)
    ap.add_argument("--ev-out", default=str(HERE / "evidence"))
    ap.add_argument("--profiles-out", default=str(HERE / "docs" / "profiles"))
    ap.add_argument("--sub-out", default=str(HERE / "docs" / "downloads"))
    ap.add_argument("--registry", default=str(Path.home() / ".cache/gems62/registry/rasters"))
    ap.add_argument("--stem", default=None)
    ap.add_argument("--no-profiles", action="store_true")
    ap.add_argument("--no-uniqueness", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    ev = Path(args.ev_out)
    ev.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ E0
    print("[E0] loading + verifying the official rasters ...", flush=True)
    stack = grid.load_stack(verify=True)
    jdump(dict(ok=True, spec=stack.spec, expected=grid.EXPECTED,
               sha256_pins=paths.SHA256_PINS,
               band_index=grid.BAND_INDEX), ev / "e0_data_verification.json")
    print(f"     footprint={stack.spec['footprint']:,} positives={stack.spec['positives']:,}"
          f"  sha256(features)={stack.spec['sha256'][paths.TRAINING_FEATURES][:16]}...",
          flush=True)

    fp = stack.footprint
    cat = stack.positives
    F = stack.features

    # ------------------------------------------------------------------ E1
    print("[E1] building lane surfaces (benches, isobase, residuals, flags) ...", flush=True)
    surf = isobase.build_surfaces(F, fp)
    jdump(surf.stats, ev / "e1_lane_surfaces.json")
    print("     " + json.dumps({k: v for k, v in surf.stats.items()}, default=str), flush=True)

    # ------------------------------------------------------------------ E2
    print("[E2] enrichment table + leakage canaries ...", flush=True)
    tab = habitat.enrichment_table(surf.tpi, surf.slope, cat, fp)
    jdump(tab, ev / "e2_enrichment.json")
    feats = {
        "tpi": surf.tpi, "slope": surf.slope, "isobase_residual_abs": np.abs(surf.resid),
        "ridge_evidence": surf.ridge_evidence,
        "habitat_enrichment_full_catalogue": habitat.habitat_enrichment(
            surf.tpi, surf.slope, cat, fp & surf.tpi_ok),
        "det_elev": surf.elev,
    }
    can = {k: holdout.leakage_canary(v, cat, fp) for k, v in feats.items()}
    can_report = dict(threshold=0.90, aucs=can,
                      any_above_threshold=bool(any(v > 0.90 for v in can.values())),
                      note=("AUC > 0.90 means leakage until proven otherwise. "
                            "habitat_enrichment_full_catalogue is measured against the "
                            "same catalogue it was fit on and is reported only to show "
                            "the ceiling of that mistake; it is NOT used in the holdout, "
                            "where the weights are rebuilt from visible faults per fold."))
    jdump(can_report, ev / "e2_canary.json")
    print("     canaries: " + ", ".join(f"{k}={v:.3f}" for k, v in can.items()), flush=True)

    # ---------------- lane steps 4-5: seed traces, extend along isobase strike
    print("[E2b] extending traces from flagged seeds along isobase strike ...", flush=True)
    seeds_mask = surf.step_flag | surf.deflect_flag
    traced, traces = isobase.extend_traces(
        seeds_mask, surf.ridge_evidence, fp, strike=surf.strike,
        min_evidence=args.min_evidence, max_len_px=args.max_len_px, taper=args.taper)
    tlen = np.array([t["n"] for t in traces], float) if traces else np.array([0.0])
    trace_stats = dict(n_seeds=int(seeds_mask.sum()), n_traces=len(traces),
                       n_traced_px=int(traced.sum()),
                       len_mean_px=float(tlen.mean()), len_median_px=float(np.median(tlen)),
                       len_p90_px=float(np.percentile(tlen, 90)), len_max_px=int(tlen.max()),
                       min_evidence=args.min_evidence, max_len_px=args.max_len_px,
                       taper=args.taper)
    jdump(trace_stats, ev / "e2b_traces.json")
    print("     " + json.dumps(trace_stats, default=str), flush=True)

    # ------------------------------------------------------------------ E3
    print(f"[E3] segmented holdout, {args.folds} folds, arms {args.arms} ...", flush=True)
    hold = {}
    for arm in args.arms:
        def emit_fn(elig, prio, foot, visible_cat, budget, _arm=arm):
            hab_w = habitat.habitat_enrichment(surf.tpi, surf.slope, visible_cat,
                                               foot & surf.tpi_ok)
            p, e = build_priority(surf, _arm, visible_cat, foot, hab_w=hab_w,
                                  traced=traced)
            r = em.emit_dots(p, e & elig, foot, visible_cat, budget=budget,
                             min_sep=args.min_sep, prune_cat_px=args.prune_cat_px)
            return r.mask

        # `elig` passed into the holdout is a permissive superset; the arm narrows it
        permissive = fp
        prio0 = surf.ridge_evidence
        res = holdout.run_holdout(permissive, prio0, fp, cat, emit_fn,
                                  n_folds=args.folds, seeds=(20, 21), budget=args.budget)
        hold[arm] = res
        print(f"     {arm}: pooled DTI={res['pooled_dti']:.4f} "
              f"CI={res['fold_dti_ci95']} withheld={res['withheld_positives_total']:,} "
              f"controls={ {k: (round(v,4) if v else None) for k,v in res['controls_mean'].items()} }",
              flush=True)
    jdump(dict(version=holdout.HOLDOUT_VERSION, budget=args.budget, arms=hold),
          ev / "e3_holdout.json")

    # per-fold canary against *withheld* truth (the honest leakage test)
    canary_withheld = {}
    seg = holdout.segments_of(cat & fp, min_size=8)[0]
    rng = np.random.default_rng(20)
    withheld, buffered = holdout.split_segments(seg, int(seg.max()), 0.35, rng, buffer_px=3)
    visible = (cat & fp) & ~buffered
    truth = withheld & fp
    hab_vis = habitat.habitat_enrichment(surf.tpi, surf.slope, visible, fp & surf.tpi_ok)
    for k, v in {"ridge_evidence": surf.ridge_evidence,
                 "habitat_from_visible_only": hab_vis,
                 "isobase_residual_abs": np.abs(surf.resid),
                 "step_z": np.clip(np.abs(surf.resid - (surf.stats.get("resid_median_m") or 0))
                                   / (3 * max(surf.stats.get("resid_mad_m") or 1, 1e-6)), 0, 1),
                 }.items():
        canary_withheld[k] = holdout.leakage_canary(v, truth, fp, known=visible)
    jdump(dict(threshold=0.90, aucs_vs_withheld_truth=canary_withheld,
              any_above_threshold=bool(any(v > 0.90 for v in canary_withheld.values())),
              n_withheld=int(truth.sum()), n_visible=int(visible.sum())),
          ev / "e3_canary_withheld.json")
    print("     canary vs withheld truth: " +
          ", ".join(f"{k}={v:.3f}" for k, v in canary_withheld.items()), flush=True)

    # ------------------------------------------------------------------ E4
    prof_out = None
    if not args.no_profiles:
        print("[E4] first deliverable: shoreline elevation-vs-distance profiles ...", flush=True)
        seeds = np.argwhere(surf.step_flag | surf.deflect_flag)
        if seeds.shape[0] > 400:
            keep = np.linspace(0, seeds.shape[0] - 1, 400).astype(int)
            seeds = seeds[keep]
        profs = profiles.extract_profiles(surf, seeds, half_len_px=40, max_profiles=400)
        prof_out = profiles.write_profiles(profs, Path(args.profiles_out), make_png=True)
        jdump(prof_out, ev / "e4_profiles.json")
        print(f"     {prof_out.get('n_profiles', 0)} profiles -> {prof_out.get('csv')}", flush=True)

    # ------------------------------------------------------------------ pick the arm
    best_arm = max(args.arms, key=lambda a: (hold[a]["pooled_dti"] or 0.0))
    best = hold[best_arm]
    ctrl_lines = best["controls_mean"].get("random_lines")
    beats_controls = bool(best["pooled_dti"] and ctrl_lines is not None
                          and best["pooled_dti"] > ctrl_lines)
    print(f"[pick] best arm on holdout = {best_arm} (DTI {best['pooled_dti']:.4f}, "
          f"random_lines {ctrl_lines})", flush=True)

    # ------------------------------------------------------------------ E5
    print("[E5] final emission with the full visible catalogue ...", flush=True)
    hab_full = habitat.habitat_enrichment(surf.tpi, surf.slope, cat, fp & surf.tpi_ok)
    prio, elig = build_priority(surf, best_arm, cat, fp, hab_w=hab_full, traced=traced)
    print(f"     arm {best_arm}: eligible={int(elig.sum()):,} px "
          f"(traced={int(traced.sum()):,}, seeds={int(seeds_mask.sum()):,})", flush=True)

    res = em.emit_dots(prio, elig, fp, cat, budget=args.budget,
                       min_sep=args.min_sep, prune_cat_px=args.prune_cat_px)
    print(f"     emitted {res.n_dots:,} dots ({res.stats.get('footprint_fraction',0)*100:.3f}% "
          f"of footprint), pruned {res.stats.get('n_pruned_on_catalogue'):,} on catalogue",
          flush=True)
    jdump(dict(best_arm=best_arm, n_traces=len(traces),
              n_traced_px=int(traced.sum()), n_seeds=int(seeds_mask.sum()),
              emission=res.stats, trace_length_histogram=dict(
                  n=float(len(traces)),
                  mean_px=float(np.mean([t["n"] for t in traces])) if traces else 0.0,
                  median_px=float(np.median([t["n"] for t in traces])) if traces else 0.0,
                  max_px=int(max([t["n"] for t in traces])) if traces else 0),
              credit_bar_at_best_organizer_score=dict(
                  dti=0.2778, bar=marginal_inclusion_threshold(0.2778),
                  attainable_kernel_weights=attainable_kernel_weights())),
          ev / "e5_emission.json")

    # ------------------------------------------------------------------ E6/E7
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    stem = args.stem or f"gems62-{LANE_ID.lower()}-lahontan-isobase-step-{res.n_dots}dots-{stamp}"
    sub_out = Path(args.sub_out)
    print(f"[E6] writing + validating {stem} ...", flush=True)
    bundle = sw.write_and_validate(res.values, fp, stem, sub_out, catalogue=cat,
                                   sample_transform=stack.transform,
                                   description=f"{LANE_ID} {LANE}",
                                   make_nan_twin=True, make_zip=True)
    jdump(bundle, ev / "e6_submission.json")
    print(f"     ok_to_submit={bundle['ok_to_submit']} "
          f"pass={bundle['receipt']['n_pass']} fail={bundle['receipt']['n_fail']} "
          f"sha256={bundle['receipt']['sha256'][:16]}...", flush=True)
    if not bundle["ok_to_submit"]:
        print("     FAILED CHECKS: " + ", ".join(bundle["failed_checks"]), flush=True)

    uni = None
    if not args.no_uniqueness:
        reg = Path(args.registry)
        if reg.is_dir():
            print(f"[E7] uniqueness vs registry at {reg} ...", flush=True)
            uni = uniqueness.check_uniqueness(res.values, reg, footprint=fp)
            jdump(uni, ev / "e7_uniqueness.json")
            print(f"     verdict={uni['verdict']} (strict-literal "
                  f"{uni['verdict_strict_literal']}) n_registry={uni['n_registry']}", flush=True)
            print(f"       worst signed rho  {uni['worst_rho_surface']['value']:+.4f} "
                  f"(limit 0.90) vs {uni['worst_rho_surface']['name']}", flush=True)
            print(f"       worst |rho|       {uni['worst_abs_rho_surface']['value']:+.4f} "
                  f"vs {uni['worst_abs_rho_surface']['name']}", flush=True)
            print(f"       worst 3px overlap {uni['worst_overlap_3px']['value']:.4f} "
                  f"(limit 0.70) vs {uni['worst_overlap_3px']['name']}", flush=True)
            print(f"       worst INFORMATIVE 3px overlap "
                  f"{uni['worst_overlap_3px_informative']['value']:.4f} vs "
                  f"{uni['worst_overlap_3px_informative']['name']}", flush=True)
            print(f"       worst jaccard     {uni['worst_jaccard']['value']:.4f} "
                  f"(limit 0.50) vs {uni['worst_jaccard']['name']}", flush=True)
            print(f"       comparators over the overlap limit: "
                  f"{uni['n_comparators_over_overlap_limit']} "
                  f"(degenerate {uni['n_comparators_over_limit_and_degenerate']}, "
                  f"informative {uni['n_comparators_over_limit_and_informative']})", flush=True)
        else:
            print(f"[E7] registry dir {reg} missing -- uniqueness UNVERIFIED", flush=True)
            uni = dict(verdict="UNVERIFIED-NO-REGISTRY", okay=False, n_registry=0)
            jdump(uni, ev / "e7_uniqueness.json")

    # ------------------------------------------------------------------ E8 run card
    note = (f"{LANE_ID} Lahontan isobase step/deflection traces; arm {best_arm}; "
            f"{res.n_dots} dots; UNSCORED")
    note = note[:140]
    card = dict(
        lane_id=LANE_ID, lane=LANE, package_version=__version__,
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        hypothesis=("Lake Lahontan's ~15 ka shoreline is a near-level datum; where it is "
                    "stepped in elevation or deflected laterally along strike, a structure "
                    "younger than the highstand cuts it. Those structures are the class of "
                    "fault the USGS/INGENIOUS catalogue is incomplete for, because they are "
                    "expressed as basin-margin scarps rather than range crests."),
        mechanism=("Fit a smooth isobase through the pluvial-lake-margin band of the "
                   "detrended-elevation surface (6 km Gaussian, so differential rebound "
                   "between sub-basins is absorbed rather than forced into one plane); "
                   "flag robust residual outliers (steps, k=2.5 MAD) and abrupt azimuth "
                   "kinks (>22 deg over 3 px, lateral deflections); seed a trace at each "
                   "flag and extend it while DEM-ridge evidence (across-strike profile "
                   "curvature + scarp-band slope + TMI/isostatic-gravity horizontal "
                   "gradient) stays above 0.60; emit single-pixel dots at >=3 px spacing, "
                   "capped at the organiser-confirmed optimum budget, with every dot "
                   "within 3 px of a mapped fault deleted."),
        named_non_fault_process_that_could_mimic_it=(
            "Differential post-pluvial isostatic rebound itself. Rebound is spatially "
            "variable across the Lahontan sub-basins, so a purely isostatic warp of the "
            "shoreline produces elevation steps and azimuth kinks with no fault at all. "
            "Secondary mimics: (a) alluvial-fan toes and debris-flow lobes, which create "
            "slope breaks in the same TPI band; (b) the ~12-14 ka Truckee/Carson River "
            "channel and delta margins, which are erosional not tectonic; (c) bedrock "
            "lithologic contacts expressed as differential erosion. The lane cannot "
            "separate (a) from a genuine scarp at 100 m pixels -- that needs the 1 m "
            "lidar in 1m_DEM_links.csv, which is not reachable from this sandbox."),
        holdout=dict(evaluator=holdout.HOLDOUT_VERSION,
                     alpha=0.2, beta=0.8, radius_m=300,
                     n_withheld_positives_total=int(best["withheld_positives_total"]),
                     pooled_dti=best["pooled_dti"],
                     ci95=best["fold_dti_ci95"],
                     controls_mean=best["controls_mean"],
                     beats_random_lines=beats_controls,
                     best_arm=best_arm, all_arms={a: hold[a]["pooled_dti"] for a in args.arms}),
        leakage_canary=dict(threshold=0.90, vs_withheld_truth=canary_withheld,
                            any_above=bool(any(v > 0.90 for v in canary_withheld.values()))),
        correlation_and_overlap_vs_registry=(
            dict(verdict=uni.get("verdict"),
                 verdict_strict_literal=uni.get("verdict_strict_literal"),
                 n_registry=uni.get("n_registry"),
                 worst_rho_surface=uni.get("worst_rho_surface"),
                 worst_abs_rho_surface=uni.get("worst_abs_rho_surface"),
                 worst_overlap_one_sided_3px=uni.get("worst_overlap_3px"),
                 worst_overlap_one_sided_3px_informative=uni.get("worst_overlap_3px_informative"),
                 worst_overlap_excess_above_chance=uni.get("worst_overlap_excess"),
                 worst_jaccard=uni.get("worst_jaccard"),
                 n_over_overlap_limit=uni.get("n_comparators_over_overlap_limit"),
                 n_over_limit_degenerate=uni.get("n_comparators_over_limit_and_degenerate"),
                 n_over_limit_informative=uni.get("n_comparators_over_limit_and_informative"),
                 n_overlap_degenerate_comparators=uni.get("n_overlap_degenerate_comparators"),
                 limits=dict(rho=0.90, overlap=0.70, jaccard=0.50),
                 degeneracy_note=uni.get("degeneracy_note"))
            if uni else dict(verdict="UNVERIFIED")),
        raster_sha256=bundle["receipt"]["sha256"],
        raster_bytes=bundle["receipt"]["bytes"],
        validator=dict(ok=bundle["ok_to_submit"],
                       n_pass=bundle["receipt"]["n_pass"],
                       n_fail=bundle["receipt"]["n_fail"],
                       failed_checks=bundle.get("failed_checks", []),
                       no_nan_inside_footprint=bool(bundle["receipt"]["n_nan"] == 0),
                       values_in_0_1=bool(bundle["receipt"]["min"] >= 0.0
                                          and bundle["receipt"]["max"] <= 1.0),
                       crs=bundle["receipt"]["epsg"],
                       shape=bundle["receipt"]["shape"],
                       transform=bundle["receipt"]["transform"]),
        submission_name=stem,
        submission_note=note,
        submission_note_chars=len(note),
        organizer_confirmed_score=None,
        verdict=("promote" if (bundle["ok_to_submit"] and beats_controls
                               and (uni is None or uni.get("verdict") == "UNIQUE"))
                 else "negative"),
        verdict_reason=None,
        elapsed_seconds=round(time.time() - t0, 1),
    )
    if card["verdict"] != "promote":
        reasons = []
        if not bundle["ok_to_submit"]:
            reasons.append("format validation failed")
        if not beats_controls:
            reasons.append(f"holdout DTI {best['pooled_dti']:.4f} does not beat "
                           f"random lines {ctrl_lines:.4f}")
        if uni is not None and uni.get("verdict") != "UNIQUE":
            reasons.append(f"uniqueness verdict {uni.get('verdict')}")
        card["verdict_reason"] = "; ".join(reasons) or "unspecified"
    jdump(card, ev / "e8_run_card.json")
    print("\n" + "=" * 78)
    print(json.dumps(card, indent=2, default=str)[:4000])
    print("=" * 78)
    print(f"[done] {time.time()-t0:.1f}s   artifact: {bundle['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
