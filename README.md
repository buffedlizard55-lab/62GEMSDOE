# 62GEMSDOE — datum-offset lane: Lake Lahontan shorelines as a strain gauge

**Competition:** [DOE GEMS Prize, DrivenData competition 306](https://www.drivendata.org/competitions/306/competition-doe-gems/)
· **Problem description:** [page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
· **Rules (PDF):** [docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
· **Live site:** <https://buffedlizard55-lab.github.io/62GEMSDOE/>

> ### Our Core Values — kept central to every decision in this repository
> **Maximize P(Win).** *"Maximize the Probability of Winning"* is our decision-making framework. In
> every decision we weigh tradeoffs, assess risk, and choose the path that maximizes the probability
> that we win this prize. We set aside our emotions and make tough decisions in order to maximize
> P(Win). It frees us from constraints and clarifies that we must put the outcome first.
>
> **Own the Outcome.** We own results end to end — not just our individual slice of the work. When
> problems arise and we have the means to act, we act without waiting for permission or assignment.
> We treat failure and success as signals and use them to improve. We stay accountable to the final
> outcome.
>
> Applied here: *Maximize P(Win)* is why this repository computes a **hard upper bound** on its own
> artifact before recommending a weekly slot, and reports `DO NOT SPEND A WEEKLY SLOT` when the
> bound does not clear the bar. *Own the Outcome* is why the negative result is published with the
> algebra that produces it, and why the lane's five untried hypotheses are ranked and left for the
> next session rather than quietly dropped.

---

## ⬇ DOWNLOAD — and read this first

**OK TO DOWNLOAD for inspection. NOT CLEARED to submit — do not spend a weekly slot.**

| | |
|---|---|
| **Primary (all-finite zeros outside the footprint)** | [`docs/downloads/gems62-lahontan-isobase-225dots-zeros.tif`](docs/downloads/gems62-lahontan-isobase-225dots-zeros.tif) |
| sha256 | `e03201fbb13cc21b25c2d343d9879fdcaea7a6cb4600647207829e30f47b2cf0` |
| bytes | 56,392 |
| dots | 225 |
| NaN-outside twin (same in-footprint values) | [`docs/downloads/gems62-lahontan-isobase-225dots-nan.tif`](docs/downloads/gems62-lahontan-isobase-225dots-nan.tif) |

**Why it is not cleared.** The metric charges `beta = 0.8` per missing truth cell
and `alpha = 0.2` per emitted cell, so a sparse file is capped by its own mass. With
|G| = 12,000 truth cells, this file's **hard upper bound — every dot perfect — is
0.0233**. The protocol gate *"do not spend a
submission slot on an idea that hasn't beaten the current holdout best"* is not met.
Full reasoning and the numbers needed to clear it: [`docs/index.html`](docs/index.html).

**Format status (local checks only, not organizer acceptance):**
`PASS` — float32, EPSG:32611,
shape (3730, 3292), transform `(100, 0, 243350, 0, -100, 4508550)`, all finite values
in [0, 1], zero non-finite values inside the footprint, values outside the footprint all
zero (the reference-template encoding class).

**Lane status:** `DISTINCT LANE` — **both halves of the rule are recorded**, because the
prompt requires the check *"on the surface before placement AND on final dots"*:

| half | max &#124;Spearman rho&#124; (limit 0.90) | worst 3-px overlap (limit 0.70) | cells |
|---|---|---|---|
| before placement — datum-offset surface | 0.015546 | 0.3742 | 60,227 |
| before placement — flagged evidence | 0.005815 | 0.3852 | 9,443 |
| final dots | 0.000756 | 0.4444 | 225 |

The worst non-vacuous comparison is `gems8_hedge_v2_01563`. Three registry rasters are reported
*vacuous* (their own 3-px dilation blankets ≥ 70 % of the footprint), independently reproducing the
sibling repositories' documented defect IR-54-016.

---

## What this lane is

Read the full statement in [`docs/index.html`](docs/index.html). In one paragraph:

> **Datum-offset lane.** The late-Pleistocene (Sehoo) highstand shoreline of Lake
> Lahontan is an **isochronous, near-level datum** that formed in years-to-decades
> immediately prior to 13.07 ± 0.06 ka. It is now deflected ~22 m (1318.4 m at the
> northern periphery to 1340.8 m in the basin centre) by isostatic rebound plus a
> small northward tilt, and — the point of the whole lane — **active faults locally
> offset it**. Map the shoreline benches in the DEM, fit a smooth isobase allowing
> for post-pluvial rebound, flag the abrupt steps and lateral deflections that
> remain, seed a fault trace at each, extend it while DEM lineament evidence
> supports it, and emit kernel-matched unit dots.

## Method, in the order the code runs it

1. `src/gems62/grid.py` — grid constants **measured** from the official bytes, and raster IO.
2. `src/gems62/metric.py` — the exact distance-weighted Tversky index, with the
   published worked example and the 1x5 counterexample enforced as tests.
3. `src/gems62/lahontan.py` — datum mapping: wave-planed highstand benches, a robust
   global isobase, multi-modal **level separation** (the stacked-shoreline mimic),
   a locally robust strand isobase, then step and deflection flags.
4. `src/gems62/emit.py` — structure tensor, trace seeding with the fault azimuth
   derived from the datum geometry, evidence-gated extension, and kernel-matched
   unit-dot emission with a catalogue exclusion.
5. `src/gems62/validate.py` — the submission contract, reported as separate facts.
6. `src/gems62/uniqueness.py` — the lane-drift rule, with the vacuity diagnostic.
7. `src/gems62/holdout.py` — whole-segment hide-and-recover, pooled DTI, cluster bootstrap.
8. `src/gems62/score_model.py` — the algebra that decides whether a lane can score at all.

Reproduce everything:

```bash
pip install rasterio numpy scipy scikit-learn pillow pytest
bash scripts/download_data.sh          # restores labels.tif, sample_submission.tif, the DEM
python scripts/fetch_registry.py       # fetches the 21 comparable prior artifacts
python -m pytest tests -q              # 10 metric identities
python scripts/run_lane.py --data data --registry /tmp/gems/registry --holdout-bootstrap 60
```

## Results, labelled

| quantity | value | class |
|---|---|---|
| benches mapped on the datum | 176 (from 90,664 wave-planed cells) | MEASURED |
| local strand isobase residual sigma | 2.99 m (published elevation-method resolution: 3 m) | MEASURED |
| step / deflection flags | 6 / 9 | MEASURED |
| traces (mean length) | 12 (6800 m) | MEASURED |
| dots | 225 | MEASURED |
| **HOLDOUT-DTI** (evaluator `gems62.holdout.v1`, 3,199 withheld whole segments, 60,988 withheld positive cells) | **0.000158**, 95 % CI [0.000102, 0.000490] (whole-segment cluster bootstrap, n = 60) | MEASURED |
| hard upper bound at 225 dots, perfect placement, \|G\| = 12,000 | **0.0233** | MODEL |
| the model reproduces the owner-reported 0.2778 | 0.27802 (c = 0.122, N = 40,199) — 0.02 % error | MODEL, check |
| **verdict** | **negative** | — |

**No organizer score exists for this or any artifact here, and no projection is written as a score.**

## The five candidate hypotheses this session ranked (for the next session)

| # | hypothesis | layers | physical signature | why it should catch an *unmapped* fault | differs from anything already implemented | expected DTI gain | cost | verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | **Datum-offset lane** (this artifact) | DEM (+ band 12/19 detrended elevation) | isobase residual step / map-view deflection of an isochronous shoreline | a shoreline offset is a *surface* expression an expert can confirm; the label population is expert-confirmed faults | no sibling repository touches pluvial shorelines (`grep` over all 60+ cached trees: zero hits) | low (mass-capped) | high | **negative** — bound 0.0233 |
| 2 | **Mass-and-quality rebalancing of the dominant family** | the family's own prior surface | none new — it is an *emission-geometry* hypothesis | it does not find new faults; it stops wasting credit | every sibling emits 37k-45k dots with c ≈ 0.13; none calibrates N to the inferred \|G\| | **highest** | low | **untested** |
| 3 | Blind-system / outflow-halo corridor | well & spring chemistry (GDR 1391 / 1486), 3-D temperature | discharge halo kilometres from a mapped trace, no surface scarp | the LLNL literature states most Great Basin systems are blind, and outflow surfaces far from the source | sibling `lane_hydro.py` exists but no corroborated emission survives | medium | medium | untested |
| 4 | 1 m lidar scarp detection at the datum margins only | 3DEP 1 m (`lidar_scarp_features_u8.tif`, 706/716 tiles) | fine-scale scarp morphology | 100 m DEM cannot resolve a 2-5 m scarp; the expert can | siblings use lidar globally, never restricted to the datum corridor | medium | high | untested |
| 5 | Basin-interior NW-striking Holocene segments | DEM + 10 m chi/knick surfaces | basin-centre lineament with no range-front expression | the Pierce & Wesnousky SCEC precedent: unmapped segments sit in **basin centres** | sibling `60GEMSDOE` runs chi/knick globally, not as a basin-centre-only detector | medium | medium | untested |

## Repository layout

```
src/gems62/        the eight modules above
scripts/           download_data.sh, fetch_registry.py, run_lane.py, lane_check_surface.py
tests/             metric identity tests (10); scripts/*.py are compiled in CI-style checks
docs/              index.html, executive-summary.html, research/sources.md, downloads/
registry/          registry_sources.json, registry_manifest.json, data_pins.json
evidence/          run card, holdout receipt, lane check, profiles, figures
```

## Limitations — stated plainly

* The DEM's 100 m A2 grid has no per-file receipt upstream (IR-62-001).
* The masking clarification is a second-hand quote in this sandbox (IR-62-002).
* The three papers the prompt names as this lane's precedents were not fetched here (IR-62-003).
* The catalogue-truth holdout **cannot** measure performance on the actual target, because the
  target is exactly the population the catalogue lacks and the organizers mask out (see
  `docs/research/sources.md` section 1).
* DrivenData's Terms of Use prohibit automated monitoring; no leaderboard scraper, feed or
  monitor is included, and no leaderboard page was fetched.

## Sources

Every claim carries a link in [`docs/research/sources.md`](docs/research/sources.md), with its
evidence class and every irregularity flagged for manual review.
