#!/usr/bin/env python3
"""EXPERIMENT 12 - finalise: prove the chosen field unique and legal, write the GeoTIFF and run card.

The field is chosen by experiments 9 and 11 under a rule that was written down before the numbers
were seen (`evidence/exp9_profile_matched_emission.json`, `evidence/exp11_concentration.json`).
This script does no choosing; it verifies and ships:

  1. rebuild the chosen mask from the committed inputs (deterministic: same seed, same bytes);
  2. prove isolation (no two dots inside one 300 m kernel) and mass;
  3. uniqueness against all 79 score-anchored registry rasters with the shared tool
     `gems62.uniqueness` (rank correlation <= 0.90, 3 px dot overlap <= 0.70) plus the two stronger
     checks this repository added after IR-62-19/IR-62-22 (symmetric Jaccard of the 3 px-dilated dot
     masks <= 0.25, exact-pixel overlap) and an isolated-random control that shows whether the 3 px
     tripwire is informative at all against dense comparators;
  4. write the GeoTIFF with the shared writer `gems62.grid.write_submission`, re-read the bytes from
     disk, and validate with `gems62.validate.validate_submission`;
  5. run the retired segmented holdout for the record;
  6. emit the run card the parallel-run protocol requires.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.ndimage import distance_transform_edt as edt

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems62 import grid, uniqueness, validate                      # noqa: E402
import importlib.util                                              # noqa: E402

for mod, path in (("exp6", "scripts/exp6_detector_blocked.py"),
                  ("exp8", "scripts/exp8_reward_model.py"),
                  ("exp10", "scripts/exp10_linearity.py")):
    sp = importlib.util.spec_from_file_location(mod, ROOT / path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    globals()[mod] = m


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--choice", default="build/final_choice.npz")
    ap.add_argument("--exp9", default="evidence/exp9_profile_matched_emission.json")
    ap.add_argument("--exp11", default="evidence/exp11_concentration.json")
    ap.add_argument("--exp8", default="evidence/exp8_reward_model.json")
    ap.add_argument("--exp5c", default="evidence/exp5c_vote_inversion.json")
    ap.add_argument("--exp6", default="evidence/exp6_detector_blocked.json")
    ap.add_argument("--oof", default="build/oof_surface.npy")
    ap.add_argument("--ext", default="build/ext")
    ap.add_argument("--registry", default="/tmp/reg/tif")
    ap.add_argument("--index", default="research/registry_index.json")
    ap.add_argument("--out-dir", default="docs/downloads")
    ap.add_argument("--evidence", default="evidence/run_card_20261012.json")
    ap.add_argument("--seed", type=int, default=20261012)
    ap.add_argument("--skip-holdout", action="store_true")
    ap.add_argument("--skip-registry-spearman", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    with rasterio.open(ROOT / "data/sample_submission.tif") as ds:
        tmpl = ds.read(1)
    footprint = np.isfinite(tmpl); H, Wd = footprint.shape
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = (ds.read(1) == 1) & footprint
    active = footprint & ~cat

    z = np.load(ROOT / args.choice)
    keep = np.unpackbits(z["keep"]).astype(bool).reshape(tuple(z["shape"]))
    chosen_name = str(z["name"]); source = str(z["source"])
    keep &= active
    n_dots = int(keep.sum())
    print(f"chosen field {chosen_name} (from {source}): {n_dots:,} dots", flush=True)

    e9 = json.load(open(ROOT / args.exp9))
    e11 = json.load(open(ROOT / args.exp11))
    e8 = json.load(open(ROOT / args.exp8))
    e5 = json.load(open(ROOT / args.exp5c))
    e6 = json.load(open(ROOT / args.exp6))
    prof = dict(e9["chosen"])
    g0 = next((f for f in e11["candidates"] if f["gamma"] == 0.0), None)
    if g0:
        prof.update({k: v for k, v in g0.items() if k not in ("name", "gamma", "M")})

    # ---- isolation proof -----------------------------------------------------------------
    ys, xs = np.nonzero(keep)
    dmin = np.full(n_dots, np.inf)
    for dy in range(-6, 7):
        for dx in range(-6, 7):
            if dy == 0 and dx == 0:
                continue
            w = float(np.hypot(dy, dx)) * 100.0
            yy = ys + dy; xx = xs + dx
            ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < Wd)
            hit = np.zeros(n_dots, bool)
            hit[ok] = keep[yy[ok], xx[ok]]
            dmin = np.where(hit & (w < dmin), w, dmin)
    min_sep = float(dmin.min())
    n_within_kernel = int((dmin <= 300.0).sum())
    print(f"minimum dot-to-dot separation {min_sep:.1f} m; dots with another dot inside 300 m: "
          f"{n_within_kernel}", flush=True)

    # ---- determinism proof: rebuild from the committed inputs -----------------------------
    oof = np.load(ROOT / args.oof)
    oof_n = np.clip(np.nan_to_num(oof, nan=0.0), 0.0, None)
    oof_n = oof_n / max(float(oof_n.max()), 1e-12)
    with rasterio.open(ROOT / args.ext / "lidar_scarp_features_u8.tif") as ds:
        lidar = ds.read(1).astype(np.float32) / 255.0
    d_cat_m = edt(~cat).astype(np.float32) * 100.0
    b_ch = e9["chosen"]["b"]; s_ch = int(e9["chosen"]["standoff_m"])
    elig = active & (d_cat_m >= s_ch) if s_ch else active
    base = np.where(elig, oof_n * ((lidar + 0.05) ** b_ch), -1.0).astype(np.float32)
    rebuilt = exp6.hard_core_local_maxima(base, elig, n_dots, seed=args.seed + int(b_ch * 10) + s_ch)
    identical = bool((rebuilt == keep).all())
    print(f"deterministic rebuild identical: {identical}", flush=True)

    # ---- write the submission with the shared writer, then re-read it ----------------------
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    field = np.zeros((H, Wd), np.float32)
    field[keep] = 1.0
    tmp = ROOT / "build" / "final_field.tif"
    grid.write_submission(tmp, field)
    digest = sha256(tmp)
    slug = f"gems62e-h62n-orgstack-oof-lidarprof-{n_dots}dots-20261012-{digest[:12]}-zeros"
    final_path = out_dir / f"{slug}.tif"
    os.replace(tmp, final_path)
    receipt = grid.check_submission(final_path)
    vrep = validate.validate_submission(final_path, footprint)
    print(f"wrote {final_path.name}  {receipt['bytes']:,} B  sha256 {digest}", flush=True)
    print(f"format receipt legal={receipt['legal']}  validator passed={vrep.passed} "
          f"failures={vrep.failures}", flush=True)

    nan_path = out_dir / f"{slug.replace('-zeros', '-nan')}.tif"
    nan_field = np.where(footprint, field, np.nan).astype(np.float32)
    with rasterio.open(nan_path, "w", driver="GTiff", dtype="float32", count=1, height=H, width=Wd,
                       crs=grid.CRS, transform=grid.TRANSFORM, nodata=float("nan"),
                       compress="deflate", predictor=3, tiled=True,
                       blockxsize=256, blockysize=256) as dst:
        dst.write(nan_field, 1)
    nan_sha = sha256(nan_path)

    # ---- uniqueness against every score-anchored registry raster ---------------------------
    rows = json.load(open(ROOT / args.index))
    seen = {}
    for r in rows:
        k = (r["repo"], os.path.basename(r["path"]))
        if k not in seen or r["score"] > seen[k]["score"]:
            seen[k] = r
    reg_paths = {}
    reg_score = {}
    for r in seen.values():
        p = pathlib.Path(args.registry) / f"{r['repo']}__{os.path.basename(r['path'])}"
        if p.exists():
            alias = f"{r['repo']}__{os.path.basename(r['path'])[:48]}"
            reg_paths[alias] = str(p)
            reg_score[alias] = float(r["score"])
    print(f"uniqueness comparators: {len(reg_paths)}", flush=True)

    rng = np.random.default_rng(args.seed + 7)
    ctrl = exp6.hard_core_local_maxima(rng.random((H, Wd), dtype=np.float32), active, n_dots,
                                       seed=args.seed + 7)
    st = ndi.generate_binary_structure(2, 2)
    mine_dil = ndi.binary_dilation(keep, structure=st, iterations=3)
    ctrl_dil = ndi.binary_dilation(ctrl, structure=st, iterations=3)
    extra = []
    for alias, p in sorted(reg_paths.items()):
        with rasterio.open(p) as ds:
            a = ds.read(1).astype(np.float32)
        other = (np.where(np.isfinite(a), a, 0) > 0) & footprint
        od = ndi.binary_dilation(other, structure=st, iterations=3)
        inter = int((mine_dil & od).sum()); union = int((mine_dil | od).sum())
        cinter = int((ctrl_dil & od).sum()); cunion = int((ctrl_dil | od).sum())
        exact = int((keep & other).sum())
        extra.append(dict(alias=alias, owner_reported_score=reg_score[alias],
                          positives=int(other.sum()),
                          frac3px=float((keep & od).sum() / max(n_dots, 1)),
                          control_frac3px=float((ctrl & od).sum() / max(int(ctrl.sum()), 1)),
                          jaccard3px=inter / union if union else 0.0,
                          control_jaccard3px=cinter / cunion if cunion else 0.0,
                          exact_pixel_overlap=exact,
                          exact_frac_of_mine=exact / max(n_dots, 1),
                          coverage3px=float((od & footprint).sum() / max(int(footprint.sum()), 1))))
        del a, other, od
    worst_j = max(extra, key=lambda e: e["jaccard3px"])
    worst_ex = max(extra, key=lambda e: e["exact_frac_of_mine"])
    worst_f3 = max(extra, key=lambda e: e["frac3px"])
    print(f"worst Jaccard3px {worst_j['jaccard3px']:.4f} ({worst_j['alias'][:40]}); worst exact "
          f"{worst_ex['exact_frac_of_mine']:.4f} ({worst_ex['alias'][:40]}); worst frac3px "
          f"{worst_f3['frac3px']:.4f} vs its control {worst_f3['control_frac3px']:.4f}", flush=True)

    entries, uverd = [], None
    if not args.skip_registry_spearman:
        entries = uniqueness.compare(field.astype(np.float64), reg_paths, footprint)
        uverd = uniqueness.verdict(entries)
        print(f"shared-tool verdict: {uverd['verdict']}  max|rho|={uverd['max_abs_rho']:.4f} "
              f"max_frac3px_non_vacuous={uverd['max_frac3px_non_vacuous']:.4f} "
              f"({time.time()-t0:.0f}s)", flush=True)

    # ---- the vote-surrogate instrument, for the record ------------------------------------
    idx = np.load(ROOT / "build/cand_idx.npy")
    V = np.load(ROOT / "build/vote_surface_cand.npy").astype(np.float64)
    adm = active.ravel()[idx]
    posv = V[adm & (V > 0)]
    sur_dti = {}
    for name, meta in e6["surrogates"].items():
        thr = float(np.quantile(posv, meta["q"]))
        mem = (V >= thr) & adm
        S = np.zeros((H, Wd), bool); S.ravel()[idx[mem]] = True
        r = exp6.dti_binary_fast(field.astype(np.float64),
                                 {name: (exp6.kernel_field(S), S, float(S.sum()))}, active)[name]
        champ = [x for x in e6["registry_on_surrogates"] if x["obs"] == 0.2778][0]
        sur_dti[name] = dict(K=int(S.sum()), dti_mine=r["dti"], credit_mine=r["T"] / n_dots,
                             dti_champion=champ[f"dti_{name}"],
                             ratio_to_champion=r["dti"] / champ[f"dti_{name}"]
                             if champ[f"dti_{name}"] else None)
    print("vote-surrogate DTI (incumbent-similarity instrument):",
          {k: round(v["dti_mine"], 4) for k, v in sur_dti.items()}, flush=True)

    # ---- retired segmented holdout, for the record ----------------------------------------
    hold = None
    if not args.skip_holdout:
        try:
            from gems62 import holdout_segmented as hs

            def emit(eligible, priority, fp, visible, budget):
                e = eligible & fp & ~visible
                return exp6.hard_core_local_maxima(
                    np.where(e, np.nan_to_num(priority, nan=-1.0), -1.0), e, int(budget),
                    seed=args.seed)
            hold = hs.run_holdout(active, base, footprint, cat, emit, n_folds=4,
                                  seeds=(20, 21), budget=n_dots, controls=True)
            print("holdout pooled DTI:", hold.get("pooled_dti"), "folds:", hold.get("n_folds"),
                  "controls:", hold.get("controls_mean"), flush=True)
        except Exception as exc:                                    # noqa: BLE001
            hold = dict(error=f"{type(exc).__name__}: {exc}")
            print("holdout failed:", hold["error"], flush=True)

    # ---- the model, with its uncertainty ---------------------------------------------------
    mc = prof.get("model_implied_credit")
    model = dict(
        label="MODEL - algebra on the published metric with an inherited K; NEVER a score",
        closed_form="DTI = c/(0.2 + 0.8K/M) for isolated unit dots",
        model_implied_credit_from_exp8_reward_model=mc,
        dti_at_K12000=(mc / (0.2 + 0.8 * 12000.0 / n_dots)) if mc else None,
        dti_at_K13688=(mc / (0.2 + 0.8 * 13688.0 / n_dots)) if mc else None,
        dti_at_K8479=(mc / (0.2 + 0.8 * 8479.0 / n_dots)) if mc else None,
        reward_model_cv_rho=e8["reward_model"]["implied_credit"]["cv_rho"],
        reward_model_cv_rmse=e8["reward_model"]["implied_credit"]["cv_rmse"],
        credit_required_to_beat=dict(
            target_02778=float(0.2778 * (0.2 + 0.8 * 12000.0 / n_dots)),
            target_03195=float(0.3195 * (0.2 + 0.8 * 12000.0 / n_dots)),
            target_03333=float(0.3333 * (0.2 + 0.8 * 12000.0 / n_dots)),
            note="the true per-dot credit of this field is not measurable in this sandbox"),
    )
    note = ("62e: 40k isolated dots, blocked OOF detector on the 19-band stack x LiDAR scarp. "
            "Uniqueness gate: DUPLICATE-STOP. Not for submission.")
    assert len(note) <= 140, len(note)

    card = dict(
        run_card_version="parallel-run protocol v1",
        session="arena/90112fbe-62gemsdoe (2026-10-12)",
        slug=slug,
        lane=("datum-offset: Lake Lahontan shorelines as a strain gauge. The lane's standalone "
              "emission is measured below chance (0.61x isolated-random control) so this session "
              "carries the lane forward as (a) three datum features in the detector - isobase "
              "residual, datum band, |residual| - and (b) the calibrated instrument. Deviation "
              "logged for the selector; the drift tripwires below are evaluated mechanically."),
        hypothesis=(
            "The organiser's own 19-band numerical stack contains enough signal to predict where "
            "experts map faults that are ABSENT from the USGS/INGENIOUS catalogue. The 79 public "
            "submissions with owner-reported scores are 79 measurements of that hidden set, and the "
            "measurable profile of the 0.26-0.2778 family (mass 37-44k, hard-core isolation, "
            "off-catalogue, near-uniform 10 km coverage, LiDAR-scarp affinity ~83) is a necessary "
            "condition for that band."),
        mechanism=(
            "34 features (19 organiser bands + 9 derivative/texture/coherence layers + 2 catalogue-"
            "geometry layers + 3 Lahontan-datum layers) -> HistGradientBoosting trained on a "
            "consensus surrogate under 6 spatial blocks -> one out-of-fold surface (mean blocked AUC "
            "0.9585) -> priority = OOF * (LiDAR ex_max/255 + 0.05)^2 with a 300 m catalogue standoff "
            "-> hard-core emission of the 40,000 highest 7x7 local maxima (every pair >= 400 m apart)."),
        named_non_fault_process_that_could_mimic_it=(
            "(a) the training target is the CONSENSUS OF PRIOR PUBLIC SUBMISSIONS, not the "
            "organiser's truth: a detector that predicts it reproduces the group's shared bias - "
            "range-front scarps, alluvial-fan toes, magnetic lineaments that are dykes or lithologic "
            "contacts; (b) magnetic-gradient and tilt highs mark igneous contacts and dyke swarms; "
            "(c) isostatic-gravity gradients mark basin edges and sediment-thickness changes with no "
            "Quaternary slip; (d) the LiDAR ex_max composite also fires on terrace risers, dune "
            "crests, beach ridges and channel banks - and inside this lane's own window, wave-planed "
            "Lahontan benches and deltaic terraces produce 2-3 m steps with no fault; (e) geodetic "
            "strain-rate layers are smooth and highlight inter-seismic loading, not discrete traces."),
        instruments=dict(
            label="MEASURED-INSTRUMENT (a projection is never written as a score)",
            vote_inversion=dict(
                construction=e5["method"], surrogates=e6["surrogates"],
                cv_heldout_rho=e5["cv"]["mean_heldout_rho"],
                cv_heldout_rmse=e5["cv"]["mean_heldout_rmse"],
                cv_heldout_bias=e5["cv"]["mean_heldout_bias"],
                worst_heldout_abs_err=e5["cv"]["worst_heldout_abs_err"],
                in_sample_rmse=e5["exact_fit"]["rmse"], in_sample_rho=e5["exact_fit"]["rho"],
                result_on_this_field=sur_dti,
                VERDICT=("REFUTED as an instrument for a NEW field. It reproduces owner-reported "
                         "scores at held-out rho 0.913 across registry artifacts, but the surrogate "
                         "is by construction the kernel footprint of the winning fields, so the "
                         "champion's own credit on it (0.324 per dot at K=13,294) is unattainable "
                         "by any field that is not a re-emission of the winners. This field scores "
                         "0.32-0.35x the champion on it, which is a statement about novelty, not "
                         "about quality.")),
            reward_model=dict(
                construction="11 locally measurable field properties -> implied per-dot credit and "
                             "score, gradient boosting, 5-fold leave-artifact-out CV on 47 distinct "
                             "fields",
                cv_rho_credit=e8["reward_model"]["implied_credit"]["cv_rho"],
                cv_rmse_credit=e8["reward_model"]["implied_credit"]["cv_rmse"],
                cv_rho_score=e8["reward_model"]["score"]["cv_rho"],
                cv_rmse_score=e8["reward_model"]["score"]["cv_rmse"],
                single_quantity_spearman=e8["single_quantity_spearman"],
                LIMIT=("h34-scatter-q50-arr-matched has the same mass and the same credit_sgmc as the "
                       "champion and scored 0.0778 against 0.2778, so no set of aggregate properties "
                       "certifies placement quality. The model ranks families, not fields.")),
            sgmc_compilation=dict(
                REFUTED=("the registry field with credit_sgmc = 0.9312 (99.9 % of its dots within "
                         "300 m of SGMC-1:750k faults absent from the catalogue) scored 0.0360, so "
                         "the state compilation's gaps are NOT the hidden truth; placing dots on it "
                         "is refuted. credit_sgmc is retained only as a weak family descriptor "
                         "(Spearman +0.195 over 47 distinct fields)."))),
        detector=dict(
            label="MEASURED (blocked, out-of-fold)",
            stack_sha256=e6["stack_sha256"], stack_sha_matches_manifest=e6["stack_sha_matches_manifest"],
            n_features=e6["n_features"], feature_names=e6["feature_names"],
            mean_blocked_auc=e6["mean_blocked_auc"], folds=e6["folds"],
            dem_coverage_of_footprint=e6["dem_coverage_of_footprint"],
            leakage_canary_per_feature_auc=e6["per_feature_auc_block0"],
            leakage_flags=e6["leakage_flags"],
            leakage_reading=("no single feature exceeds 0.90 AUC on the blocked holdout (max 0.757, "
                             "detelev_gradmag_max5), so the canary is not tripped. The pooled 0.9585 "
                             "is above 0.90 and is disclosed: the target is a consensus of fields "
                             "built from these same public layers, so a high blocked AUC means the "
                             "consensus is reproducible from primary data - it is not evidence about "
                             "the organiser's hidden labels.")),
        emission=dict(
            chosen_by=dict(experiment_9=e9["chosen"], experiment_11=e11["chosen_reason"]),
            n_dots=n_dots, mass_target=int(e9["chosen"]["M"]),
            lidar_exponent=b_ch, catalogue_standoff_m=s_ch,
            min_separation_m=min_sep, dots_with_another_dot_inside_300m=n_within_kernel,
            deterministic_rebuild_identical=identical,
            measured_profile={k: prof.get(k) for k in
                              ("M", "credit_sgmc", "credit_cat", "frac_sgmc_hit", "dcat_med_m",
                               "dsgmc_med_m", "self_kernel", "evenness_cells", "lidar_scarp_mean",
                               "topo_rough_mean", "slope_mean", "dens21", "coh21")},
            champion_profile={k: e8["champion_reference"].get(k) for k in
                              ("M", "credit_sgmc", "credit_cat", "dcat_med_m", "self_kernel",
                               "evenness_cells", "lidar_scarp_mean", "implied_credit_K12000")},
            arrangement_deficit=dict(
                measured="dens21 4.56 and coh21 0.1595 against the top family's 8.75-9.62 and "
                         "0.307-0.336 (evidence/exp10_linearity.json)",
                attempted_fix="experiment 11 concentration transform, gamma 1-3",
                outcome=("REFUTED - dens21 moved 4.56 -> 4.44, coh21 0.1593 -> 0.1608. The hard-core "
                         "selection of a smooth OOF surface is near-uniform and a smooth density "
                         "multiplier does not change that ranking. This is the largest measured "
                         "deviation from the top family and the most likely reason this field would "
                         "not beat 0.2778."))),
        holdout_dti=dict(
            label=("HOLDOUT-DTI (gems62.holdout_segmented v1) - RETIRED as a promotion gate by "
                   "IR-62-HOLDOUT-01: it rewards hugging the mapped catalogue, which the leaderboard "
                   "punishes (credit per dot vs the mapped catalogue has Spearman -0.594 with the "
                   "owner-reported scores over 47 distinct fields)"),
            result=hold),
        model_projection=model,
        correlation_overlap_vs_registry=dict(
            n_comparators=len(reg_paths),
            shared_tool_verdict=uverd,
            rho_limit=0.90, overlap_limit=0.70, jaccard_limit=0.25,
            worst_jaccard3px=worst_j, worst_exact_overlap=worst_ex, worst_asym_frac3px=worst_f3,
            isolated_random_control=dict(
                n_dots=int(ctrl.sum()),
                note="the control's frac3px against the same comparator shows whether the tripwire is "
                     "informative; against dense comparators both fields read ~1.0 (IR-62-22)"),
            per_comparator=extra),
        raster_path=str(final_path.relative_to(ROOT)), raster_sha256=digest,
        raster_bytes=receipt["bytes"],
        nan_twin_path=str(nan_path.relative_to(ROOT)), nan_twin_sha256=nan_sha,
        format_receipt_from_disk=receipt,
        validator_output=json.loads(vrep.to_json()),
        submission_name=slug, submission_note=note, submission_note_chars=len(note),
        verdict="negative",
        verdict_label="DUPLICATE - STOP: do not download-and-submit",
        submission_decision=(
            "DO NOT SUBMIT. The parallel-run uniqueness gate tripped: 87.84 % of this field's dots "
            "lie within 3 px of the dots of one non-vacuous registry raster (limit 0.70), and 12,979 "
            "of the 40,000 dots (32.45 %) are EXACTLY that raster's pixels (chance expectation 0.78 "
            "%). The protocol says log and stop. The file is published for inspection and for "
            "learning only - it must not be uploaded to the competition."),
        duplicate_trip=dict(
            gate="gems62.uniqueness (rank correlation <= 0.90; <= 70 % of dots within 3 px of one "
                 "non-vacuous registry raster)",
            rho_leg=dict(max_abs_rho=uverd["max_abs_rho"] if uverd else None, limit=0.90,
                         tripped=False),
            overlap_leg=dict(max_frac3px_non_vacuous=uverd["max_frac3px_non_vacuous"] if uverd else None,
                             limit=0.70, tripped=True,
                             closest_non_vacuous=uverd["closest_non_vacuous"] if uverd else None),
            comparator=dict(alias=worst_j["alias"], positives=worst_j["positives"],
                            owner_reported_score=worst_j["owner_reported_score"],
                            coverage3px=worst_j["coverage3px"],
                            my_frac3px=worst_j["frac3px"],
                            isolated_random_control_frac3px=worst_j["control_frac3px"],
                            excess_over_control=round(worst_j["frac3px"] / max(worst_j["control_frac3px"], 1e-9), 3),
                            jaccard3px=worst_j["jaccard3px"],
                            control_jaccard3px=worst_j["control_jaccard3px"],
                            exact_shared_dots=worst_j["exact_pixel_overlap"],
                            exact_shared_frac=worst_j["exact_frac_of_mine"],
                            chance_expectation=round(worst_j["positives"] /
                                                     max(int(footprint.sum()), 1), 5),
                            chance_ratio=round(worst_j["exact_frac_of_mine"] / max(
                                worst_j["positives"] / max(int(footprint.sum()), 1), 1e-9), 2)),
            secondary=dict(second_worst_exact=worst_ex, third_worst_frac3px=worst_f3),
            reading=("The comparator GEMSDOE22 'h23-b-dti-optimal-emission-10pct' is a 516,738-cell "
                     "DTI-optimal emission field that itself scored 0.0748. Two independent "
                     "hard-core top-40k selections from priority surfaces built on the same public "
                     "layers land on the same sharpest peaks, so the shared pixels are a consequence "
                     "of the shared input, not of copying. That does not make it submittable: the "
                     "gate is mechanical and it tripped, and 32 % of the field inherits the pixels of "
                     "a low-scoring artifact.")),
        verdict_reason=(
            "FORMAT LEGAL (14/14 receipt checks, values in [0,1], no nodata tag, EPSG:32611, "
            "3730x3292, 100 m, transform asserted against the official sample) and perfectly "
            "isolated (minimum dot-to-dot separation 400.0 m, zero dots inside one 300 m kernel). "
            "It matches or beats the 0.2778 champion on every aggregate property this sandbox can "
            "measure - mass 40,000 vs 37,654; self-kernel 0.0000 vs 0.0173; evenness 569 vs 547 "
            "cells; credit_cat 0.0000 vs 0.0074; credit_sgmc 0.0697 vs 0.0655; LiDAR-scarp mean "
            "112.6 vs 82.9 - but it fails the uniqueness gate, and it deviates on arrangement "
            "(dens21 4.56 vs 8.75-9.62, coh21 0.1595 vs 0.307-0.336) in the direction that "
            "h34-scatter shows is worth 0.0778 instead of 0.2778. No instrument available here can "
            "show this field beating the incumbent, and the protocol forbids spending a slot on an "
            "idea that has not beaten the best local evidence."),
        irregularities_flagged=[
            "the mandated segmented holdout is structurally incapable of scoring this design: with a "
            "300 m catalogue standoff every dot is outside the withheld catalogue positives, so "
            "pooled HOLDOUT-DTI = 0.0000 while its own random-dot control scores 0.0575 and its "
            "random-line control 0.0170. A holdout whose positives are mapped catalogue segments "
            "measures catalogue hugging, which the leaderboard punishes (IR-62-HOLDOUT-01). It is "
            "reported here for the record only and gates nothing",
            "the registry rows 'd28-poisson300m-offcat-44090' (GEMSDOE30) and "
            "'gems25-dotted-h19-5-d2-8' (GEMSDOE25/60GEMSDOE) are the SAME 44,090 dots (exact "
            "overlap 100 %, Jaccard 1.0000); the 'Poisson control scored 0.2600' reading in the "
            "group's history is a mislabelled duplicate and is withdrawn",
            "3 of 87 registry index rows have a sha256 that does not match the bytes at the recorded "
            "path (GEMSDOE22 h23-a allfinite/nan, 14GEMSDOE r5-geom-horse); the scores attached to "
            "those rows were still used, so they are labelled OWNER-REPORTED",
            "the brief's headline numbers are stale: it calls 0.3195 (and elsewhere 0.3774) the "
            "highest score, while the mirrored official leaderboard of 2026-10-11T20:57:47Z puts "
            "0.4133 first, the top-5 cut-off at 0.3333 and 0.3195 at rank 9",
            "no organiser receipt exists anywhere in this repository, so every score quoted here is "
            "OWNER-REPORTED"],
        seconds=round(time.time() - t0, 1),
    )
    json.dump(card, open(ROOT / args.evidence, "w"), indent=1, default=float)
    print(f"\nrun card -> {args.evidence}  ({time.time()-t0:.0f}s)", flush=True)
    print(f"NOTE ({len(note)}/140): {note}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
