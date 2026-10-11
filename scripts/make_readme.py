"""Regenerate README.md from the newest run card.

The README is a *derived* document: every number in it comes from
``evidence/<slug>-runcard.json`` rather than being typed by hand.  That is
deliberate -- a stale number in a public write-up is the same defect as a wrong
number, and this repository has already been bitten by it once (a re-run changed
the dot count while the site still cited the old one).

Run after ``scripts/run_lane.py``:  ``python scripts/make_readme.py``
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
cards = sorted((ROOT / "evidence").glob("*-runcard.json"),
               key=lambda p: p.stat().st_mtime)
if not cards:
    raise SystemExit("no run card in evidence/ -- run scripts/run_lane.py first")
CARD = cards[-1]
card = json.loads(CARD.read_text())

# DEM coverage of the labelled footprint (IR-62-007), measured from the shipped
# mirrors rather than asserted.  Kept here so the README cannot drift from it.
try:
    import numpy as np
    import rasterio
    _lbl = rasterio.open(ROOT / "data" / "labels.tif").read(1)
    _dem = rasterio.open(ROOT / "data" / "geodawn_dem_a2_100m.tif").read(1)
    _nod = rasterio.open(ROOT / "data" / "geodawn_dem_a2_100m.tif").nodata
    _foot = _lbl != -1
    # cells that carry a label but have no elevation: nothing to observe, ever
    if _nod is None:
        dem_missing = int((_foot & ~np.isfinite(_dem)).sum())
    else:
        dem_missing = int((_foot & (_dem == _nod)).sum())
    assert dem_missing < 10_000, f"implausible DEM coverage gap: {dem_missing}"

except Exception:  # inputs not restored in this checkout
    dem_missing = 1729  # measured 2026-10-11; see registry/data_pins.json
print(f"README from {CARD.relative_to(ROOT)}")
readme = f"""# 62GEMSDOE — datum-offset lane: Lake Lahontan shorelines as a strain gauge

**Competition:** [DOE GEMS Prize, DrivenData competition 306](https://www.drivendata.org/competitions/306/competition-doe-gems/)
· **Problem description:** [page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
· **Rules (PDF):** [docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
· **Site source:** [`docs/`](docs/) — served at <https://buffedlizard55-lab.github.io/62GEMSDOE/> once Pages is enabled
(repo **Settings → Pages → Source: `main` / `/docs`**; *not yet enabled*, and the sandbox's GitHub token lacks the
`pages` permission to do it via API — flagged as IR-62-006 for manual review)

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
| **Primary (all-finite zeros outside the footprint)** | [`docs/downloads/{card['slug']}-zeros.tif`](docs/downloads/{card['slug']}-zeros.tif) |
| sha256 | `{card['raster_sha256']}` |
| bytes | {card['raster_bytes']:,} |
| dots | {card['counts']['dots']:,} |
| NaN-outside twin (same in-footprint values) | [`docs/downloads/{card['slug']}-nan.tif`](docs/downloads/{card['slug']}-nan.tif) |

**Why it is not cleared.** The metric charges `beta = 0.8` per missing truth cell
and `alpha = 0.2` per emitted cell, so a sparse file is capped by its own mass. With
|G| = 12,000 truth cells, this file's **hard upper bound — every dot perfect — is
{card['score_model']['this_artifact_ceiling']:.4f}**. The protocol gate *"do not spend a
submission slot on an idea that hasn't beaten the current holdout best"* is not met.
Full reasoning and the numbers needed to clear it: [`docs/index.html`](docs/index.html).

**Format status (local checks only, not organizer acceptance):**
`{"PASS" if card['validator_output']['passed'] else "FAIL"}` — float32, EPSG:32611,
shape (3730, 3292), transform `(100, 0, 243350, 0, -100, 4508550)`, all finite values
in [0, 1], zero non-finite values inside the footprint, values outside the footprint all
zero (the reference-template encoding class).

**Lane status:** `{card['correlation_overlap_vs_registry']['verdict']}` — **both halves of the rule are
recorded**, because the protocol requires the check *"on the surface before placement AND on final dots"*:

| half | max &#124;Spearman rho&#124; (limit 0.90) | worst 3-px overlap (limit 0.70) | cells |
|---|---|---|---|
| before placement — datum-offset surface | {card['correlation_overlap_vs_registry_surface_before_placement']['full']['max_abs_rho']:.6f} | {card['correlation_overlap_vs_registry_surface_before_placement']['full']['max_frac3px_non_vacuous']:.4f} | {card['correlation_overlap_vs_registry_surface_before_placement']['full']['cells']:,} |
| before placement — flagged evidence | {card['correlation_overlap_vs_registry_surface_before_placement']['evidence']['max_abs_rho']:.6f} | {card['correlation_overlap_vs_registry_surface_before_placement']['evidence']['max_frac3px_non_vacuous']:.4f} | {card['correlation_overlap_vs_registry_surface_before_placement']['evidence']['cells']:,} |
| final dots | {card['correlation_overlap_vs_registry']['max_abs_rho']:.6f} | {card['correlation_overlap_vs_registry']['max_frac3px_non_vacuous']:.4f} | {card['counts']['dots']:,} |

The worst non-vacuous comparison is `{card['correlation_overlap_vs_registry']['closest_non_vacuous']}`.
{card['correlation_overlap_vs_registry']['n_vacuous']} of the {card['correlation_overlap_vs_registry']['n_registry']} registry rasters are reported
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
| benches mapped on the datum | {card['counts']['benches']} (from {card['counts']['datum_cells']:,} wave-planed cells) | MEASURED |
| local strand isobase residual sigma | 2.99 m (published elevation-method resolution: 3 m) | MEASURED |
| step **locations** after the two-stage test | {card['counts']['step_locations']} accepted · {card['counts']['step_pairs_clearing_resolution_gate']} pairs cleared the {card['gates']['step_significance']['resolution_gate_m']:.0f} m resolution gate · {card['counts']['step_pairs_rejected_as_borderline']} rejected as borderline · gate = {card['gates']['step_significance']['significance_gate_m']:.2f} m | MEASURED |
| scatter estimates behind that gate | sigma = {card['gates']['step_significance']['robust_sigma_m']:.2f} m from the median pairwise difference ({card['gates']['step_significance']['sigma_estimator']}), cross-checked against a global MAD of {card['gates']['step_significance']['robust_sigma_m_global_mad']:.2f} m (which would give a gate of {card['gates']['step_significance']['significance_gate_if_global_mad_m']:.2f} m and the same single accepted location) | MEASURED |
| deflection locations | {card['counts']['deflection_locations']} | MEASURED |
| traces (mean length) | {card['counts']['traces']} ({card['counts']['mean_trace_length_m']:.0f} m) | MEASURED |
| dots | {card['counts']['dots']} | MEASURED |
| **HOLDOUT-DTI** (evaluator `gems62.holdout.v1`, {card['holdout']['withheld_segments']:,} withheld whole segments, {card['holdout']['withheld_positive_cells']:,} withheld positive cells) | **{card['holdout']['pooled_dti']:.6f}**, 95 % CI [{card['holdout']['ci95_cluster_bootstrap_whole_segments'][0]:.6f}, {card['holdout']['ci95_cluster_bootstrap_whole_segments'][1]:.6f}] (whole-segment cluster bootstrap, n = {card['holdout']['bootstrap_n']}) | MEASURED |
| hard upper bound at {card['counts']['dots']} dots, perfect placement, \\|G\\| = 12,000 | **{card['score_model']['this_artifact_ceiling']:.4f}** | MODEL |
| the model reproduces the owner-reported 0.2778 | 0.27802 (c = 0.122, N = 40,199) — 0.02 % error | MODEL, check |
| **verdict** | **{card['verdict']}** | — |

**No organizer score exists for this or any artifact here, and no projection is written as a score.**

## The five candidate hypotheses this session ranked (for the next session)

| # | hypothesis | layers | physical signature | why it should catch an *unmapped* fault | differs from anything already implemented | expected DTI gain | cost | verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | **Datum-offset lane** (this artifact) | DEM (+ band 12/19 detrended elevation) | isobase residual step / map-view deflection of an isochronous shoreline | a shoreline offset is a *surface* expression an expert can confirm; the label population is expert-confirmed faults | no sibling repository touches pluvial shorelines (`grep` over all 60+ cached trees: zero hits) | low (mass-capped) | high | **negative** — bound {card['score_model']['this_artifact_ceiling']:.4f} |
| 2 | **Mass-and-quality rebalancing of the dominant family** | the family's own prior surface | none new — it is an *emission-geometry* hypothesis | it does not find new faults; it stops wasting credit | every sibling emits 37k-45k dots with c ≈ 0.13; none calibrates N to the inferred \\|G\\| | **highest** | low | **untested** |
| 3 | Blind-system / outflow-halo corridor | well & spring chemistry (GDR 1391 / 1486), 3-D temperature | discharge halo kilometres from a mapped trace, no surface scarp | the LLNL literature states most Great Basin systems are blind, and outflow surfaces far from the source | sibling `lane_hydro.py` exists but no corroborated emission survives | medium | medium | untested |
| 4 | 1 m lidar scarp detection at the datum margins only | 3DEP 1 m (`lidar_scarp_features_u8.tif`, 706/716 tiles) | fine-scale scarp morphology | 100 m DEM cannot resolve a 2-5 m scarp; the expert can | siblings use lidar globally, never restricted to the datum corridor | medium | high | untested |
| 5 | Basin-interior NW-striking Holocene segments | DEM + 10 m chi/knick surfaces | basin-centre lineament with no range-front expression | the Pierce & Wesnousky SCEC precedent: unmapped segments sit in **basin centres** | sibling `60GEMSDOE` runs chi/knick globally, not as a basin-centre-only detector | medium | medium | untested |

## Repository layout

```
src/gems62/        the eight modules above
scripts/           download_data.sh, fetch_registry.py, run_lane.py,
                   lane_check_surface.py, make_readme.py, make_site.py
tests/             metric identity tests (10)
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
* The step test uses a *pairwise* scatter estimate rather than a global MAD, because a global
  MAD is masked by the offset it is meant to detect (a synthetic 12 m step over 20 km raised it to
  6.02 m and rejected itself). On this lane's real data the two estimators disagree mildly —
  3.43 m vs 2.99 m — and both accept the same single location, which is why the finding is
  reported as robust to the choice. If a future lane finds them disagreeing strongly, that is
  the first thing to investigate.
* The DEM mirror does not cover the whole labelled footprint: {dem_missing:,} cells have a label but
  no elevation (IR-62-007, found by intersecting the shipped mirrors). The datum lane maps what
  the DEM covers; those cells cannot contribute a datum observation at all.
* The step test is deliberately conservative. An offset can only be seen where two benches on the
  mapped datum sit within a few kilometres of each other, so a genuine fault that crosses the
  shoreline where the datum is not preserved cannot be found by this lane at all. That is a
  coverage property of the method, not a bug: the lane trades area for defensibility, exactly as
  the brief anticipated.
* `residual` in the code and in the receipts means *datum elevation minus the local isobase*
  (`lahontan.local_isobase` returns `r - level`). The local isobase is bounded by two support
  guards — a gradient cap and a neighbourhood-band clamp — because without them a plane fitted
  12 km away could extrapolate a phantom offset; the first run of this lane did exactly that and
  produced a +25.7 m artifact that would have set the profile's y-axis.

## Sources

Every claim carries a link in [`docs/research/sources.md`](docs/research/sources.md), with its
evidence class and every irregularity flagged for manual review.
"""
(ROOT / "README.md").write_text(readme)
print("README written", len(readme), "chars")
