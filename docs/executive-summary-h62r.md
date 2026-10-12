# Executive summary — H62-R, the file, and exactly how to submit it

Session `arena/7eee17f9-62gemsdoe`, 2026-10-12. Every number below is either **MEASURED**
in this checkout (the receipt that produced it is named) or **OWNER-REPORTED** (a score
quoted by the owner; no receipt). No projection is written as a score anywhere on this page.

---

## 1. Download this file

**`docs/downloads/gems62-h62r-multilevel-datum-repeat-offset-zeros.tif`** &nbsp;·&nbsp;
[⬇ download](downloads/gems62-h62r-multilevel-datum-repeat-offset-zeros.tif) &nbsp;·&nbsp;
[.zip](downloads/gems62-h62r-multilevel-datum-repeat-offset-zeros.zip)

| | |
| --- | --- |
| **bytes** | 116,946 |
| **sha256** | `d5a15369fdd8863f73691ad01d2557feafd8f901d442d593c4f4b9bd858b4731` |
| **dots** | **14,765** single-pixel dots, values exactly `{0, 1}` |
| **isolation** | MEASURED: minimum nearest-neighbour distance **300.000000 m**; **0** of 14,765 dots has any kernel overlap with another dot (max kernel mass received from other dots = **0.000000**) |
| **submission name** | `gems62-h62r-multilevel-datum-repeat-offset-zeros` |
| **note (137/140 chars)** | `H62-R: 4 measured Lahontan datum levels, collinear steps on >=2 levels, 14,765 isolated off-catalogue dots. Legal; probe.` |

### Verdict

| leg | result | receipt |
| --- | --- | --- |
| **FORMAT** | ✅ **LEGAL — 14/14** on the bytes re-read from disk: single band, `float32`, EPSG:32611, 3730×3292, the sample submission's exact geotransform, `n_outside_0_1 = 0`, `nan_count = 0`, `nodata = null`. The portal error *"Predicted values must be in range [0, 1]"* **cannot occur** for these bytes. | `evidence/h62r/e6_validation.json`, `evidence/h62r/e5_emission.json` |
| **UNIQUENESS** | ✅ **UNIQUE.** 475 comparators from the auto-harvested registry: max \|Spearman\| **0.0128** (limit 0.90), worst symmetric 3-px Jaccard **0.0918** (limit 0.25), **0** comparators over the overlap limit among the non-vacuous. 14 comparators flagged *vacuous* (their own 3-px dilation covers ≥70 % of the footprint, so overlap with anything is meaningless — IR-62-22). | `evidence/h62r/e7_uniqueness.json` |
| **OFF-CATALOGUE** | ✅ MEASURED: **0.0 %** of dots within 300 m of a mapped fault; median distance **2,062 m**; 76.5 % beyond 1 km. Dots within 300 m of the catalogue were deleted — those pixels are masked out of live scoring (OFFICIAL, organizer forum thread 11516). | `evidence/h62r/e10_field_stats.json` |
| **HOLDOUT-DTI** | ⚠️ **0.000000** — **structurally vacuous, not a failure.** The catalogue-exclusion radius and the metric kernel radius are both 300 m, so a dot that obeys the exclusion has kernel weight exactly 0 against every mapped fault. Equal-budget controls on the same folds: random_lines **0.0032**, random_dots **0.0287**, catalogue_offset **0.0249**. Logged `IR-62-H62R-02`. | `evidence/h62r/e9_holdout.json` |
| **EXPECTED SCORE** | **Not claimed.** No local instrument in this repository can rank this field; see §4. | — |
| **ORGANIZER SCORE** | **none** — never submitted. `organizer_score: null`. | — |

### The one-line version

> **A legal, unique, provably-isolated, off-catalogue dotted field produced by a method that
> has never been run in this group — four independently *measured* Lahontan shorelines
> (1455, 1389, 1325, 1278 m) and a Hough collinearity repeat-offset test across them. It
> cannot be a re-run of anything: its only input is the DEM. It is a probe, not a validated
> gain, and the holdout gate is reported as structurally vacuous rather than quietly failing.**

---

## 2. How to submit this file — six steps, no edits

1. **Download** `gems62-h62r-multilevel-datum-repeat-offset-zeros.tif` (or the `.zip`, which
   contains exactly that one GeoTIFF — verified with `unzip -l`).
2. **Verify the bytes** (5 s): `sha256sum …tif` must start `d5a15369`.
3. **Sign in** and open the [submission page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/).
4. **File to submit** → the `.tif` from step 1. A bare GeoTIFF is accepted; no `.zip` needed.
5. **Note (optional, 137 chars)** → paste the note from §1.
6. **Submit.** The score appears on the [leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).

**Step 7 — the highest-value action available to this project.** Copy the score row into
`evidence/organizer_receipts.json` and commit it. This repository contains **zero**
organizer-confirmed scores; one receipt converts every proxy argument in it into a
calibrated instrument.

### What the form checks, and where this file satisfies each check

| portal requirement | this file | enforced by |
| --- | --- | --- |
| single-band GeoTIFF | `count = 1` | one writer, then re-read from disk |
| 32-bit float | `float32` | asserted on write and on re-read |
| matches the training CRS | EPSG:32611 | pinned constant, asserted |
| matches the shape | 3730 × 3292 | asserted against the official sample submission |
| matches the geotransform | `(100, 0, 243350, 0, −100, 4508550)` | compared to 1e-6 |
| values in `[0, 1]` | min 0.0, max 1.0, `n_outside_0_1 = 0` | asserted before write **and** re-counted after |
| no NaN inside the footprint | `nan_count = 0`, all finite, **no nodata tag at all** | zeros outside the footprint |

---

## 3. What this session actually did

### 3.1 The lane, step by step, each step measured

| step (lane paragraph) | implementation | MEASURED result |
| --- | --- | --- |
| "map shoreline benches in the DEM" | `gems62.datum.bench_response` — flat tread, riser 100–500 m away, ≥12 m above the local 3 km floor | bench pixels at the four levels: **25,044 / 22,763 / 21,324 / 18,080** |
| "fit a smooth isobase, allowing for post-pluvial isostatic rebound" | per-level **robust tile-mode** isobase (`gems62.levels.robust_isobase`, 4 km tiles, 5.5 km NaN-aware smoothing) | residual medians **0.4–2.7 m**, MAD **22.7–26.7 m** |
| "flag abrupt steps or lateral deflections along strike" | steps: robust z-test inside a physical 15–140 m throw window. Deflections: 12 px (1.2 km) azimuth kink | steps **12,211** px (3,164 / 3,301 / 2,866 / 2,880); deflections **0 px** |
| "seed a trace at each, extend it while DEM-ridge evidence supports it" | `gems62.emit.structure_tensor` → `traces_from_flags`, then a 2 km seed dedupe | **2,509** lines accepted (all multi-level), **8,724** support px → **771** distinct traces, **6,983 km** |
| "emit dotted lines" | `dots_from_traces` at 300 m spacing, 300 m catalogue exclusion | **14,765** dots; 24,037 samples taken, 2,195 dropped on the exclusion |

### 3.2 The new idea, stated once

The Lahontan datum is not one surface. It is a **stack of nested shorelines** at different
elevations and therefore of different ages. This session **detected** that stack from the DEM
(1455, 1389, 1325, 1278 m; block support 7, 7, 12, 7 of 323 twenty-kilometre blocks) instead
of assuming a single datum band, then demanded that a flagged step lie on **one common line
with flagged steps on at least one other level**. Because shorelines are nested, the naive
test ("the same place on two levels") is geometrically wrong — a fault is a *line*, and it
crosses each level at a *different* point — which is why the test here is a Hough collinearity
vote with sign agreement. Independent cross-check that the detection is real: the strongest
level, **1325 m**, matches both the published Lahontan highstand band and the **1,332–1,347 m**
block isobase an earlier session fitted independently (`lane62/evidence/isobase.json`, 86 blocks).

### 3.3 Three defects this session found and fixed

* **`IR-62-REG-01`** — `tools/fetch_registry.py` wrote every blob to `f"{repo}__{basename}"`, so
  all `docs/downloads/submission.tif` files collapsed onto one filename: 46 of the first 51
  fetches overwrote each other. The uniqueness gate would have compared against a fraction of
  the registry **while reporting the full count**. Fixed; the re-fetch returned **476** distinct
  rasters.
* **`IR-62-REG-02`** — `src/gems62/uniqueness.py` raised `ValueError` on a shape mismatch, so a
  single 32×48 format-test image killed an unattended uniqueness run. Now skipped and counted
  in the verdict.
* **`IR-62-H62R-03`** — the first version of this lane's own isolation statistic counted a
  radius-3 disc **including its boundary**, so two dots exactly 300 m apart (kernel weight
  exactly 0) were reported as "sharing a disc" — the receipt said 39 % of dots shared one while
  a k-d tree said the minimum nearest-neighbour distance was exactly 300.000 m and the mean
  self-kernel was 0.000000. The statistic now measures the thing that costs mass, and the two
  agree: **0 dots with kernel overlap**.

### 3.4 The deliverable the lane names first

**`docs/h62r/h62r_shoreline_profiles.png`** — **532** shoreline runs, **2,844 km** total,
**119** carrying flagged steps, plotted as elevation *above the fitted isobase* against
along-strike distance. Machine-readable: `docs/downloads/h62r-shoreline-profiles.csv`
(one row per sample, `is_step` column) and `evidence/h62r/e4_profiles.json`.
Also: `docs/h62r/h62r_level_spectrum.png` (the measured level spectrum, per 20 km block) and
`docs/h62r/h62r_field_map.png` (the emitted field against the excluded catalogue).

---

## 4. Limits of this page

* **No organizer score exists for any file here.** Every comparison is a proxy.
* The leaderboard mirror in `research/leaderboard_series.json` is owner-reported; this sandbox
  cannot reach `drivendata.org` (MEASURED: curl exit 35 / HTTP 000).
* A local format check is **not** organizer acceptance, and uniqueness against a harvest of
  other groups' public repos is **not** the organizer's novelty check.
* The holdout number is **structurally vacuous** for this field and is labelled as such; the
  controls on the same folds are what make that visible (the field scores *below* its own
  random-dot control, which cannot happen for a field that is being measured honestly).
* The DEM is an owner-supplied mirror, not organizer-authenticated, and it is not on the
  competition data tab (`IR-62-DEM-01`).
* The lateral-deflection half of the lane paragraph is a **measured NULL** on all four levels
  even at a 1.2 km lever arm (`IR-62-DEFL-01`); no deflection flags are claimed.
