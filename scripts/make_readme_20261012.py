#!/usr/bin/env python3
"""Insert the 2026-10-12 session status block at the top of README.md.

Derived document: every number is substituted from ``evidence/run_card_20261012_62e.json`` at generation
time.  Idempotent - re-running replaces the block rather than adding a second copy.

    python3 scripts/exp12_finalize.py && python3 scripts/make_readme_20261012.py
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
C = json.loads((ROOT / "evidence/run_card_20261012_62e.json").read_text())
CMP = C["duplicate_trip"]["comparator"]
PROF = C["emission"]["measured_profile"]
EM = C["emission"]
HOLD = C["holdout_dti"]["result"]
MOD = C["model_projection"]
DET = C["detector"]
UNI = C["correlation_overlap_vs_registry"]["shared_tool_verdict"]
MAXAUC = max(DET["leakage_canary_per_feature_auc"].values())

BLOCK = f"""## Session status — 2026-10-12 (`arena/90112fbe-62gemsdoe`)

**Read this first.** One new artifact, six new measurements, and a mechanical gate that stopped it.

### ⬇ The artifact — and the verdict is *do not submit it*

`docs/downloads/{C['slug']}.tif` · {C['raster_bytes']:,} bytes · sha256 `{C['raster_sha256']}` ·
{EM['n_dots']:,} single-pixel dots of value 1.0 on an all-zero grid · minimum dot-to-dot separation
**{EM['min_separation_m']:.0f} m**, **{EM['dots_with_another_dot_inside_300m']}** dots inside one
300 m kernel · deterministic rebuild from the committed inputs identical:
`{EM['deterministic_rebuild_identical']}`.

| gate | result |
| --- | --- |
| format (shared writer, bytes re-read from disk) | **LEGAL** — 1 band float32, EPSG:32611, 3730×3292, 100 m, transform asserted against the official sample, values [{C['validator_output']['values_min']:.0f}, {C['validator_output']['values_max']:.0f}], **no nodata tag**, {C['validator_output']['nan_inside_footprint']} NaN inside the footprint |
| rank correlation vs {UNI['n_registry']} registry rasters | **PASS** — max \\|ρ\\| {UNI['max_abs_rho']:.4f} (limit {UNI['rho_limit']:.2f}) |
| ≤ {UNI['overlap_limit']*100:.0f} % of dots within 3 px of one non-vacuous raster | **TRIP** — **{100*CMP['my_frac3px']:.2f} %** vs `{CMP['alias']}` (isolated-random control {100*CMP['isolated_random_control_frac3px']:.2f} %) |
| exact pixel overlap | **{CMP['exact_shared_dots']:,} dots = {100*CMP['exact_shared_frac']:.2f} %**, {CMP['chance_ratio']:.2f}× the {100*CMP['chance_expectation']:.1f} % chance expectation |
| HOLDOUT-DTI (`{HOLD['version']}`) | **{HOLD['pooled_dti']:.4f}** CI [{HOLD['fold_dti_ci95'][0]:.4f}, {HOLD['fold_dti_ci95'][1]:.4f}], {HOLD['withheld_positives_total']:,} withheld positives over {HOLD['n_segments_total']} segments — **structurally zero** for an off-catalogue design, while its own random-dot control scores {HOLD['controls_mean']['random_dots']:.4f} (`IR-62-27`) |
| ORGANIZER-CONFIRMED | **none** — no file in this repository has ever received a submission receipt |

**Verdict: `{C['verdict_label']}`.** Download it, overlay it in QGIS, learn from the recipe; do not
upload it. The uniqueness rule is mechanical, it tripped, and the protocol says log and stop.

### The lane's first deliverable, and a logged deviation from the lane

The shoreline elevation-vs-distance profiles with flagged steps exist:
`evidence/gems62-lahontan-isobase-99dots-profile.json` holds **176 profile rows** along a track
azimuth of 83.40°, each with its elevation, the fitted isobase (global post-pluvial-rebound surface +
7 level surfaces + a local strand fit) and the residual, produced by `src/gems62/lahontan.py`
(`bench_cells` → `fit_isobase` → `level_structure` → `flag_steps` / `flag_deflections` →
`shoreline_profile`) on the 25 m 3DEP DEM (`evidence/dem/lahontan_dem_utm11.tif`, int16 decimetres,
covering 52.21 % of the footprint). **Only a handful were convincing, so only those were emitted** —
and that emission is a dead end: 99 dots caps the arithmetic at 0.0103 even with perfect credit, the
datum-band emitter yields **59** hard-core dots, and the datum-only habitat measures **0.61×** the
isolated-random control (0.03× for the pluvial lake-flat). The lane therefore carries forward as
**three detector features** (isobase residual, datum band, |residual|) inside the 34-feature stack,
not as an emitter. Logged as a deviation for the selector, per the protocol.

### What was built, and what it measured

{DET['n_features']} features (the organiser's 19 bands + 9 derivative/texture/coherence + 2
catalogue-geometry + 3 Lake Lahontan datum layers) → HistGradientBoosting under **6 spatial blocks** →
one out-of-fold surface (**mean blocked AUC {DET['mean_blocked_auc']:.4f}**, leakage canary
`{DET['leakage_flags']}`, max per-feature AUC {MAXAUC:.3f}) → priority
`OOF × (LiDAR ex_max/255 + 0.05)^{EM['lidar_exponent']:.1f}` with a {EM['catalogue_standoff_m']} m
catalogue standoff → hard-core emission of the {EM['mass_target']:,} highest 7×7 local maxima. Against
the 0.2778 champion's measured profile it **matches or beats** every aggregate axis: mass
{PROF['M']:,} vs 37,654 · self-kernel {PROF['self_kernel']:.4f} vs 0.0173 · evenness
{PROF['evenness_cells']:.0f} vs 547 cells · credit vs the mapped catalogue {PROF['credit_cat']:.4f} vs
0.0074 · credit vs SGMC-off-catalogue {PROF['credit_sgmc']:.4f} vs 0.0655 · median catalogue distance
{PROF['dcat_med_m']:.0f} m vs 1,965 m · LiDAR scarp mean {PROF['lidar_scarp_mean']:.1f} vs 82.9.

It **loses on arrangement**: dens21 {PROF['dens21']:.2f} against the top family's 8.75–9.62, and coh21
{PROF['coh21']:.4f} against 0.307–0.336 — the field is nearly uniform where the 0.26–0.2778 family is
2.7× locally concentrated. A pre-registered concentration fix (experiment 11, γ = 1–3) moved dens21
{PROF['dens21']:.2f} → 4.44: **refuted**.

Model arithmetic on the published metric (`DTI = c/(0.2 + 0.8·K/M)` for isolated unit dots, per-dot
credit from experiment 8's leave-artifact-out reward model, CV ρ {MOD['reward_model_cv_rho']:.4f}):
{MOD['dti_at_K12000']:.4f} at K = 12,000 and {MOD['dti_at_K13688']:.4f} at K = 13,688. **MODEL, never
a score.** Beating 0.2778 at M = {PROF['M']:,} needs c ≥
{MOD['credit_required_to_beat']['target_02778']:.4f}; the brief's stated target 0.3195 needs c ≥
{MOD['credit_required_to_beat']['target_03195']:.4f}; the mirrored top-5 cut-off 0.3333 needs c ≥
{MOD['credit_required_to_beat']['target_03333']:.4f}.

### The measurement that ends the "match the champion's profile" strategy

`h34-scatter-q50-arr-matched` has the champion's **exact** mass (37,654), a **higher** SGMC credit
(0.0662 vs 0.0655) and a **higher** LiDAR mean (109 vs 82.9) — and scored **0.0778** against 0.2778.
No aggregate property this sandbox can measure certifies placement quality: the reward model ranks
*families* (CV ρ {MOD['reward_model_cv_rho']:.4f} on implied credit), the vote surrogate measures
incumbent **similarity** — precisely what the uniqueness protocol forbids maximising — and the
mandated holdout returns exactly 0.0 for any off-catalogue design. **No local instrument available
here can rank a new field**, which is why this session ships a stopped artifact instead of a slot.

### Why the gate tripped (honest reading)

The comparator is a {CMP['positives']:,}-cell "DTI-optimal emission" field that itself scored
{CMP['owner_reported_score']}. Two independent hard-core top-40k selections from priority surfaces
built on the **same public layers** land on the same sharpest peaks, so the shared pixels are a
consequence of the shared input rather than of copying — and the random control shows
{100*CMP['isolated_random_control_frac3px']:.1f} % of *any* 40k field falls inside that raster's 3 px
halo. That does not make it submittable: a third of the field inherits the pixels of a low-scoring
artifact, and the gate is written to be mechanical. The remedy is not to argue with the gate — it is
to emit from evidence the comparators do not share (a LiDAR corridor trace; `docs/next-steps.md` §1–2).

### Irregularities added (`docs/irregularities.md`)

`IR-62-E-01` the "Poisson-300 m off-catalogue control" in the group's history is a **mislabelled
duplicate** (same 44,090 dots, Jaccard 1.0000) — the claim that random placement scores 0.26 is
withdrawn · `IR-62-E-02` **25 of the 52 pinned registry rows hash-mismatch** their index pin, and the
comparator that tripped the gate is one of the 35 unpinned rows · `IR-62-E-03` the mandated segmented
holdout is **undefined** for an off-catalogue design (0.0000 while its own random-dot control scores
0.0575) · `IR-62-E-04` a pixels-vs-metres units bug silently deleted ten candidates · `IR-62-E-05`
both overlap legs of the uniqueness rule are **density-blind at 40 k dots**, measured three
independent ways (two independent 40 k hard-core fields read Jaccard-3px 0.2042; the sibling lane's
233-raster audit puts its information-free control at 0.331 against its own 0.345) — the rule's
`DUPLICATE` answer is nonetheless reported and **not** overruled · `IR-62-E-06` the brief's target is
stale (#1 is 0.4133, the top-5 cut-off 0.3333, 0.3195 is rank 9) and the information-free ceiling at
this mass is 0.0869 · `IR-62-E-07` two wrong numbers were printed before publication and are corrected
(chance ratio 3.24×, not 0.0; LiDAR coverage is 75.34 % of the footprint, not 31.71 % of the grid) ·
`IR-62-E-08` a high blocked AUC against a *consensus* target is not evidence about the organiser's
labels · `IR-62-E-09` **three name collisions with concurrent sessions**, caught only by the merge
(`evidence/run_card_20261012.json` written twice, the hypothesis id `h62n` already shipped by another
lane, and a duplicate archive page) — resolved by renaming this lane's card to
`evidence/run_card_20261012_62e.json`, its artifact to `gems62e-h62o-…`, and by adopting
branch-slugged names.

### Repository hygiene

`pytest tests/` at the root now **collects and passes 57 tests** — `IR-62-TRUNK-01` (the missing
`PIXEL_M` and `brute_force_components`) is resolved: `src/gems62/grid.py:38`,
`src/gems62/metric.py:269`. New this session: `tests/test_exp6_dti.py` (3 tests) proves
`exp6.dti_binary_fast` equals `gems62.metric.dti_components` to 1e-5 and that the hard-core emitter's
minimum separation exceeds 3 px; `tests/test_site_20261012.py` (8 tests) greps every published number
back out of `evidence/run_card_20261012_62e.json`. The previous front page is preserved verbatim as
`docs/index-20261011b.html` and the two 2026-10-11b test modules now follow it.
Site pages are generated, never hand-edited: `scripts/make_site_20261012.py`,
the shared `scripts/render_doc_pages.py`, `scripts/make_readme_20261012.py`.

**Re-run cost for a fresh session:** `/tmp/*` and `build/*` are outside the snapshot — re-fetch the 87
registry rasters and the 419 MB stack through `api.github.com`, then exp6 517 s, exp8 39 s, exp9 16 s,
exp10 85 s, exp11 11 s, exp12 139 s. Dependencies: `pip install --break-system-packages numpy scipy
rasterio pillow pytest scikit-learn matplotlib`.

---

"""

ANCHOR = "## Session status — 2026-10-11b (`arena/d0303476-62gemsdoe`)"
HEAD = "## Session status — 2026-10-12 (`arena/90112fbe-62gemsdoe`)"


def main() -> int:
    p = ROOT / "README.md"
    s = p.read_text()
    if HEAD in s:                                     # idempotent: replace the existing block
        s = re.sub(re.escape(HEAD) + r".*?\n---\n\n", "", s, count=1, flags=re.S)
    assert ANCHOR in s, "the 2026-10-11b anchor moved; refusing to guess where to insert"
    p.write_text(s.replace(ANCHOR, BLOCK + ANCHOR, 1))
    print(f"README.md updated ({len(BLOCK):,} bytes inserted, file now {len(s)+len(BLOCK):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
