# Executive summary — exactly how to make a submission, and what to submit

## 0. CURRENT (session 2026-10-12, `arena/778884cc-62gemsdoe`) — the file this session generated

**VERDICT: OK TO DOWNLOAD — format-legal and unique; NEGATIVE as an improvement — do not spend a
weekly slot expecting to beat 0.2778.**

| | |
|---|---|
| **Download** | [`downloads/gems62-h62n-lahontan-localmode-balanced-16864dots-20261012T003242Z-zeros.tif`](downloads/gems62-h62n-lahontan-localmode-balanced-16864dots-20261012T003242Z-zeros.tif) — 129,539 bytes ([zip](downloads/gems62-h62n-lahontan-localmode-balanced-16864dots-20261012T003242Z-zeros.zip)) |
| **sha256** | `2a25f29a6b235520a4965199045dae7226260665fc3ec248a79f04cb78bbe7f0` |
| **Submission name** | `gems62-h62n-lahontan-localmode-balanced-16864dots-20261012T003242Z-zeros` |
| **Submission note** (130 / 140 chars) | `H62-N Lahontan local-mode isobase, block-balanced trace network; 16,864 isolated dots >=300m off-catalogue; unique vs 379 rasters.` |
| **Portal-legal?** | **Yes** — validator on the re-read bytes: single band, float32, EPSG:32611, 3730×3292, sample transform, `nan_count = 0`, `n_outside_0_1 = 0`, no nodata tag; the "[0,1]" error cannot occur (`evidence/h62n_validator.json`). |
| **Unique?** | **Yes** — 379 comparators, 0 flags, worst informative Jaccard 0.2103 (limit 0.25), scored-comparator max 3-px overlap 38.4 % vs gate_ortho (limit 70 %) (`evidence/h62n_uniqueness.json`). |
| **Worth a slot?** | **No, on the measurements.** PROJECTION 0.0210 on the kernel-fixed portal-calibrated instrument (DTI(S*†) 0.0545 × 0.3848; a projection is never a score; the instrument under-predicts out-of-family fields ~4×, so the plausible band is 0.02–0.10 — below the incumbent 0.24–0.28 and below this repo's best, the datum62 detector at 0.2127). |
| **Organizer score** | none — never submitted. |

The rest of this page (how the portal validates, how to submit) is unchanged and applies to this
file identically. The section below is the 2026-10-11 session's file, kept as history.

## 1. The 2026-10-11 file, and the verdict on it (history)

**<span style="color:#f85149">VERDICT: NEGATIVE — this file is legal and unique, but it should not
take a weekly slot.</span>**

| | |
|---|---|
| **Download** | [`downloads/gems62-h62g-benchcrosscut-hardcore-zeros.tif`](downloads/gems62-h62g-benchcrosscut-hardcore-zeros.tif) — 98,893 bytes |
| **sha256** | `79eb0a7ddc2dcfb4667bff41bbc237f8d5663dd63e025eed79af8c8f984ed500` |
| **Submission name** | `gems62-h62g-benchcrosscut-hardcore-zeros` |
| **Submission note** (117 / 140 chars) | `H62-G Lahontan bench cross-cut, 10k isolated dots; credit at isolated-random control. NEGATIVE - do not spend a slot.` |
| **Portal-legal?** | **Yes.** Every validator check passes on the re-read bytes (§2). |
| **Worth a slot?** | **No.** Mean 300 m kernel credit **0.0420** at 10,000 dots vs a mass-matched isolated-random control of **0.04330 ± 0.00165** (5 seeds). At chance. At 5,000 dots it is 0.0572 vs 0.04279 (1.34×) — real but tiny, and the closed form still gives 0.027. |
| **Organizer score** | none — never submitted. |

## 2. The seven things the portal checks, and where each one is satisfied

The competition accepts *a single-band GeoTIFF (`.tif`), or a `.zip` containing a single GeoTIFF,
matching the submission format's CRS, shape and geotransform*
([submission form text, quoted by the owner](https://www.drivendata.org/competitions/306/competition-doe-gems/)),
and the format spec asks for *a single layer, 32-bit float, values between 0 and 1, same CRS /
resolution / bounds as the training data* ([problem description, page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).

| # | check | this file | how it is enforced |
|---|---|---|---|
| 1 | single band | `count = 1` | `grid.write_submission` writes `count=1` |
| 2 | `float32` | `dtype = float32` | written as `np.float32` |
| 3 | CRS `EPSG:32611` | `EPSG:32611` | pinned constant, asserted on write |
| 4 | shape `3730 × 3292` | `3730 × 3292` | asserted against the sample submission's grid |
| 5 | geotransform `(100, 0, 243350, 0, -100, 4508550)` | exact match | compared to 6 dp |
| 6 | **values in [0, 1]** | `n_outside_0_1 = 0`, min 0.0, max 1.0 | asserted before write **and** re-checked after re-reading the file from disk |
| 7 | no NaN inside the footprint | `nan_count = 0`, `all_finite = true` | all-finite zeros are written outside the footprint and **no `nodata` tag is set** (`nodata = null`) |

Checks 6 and 7 are the two that produce the portal error *“Predicted values must be in range [0, 1]”*.
Both failure mechanisms are structurally absent here rather than merely avoided:

* a `float32` **nodata sentinel** such as `-3.4028235e38` survives as a wild value inside the valid
  footprint → this file has **no nodata tag at all**;
* a **NaN nodata tag** makes the reader return NaN, which is not in `[0, 1]` → this file writes
  **all-finite zeros** outside the footprint.

The receipt is not built from the in-memory array; `grid.check_submission` **re-opens the file from
disk** and counts. See [`evidence/h62g/receipt.json`](../evidence/h62g/receipt.json).

## 3. Step-by-step submission

1. Download the `.tif` above (no `.zip` needed — a bare GeoTIFF is accepted).
2. Open the [submission form](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/)
   and sign in.
3. **File to submit** → choose the `.tif`.
4. **Note (optional)** → paste the 117-character note from the table above. The stated limit is
   140 characters; this repository keeps to it.
5. Submit. The score appears on the
   [public leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).
6. **Export the receipt.** Copy the score row into `evidence/` and commit it. This repository
   contains **zero** organizer-confirmed scores; the first receipt converts every future local
   comparison from an argument into an anchored measurement.

## 4. What to submit instead, if a slot is going to be spent

The standing brief says promotion to a real slot is a *separate selector step*. This session's
measurement points the selector at one file:

**`buffedlizard55-lab/GEMSDOE32` → `docs/downloads/gems32-bayesopt-dilation-scarp-d28-20261004-zeros.tif`**
(302,357 bytes, 45,000 dots).

Measured on the same independent off-catalogue instrument as everything else in this repository, its
mean 300 m kernel credit is **0.29294 per dot** — 3.0× the submitted champion family (0.09892 at the
same mass), 3.4× this session's quarantined H62-I, and 6.8× this session's in-lane H62-G. It appears
in no score registry anywhere in the group's 73 public repositories, i.e. **it has never been
submitted**.

**Read the caveat before acting on it.** 0.29294 is a *proxy-instrument* credit, not an organizer
score, and that instrument is a 1:750 k geological compilation which favours scarp-like geomorphology
over genuinely new faults. The closed form turns 0.29294 at 45,000 dots into 0.71 at a planning truth
mass of 12,000 cells — implausibly high, so discount it hard. Even discounted 4× it clears the top-5
cut-off of 0.3333. This session did **not** copy that file into a submission: the standing brief
forbids copying a previous submission.

## 5. Limits on this page's authority

* **No organizer score exists for any file in this repository.** `organizer_score` is `null` everywhere.
* The leaderboard table used to set the target is a **mirror of the official page**, scraped
  2026-10-11T20:57:47Z by a sibling repository's scheduled workflow
  ([`research/leaderboard_series.json`](../research/leaderboard_series.json)). This sandbox cannot
  reach `drivendata.org`, so it is not re-verified here.
* The per-dot credits quoted above are measured on **SGMC 1:750 k off-catalogue**, an independent
  public compilation — *not* the organizer's private expert set.
* A local format check is **not** organizer acceptance.
