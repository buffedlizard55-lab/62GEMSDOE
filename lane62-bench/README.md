# 62GEMSDOE — Lahontan bench datum-offset lane

Primary-signal lane for the GEMS Prize contest (DrivenData, `competition-doe-gems`):
the measured vertical offset of a **pluvial Lake Lahontan shoreline datum** across
candidate fault traces, computed from the contest DEM alone. No catalogue-derived
feature, no training labels, no model.

```
data/*.tif (trunk contest rasters)  ->  lane62-bench/src/gems62_bench/lahontan.py  ->  lane62-bench/scripts/run_lane62.py
                                                   ├─ leakage canary (per-feature AUC)
                                                   ├─ segmented hide-and-recover holdout
                                                   ├─ docs/downloads/*.tif  (submission)
                                                   └─ evidence/*.json       (run card)
                     lane62-bench/scripts/shoreline_profiles62.py  (independent re-measurement + figures)
                     lane62-bench/scripts/blend_eval62.py          (prices this lane against siblings)
                     lane62-bench/scripts/uniqueness_gate62.py     (literal-copy protocol gate)
```

## Why a geomorphic lane at all

The positive class is a *linear* feature and the public ground truth is the known
USGS/INGENIOUS catalogue, while the private labels are expert-added **new** faults
and the submission is required to be zero on the mapped catalogue. A model trained
on catalogue-derived shape therefore optimises re-deriving the catalogue. The
family's catalogue-fed lanes plateaued at **0.2778** (rank ~23, top of board
0.4133), and the internal corridor canary measured how little the geophysics had
to say about *where* to place a dot (AUC ~0.51). This lane is an attempt at an
independent measurement instead of another classifier.

The physics: Lake Lahontan stood at the Sehoo highstand (~1337-1338 m,
15,475 ± 720 cal yr BP) and left benches, relict shorelines and spillways that the
same range-front faults later cut. Published throws across individual strands are
12-15 m on channels and 35-43 m on side canyons across 39 ± 4 kyr of incision
(2.6 ± 0.3 mm/yr; Briggs & Wesnousky 2004, JGR 109:B08402), ~14 m of shoreline
offset near the Wassuk Range (~0.9 mm/yr; Dong et al. 2014, Geosphere), and
15 ± 10 m on a Sehoo-age ridge (Angster et al. 2016, BSSA). So the *expected
signal* is a 10-45 m vertical offset of a continuous near-level surface.
Regional post-Lahontan rebound is O(1 m/km), i.e. <1 m over the operator's
0.2-1 km lever arm: it cannot fabricate a step, so no datum correction is needed
before gating (one is still computed, for the profiles and maps).

## Method (`lane62-bench/src/gems62_bench/lahontan.py`)

1. **Tread test, direction-free.** A cell is on a bench if it is inside the
   pluvial elevation window (1120-1520 m on this grid), near-level (≤ 7°),
   flanked within 4 px by ground both ≥ 6 m higher *and* ≥ 6 m lower (a riser on
   both sides), and within 3 m of its 5×5 median. An isotropic |z − median₇| test
   was built, measured and discarded: a 500-700 m tread is mostly riser pixels
   inside a 7×7 window, so real benches fail it for the wrong reason.
2. **Matched filter over 12 trace trends.** For trend `az`, `T = (sin az, cos az)`
   walks along the trace and `N = (cos az, −sin az)` is across the step. The datum
   is compared between ± legs along `N` at 2-5 px, each leg averaged over ±1 px
   across the tread so a 1-2-cell-wide bench still yields a continuous field. Only
   tread pixels enter the mean — a softened weight lets the *riser* into a limb
   mean and fabricates a step of exactly the bench relief at every tread margin
   (it did: 60 m readings everywhere).
3. **Stability gate.** Each limb is measured in four independent sub-windows
   (2-3, 4-5, 7-8, 9-10 px) and must keep *one level* (spread ≤ 10 m); the offset
   must keep its sign for a couple of pixels along the trace; accepted band
   12-60 m. This is what rejects DEM spikes, valley sides and scarp faces.
4. **Anchoring.** The anchor pixel of a step *is* the riser, which the tread test
   rejects, so the flag lives on the tread beside the step (`zone` = gated ∧ dilate
   (bench, 2) ∧ slope ≤ 12°). Requiring the anchor to be on the bench suppresses
   every genuine crossing; not rejecting steep anchors lets a range-front face read
   3-4× the true offset (82 m for an injected 22 m step).
5. **Emission.** Seeds are the strongest flagged steps (≥ 25 m), thinned at 6 px;
   each is extended both ways along its own trend while the evidence ridge supports
   it (≤ 100 px, ±2 px lateral wander); dots every 2 px; dots within 3 px of the
   mapped catalogue are deleted (the family's forensic rule, and required by
   `zero_on_catalogue`).

## Validation — `tests/test_lahontan.py`, 21 passed

* `_at` shift helper vs an explicit index loop (5 offsets) + the zeroed edge strip.
* the shared metric reproduces the organiser's worked example (TP 3.00 / FP 1.89 /
  FN 2.00 → **0.60**) and matches the brute-force DTI.
* on a synthetic bench (tread with 11° risers and 8.5° waste slopes, displaced
  along its own strike) the operator recovers an injected 22 m offset to
  **22.0 ± 1.5 m** with **zero spurious flags** along strike, at trends 0/30/65/
  100/145°, and survives 1 m of DEM noise.
* 60 isolated 25 m DEM spikes → **0** flags; the amplitude must also be confirmed by
  the control legs, or the pixel is not emitted.
* two *documented limitations*, pinned by tests rather than glossed: on a straight
  scarp over level ground the arg-max trend is only weakly determined (the |J|
  response is genuinely flat — the trace is therefore followed through the sign
  boundary of `step_signed`, not by integrating `step_azim`), and a ~600 m alluvial
  lens that carries the tread up and then returns to the datum is **not** vetoed,
  because at 100 m cells that is what a short range-front scarp looks like.
* `fit_isobase_1d` recovers a tilt with the faulted window excluded, and
  `profile_along` reproduces the flagged-pixel step field exactly.

A synthetic made of *flat terraces* instead of a tread with steep risers is
degenerate — every terrace edge then reads as a fault — which is how the 60 m
artefact above was found.

## Measured results (2026-10-11, all from `lane62-bench/evidence/lane62.json`)

| quantity | value |
|---|---|
| pluvial band / tread / flagged / habitat pixels | 2,521,687 / 955,946 / 388,955 / 1,643,507 |
| median measured offset on flagged pixels | **16.4 m** (published range 10-45 m) |
| leakage canary, AUC of each feature against hidden truth | bench 0.495, anomaly 0.486, step 0.506, evidence 0.510, slope 0.583 → **no leakage flag** (< 0.90) |
| holdout pooled DTI, budget ladder | 0.0300 (35 k px) → 0.0390 (69 k) → **0.0397** (71 k, 95% CI 0.0341-0.0443); detached-segment mode 0.0330 / 0.0419 / **0.0429**; hidden-truth coverage 7.9% |
| equal-budget controls | random dots 0.0002, random lines 0.0002 |
| emission | 63,750 dots = 1.2% of the contest footprint; median 20.8 px (2.1 km) from the mapped catalogue |
| catalogue rule | only 10.3% of the lane's dots are deleted by the off-catalogue rule — the signal is not the catalogue |
| submission | `lane62-bench/docs/downloads/gems62-lahontan-datumstep-min12max60-seed25-traceonly.tif`, float32, 3730×3292, EPSG:32611, sha256 `12aa5d45…`, 179,828 B, **27/27 validator checks passed**, re-verified from disk |
| uniqueness screen, 753 sibling rasters | worst Spearman 0.037 (emission) / 0.129 (surface); worst 3-px support overlap 0.38 → **PASS** (limits 0.90 / 0.70) |

For scale on the *same* holdout harness: the external Nevada fault raster prices at
0.087, and the sibling heuristic lanes (projected basement step, gravity corridor,
relief ribbon) at 0.002-0.013. This lane is ~3× its best sibling without using a
single external layer. `lane62-bench/scripts/blend_eval62.py` produced that table.

## Relationship to the trunk (this is the third Lahontan lane in this repo)

Between the commit this lane was branched from and the moment it was merged, `main`
moved by 292 files and grew its **own** `src/gems62/lahontan.py` plus
`src/gems62/datum.py`: an independently written Lahontan lane whose primary detector
is the **map-view lateral deflection** of the shoreline trace (its own docstring
records that the *elevation* method resolves to ~3 m — Adams, Wesnousky & Bills 1999
— and that map-view geometry is not limited by that), with two further siblings under
`lane62/` (datum-break dotted) and `lane62-h62a/` (isobase step, 38,000 dots).

That is good news for the science and awkward for the code, and both are recorded here.

* **Science.** Three sessions read the same datum and picked two different observables
  from it. This lane's own negative result is evidence *for the trunk's choice*: the
  vertical amplitude measured through 100 m leg windows agrees with an independent
  per-limb profile estimator at correlation 0.08, so vertical amplitude at this cell
  size is not a trustworthy throw, while the geometry (84% of the top detections
  further than 3 px from any mapped fault, median measured offset inside the published
  12-45 m band) does hold up. A lane that keys off where the shoreline trace *bends*
  sidesteps exactly the failure this lane measured.
* **Code.** Nothing outside `lane62-bench/` is added or modified by this lane: no
  writes to `src/gems62/**`, the root `docs/`, `evidence/`, `scripts/` or `tests/`,
  and no data files (the contest rasters are read from the trunk's `data/`). The
  modules this lane was built against are vendored as the package `gems62_bench`,
  because the trunk's shared APIs have since diverged from them — `grid` now exposes
  `GRID/load_band/check_submission` and no `load_grid()`, `validate` is
  `validate_submission(path, footprint, ...)` returning a `ValidationReport`,
  `holdout.evaluate` replaced `holdout_segmented.build_holdout`, `uniqueness` is
  `compare/verdict/dump` instead of `compare_array_to_registry`, and
  `submission_writer` was removed in favour of `grid.write_submission`. Porting onto
  those interfaces would have changed the layout *and* the semantics of every number
  in this README at once, which destroys the audit trail; the follow-up is listed
  below instead.
* **Reproduction after the move.** The field-cache key is a hash of
  (DEM, detector source, gate parameters) and came out unchanged, `8cb1391bcc519270`;
  the holdout ladder reproduced digit-for-digit (0.0300 / 0.0390 / 0.0397, same CIs,
  same emitted-pixel counts) and the re-emitted raster came back with the same sha256,
  `12aa5d45…`, `checks_passed=True`, 184.9 s. That run is committed as
  `lane62-bench/evidence/repro_lane62.json`: every block is comparable to
  `lane62-bench/evidence/lane62.json`, and the only differences are the vendored package
  name inside `holdout.evaluator` and the writer's staging temp path.

* **Agreement with the siblings.** `lane62-bench/scripts/sibling_crosscheck62.py`
  measures this emission against every submission raster in the repo — not to rank
  them, but because a lane that is 90% contained in another is redundant, and a lane
  that is 5% contained is a second, independent look.
  Numbers (`lane62-bench/evidence/sibling_crosscheck62.json`, 300 m radius, 4-px
  strided ranks), with a chance level from dots of the same size drawn inside the
  same tread habitat:

  | sibling emission | its dots | share of *my* dots within 300 m | chance | enrichment |
  |---|---|---|---|---|
  | `lane62/` datum-break dotted (primary) | 86,968 | 0.676 | 0.576 | **1.17×** |
  | `lane62-h62a/` isobase step | 38,000 | 0.249 | 0.215 | **1.16×** |
  | trunk `docs/` isobase 99-dot demo | 99 | 0.003 | — | (its dots: 66% near mine) |

  Read this before anyone proposes a merge or reads overlap as corroboration. All
  three lanes are tread-restricted, so most of their mutual overlap *is* the habitat
  mask: within-habitat placement agreement is only ~17% above chance, which is why
  Spearman between lanes is 0.01-0.03 and the 3-px IoU after 300 m dilation is
  0.14-0.28. It does **not** follow that the lanes are interchangeable — the holdout
  separates them by 3-8× (this lane 0.0397, `lane62-h62a`-class siblings 0.002-0.013)
  and a random dot set drawn *in the same habitat, at the same budget* scores
  **0.0002** against the same hidden truth, i.e. within-habitat placement, not the
  habitat prior, is what the score is paying for. Two consequences: overlap numbers
  here must be null-corrected before they count as agreement, and unioning this lane
  with the wider sibling adds little new territory — consistent with the measured
  −0.008 for the external-catalogue union (`lane62-bench/evidence/blend62.json`).

## Follow-up work (not done, and not silently skipped)

1. **Exact uniqueness pass.** The `PASS` above is a 4-px-stride screening pass over
   all 753 accessible sibling rasters (170 s), justified because Spearman and
   support-overlap are rank/area statistics that a stride does not move; the
   full-resolution protocol run was interrupted and
   `lane62-bench/evidence/uniqueness.json` says so rather than implying a clearance.
   Re-run `lane62-bench/scripts/uniqueness_gate62.py` (~25 min per candidate) to close it.
2. **Port to the trunk modules** (`grid`, `validate_submission`, `holdout.evaluate`,
   `uniqueness.compare`) and delete the vendored copies, re-running the ladder in the
   same commit so the before/after numbers are comparable.
3. **Test the amplitude claim differently.** Run the trunk's map-view deflection
   detector on *this* lane's detections: if the two agree on where the datum breaks,
   the geometry is confirmed twice and the amplitude question can be retired.
4. **Validate the profile estimator itself.** It is used here to reject a claim, and
   it has no synthetic-truth test of its own — on scarps of known throw, the
   per-limb intercept difference should recover the injected offset to a few metres.
   Until it does, "0.3 m median" is a comparison, not a measurement of the true throw.

## The negative result, stated plainly

`lane62-bench/scripts/shoreline_profiles62.py` re-measures the top 400 detections with an
independent estimator — each limb of a 3 km bench profile gets its own robust line,
and the throw is the difference of the two intercepts at the detected crossing.
Median profile offset **0.3 m** against a matched-filter median of 44.8 m, median
absolute disagreement 15.0 m, agreement within 5 m on 19% of profiles, correlation
**0.08**. So:

* the *amplitude ranking of this lane is not confirmed* and must not be quoted as
  slip. On real terrain the leg windows straddle several tread levels, and oblique
  trends inflate |J| — the same mechanism the synthetic exposes when terraces are
  flat. 0.25% of flagged pixels sit at the 60 m saturation cap and are the least
  confirmable of all.
* what *is* supported is the geometric claim (a broken level surface on a pluvial
  tread, off the catalogue: 84% of the top detections are more than 3 px from any
  mapped fault) and the 16.4 m median, which is in the published band.
* consequently this lane is used as a **detection prior for trace placement**, and
  the submission is standalone: the pricing run showed that unioning it with the
  external catalogue raster *lowers* the proxy score (−0.008), so blending was
  rejected on measurement, not on taste.

## Holdout caveat

The segmented holdout hides 20% of the *catalogue* and scores only that. A lane
that does not read the catalogue can therefore only score where its geomorphic
detection happens to coincide with a catalogued-but-withheld trace, which is a
*pessimistic* proxy for a submission scored against expert-added new faults. The
live value of this lane is not predictable from 0.0397 in either direction; it is
a measurement, and it is what the run card records.

## Reproduce

```bash
PY=/home/user/.venv/bin/python            # numpy 2.4, scipy 1.17, rasterio 1.4.4
$PY -m pytest tests/test_lahontan.py -q    # 21 passed
$PY lane62-bench/scripts/run_lane62.py --rebuild-field --min-step 12 --max-step 60 \
    --seed-min-step 25 --sep-px 6 --max-seeds 12000 --trace-max-px 100 \
    --trace-min-score 0.02 --no-fill --ladder 40000,80000,120000 --emit \
    --name gems62-lahontan-datumstep-min12max60-seed25-traceonly \
    --note "Lahontan bench datum-step lane: matched filter over 12 trends on pluvial tread pixels, per-limb stability gate, trace-only emission"
$PY lane62-bench/scripts/shoreline_profiles62.py --n 400
$PY lane62-bench/scripts/blend_eval62.py
$PY lane62-bench/scripts/uniqueness_gate62.py           # exact-protocol gate, ~25 min per candidate
```

The step field is cached in `/home/user/datacache/lahontan62_*.npy` under a key
derived from the DEM hash, the detector source and the gate parameters, so a stale
field cannot be mistaken for a current one (an out-of-date cache invalidated a
whole morning of debugging here, hence the pin). `--skip-uniqueness` moves the
registry scan out of the critical path; it used to run before the writer and once
cost the run its artifact.

## Provenance and licensing

Inputs: the contest DEM tile `geodawn_dem_a2_100m.tif` (49.5 MB float32, nodata
−999999, sha256 `d32762a382…e14431`, pinned in `lane62-bench/scripts/run_lane62.py`) and
`data/ (the trunk's contest rasters){sample_submission,existing_faults,labels}.tif`. The sibling-lane and
registry rasters used *only* for scoring comparisons are read from an external
cache (`$GEMS_REGISTRY`, default `/home/user/datacache/registry`, built by
`scripts/refresh_registry62.py` from 72 accessible sibling repositories, 753
unique competition-grid rasters, 0 errors). No external data enters this lane's
submission raster, so no third-party licence applies to the artifact; the SGMC
Nevada fault layers appear in `blend_eval62.py`'s pricing table only, and a
submission that embedded them would need the sponsor-sharing licence confirmed
first.

Figures: `lane62-bench/docs/assets/lahontan62_profiles.png` (measured profiles against the fitted
datum), `lane62-bench/docs/assets/lahontan62_map.png` (tread habitat, off-catalogue steps).
Run card: `lane62-bench/evidence/lane62.json`. Held-out pricing: `lane62-bench/evidence/blend62.json`.
Independent re-measurement: `lane62-bench/evidence/shoreline_profiles62.{json,csv}`.
Uniqueness: `lane62-bench/evidence/uniqueness_screen62.json` (screening pass, 4-px stride) and
`lane62-bench/evidence/uniqueness.json` (exact protocol; left incomplete when the run was
ended — re-run the gate to regenerate).
