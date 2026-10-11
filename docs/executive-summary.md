# Executive summary — is it OK to download and submit this file?

## 🛑 Verdict: download for review only; DO NOT SUBMIT

**Download for inspection:** [`downloads/gemsdoe62-datum-lahontan-isobase-v8.tif`](downloads/gemsdoe62-datum-lahontan-isobase-v8.tif) —
sha256 `3d4b66e651bc8e3f58779e4c52e4af66c70d6f8d871308b21720e9003ebd43ba`, 62,709 bytes.

The format receipt is **legal = true**: single-band `float32`, EPSG:32611, 100 m, 3730×3292,
values in `[0, 1]`, no nodata tag and no NaN. That confirms format only; it does not clear the
file for submission.

**The strict uniqueness gate fails.** The preserved maximum one-sided dot overlap is **1.00**
within 3 px, above the binding **0.70** stop threshold across 289 prior rasters. The reported
symmetric Jaccard **0.030** is diagnostic only and cannot override that trip. The previous
`UNIQUE-VS-REGISTRY` label was wrong. Record the result as **DUPLICATE — STOP**, and do not spend
a weekly slot. The required pre-placement surface-gate receipt is absent, so that half is
**NOT VERIFIED**; the final-dot trip already blocks submission. Full correction:
[`irregularities.md`](irregularities.md) §3.

The HOLDOUT-DTI is also weak and is **not** an organizer score. No replacement candidate, fresh
registry scan, new holdout run, or organizer-confirmed receipt was produced in this correction.

---

## 1. What the file is

1,660 dots at **pluvial-Lake-Lahontan bench steps and deflections**, found in the official
25 m USGS 3DEP DEM by the datum-offset lane:

| step | what it does | result |
| --- | --- | --- |
| benches | flat pixels whose elevation equals the local mode in an 8 km tile, inside the basin-wide stand band [1157, 1455] m | 1,471,982 flat pixels hit the pass-1 filter |
| isobase | robust (Huber IRLS) 6-term quadratic in UTM — absorbs post-pluvial rebound and regional tilt, **cannot** follow a fan apron or one scarp | r.m.s. residual 48.4 m |
| loci | Frangi ridge of \|∇(z − isobase)\|, offset measured at ±250 m, requiring evidence ≥ 0.10, step ≥ 2 m, ≤ 1500 m from a bench, **and the step trace crossing the datum contours by ≥ 30°** | 2,003 flagged → 400 kept after 2 km separation |
| traces | 5-candidate heading search, whole-segment sampling, stop when DEM-ridge evidence < 0.15 | **221 traces** (median 1.3 km, longest 5.6 km) → **1,660 dots** |

The cross-cut gate is the geomorphological discriminator and the reason this lane is not firing on
every range front: a step that runs *parallel* to a datum contour is a level feature (fan-head
riser, wave-cut bluff, berm); a tectonic scarp steps height *across its own trace*, so it crosses
contours. Full method and the six bugs that were found and fixed on the way:
[`run-card.md`](run-card.md).

## 2. Format and uniqueness receipts

| check | value | class |
| --- | --- | --- |
| bytes / sha256 | 62,709 / `3d4b66e651bc8e3f…` | MEASURED |
| driver / band / dtype | GTiff / 1 / float32 | MEASURED |
| CRS / shape / res / transform | EPSG:32611 / 3730×3292 / 100 m / (243350, 4508550) | MEASURED, matches the official sample |
| values | min 0.0, max 1.0, `n_outside_0_1 = 0`, `nan_count = 0`, `all_finite = true`, `nodata = null` | MEASURED |
| `legal` | **true** — format validity only, not submission clearance | MEASURED (`grid.check_submission`) |
| rank correlation vs 289 registry rasters | max **−0.065**; no rank trip at 0.90 | MEASURED |
| one-sided dot overlap vs 289 registry rasters | max **1.00** within 3 px; strict trip because 1.00 > 0.70 | MEASURED; **DUPLICATE — STOP** |
| symmetric Jaccard | **0.030** | diagnostic only; not a substitute gate |

## 3. The number you must not over-read — and why

| emission | local proxy metric and evidence class | ratio to its own Poisson null |
| --- | --- | ---: |
| **this file (v8)** | **HOLDOUT-DTI 0.00286** — `scripts/run_holdout.py` v2; 60,362 withheld positives; spatial-fold 95% CI not estimable (5/6 folds have no predictions); pooled-recall Wilson95 [0.001955, 0.002723] is not a DTI CI | 0.74× |
| `gems32-h33-2-b2-…-zeros` (**OWNER-REPORTED, unverified live value 0.2778; not organizer-confirmed**) | calibration proxy DTI 0.0067; evaluator/withheld count/CI not supplied in this legacy comparison; not a score | **0.10×** |
| Poisson control, same density as this file (1,660 dots) | legacy proxy calibration value 0.0039; no DTI CI retained; not a score | 1.00× |
| Poisson control, same density as h33 (37,654 dots) | legacy proxy calibration value **0.0669**; no DTI CI retained; not a score | 1.00× |

Read the bottom two rows against the top two. On the local instrument a **uniform random** field
outscores the artifact that actually scored 0.2778 on the live board, by 10×. The instrument
therefore measures the wrong quantity for this task — its truth is the USGS/INGENIOUS catalogue,
while the competition truth is precisely the faults *absent* from that catalogue. A sibling
repository measured the same defect independently: its catalogue-hidden proxy ranks live scores at
Spearman ρ = **+0.087**, and its Poisson control (0.098) beat the same h33 artifact (0.019).

So "below the catalogue null" is a **novelty signature, not a quality score**: h33 is 0.10× its
null and scored 0.2778. v8 is 0.74× its null — *less* novel than h33, and that is the single most
useful honest statement about this file. The instrument is kept only as a **screen** (it did catch
genuine bugs, and it produces the Poisson null above); it is not used to promote or reject.
See [`irregularities.md`](irregularities.md) §2.

## 4. Download and submission instructions

**Do not upload v8.** The linked GeoTIFF is available only for review; its strict gate is
`DUPLICATE — STOP` despite passing the format validator. Do not spend a weekly slot on it.

For internal tracking only:

- artifact name: `gemsdoe62-datum-lahontan-isobase-v8`;
- note (134 characters; explicitly negative, not an upload recommendation):
  > `Lake Lahontan pluvial-bench isobase: 1660 dots on shoreline datum breaks; 221 DEM-ridge traces; DO NOT SUBMIT (registry overlap trip).`

For a future candidate, first pass the spatially blocked holdout as a screen and both uniqueness
checks (surface before placement and final dots) using the literal rank-correlation and one-sided
overlap thresholds. Only a candidate with a new verified run card and a non-trip may be considered
for upload. No such replacement file is part of this correction.

## 5. Where this leaves the effort (limitations, stated plainly)

* **Coverage.** 1,641 of the 1,660 dots fall in one 171 × 110 km sub-region of a 373 × 329 km
  grid. This lane buys defensibility in the Lahontan basin, not area.
* **Traces are short.** Median 1.3 km — a real fault trace is usually longer. The emitter's
  stopping rule, not the geology, is the likely binding constraint.
* **No local instrument can certify novelty.** The catalogue proxy anti-selects it (above). The
  only remaining evidence is geological argument, and it is recorded as such.
* **Unrun, cheap, highest expected value:** marginal-credit density calibration (hypothesis H3 in
  [`hypotheses.md`](hypotheses.md)) — β = 0.8 makes the metric recall-dominated, so the emission
  *density* is worth more than the detector's precision, and the break-even condition is
  computable from `metric.marginal_bar` without any hidden truth.
