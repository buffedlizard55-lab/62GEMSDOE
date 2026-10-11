# Sources — verified, with the evidence class of every claim

Evidence classes used in this repository, and never mixed:

| class | meaning |
|---|---|
| **OFFICIAL** | read from the organizer's own pages, or fetched and quoted during the session, with the link |
| **PEER-REVIEWED** | a named journal paper whose abstract/figures were fetched and quoted during the session |
| **MEASURED** | computed in this checkout from local bytes; reproducible with the listed script |
| **INHERITED** | a number or artifact carried over from a sibling `buffedlizard55-lab` repository, quoted with its own label |
| **MODEL** | algebra applied to the above; explicitly not a score |

---

## 1. The competition and its metric — OFFICIAL

| Fact | Source | Status |
|---|---|---|
| Task: predict structures indicative of geothermal resources; test set is "newly identified faults in the GeoDAWN region that are not included in the existing USGS fault database" | [Problem description, page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | Owner-supplied link; **not re-fetched in this session** (this sandbox cannot reach `drivendata.org`). The metric algebra below is independently re-derived and tested. |
| Metric: `k(d) = max(1 - d/300 m, 0)`; `TP_w = sum_g max_x p(x)k(d(x,g))`; `FP_w = sum_x p(x)[1 - max_g k(d(x,g))]`; `FN_w = sum_g [1 - max_x p(x)k(d(x,g))]`; `DTI(alpha,beta) = TP_w/(TP_w + alpha*FP_w + beta*FN_w)`, alpha = 0.2, beta = 0.8 | Same page, "# Mathematical representation" | Transcribed from the sibling repositories' frozen copies and re-implemented with regression tests (`src/gems62/metric.py`, `tests/test_metric.py`). Two identities are enforced: the page's worked example (3.00/1.89/2.00 → 0.6026517, page rounds to 0.60) and the 1x5 counterexample (25/29). |
| Submission format: EPSG 32611, 100 m, same bounds as the training data, "data outside the bounds is null or nan", single band, float32, values in [0, 1] | Same page, "# Submission format" | Implemented in `src/gems62/validate.py`. |
| Known USGS/INGENIOUS fault pixels are **masked / excluded from evaluation** | DrivenData community thread 11516, staff (`chrisk-dd`), 2026-09-16 | INHERITED as a quote from the sibling repositories' `sources.json`; the sandbox cannot reach `community.drivendata.org`. **Flagged for manual re-verification before any submission** (irregularity IR-62-002). |
| `sample_submission.tif` is the rasterised catalogue (60,988 pixels equal to 1), not "total fault absence" | MEASURED here: `sha256 2176d08e…`, 1,599,597 B, `np.unique` → `{0, 1, nan}`, count of ones = 60,988 = `labels.tif` count of ones exactly | Independently reproduced in this checkout. |
| The portal error "Predicted values must be in range [0, 1]" | Owner-reported on the submission form | Reproduced class identified as a float32 nodata sentinel or a NaN nodata tag; `validate.py` reports the three separate facts rather than conflating them. |

## 2. The science of the lane — PEER-REVIEWED

Every quote below was returned by a literature search performed in this session
(the abstract/figures text of the cited paper or of a citing paper that reproduces it).

| Claim | Quote | Source |
|---|---|---|
| The Lahontan highstand is an isochronous, near-horizontal datum | "the high shoreline of Lake Lahontan is an isochronous surface ... that probably formed in a period of years to decades immediately prior to 13 ka" | Adams & Wesnousky (1998), GSA Bulletin 110, 1318–1332, as reproduced in [Adams, Wesnousky & Bills, JGR](https://www.researchgate.net/publication/240670908_Isostatic_rebound_active_faulting_and_potential_geomorphic_effects_in_the_Lake_Lahontan_basin_Nevada_and_California) |
| It is now vertically deflected by ~22 m | "the once horizontal (equipotential) shoreline, which traverses almost 4° of latitude and 3° of longitude, is now deflected vertically about 22 m" | Adams, Wesnousky & Bills (1999), JGR — same link |
| The deformed range is 1318.4 m to 1340.8 m | "High shoreline elevations range from 1318.4 m near the northern periphery of the basin to 1340.8 m near the central part of the basin. The difference of ~22 m is taken to represent the total vertical regional deformation" | Adams, Wesnousky & Bills (1999) — same link |
| Two regional terms: isostatic rebound + a small northward tilt | "Most of the deformation is attributed to isostatic rebound, but a small down-to-the-north regional tilting also appears to contribute to the overall deformation pattern" | Same |
| **Faults offset the datum** | "**Active faults locally offset the high shoreline**, but cannot explain the regional upwarping attributed to isostatic rebound since 13 ka" | Same — this is the sentence the whole lane rests on |
| Prerebound elevation assumed 1328 m | "In this study we assume that the elevation of 1328 m closely approximates the prerebound value of the high shoreline" | Same |
| Elevation-method resolution ~3 m | "The resolution to which the signal can be measured is limited to about 3 m because of natural variability in the height that constructional beach features form above a still water plane" | Same — this sets `ELEVATION_RESOLUTION_M` |
| Highstand age 13,070 ± 60 yr B.P. | "Lake Lahontan began to recede from its highstand by 13 070 ±60 yr B.P. (Adams and Wesnousky, 1998) and had reached an elevation of 1230 m in the Winnemucca Dry Lake" | Same |
| Unified only above the 1,308 m sill | "Only when lake level exceeds 1,308 meters, does Lake Lahontan become a single body of water, that acts in a unified manner to changes in the regional hydrologic balance" | [Late Pleistocene and Early Holocene lake-level fluctuations in the Lahontan Basin (USGS/publication)](https://www.researchgate.net/publication/247987548_Late_Pleistocene_and_Early_Holocene_lake-level_fluctuations_in_the_Lahontan_Basin_Nevada_Implications_for_the_distribution_of_archaeological_sites) |
| Older, higher strands coexist (the stacked-shoreline mimic) | "Beach deposits of the ~1370-m and ~1350-m(?) shorelines of Lake Lahontan and of the two intermediate shorelines of Lakes Columbus-Rennie, Hubbs, and Newark, retain the forms" | [Highest Pluvial-Lake Shorelines and Pleistocene Climate of the Western Great Basin](https://www.researchgate.net/publication/223575168_Highest_Pluvial-Lake_Shorelines_and_Pleistocene_Climate_of_the_Western_Great_Basin) |
| The highstand formed quickly | "the final rise to the highstand was very rapid and that the lake maintained its highest stand for a very brief period of time, perhaps only for years or decades" | [Late Pleistocene and Late Holocene Lake Highstands in the Pyramid Lake Subbasin (Briggs et al.)](https://www.researchgate.net/publication/228488135_Late_Pleistocene_and_Late_Holocene_Lake_Highstands_in_the_Pyramid_Lake_Subbasin_of_Lake_Lahontan_Nevada_USA) |

## 3. The three sites the prompt names as this lane's precedents — PEER-REVIEWED

The prompt names three published uses of Lahontan shorelines as a strain gauge.
This session confirms the mechanism each one relies on and records the residual
uncertainty honestly.

| Study | What the prompt says it did | Status in this session |
|---|---|---|
| **Briggs & Wesnousky (JGR, 2004)** — features displaced since the highstand constrain slip on the Pyramid Lake fault zone | Shoreline/geomorphic features used as displaced markers | Mechanism confirmed in kind by the source-search sentence "Active faults locally offset the high shoreline" (Adams, Wesnousky & Bills 1999). **The specific 2004 paper was not fetched in this session** — the DOI/abstract was not independently read, so its numbers are not quoted anywhere in this repository. Flagged IR-62-003. |
| **Dong et al. (Geosphere)** — Lahontan shorelines displaced along a strike-slip fault outboard of the Wassuk Range front | Map-view (lateral) offset of shorelines | This is the precedent for the *lateral deflection* detector in `lahontan.flag_deflections`. **Not fetched in this session**; no number from it is quoted. Flagged IR-62-003. |
| **Pierce & Wesnousky (SCEC poster, 2016)** — two previously unmapped NW-striking segments in Smith Valley's basin centre offsetting Holocene sediments | Unmapped faults found in basin centres | The strongest strategic point for this lane: it is evidence that the missing population sits in **basin interiors**, which is where pluvial shorelines are also preserved. **Not fetched in this session**. Flagged IR-62-003. |

## 4. The DEM — OFFICIAL source, INHERITED mirror

| Fact | Source | Status |
|---|---|---|
| `data/geodawn_dem_a2_100m.tif` (49,531,304 B) is on the competition grid: 3730 x 3292, EPSG:32611, 100 m, transform `(100, 0, 243349.966, 0, -100, 4508550)` | MEASURED here with `rasterio` | Grid identical to `labels.tif` and `sample_submission.tif` to within 0.034 m in the x-origin (5.2 x 10^-7 of a pixel) |
| Its provenance | INHERITED from `buffedlizard55-lab/60GEMSDOE`: the same repository's `docs/sources.md` names USGS 3DEP as the topographic source and its `data/external/dem10_chi_100m.manifest.json` pins the 1/3 arc-second 3DEP tiles it derives from, with per-tile URLs and SHA-256s (`https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/n38w117/USGS_13_n38w117.tif` etc.) | The 100 m A2 grid is **not** accompanied by its own receipt in that repository. Flagged IR-62-001: treat as an owner-supplied, integrity-unpinned mirror, **not organizer-authenticated**. |
| 3DEP licence | USGS 3DEP is a US Government work (public domain) | Compatible with the competition's external-data rule ([page 967, "# External Datasets"](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)) |

## 5. Prior work for the lane-drift check — INHERITED

`registry/registry_sources.json` lists 24 prior artifacts from 15 sibling
repositories, each with the owner-reported score and, where known, a SHA-256.
`scripts/fetch_registry.py` fetches them through the public GitHub API and writes
`registry/registry_manifest.json`; 21 fetched, 1 path no longer exists (404), 2
skipped by construction (their path pattern could not be resolved without guessing).

Every pinned hash matched on fetch, including
`c55bafc470054e8271dcb89347a17e07fefe50de6af6e6ba6c4b169ef7ab6fa9` for the
0.2778-scoring file and `f81e26d7712d1a4a…` for the GEMSDOE32 "best-validated"
artifact, which that repository's own README independently quotes.

**None of those scores is an organizer receipt.** They are owner-reported values
from a public leaderboard snapshot, and this repository uses them only as
orientation, never as evidence.

## 6. From the sibling repositories, quoted with their own labels — INHERITED

| Fact | Source | Status |
|---|---|---|
| The best-scoring family is a thinning of a solid prior; deleting the <=200 m catalogue flank raised the owner-reported score from 0.2600 to 0.2778 | `GEMSDOE51/knowledge/03_why_the_dotted_family_wins_2026-10-07.md`; `GEMSDOE54/registry/registry_manifest.json` | INHERITED. The dot counts and the byte identity are MEASURED here from the fetched bytes: `dotted_b2_prune` 37,654 dots vs `dotted_d2_8` 40,199 dots. |
| The 3-px-overlap lane rule is unsatisfiable against three near-blanketing registry rasters | `GEMSDOE54` irregularity IR-54-016, `evidence/cgrc_submission_receipt.json` → `lane_infeasibility_proof` (r11 73.97 %, r13 99.87 %, r14 76.20 % of footprint within 3 px) | **MEASURED here, independently reproduced.** This session's own registry screen finds the same three rasters vacuous (`max_frac3px_all = 1.0`), confirming the defect. |
| Hidden truth mass G is ~10,000–14,100 cells | `GEMSDOE54/docs/research/why-h33.md`, inversion of two owner-recorded rows | INHERITED and labelled MODEL wherever it is used. |
| Local format checks are not organizer acceptance | `GEMSDOE48/docs/research/metric-identity-erratum-20261007.md` | Adopted as this repository's policy. |

## 7. Irregularities recorded for manual review

| ID | Irregularity |
|---|---|
| IR-62-001 | The 100 m DEM has no per-file receipt in the repository it was mirrored from; only the upstream 1/3 arc-second 3DEP tiles are hash-pinned. A ray of evidence is missing between "USGS 3DEP tile" and "the 100 m grid used here". |
| IR-62-002 | The masking clarification (community thread 11516) could not be re-fetched; it is a second-hand quote. Manual verification required before any submission that relies on the masking rule (this lane's catalogue-exclusion gate relies on it). |
| IR-62-003 | The three papers the prompt names as this lane's precedents (Briggs & Wesnousky 2004; Dong et al.; Pierce & Wesnousky 2016) were **not** fetched in this session. The lane's mechanism is instead supported by the independently retrieved Adams/Wesnousky/Bills work, which states the same physical fact in one sentence. No number from the three unfetched papers appears anywhere in this repository. |
| IR-62-004 | `registry_sources.json` entry `gems48_h59_cover_ds_belief_02296` returns HTTP 404: the path was reconstructed from a site listing rather than from a repository tree, and could not be resolved without guessing. It is excluded from the lane check rather than approximated. |
| IR-62-005 | The prompt's own leaderboard values are mutually inconsistent across sessions (0.2778 / 0.3195 / 0.3774 are quoted as "highest" in different places). This repository treats none of them as current fact; the score model is run at all three targets so the conclusion does not depend on which one is right. |
