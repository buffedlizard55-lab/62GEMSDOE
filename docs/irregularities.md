# Irregularities, defects and traps — flagged, with what was done about each

The brief asks for irregularities to be flagged rather than smoothed over. These are ordered by
how much damage they could do.

## 1. The portal error you hit: "Predicted values must be in range [0, 1]"

**Diagnosis.** The official spec asks for a single-band `float32` raster with values in `[0, 1]`
[OFFICIAL, competition page 967]. Two writing habits violate it while looking correct on screen:
a `float32` **sentinel** such as `-3.4028235e38` (survives as an outlier inside the valid
footprint), and a **NaN nodata tag** (the reader returns NaN, which is not in `[0, 1]`).
The defective artifact from the earlier session — `gems32-h19-5-smoothmaxcov-44090.tif` — is one
of these, and it is **quarantined by standing rule: never ship, never re-emit.**

**What is done about it.** One writer, one code path, and the file is **re-opened from disk and
re-counted** before anything is published (`grid.check_submission`). The current file reports
`nodata = null`, `nan_count = 0`, `n_outside_0_1 = 0`, `all_finite = true`. The two mechanisms are
structurally absent, not merely avoided.

## 2. This session's own holdout instrument was wrong three times

Reported in full, because the numbers above are only trustworthy if the failures are visible.

| defect | symptom | fix |
| --- | --- | --- |
| fold did not confine scoring (`active = footprint & ~visible`) | `n_pred = 1660` in *every* fold; the whole footprint was scored each time | score only inside the eroded block |
| canary negatives drawn basin-wide while positives were fold-local | AUC pinned at exactly ~0.500 in every fold — a degenerate tie, not a clean bill of health | negatives from the same fold interior |
| "wholly inside the block" component rule | `n_truth = 0` in all 6 folds — the catalogue is one basin-scale connected component, so nothing is ever "wholly inside" | block-scale withholding with a 3 px erosion |
| `metric.dti_binary(pred, truth & active, active)` | truth silently zeroed (the module applies `active` to truth itself) | pass the block as the scored domain, not the block minus the catalogue |

Then a fifth, of a different kind: a run crashed on an undefined variable, its stdout/stderr were
suppressed to `/dev/null`, and the **stale JSON from the previous run was read as the result**.
The lesson is recorded in the commands: never suppress output when the artefact is the evidence.

The evaluator version that produced the numbers in `run-card.md` is the one *after* all five
fixes, and the fold arithmetic is asserted (`a withheld pixel survived inside the scoring zone`
raises).

## 3. The one-sided registry tripwire is density-blind — but remains binding

**Protocol defect and consequence.** The literal rule is "> 70% of the candidate's dots within
3 px of one registry raster's dots ⇒ trip/stop." A dense comparator can make this uninformative.
The registry includes `13gems_20261001_r13-lattice-s5_v2` with **206,895 dots**; its 3 px
neighbourhood blankets the submission footprint. A uniform-random 1,660-dot control was previously
measured at `dot_overlap_within_kernel = 0.9982` against it, demonstrating that this gate can trip
on unrelated sparse dots.

**Required implementation.** Despite that known limitation, the literal threshold is binding:
compare every registry raster, trip if the one-sided Euclidean overlap is **> 0.70**, and do not
suppress a trip because a comparator is dense or because symmetric Jaccard is low. The code in
`src/gems62/uniqueness.py` and `scripts/check_uniqueness.py` now follows that decision rule.
Comparator coverage and symmetric Jaccard remain diagnostics only. The script also masks both
rasters to the official footprint and uses Euclidean distance (not square/Chebyshev dilation).

**Corrected result for v8:** the preserved 289-raster report gives maximum rank correlation
**−0.0652** (no rank trip) and maximum one-sided overlap **1.00** (trip). Its maximum Jaccard
**0.0302** is not a waiver. The correct verdict is **DUPLICATE — STOP**. The previous
`UNIQUE-VS-REGISTRY` result was wrong; it substituted Jaccard for the binding condition. Because
per-comparator rows were trimmed from the legacy JSON and the registry is not present in the
current checkout, this is a retrospective reclassification of the preserved maximum, not a fresh
registry scan. Do not submit v8.

## 4. The catalogue-based holdout anti-selects novelty — so it is not a score

Measured three independent ways (`hypotheses.md`, "the validation trap"): a sibling repository
measured ρ = **+0.087** between its catalogue-hidden proxy and the live leaderboard; its Poisson
control (0.098) beats an artifact that scored 0.2778 live (0.019); and this repository's own
Poisson control (0.0669) beats the same artifact (0.0067) by 10×.

**Consequence, stated in every document that carries the number:** the holdout is a bug screen, a
leakage canary and a null generator. It is **never** written as a score, and it is never used to
promote or reject a file.

## 5. Owner-reported scores are claims, not receipts

The scores the user has quoted (0.2778, 0.3774, …) are recorded here as **OWNER-REPORTED**. No
organizer receipt, e-mail or exported leaderboard row is present in this repository, and the
competition pages do not expose them to this sandbox. They are used only to *rank the group's own
artifacts against each other*, which is what the user asked for, and never as an evaluation of a
file produced here. If a receipt exists, it should be committed as `evidence/` and this file
updated — it would be the first ORGANIZER-CONFIRMED number in the repository.

## 6. Submission note length

The stated limit is 140 characters; the site has previously accepted 177–200 [OWNER-REPORTED].
This repository keeps **≤ 140** because that is the stated limit. The v8 tracking note is 134
characters and explicitly says not to submit.

## 7. DEM transport and format traps

* The 3DEP transport GeoTIFF is **int16 decimetres**, not metres, and the first fetch clipped the
  −32767 nodata sentinel to −32766 when rounding to decimetres. Handling it as metres made every
  elevation gate false; the fix is in `read_z()` and in the fetch writer (sentinel written *after*
  the clip, readers mask ≤ −32000).
* Run **38169049665** is recorded as **success with no artifact** — a silent-empty result. It is
  kept in `evidence/` precisely because "success" was not the same as "produced data".
* `dem_transport.json` records `resampling: "as-is"`, i.e. the mosaic is not reprojected here; the
  tiles are already EPSG:32611 at 25 m.
* Coverage after run **38169727207**: 6 tiles, valid fraction **0.8088** (was 0.590 with 5). The
  per-block coverage map has not been re-verified since the 6th tile landed — a gap in this
  session's evidence, listed in `next-steps.md`.

## 8. Second-hand layer names

The band names used for hypotheses H-A and H-D (`lidar_scarp_features_u8.tif`, `geodawn_rad_u8.tif`,
`training_features.tif` bands 13/15/17) are **[SIBLING-MEASURED]** — read from band descriptions in
a sibling checkout. This repository does not clone the 418 MB feature stack, so they are **not
re-verified here**. Treat them as a lead to confirm before building on.

## 9. What the organizers will and will not tell us — read this before trusting any local score

* They will **not** share the data sources, fault types or coverage behind the test faults beyond
  the problem description [OFFICIAL, thread 11527 — chrisk-dd, 2026-09-23].
* **Phase 2 uses a test set updated by expert review of all Phase 1 submissions** [OFFICIAL, same
  post]. That does not waive the repository's strict duplicate stop: v8's verdict is **DO NOT
  SUBMIT**, independent of any strategic argument about Phase 1.

## 10. A suspicious statistic in this file's own output

The 221 traces have a **median length of 1.3 km** (max 5.6 km). Real fault traces are usually
longer, so the binding constraint is probably the trace-stopping rule rather than the geology.
Flagged as unresolved; see `next-steps.md`.
