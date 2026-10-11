# 62GEMSDOE — Lake Lahontan shorelines as a strain gauge

**Datum-offset lane (H62-A) of the DOE GEMS Prize Challenge** — DrivenData competition #306,
GeoDAWN airborne magnetic & radiometric survey region, northwestern Great Basin, Nevada.

[**Open the site**](https://buffedlizard55-lab.github.io/62GEMSDOE/docs/) ·
[**Executive summary & how to submit**](https://buffedlizard55-lab.github.io/62GEMSDOE/docs/executive-summary.html) ·
[Competition #306](https://www.drivendata.org/competitions/306/competition-doe-gems/) ·
[Problem description & metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) ·
[Reference solution](https://github.com/drivendataorg/gems-prize-reference-solution)

---

## ⬇ ONE-CLICK SUBMISSION FILE

The single artifact this repository offers for submission lives here. **Read the
status table below before you click** — it says plainly whether the file is
format-legal, whether it is unique against every earlier raster, and whether it
should be given a weekly slot.

| | |
|---|---|
| **Download (primary, `.tif`)** | [`docs/downloads/`](docs/downloads/) — see [`docs/index.html`](https://buffedlizard55-lab.github.io/62GEMSDOE/docs/) for the live link |
| **Download (`.zip`, single GeoTIFF inside)** | same folder |
| **Format receipt (re-read from the bytes on disk)** | `docs/downloads/*-zeros.json` |
| **Run card (the JSON card the protocol requires)** | [`evidence/e8_run_card.json`](evidence/e8_run_card.json) |

### Is it OK to download and submit?

**Download: YES.** The validator passes **26/26** checks on the bytes on disk —
EPSG:32611, 3730×3292, single-band float32, values in [0, 1], no NaN or
float32 sentinel inside the footprint, zeros outside it, no nodata tag, zero
dots on the mapped catalogue. sha256
`eabd03c1ca1a5380d100024b3ed7c7401a847bdab5913a423c396bb50f624ed5`.

**Submit: NO — not validated.** The file is format-legal and it is *not a copy*
of anything in the 709-raster registry, but this repository cannot justify
spending a weekly slot on it, for two measured reasons that both need a human
decision:

- **IR-62-HOLDOUT-01 (critical) — the promotion gate is pointed the wrong way.**
  Scoring 10 ORGANIZER-CONFIRMED artifacts as frozen dot masks on one identical
  holdout gives **Spearman(HOLDOUT-DTI, organizer score) = −0.9141 (p = 0.0002)**.
  It is not a dot-count artefact: the partial Spearman controlling for `n_dots`
  is **−0.6810 (p = 0.0302)**, and in **7 of 8** count-matched pairs the file
  with the *lower* holdout carries the *higher* organizer score. Cleanest case:
  `h33-h33-2-b2` (37,654 dots, HOLDOUT 0.0053, **ORGANIZER 0.2778**) vs
  `h36-1-rung30-blind-r1` (37,660 dots — six apart — HOLDOUT 0.0368, ORGANIZER
  0.2710). *Mechanism:* the holdout withholds segments of the **public**
  catalogue and scores their recovery, while the organizer's Initial Prize Round
  scores a **private** set of faults labelled before the competition. One rewards
  hugging the catalogue, the other rewards avoiding it. The 0.2778 winner was
  built by *deleting* 6,436 dots within 3 px of the catalogue, which raised its
  organizer score 0.2600 → 0.2778 and collapses its holdout DTI 0.1322 → 0.0053.
  Our artifact has zero dots within 3 px of any catalogue pixel (minimum
  distance 3.2 px, median 18.9 px), so its frozen HOLDOUT-DTI is **exactly
  0.0000** — by construction, not by failure. The standing instruction ("do not
  spend a slot on an idea that has not beaten the current holdout best") is
  therefore **unevaluable**, and following it literally would steer away from
  what actually scores. See [`evidence/e9_frozen_artifact_holdout.json`](evidence/e9_frozen_artifact_holdout.json).
- **IR-62-UNIQ-01 — the uniqueness rule returns DUPLICATE, and the artifact is
  still not a copy.** 64 comparator rows put >70 % of our dots within 3 px.
  Calibrating that leg with two nulls (dots scattered anywhere in the footprint,
  and dots scattered through *our own* catalogue-free lane habitat) waives all
  but **2 distinct fields**, and those bind only marginally: their habitat nulls
  are 0.656 and 0.672 — within 0.05 of the 0.70 waiver cliff — and *which*
  comparators bind flips with the null seed (`13gems-r8-ensemble` binds under one
  20,000-point draw and is waived under another). A rule whose verdict moves on
  the null seed cannot gate a submission. So the rule's answer stands:
  **DUPLICATE**, and this repository does not overrule its own tasking protocol
  autonomously. But every statistic that can actually detect *copying* is far
  inside its limit: max Jaccard **0.0253** (limit 0.50), max signed ρ **+0.0647**
  (limit 0.90; most negative **−1.0000**, which is anti-correlation — the
  opposite of copying), max mutual containment **0.3195**. `is_a_copy = false`.
  Against the 0.2778 file specifically we share **1,421** exact pixels of its
  37,654, sit within 3 px of **41.7 %** of them, and **58.3 %** of our dots are
  in places it does not cover. What trips the leg is that 61 of the 64 rows are
  regular lattices (spacing ≤ 6 px, whose 3 px dilation tiles the whole
  footprint) or 4–100 %-density fields ranking the same basin-margin geology this
  lane is assigned to — a *random* dot set trips it against them too.
  See [`evidence/e7_uniqueness.json`](evidence/e7_uniqueness.json),
  [`evidence/e7b_uniqueness_null_analysis.json`](evidence/e7b_uniqueness_null_analysis.json),
  [`evidence/e7c_habitat_pool.json`](evidence/e7c_habitat_pool.json).

**Verdict on the run card: `negative`.** The negative result is the deliverable.
The arm-A3 procedure still measures HOLDOUT-DTI **0.1224** [0.1154, 0.1284]
against random-line controls at 0.0228 — a correct measurement of the
*procedure* under per-fold visible-only pruning, and no longer offered as a
promotion argument.

Everything about the current artifact — its sha256, its validator output, its
holdout DTI with a 95 % CI, its uniqueness verdict and its promote/negative
verdict — is rendered at the top of [`docs/index.html`](docs/index.html) and in
[`docs/executive-summary.html`](docs/executive-summary.html). Nothing on this
site asks you to trust a number that is not labelled **HOLDOUT-DTI** or
**ORGANIZER-CONFIRMED**, and no score is projected for this artifact anywhere.

---

## The tasking prompt (kept verbatim, re-read at the start of every session)

> This block is the standing brief for this repository. It is reproduced in full so that
> every session starts from the same requirements rather than from a summary of them.

<details>
<summary><b>Click to expand the full tasking prompt</b></summary>

```
Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS
SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF
SUBMISSION.  IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF
SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the
entire prompt.

Datum-offset lane: Lake Lahontan shorelines as a strain gauge. In the northwestern Great Basin
the Lahontan highstand shoreline is a near-level datum about 15 ka. Briggs and Wesnousky (JGR,
2004) used features displaced since the highstand to constrain slip on the Pyramid Lake fault
zone. Dong and coauthors (Geosphere) documented Lahontan shorelines displaced along a
strike-slip fault outboard of the Wassuk Range front. Lidar mapping nearby has also found
faults missing from earlier maps: Pierce and Wesnousky (SCEC poster, 2016) report two
previously unmapped northwest-striking segments in Smith Valley's basin centre offsetting
Holocene sediments. Map shoreline benches in the DEM and fit a smooth isobase, allowing for
post-pluvial isostatic rebound. Flag abrupt steps or lateral deflections along strike, seed a
trace at each, extend it while DEM-ridge evidence supports it, and emit dotted lines. First
deliverable: shoreline elevation-versus-distance profiles with the flagged steps. If only a
handful are convincing, emit only those. Coverage is limited to pluvial-lake margins, so this
lane buys defensibility more than area. Output the standard validated GeoTIFF,
uniqueness-checked against every earlier raster.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same
prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's
   rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots
   fall within 3 px of one registry raster's dots, you have drifted into another lane: log it
   as a duplicate and stop. Check this on the surface before placement AND on the final dots.

2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_holdout.py and
   submission_writer.py. Holdout = hide-and-recover: withhold whole fault segments with a
   buffer, derive every catalogue-based feature only from the visible faults, mask visible
   faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a
   shared tool is wrong, fix it once in the template and report it; never keep a private fork.

3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI)
   or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never
   written as a score.

4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above
   [0.90] means leakage until proven otherwise.

5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that
   could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator
   output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission
   name + note of at most 140 characters; verdict promote / negative. Negative results are
   deliverables.

6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a
   real slot is a separate selector step, within the weekly cap shown on the submission page.

[...]

We need to focus on being able to generate a submission into the competition.

The site should be able to generate a TIF file that is required for submission.  It should be
as easy as download to click a File to submit into the competition.  This needs to be in the
executive summary or the very beginning of the site.  it should be obvious when you visit the
site.

I tried to submit the document that i downloaded from the site but it returned this error on
the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell
submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the
contest.

[...]

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each
naming: the specific layer(s) involved, the physical signature being targeted (e.g., an
edge-detection or curvature transform), why it should catch a fault missing from the
USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything
already implemented in this repo. Rank them by expected DTI improvement and implementation
cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly
submission slot — do not spend a submission slot on an idea that hasn't beaten the current
holdout best. If a candidate can't be validated without new external data, name the specific
free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual
review.  There should be no manual input, work on your own to complete tasks.  Flag any
irregularities for review.  No hallucinations.
```

</details>

---

## Core Values (Arena AI) — the decision frame for this repository

**Maximize P(Win).** Every weekly submission slot is an experiment, not a lottery ticket. A
negative result that is measured, published and never submitted is worth more than a hopeful
file that burns a slot. Nothing here is promoted on a projection.

**Own the Outcome.** Every claim carries an evidence class. Where this session found a defect
in shared tooling, it fixed it once in the template and reported it (see
[Irregularities](docs/irregularities.html)) rather than keeping a private fork.

---

## What this repository is

An auditable implementation of one lane of the GEMS Prize: use the ~15 ka Lake Lahontan
highstand shoreline as a **near-level datum**, find where that datum is *stepped* or
*deflected*, and ship those structures as a legal, unique GeoTIFF.

```
src/gems62/
  metric.py             official DTI, transcribed from the competition page + brute-force cross-check
  grid.py               raster IO, the 19-band inventory, sha256 pin verification
  isobase.py            THE LANE: benches, isobase fit, step/deflection flags, trace extension
  habitat.py            topographic-position x slope habitat weights (visible faults only)
  emission.py           dotted emission: >=3 px spacing, budget cap, catalogue prune
  holdout.py            segmented hide-and-recover holdout + equal-budget controls + canary
  uniqueness.py         the two stop conditions vs every earlier raster
  validate.py           the format checks, re-read from the bytes on disk
  submission_writer.py  fail-closed writer: zeros-outside primary, NaN-outside twin, .zip
  profiles.py           FIRST DELIVERABLE: shoreline elevation-vs-distance profiles + PNGs
scripts/
  run_lane.py           E0..E8 end-to-end: verify -> surfaces -> canaries -> holdout -> emit -> validate -> unique -> run card
  build_registry.py     fetch every earlier raster from all sibling repos for the uniqueness gate
  build_site.py         regenerate docs/ from evidence/*.json
tests/test_gems62.py    36 assertions, all against published numbers or brute force
evidence/               one JSON per experiment step; e8_run_card.json is THE card
registry/               raster index + organiser-confirmed score anchors
docs/                   the GitHub Pages site
```

### Data

The three official rasters are **not** committed (419 MB). They are sha256-pinned and verified
on every run:

| file | bytes | sha256 |
|---|---|---|
| `training_features.tif` | 418,912,844 | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` |
| `labels.tif` | 425,830 | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` |
| `sample_submission.tif` | 1,599,597 | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` |

All three were re-verified against those pins on 2026-10-11 — see
[`evidence/e0_data_verification.json`](evidence/e0_data_verification.json). To obtain them,
run `bash scripts/download_competition_data.sh` on a machine with DrivenData access
([data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), login
required), or restore them from the in-organisation git bridge documented in that script.

---

## The brief's questions, answered

**Why did `h33-h33-2-b2` score 0.2778?** Because DTI is a *budget*, not an accuracy score.
Writing `DTI = T / (0.2·(T+F) + 0.8·|G|)`, every unit of emitted mass costs 0.2 whether it
hits or misses, and earns at most 1.0 if it hits. A filled probability surface emits many
redundant pixels that all cover the *same* truth pixel, so most of its mass is pure cost.
Thinning to single pixels at ≥3 px spacing keeps the geometry and deletes the redundancy. The
organiser-confirmed ladder measured by the group is 61,328 dots → 0.2449, 60,069 → 0.2477,
44,090 → 0.2600, 40,199 → 0.2708, **37,654 → 0.2778** — an optimum near 38 k dots. The last
step, deleting the 6,436 dots that sat within 3 px of an already-mapped fault, is worth
+0.0178 on its own: the hidden truth is *new* faults, so mass spent next to known ones earns
nothing. Full derivation in [`docs/analysis.html`](docs/analysis.html).

**Can this lane beat 0.2778?** Not on its own, and the arithmetic says so rather than the
pessimism of the author. This lane is confined to pluvial-lake margins — 22.8 % of the
footprint — and the metric's false-negative term `0.8·|G|` is charged over the *whole* hidden
set. A geographically confined file cannot raise `T` enough to move the denominator. The lane
buys **defensibility**: its seeds are structures that demonstrably offset a 15 ka surface,
which is the class of fault the expert panel adds in the Final Prize Round. Measured result and
verdict are in [`evidence/e8_run_card.json`](evidence/e8_run_card.json); the honest number is on
the front page, not buried.

---

## Limitations & what would unblock the next step

| limitation | effect | unblock |
|---|---|---|
| **No absolute elevation band** (IR-62-DEM-01). The stack has only *detrended* elevation and its slope. | A Lahontan isobase is an absolute datum; detrending removes part of it. The lane fits its isobase in detrended-elevation space instead. | `1m_DEM_links.csv` (USGS 3DEP 1 m lidar) from the DrivenData data tab, or 3DEP directly. Free, public domain. Not reachable from this sandbox. |
| **100 m pixels.** A 15–45 m shoreline step is 0.15–0.45 pixel of relief. | Step detection is bracketed by pixel resolution; the physical throw window had to be widened to 15–130 m. | same 1 m lidar source |
| **No organiser score exists** for any artifact in this repository. | Every number here is HOLDOUT-DTI or ORGANIZER-CONFIRMED-from-an-earlier-file. Never a projection written as a score. | a submission slot, which is a separate selector step |
| **IR-62-HOLDOUT-01 (critical): the holdout is *anti*-correlated with the organiser's score.** Measured Spearman **−0.9141** (p = 0.0002) over 10 ORGANIZER-CONFIRMED artifacts; partial **−0.6810** (p = 0.0302) controlling for dot count; 7 of 8 count-matched pairs inverted. | The promotion gate cannot be used. Withholding *public catalogue* segments rewards hugging the catalogue; the organiser's *private* pre-competition label set rewards avoiding it. Any off-catalogue artifact — including the 0.2778 winner — scores ≈0 on it. | A hidden truth set that is **not** the public catalogue. Not obtainable in this sandbox, and not public. Until then, selection between off-catalogue artifacts is a human judgement informed by the ORGANIZER-CONFIRMED budget ladder — which is what the protocol already implies by making promotion a separate selector step. |
| **IR-62-UNIQ-01: the literal overlap leg of the uniqueness rule is degenerate.** | Regular lattices (spacing ≤ 6 px) and 4–100 %-density fields trip ">70 % of dots within 3 px" for *any* artifact, including a random one. Reported both ways rather than silently waived. | Nothing needed — the calibrated rule (habitat null + Jaccard + signed ρ) is implemented and unit-tested. A human sign-off on the waiver is what is missing. |

---

## Reproduce

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export GEMS62_DATA=/path/to/dir/with/the/three/official/rasters
pytest tests -q                                  # 41 assertions
python scripts/build_registry.py                 # fetch every earlier raster (uniqueness gate)
python scripts/run_lane.py --budget 38000 --arms A1 A2 A3 --folds 4
python scripts/uniq_null_analysis.py             # IR-62-UNIQ-01: calibrate the overlap leg
python scripts/compare_holdout.py --top 10       # IR-62-HOLDOUT-01: rank frozen artifacts
python scripts/recheck_uniqueness.py             # re-gate an existing artifact (bytes untouched)
python scripts/finalize_run_card.py              # write the verdict from evidence, never by hand
python scripts/verify_all.py                     # 92 checks, groups A-F
python scripts/build_site.py                     # regenerate docs/ from evidence/*.json
```

`scripts/finalize_run_card.py` is the only thing that writes the verdict into
`evidence/e8_run_card.json`. The run card is never hand-edited, so the verdict
always traces to measured files.

## Licence & provenance

Code in this repository is original. The metric implementation is a transcription of the
organiser's published formula. All data provenance, with links for manual review, is on
[`docs/sources.html`](docs/sources.html).
