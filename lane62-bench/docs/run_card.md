# Run card — 62GEMSDOE Lahontan datum-offset lane

Generated 2026-10-11 (UTC). Every number here is reproducible from the commands in
`README.md`; the machine-readable version is `lane62-bench/evidence/lane62.json`.

## Artifact

| field | value |
|---|---|
| file | `lane62-bench/docs/downloads/gems62-lahontan-datumstep-min12max60-seed25-traceonly.tif` |
| zip | `lane62-bench/docs/downloads/gems62-lahontan-datumstep-min12max60-seed25-traceonly.zip` (single TIFF) |
| sha256 | `12aa5d4534b5ddcae90e6e2ec10e1f10262df437358ccd9316b8ba9bcf8ca503` |
| bytes | 179,828 (zip 140,550) |
| grid | 3730 × 3292, float32, EPSG:32611, transform identical to `sample_submission.tif` |
| values | 1.0 on emitted pixels, 0.0 elsewhere; NaN never written (outside-footprint = 0) |
| positive pixels | 63,750 = 1.2% of the 5,167,373-px contest footprint (3.9% of the 1,643,507-px tread habitat) |
| validator | **27/27 checks passed**, incl. `zero_on_catalogue`, `outside_footprint_zero`, `in_footprint_range_0_1`, `nonempty`; re-verified from disk after the run (`validate.assert_valid` on the shipped file: 63,750 positive px, 0 on catalogue, unique positive value 1.0, no NaN/inf) |
| note (≤140 ch) | Lahontan bench datum-step lane: matched filter over 12 trends on pluvial tread pixels, per-limb stability gate, trace-only emission |

Upload is a manual step for the operator; this card and the receipt
(`docs/downloads/<stem>.json`, written by the submission writer, the
convention the sibling lanes use) are what an auditor keeps.

## Inputs and pins

* DEM `geodawn_dem_a2_100m.tif`, sha256 `d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431`, asserted at run time.
* `data/ (the trunk's contest rasters)existing_faults.tif` == `labels.tif` (byte-identical); used only as the
  exclusion mask and the holdout's visible catalogue, never as a predictor.
* Registry inventory `index.json`: 72 repos, 753 unique competition-grid rasters,
  0 errors, `declared_scope_complete: true` for "every accessible sibling repo".

## Detector configuration (what the numbers below mean)

```
pluvial window 1120-1520 m   slope ≤ 7°   flank ±4 px with ≥ 6 m relief both ways
planarity |z − median5| ≤ 3 m              trends 0..165° / 15°
legs 2,3,4,5 px   control legs 7,8,9,10 px   CROSS ±1 px
limb level tolerance 10 m    ≥3 bench cells per limb side, ≥2 usable sub-windows
offset band 12-60 m          seed offset ≥ 25 m   seed thinning 6 px
trace extension ≤ 100 px each way, ±2 px wander, stop below 0.05 evidence
dots every 2 px, no ranked fill, prune 3 px against the catalogue
```

Field: 2,521,687 band / 955,946 tread / 388,955 flagged / 1,643,507 habitat px.
Median measured offset on flags: 16.4 m (published Lahontan throws: 10-45 m).

## Held-out measurement

Segmented hide-and-recover (`gems62/holdout_segmented.py`, 2 draws × 4 quadrants,
20% of catalogue segments hidden, `active = domain & ~visible`, 300 m triangular
kernel, α 0.2 / β 0.8):

| budget | emitted px | pooled DTI | 95% CI | random dots | random lines |
|---|---|---|---|---|---|
| 40,000 | 35,263 | 0.0300 | 0.0232-0.0333 | 0.0001 | 0.0001 |
| 80,000 | 68,595 | 0.0390 | 0.0334-0.0427 | 0.0002 | 0.0002 |
| **120,000** | **71,088** | **0.0397** | **0.0341-0.0443** | 0.0002 | 0.0002 |

Detached-segment mode (hidden segments broken 4 px back from the visible edge, so a
lane cannot score by hugging the retained catalogue) tracks the same ordering and is
slightly *higher*: 0.0330 / 0.0419 / **0.0429**. Coverage of hidden truth at the
chosen rung: 7.9% of 22,641 hidden segment pixels within the 300 m kernel.
Plateau: budgets above 80k add pixels, not signal; denser masks score worse
(all 388,955 flagged px → 0.0170) because the FP weight is linear in positive
pixels. Sibling lanes on this harness: 0.002-0.013; the external Nevada fault
raster: 0.087.

Leakage canary — AUC of each lane feature against hidden truth on the scored
domain, flag at 0.90: bench 0.495, |anomaly| 0.486, step 0.506, evidence 0.510,
slope 0.583. **No flag**: the field carries essentially no catalogue information.

## Independent physical check (the reason to trust or distrust the amplitudes)

`shoreline_profiles62.py`, 398 usable profiles of the 400 strongest detections in
the 8-45 m band, per-limb robust line fits, offset = intercept difference at the
crossing:

```
matched-filter median      44.8 m        profile median        0.3 m
raw limb-level difference     8.4 m      |disagreement| median  15.0 m
within 5 m                    19%        correlation           0.08
|offset| ≥ 8 m                92%        at 60 m saturation cap 0.25% of flags
top detections >3 px from the mapped catalogue                   84%
median distance to catalogue                                   15.9 px
```

Verdict recorded in the lane: **geometry is supported, amplitude ranking is not**.
The lane is therefore emitted from a fixed amplitude band and used as a placement
prior; nothing downstream (budget, ordering within a trace) is allowed to depend on
the amplitude beyond the seed threshold, and the seed threshold itself was chosen
from the published offset band rather than tuned on the holdout.

## Uniqueness / literal-copy protocol

Screening pass over all 753 accessible sibling rasters (`lane62-bench/evidence/uniqueness_screen62.json`):
worst signed Spearman **0.037** for the emission and **0.129** for the evidence
surface (limit 0.90); worst 3-px support overlap **0.38** (limit 0.70), against
`GEMSDOE47:docs/downloads/gems47-h47gsa-37654px-…tif` — a third of that lane's
footprint is geographically shared with this one, which is a relationship worth
knowing but not a copy. **PASS.**

The exact-protocol pass (`lane62-bench/scripts/uniqueness_gate62.py`, full-resolution ranks,
sha256 pin verification per raster) was started and is ~20% complete when the run
was ended; `lane62-bench/evidence/uniqueness.json` currently records that partial state
(0 rasters cleared, from a pre-fix glob bug). Re-run the gate before treating the
exact verdict as on file.

## Tests

`lane62-bench/tests/test_lahontan.py` — 21 passed: shift-helper equivalence, the organiser's
worked DTI example, fast-vs-brute-force metric identity, amplitude recovery at five
trends with zero spurious flags, spike veto, noise survival, isobase/profile API,
and two pinned limitations (flat azimuth response on a straight scarp; a 600 m
alluvial lens is not vetoed).

## Post-restructure reproduction (22:07 UTC)

`lane62-bench/evidence/repro_lane62.json`: same command, field cache key
`8cb1391bcc519270`, ladder 0.0300 / 0.0390 / 0.0397 with identical CIs and
identical emitted counts, artifact sha256 `12aa5d45…` unchanged,
`checks_passed=True`, 184.9 s. The only card differences are the vendored package
name and the writer's staging temp path.

## Sibling-lane overlap, null-corrected

Within-habitat placement enrichment over chance: **1.17×** vs `lane62/` primary
(0.676 observed, 0.576 null), **1.16×** vs `lane62-h62a/` (0.249 / 0.215). Overlap
between lanes is mostly the shared tread habitat. Meanwhile a same-budget random dot
set *inside the habitat* scores 0.0002 on the holdout against this lane's 0.0397, so
the score is paying for placement, not for the habitat prior. Detail:
`lane62-bench/evidence/sibling_crosscheck62.json`.

## What is deliberately NOT here

* No external gravity/magnetics or third-party fault layer in the submission, so no
  licence exposure on the artifact.
* No blending with the sibling lanes: the union was measured (−0.008 pooled DTI on
  the external catalogue, −0.001 to +0.019 on the weak siblings) and rejected as a
  submission change; the positive deltas are against lanes this lane outperforms,
  not against the family best.
* No isobase-subtracting detector: the whole-lake residual version was built,
  measured (tread |anomaly| median 45 m) and rejected as level selection, not
  faulting. It survives only as the reporting surface for profiles.
