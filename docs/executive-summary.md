# Executive summary — is it OK to download and submit this file?

## ✅ Verdict

**Download:** [`downloads/gemsdoe62-datum-lahontan-isobase-v8.tif`](downloads/gemsdoe62-datum-lahontan-isobase-v8.tif) —
sha256 `3d4b66e651bc8e3f58779e4c52e4af66c70d6f8d871308b21720e9003ebd43ba`, 62,709 bytes.

**It is legal to submit.** Single band, `float32`, EPSG:32611, 100 m, 3730×3292, values exactly
in `[0, 1]`, **no nodata tag and no NaN anywhere** — the two mechanisms behind the portal error
you hit ("Predicted values must be in range [0, 1]") are structurally absent. Every field below
is re-read from the bytes on disk by `grid.check_submission`, not from the array in memory.

**It is unique.** Checked against all **289** prior rasters in the group registry: worst rank
correlation is **−0.065** (threshold 0.90) and worst symmetric dot overlap is **0.030** (threshold
0.25 as corrected, see below). No duplicate flag.

**Should you spend a weekly slot on it?** *Only as a novelty probe, never as your lead horse.*
The honest expectation is **below** the group's best scored artifact
(`gems32-h33-h33-2-b2-…-zeros`, 0.2778, OWNER-REPORTED). The reasoning and the numbers are in
§3 — including the measured fact that the local holdout instrument **cannot** rank submissions
for this task, so it is reported rather than used as a gate.

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
| `legal` | **true** | MEASURED (`grid.check_submission`) |
| rank correlation vs 289 registry rasters | max **−0.065** | MEASURED |
| dot overlap vs 289 registry rasters | max asymmetric 1.00 (**density artefact**), max symmetric Jaccard **0.030** | MEASURED |

## 3. The number you must not over-read — and why

| emission | local holdout DTI | ratio to its own Poisson null |
| --- | ---: | ---: |
| **this file (v8)** | 0.0029 | 0.74× |
| `gems32-h33-2-b2-…-zeros` (**OWNER-REPORTED live 0.2778**) | 0.0067 | **0.10×** |
| Poisson control, same density as this file (1,660 dots) | 0.0039 | 1.00× |
| Poisson control, same density as h33 (37,654 dots) | **0.0669** | 1.00× |

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

## 4. How to submit

1. Download `docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif` (one click, [`index.html`](index.html)).
2. On the DrivenData submission page for competition 306, upload it as-is — do not re-encode, do
   not add a nodata tag, do not convert to a different dtype.
3. Submission name: `gemsdoe62-datum-lahontan-isobase-v8`; note (≤ 140 characters, site has
   previously accepted longer but the stated limit is 140):
   > `Lake Lahontan pluvial-bench isobase: 1660 dots on stepped/deflected shoreline benches; 221 DEM-ridge traces; unique vs registry.`
4. If you have only one slot in the week, spend it on the group's h33 lineage, not on this file.

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
