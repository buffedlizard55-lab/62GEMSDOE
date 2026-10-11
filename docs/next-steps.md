# Remaining work and limitations

## What is finished

* The **assigned lane** is implemented end-to-end: DEM → stands → robust isobase → datum-step loci
  → traces → a validated, unique GeoTIFF with two machine-readable receipts.
* A **download page** with an explicit verdict, and this documentation set.
* The **shared tools were fixed and reported, not forked** (`irregularities.md` §2, §3): the
  holdout evaluator (five defects) and the registry uniqueness tripwire (density-blind).
* A **Poisson null** generator (`scripts/make_control.py`), without which no holdout number in this
  repository is interpretable.

## Ranked next work

### 1. Density calibration against the marginal-credit bar — highest expected value, hours of work
β = 0.8 makes DTI recall-dominated and the catalogue is masked, so emission **density** is worth
more than any single detector. `metric.marginal_bar` already computes the break-even condition.
Next concrete step: sweep the density/threshold of the existing fields, tabulate the marginal
credit curve, and pick the density that maximises expected DTI under a stated recall model. This
applies to the group's h33 lineage as much as to this lane, and it needs no new data.

### 2. Re-verify the DEM coverage map after the sixth tile
Run 38169727207 raised valid fraction 0.590 → 0.8088 but the per-block map was not re-checked.
Cheap, and it bounds what any DEM lane in this basin can claim: **Pyramid Lake, the Truckee
corridor and the lower Carson were NaN in the five-tile mosaic.**

### 3. Fix the trace stopping rule
Median trace length is 1.3 km; real fault traces are longer. The stopping rule (`min_evidence
0.15`, whole-segment sampling) is the prime suspect, not the geology. This is the single change
most likely to raise this lane's coverage — which, per (1), is what the metric rewards.

### 4. Run the hypotheses in `hypotheses.md`
H-A (LiDAR scarp polarity) → H-B (lateral shoreline deflection, strike-slip) → H-C (facet-base
lines) → H-D (basement steps in catalogue-empty corridors). Each must pass the blocked holdout
**as a screen** and, more importantly, must be reported against its own Poisson null.

### 5. Get one ORGANIZER-CONFIRMED number into `evidence/`
The repository contains **zero** verified organizer scores. The first submission-page receipt that
is exported and committed converts every future local comparison from a proxy argument into an
anchored one.

## Limitations — stated as limitations, not as future work

1. **No local instrument can certify novelty.** The only local truth is the catalogue, and the
   competition truth is precisely what the catalogue lacks. A random field outscores the best
   scored artifact on both available proxies (`hypotheses.md`, validation trap). Everything this
   repository can say about a file's *competitiveness* is therefore an argument, not a measurement.
2. **Coverage of the delivered file is one sub-region.** 1,641 of 1,660 dots lie in a 171 × 110 km
   area. This lane buys defensibility in the Lahontan basin; it does not buy area.
3. **The lane's loci are candidates, not faults.** The named confuser is the level-feature family
   (bluffs, berms, risers, delta topsets), and the flat-pixel histogram contains 15 stands between
   1175 and 1437 m. The cross-cut gate removes the contour-parallel family; it does not prove the
   remainder are tectonic.
4. **25 m DEM resolution bounds the detector.** Shoreline steps of 2 m are at the edge of what the
   gridded product supports; the 1 m lidar composite in the training stack is the remedy and is not
   available in this checkout.
5. **The weekly slot decision is not made here.** Per the brief, choosing what to promote to a real
   slot is a separate selector step within the weekly cap. This repository only states what the
   evidence supports: a low-risk Phase-1 novelty probe, explicitly not the lead horse.
6. **Owner-reported scores are unverifiable here** (`irregularities.md` §5) and are used only to
   rank the group's own artifacts against each other.
7. **Sandbox reachability is a hard constraint.** USGS hosts are unreachable (HTTP 000); DEM
   fetching, and any future external data, must round-trip through a GitHub Actions runner and git.
