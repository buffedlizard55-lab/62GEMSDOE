# Remaining work and access limitations

## Completed in this review

- Re-read the repository and held scope to the assigned datum-offset / Lake Lahontan shoreline lane.
- Updated the README and landing page to state **NOT CLEARED — DO NOT SUBMIT**.
- Corrected the shared writer to write NaN outside the official footprint, with no nodata tag, and
  to validate the written bytes.
- Corrected the shared uniqueness rule so literal rank/overlap thresholds stop the run; no
  vacuity/Jaccard exemption is applied.
- Recomputed **HOLDOUT-DTI** with a six-spatial-block cluster bootstrap CI and feature-alone
  leakage canary; all outputs carry evaluator/proxy caveats.
- Fetched a registry snapshot (525 TIFFs from 88 repositories; 12 repositories skipped above the
  90 MB cap), then reproduced a strict final-dot overlap failure against the 13GEMSDOE r11-greedy-mp raster (fail-fast stop at 9/525 TIFFs).
- Ran three implementation/review passes and added regression tests. See
  [`irregularities.md`](irregularities.md) and
  [`evidence/lahontan_run_card_20261011.json`](evidence/lahontan_run_card_20261011.json).

## Hard stop before any new experiment or submission candidate

The old v8 output is both format-invalid outside the footprint and over the strict 70% overlap
limit. Do not rename or re-emit it. A future attempt must begin from the ranked
[datum-offset hypotheses](hypotheses.md), save its **pre-placement surface**, and run the strict
registry gate before any dots are placed. After final emission, run the gate again on the final
raster. If either strict gate fails, log `DUPLICATE-STOP` and stop. No submission slot is selected
here.

The top proposed future experiment is **multi-strand co-displacement coherence**, using the local
25 m USGS 3DEP DEM. It has not been implemented or holdout-validated. The prior v8 HOLDOUT-DTI is
not validation of this new hypothesis and cannot be reused as such. No slot recommendation is
possible before a new candidate clears its own spatially blocked screen and the strict registry
checks; even then the local catalogue proxy cannot certify hidden-new-fault performance.

## Remaining gaps

1. **Pre-placement surface receipt:** the historical v8 surface was not retained, so no pre-placement
   comparison can be reconstructed from its bytes. Persist this for any future candidate.
2. **Registry completeness:** 12 of 100 scanned repositories exceeded the 90 MB fetch cap. This
   does not weaken the current stop, but a future candidate cannot claim exhaustive clearance from
   this partial snapshot.
3. **v8 profile arrays:** the v8 per-bench profile arrays were not retained. The present profile
   figure is from the earlier 99-dot exploratory run and is explicitly labeled historical.
4. **High-resolution LiDAR availability:** official USGS TNM product discovery is accessible via
   the [3DEP API](https://tnmaccess.nationalmap.gov/api/v1/products), but exact coverage of each
   candidate shoreline transect has not been verified. The ranked hypotheses do not require it.
5. **Organizer receipt:** no submission-page receipt or organizer-confirmed score is present.
6. **External network:** direct USGS/TNM requests from the sandbox returned HTTP 000; the existing
   25 m DEM was obtained through a GitHub runner. New official data may require the same route.

## What will not be done

- No weekly submission slot will be chosen or spent by this run.
- No projection, leaderboard claim, or proxy result will be labeled as an organizer score.
- No unrelated fault-detection lane will be introduced.
