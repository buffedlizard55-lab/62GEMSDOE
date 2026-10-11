# Irregularities, defects, and review record — 2026-10-11

This page records evidence and failures without smoothing them over. The active decision is
**negative**: the historical v8 TIF is not cleared for submission. See the current
[executive summary](executive-summary.md) and machine-readable
[run card](evidence/lahontan_run_card_20261011.json).

## 1. Strict registry result: stop, not a uniqueness pass

The previous root checker and older reports applied a vacuity/Jaccard exemption to a literal
70%-within-3-px rule. That did not match the user's stop condition. The shared tool was changed so
that the asymmetric raw fraction is a hard stop for every comparable raster; footprint coverage
and Jaccard are not exemptions. The check now returns a non-zero status on duplicate-stop and
searches nested repository snapshots recursively.

**Reproduced final-dot result for historical v8:**

- Candidate: 1,660 positive cells.
- First blocking comparator in the recursive fail-fast scan: `13GEMSDOE` `r11-greedy-mp-v2`,
  SHA-256 `033df94ceef16350030a69d5cfdec0afe7bc605bb155d8f3b98b203aabf80abd`, 272,853 positive cells.
- Spearman rho: −0.3317889 (not over the 0.90 threshold).
- Candidate dots within Euclidean 3 px: **1,601/1,660 = 0.9644578** (hard-stop threshold: more
  than 0.70).
- Comparator's 3 px footprint coverage: 0.7397312; this is diagnostic and does **not** exempt it
  from the strict test.
- Scan stopped after 9 of 525 fetched TIFFs (516 unscanned after stop). Verdict:
  **`DUPLICATE-STOP`**. Do not submit or emit a repackaged TIF.

Receipt: [`evidence/uniqueness_v8_strict_review.json`](evidence/uniqueness_v8_strict_review.json).
The fetched registry snapshot contains 525 GeoTIFFs from 88 repositories; 12 repositories exceeded
the 90 MB cap. The snapshot is incomplete, but one failing comparator is sufficient for the stop.
No exhaustive-uniqueness claim is made.

Older artifacts such as `evidence/uniqueness_v8.json`, `evidence/run_card_v8.json`,
`evidence/gems62-lahontan-isobase-99dots-lane.json`, and the old static pages used the prior
informative-comparator/Jaccard logic. They are retained as provenance, not as current clearance.

## 2. The historical TIF fails the current format check

Official submission rules require a single-band `float32` raster aligned to the training grid,
values in `[0,1]` inside the footprint, and null/NaN outside it. The shared writer was corrected to
write NaN outside, leave the nodata tag unset, reopen the bytes, and fail closed.

The historical v8 TIF itself has correct band count, dtype, CRS, shape, resolution, transform,
bounds, in-footprint range, and no nodata tag. It has **7,111,787 non-NaN outside-footprint
pixels**, however; `grid.check_submission` returns `legal: false` with
`all_nan_outside_footprint` failed. No replacement was written because the strict duplicate stop
was reached. Thus the README and site now say **DO NOT SUBMIT**.

## 3. Holdout and leakage canary are evidence-qualified

Recomputed with `scripts/run_holdout.py` evaluator `root-run_holdout-v3`:

- **HOLDOUT-DTI 0.0028633750**, six spatial blocks, **60,362 withheld positive catalogue cells**.
- 95% CI `[0, 0.0068419286]`, percentile bootstrap resampling the six blocks as clusters, 10,000
  replicates, seed 62. This is a coarse six-cluster uncertainty interval, not a guarantee of
  generalization.
- Feature-alone canary AUC: `lane_kernel_proximity` 0.5020115 and `lane_binary_mask` 0.4999204;
  neither is above the 0.90 leakage alarm. Near-chance AUC indicates little signal about the
  catalogue in these features; it does not prove that every possible leakage path is absent.

The proxy truth is the existing USGS/INGENIOUS catalogue. It cannot evaluate the competition's
hidden-new-fault target and is not an organizer score. No submission-page receipt is present.

## 4. Three review passes

1. **Scientific scope and evidence.** Kept work in the Lake Lahontan datum-offset lane; re-read the
   official metric/format/rules and geological context; separated historical measurements from
   organizer-confirmed evidence; identified wave-cut bluffs, berms, fan-head risers, delta topsets,
   and differential rebound as non-fault mimics; ranked four future lane-compatible hypotheses.
2. **Implementation review.** Corrected the shared `grid.write_submission` outside-footprint
   behavior and validator; fixed the aggregate-credit DTI guard; added a UTM-safe map writer;
   reconciled receipt logging; added fold-cluster bootstrap CI; replaced the vacuity/Jaccard
   uniqueness exemption with the literal strict gate in shared `src/gems62/uniqueness.py`; added
   regression tests for writer and strict raw-overlap behavior.
3. **Release review.** Root tests: **28 passed**. Recomputed holdout/canary; independently ran the
   strict final-dot comparison against the fetched 13GEMSDOE raster; confirmed
   `DUPLICATE-STOP` and the historical TIF's local format failure; made no new emission, slot
   selection, or organizer-result claim.

## 5. Pre-placement surface and profile artifacts

The historical v8 pre-placement surface raster was not retained. Its pre-placement registry check
therefore cannot be reconstructed from saved bytes without rerunning the pipeline. No new emission
or submission placement happened in this review. Any future candidate must persist and test its
pre-placement surface before emission, then test final dots afterward; either strict failure is a
stop.

The visible profile figure `docs/assets/profile.png` is from an earlier 99-dot exploratory run,
not v8. Its data receipt is `evidence/gems62-lahontan-isobase-99dots-profile.json`. The v8 run's
full profile arrays were not retained. Do not present the older figure as validation of v8.

## 6. Registry-fetch limits and access

The registry fetch completed successfully under `/tmp/gems62_registry_review`: 88 repositories and
525 TIFFs were fetched; 12 repositories were skipped because the configured archive limit was
90 MB. The skipped repositories are listed in that temporary directory's manifest (the sandbox
snapshot does not persist `/tmp`). Current strict stop does not depend on the skipped artifacts.

The cached 25 m Lahontan DEM is available in `evidence/dem/`. Direct requests from this sandbox to
USGS/TNM hosts returned HTTP 000; the already documented 3DEP mosaic was transported through a
GitHub runner. Exact 1 m LiDAR tile coverage along each future shoreline transect remains
unverified, so no future-hypothesis ranking assumes those tiles exist.

## 7. Leaderboard and score integrity

There is no ORGANIZER-CONFIRMED score for any artifact in this repository. User-provided historical
scores remain `OWNER-REPORTED` claims in the irregularities/source records. The public leaderboard
page observation is not a receipt for this candidate. No projection or proxy metric is described
as a competition score.

## 8. Shared-tool and implementation fixes made in this branch

- `src/gems62/grid.py`: footprint-aware write/read validation; NaN outside, no nodata tag; local
  receipt only.
- `src/gems62/metric.py`: soft DTI/reference helpers and corrected aggregate credit validation.
- `src/gems62/uniqueness.py` + `scripts/check_uniqueness.py`: one strict shared rule, recursive
  registry CLI, dense comparators remain hard-stop comparators.
- `scripts/run_holdout.py`: deterministic spatial-fold cluster-bootstrap DTI CI and evaluator
  version recorded in output.
- `scripts/run_lane.py`: diagnostic PNG map writer validates UTM flag coordinates; receipt logging
  uses keys that the shared writer actually returns.

These changes do not transform the old TIF into a submission-ready file. The negative verdict is
the intended deliverable of this review.
