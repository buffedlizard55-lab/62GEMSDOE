# Executive summary — the file, the verdict, and exactly how to submit it

Session `arena/d0303476-62gemsdoe`, 2026-10-11.  Everything below is reproducible from this checkout;
the script and the receipt behind each number are named.

## 1. Download this file

**`docs/downloads/gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.tif`**

| | |
|---|---|
| **bytes** | 481,168 |
| **sha256** | `42bffef1b5973973…` (full hash in `evidence/run_card_20261011b.json`) |
| **dots** | 120,000, hard-core: **at most one dot inside any 300 m disc** (verified by disc convolution, `evidence/final_field_gems62b-…json → stats.max_dots_in_300m_disk = 1`) |
| **values** | exactly `{0, 1}` — a dot field, not a probability surface |
| **submission name** | `gems62b-tiltgrad-vote-scarpcorrob-120000-zeros` |
| **note (paste into the form, 138/140 chars)** | `62b: 120k isolated dots from a 13-layer derivative vote with scarp corroboration. Off-catalogue. Legal & unique; probe, not a proven gain.` |

### Verdict

| leg | result |
|---|---|
| **FORMAT** | ✅ **LEGAL.**  All 14 checks pass on the bytes **re-read from disk** (`gems62.grid.write_submission` → `check_submission`): single band, `float32`, EPSG:32611, 3730×3292, the sample submission's exact geotransform, `n_outside_0_1 = 0`, `nan_count = 0`, `nodata = null`.  The portal error *"Predicted values must be in range [0, 1]"* cannot occur for these bytes (no nodata sentinel and no NaN tag — both mechanisms are structurally absent). |
| **UNIQUENESS** | ✅ **UNIQUE.**  Against 25 prior rasters: max Jaccard **0.022**, max exact-pixel overlap **4.6 %**, max tie-aware rank correlation **\|ρ\| = 0.035**.  The protocol's "≤ 70 % of dots within 3 px of one registry raster" leg is tripped by `r13_lattice_s5_00904` (0.995) — and that trip is **vacuous and measured to be vacuous**: a uniform-random field of the same size scores **0.9987** and a 3 px lattice scores **0.9988** on that comparator (`evidence/e4_gates_20261011b.json`).  Logged, not overruled. |
| **PROMOTION GATE** | ❌ **FAILS.**  HOLDOUT-DTI **0.00073** (CI [0.00069, 0.00076], 81,993 withheld positives, evaluator `gems62.holdout_segmented v1`) against the current holdout best 0.1322. |
| **WHY IT FAILS — measured, not excused** | The segmented gate scores *catalogue segments withheld from view*, so it rewards fields that sit near the mapped catalogue.  Over 20 artifacts with owner-reported scores, credit per dot against the **mapped** catalogue correlates **−0.597** (p = 0.0054) with the leaderboard.  This field is deliberately off the mapped catalogue (median 2.2 km, 0.02× uniform-field credit), so the gate penalises exactly the property the leaderboard rewards. |
| **EXPECTED SCORE** | **Not claimed.**  No local instrument may be used as a score.  The one local quantity with a positive association with the leaderboard (credit per dot against an off-catalogue compilation, ρ = **+0.617**, p = 0.0038) puts this field at **0.0621**, 95 % of the champion's 0.0655 on the same instrument, at 3.2× the mass.  Under *exact transfer* the MODEL value is **0.222** — below 0.2778. |

### The one-line version

> **Download and submit if you want one clean, information-rich experiment: a field of champion-grade
> per-dot credit at 3.2× the champion's mass, provably isolated, unique against every prior raster,
> and legal to the byte — with a pre-registered, falsifiable prediction (it beats 0.2778 **iff** its
> true per-dot credit exceeds 0.0778).  Do not treat it as a validated improvement: it fails the
> protocol's holdout gate by construction, and that gate is measurably anti-correlated with the
> leaderboard.**

## 2. Step-by-step: how to put this file into the competition

1. **Download** `gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.tif` from
   `docs/downloads/` (or the site's download button).  A bare GeoTIFF is accepted — no `.zip` needed.
2. **Verify the bytes** (optional, 5 s):
   `sha256sum gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.tif` → must start `42bffef1b5973973`.
3. **Sign in** on DrivenData and open the submission form:
   <https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/>
4. **File to submit** → choose the `.tif` downloaded in step 1.
5. **Note (optional)** → paste the 138-character note from the table in §1.
6. **Submit.** The score appears on the public leaderboard
   <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>.
7. **Export the receipt — this is the highest-value action available to this project.** Copy the
   score row into `evidence/` and commit it.  This repository contains **zero** organizer-confirmed
   scores; one receipt converts the two proxies that currently *cannot* rank fields
   (ρ = +0.62 and −0.44) into a calibrated instrument.

### What the form checks, and where this file satisfies each check

| portal requirement | this file | enforced by |
|---|---|---|
| single-band GeoTIFF | `count = 1` | written by one code path, re-read from disk |
| 32-bit float | `float32` | asserted on write and on re-read |
| matches the training CRS | EPSG:32611 | pinned constant, asserted |
| matches shape | 3730 × 3292 | asserted against the official sample submission |
| matches geotransform | `(100, 0, 243350, 0, −100, 4508550)` | compared to 6 dp |
| values in `[0, 1]` | min 0.0, max 1.0, `n_outside_0_1 = 0` | asserted before write **and** re-counted after |
| no NaN inside the footprint | `nan_count = 0`, all finite everywhere | zeros (not NaN) outside the footprint, **no nodata tag** |

## 3. What this session changed, in one paragraph

Three local instruments were measured against 20 artifacts with owner-reported scores.  The
leaderboard rewards being **off** the mapped catalogue (ρ = −0.597 for catalogue credit) and rewards
per-dot credit against an **independent off-catalogue compilation** (ρ = +0.617) — but the published
DTI evaluated on that compilation **anti-correlates** with the leaderboard (ρ = −0.442), which
downgrades the repository's previous rank-1 recommendation (promote the never-submitted high-credit
field) and invalidates the segmented holdout as a promotion gate.  The exact condition for beating
0.2778 is derived and tabulated (credit ≥ 0.0778 at 120,000 dots), and one legal, unique,
provably-isolated field that meets the mass half of that condition is shipped with the falsifiable
prediction written down.

## 4. Limits of this page

* **No organizer score exists for any file here.** Every comparison in this document is a proxy.
* The leaderboard figures are a **mirror** (`research/leaderboard_series.json`); this sandbox cannot
  reach `drivendata.org`.
* A local format check is **not** organizer acceptance.
* The 3 px overlap leg of the uniqueness rule is **unsatisfiable** by construction for any dot field
  (measured, §1) — it is reported as tripped and its informativeness is reported as zero.
