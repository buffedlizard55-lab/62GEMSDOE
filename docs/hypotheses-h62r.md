# Five candidate hypotheses, ranked — session `arena/7eee17f9-62gemsdoe` (H62-R)

The brief asks for 3–5 candidates **not yet tried**, each naming the specific layer(s), the
physical signature targeted, why it should catch a fault **missing from the USGS/INGENIOUS
catalogue** rather than one already in it, and how it differs from anything already implemented
in this repository; then ranked by expected DTI improvement against implementation cost, with
the top candidate validated on the spatially-blocked holdout **before** any weekly slot is
touched.

Evidence classes used on this page, and nothing else:

* **MEASURED** — computed in this checkout on this session's run; the file is named.
* **OFFICIAL** — quoted from an organizer-controlled page or the reference solution.
* **DIAGNOSIS** — a mechanism inferred from bytes that were read here, not an organizer statement.
* **EXPECTATION** — stated as an expectation, never as a result.

---

## Rank 1 — H62-R  Multi-level Lahontan datum stack with a **collinearity** repeat-offset test
### *implemented and measured this session*

| | |
| --- | --- |
| **Layers** | the owner-mirrored 100 m DEM on the competition grid, `build/ext/geodawn_dem_a2_100m.tif`, sha256 `d32762a382227643…` (pin in `registry/data_pins.json`). No catalogue layer, no geophysics layer, no label layer. |
| **Physical signature** | the **residual of a near-level datum against a robust local datum surface**, measured at **four independent lake levels**, then a **Hough collinearity vote** over the flagged pixels of all four levels. |
| **Why it targets a *missing* fault** | The signature is *cumulative vertical displacement of a 15 ka datum*, not similarity to a mapped trace. A fault with no catalogue entry still offsets the shoreline; conversely, matching the catalogue is explicitly not required. MEASURED on the emitted field: median distance from a dot to the mapped catalogue **2,052 m**, **0.0 %** of dots within 300 m of it. |
| **How it differs from everything already here** | Every earlier session treated the datum as **one** surface: one "pluvial-lake-margin band" (H62-A), one fitted isobase of detrended elevation, one 1308–1360 m window (H62-G/H62-I), one 1320–1350 m pick band (`lane62`). This one (a) **detects** the level set from the DEM rather than assuming it, (b) fits a **robust tile-mode** isobase per level rather than a Gaussian of all in-band pixels, and (c) tests for **one common line** across levels rather than for a repeated point. |
| **Result** | MEASURED — see `evidence/h62r/e3_repeat_offsets.json`, `e4_profiles.json`, `e5_emission.json`. 4 levels detected (1455, 1389, 1325, 1278 m; block support 7, 7, 12, 7 of 323 blocks); 12,211 flagged step pixels; **2,016 lines** accepted with ≥6 inliers from ≥2 distinct levels spanning ≥2 km; **532** shoreline profiles totalling **2,844 km**; **27,623** isolated dots from 1,872 traces (16,702 km). |
| **Expected ΔDTI** | **Not claimed.** No local instrument can rank this field (see the limitation below). |
| **Cost** | medium — done; ~50 s end-to-end on 2 cores. |
| **Named non-fault process that could mimic it** | **Bedrock lithology**: a resistant unit that stands as a bench at every lake level crosses several levels and is collinear along strike, which satisfies every clause of the test. Second: **isobase-fit error** at the edge of a level's extent. Third: a **prograding delta/fan** that occupied the same position across lake cycles. |

---

## Rank 2 — H62-T  Cross-datum **throw-ratio** (kinematic) test  ·  **not run this session**

| | |
| --- | --- |
| **Layers** | the same DEM; the four level surfaces and the 2,016 accepted lines from Rank 1 (already computed and committed as evidence). |
| **Physical signature** | the **ratio** of cumulative throw between two levels of different age on the same line. For constant slip rate `s` and level ages `t_i > t_j` the prediction is `throw_i / throw_j = t_i / t_j > 1`. Rank 1 already uses this only as a *rejection filter* (a 40 % tolerance); Rank 2 uses it as the **estimator**: a bootstrap slip rate per line, with lines whose ratios are internally inconsistent discarded. |
| **Why it targets a *missing* fault** | The ratio is a kinematic quantity that does not exist in any map. It cannot be produced by copying the catalogue, and it is insensitive to whether the catalogue happens to have drawn a line nearby. |
| **How it differs** | Nothing in this repository computes a cross-datum throw ratio at all — Rank 1's filter is its first appearance, in the weakest possible form. |
| **Expected ΔDTI** | **medium** — it does not add mass, it **re-ranks** existing mass, and the whole score is a per-dot credit problem (see §3(a) of `docs/research/beating-02778-2026-10-11b.md`). |
| **Cost** | **low** — the inputs are in `evidence/h62r/e3_repeat_offsets.json`; one afternoon. |

---

## Rank 3 — H62-W  Datum-offset lines ∩ radiometric alteration lineaments  ·  **not run**

| | |
| --- | --- |
| **Layers** | `build/ext/geodawn_rad_u8.tif` (4 bands, fetched this session, sha256 `c22420f7…`) **and** the Rank-1 line set. |
| **Physical signature** | potassium enrichment and Th/U change along the *accepted Hough lines only* — a hydrothermal-pathway signature, i.e. the physics the competition is actually named for ("structures indicative of geothermal resources"). |
| **Why it targets a *missing* fault** | MEASURED in a sibling session's 54-layer screen (`evidence/e1_layer_screen_20261011b.json`): `rad_K` is the **third-best** layer on the off-catalogue instrument (credit 0.0840, 4.9× a uniform field) while being **anti-aligned** with the mapped catalogue (0.0345, 0.8×). A layer that is strong off-catalogue and weak on-catalogue is the rarest useful combination in this problem. |
| **How it differs** | Radiometrics were previously used as *voters in a symmetric consensus* (H62-L) or fused with scarps (`GEMSDOE46`). Here they are used as a **gate on a datum-offset line**, so they can only suppress or promote lines that already satisfy the geometric test. |
| **Expected ΔDTI** | **medium** if real, **zero** if not; the test is cheap enough to be worth one run. |
| **Cost** | low — the layer is fetched and hash-verified in this checkout. |
| **Named non-fault mimic** | **Agricultural potassium** (fertiliser) and **playa evaporite chemistry** both make K lineaments with no fault. Also: the coverage mask itself scores 0.0709 on the off-catalogue instrument, a warning that radiometric coverage correlates with mapped fault density. |

---

## Rank 4 — H62-V  Shoreline-**geometry** azimuth tomogram (a second, different deflection estimator)

| | |
| --- | --- |
| **Layers** | the DEM and the 532 traced shoreline runs already produced (`evidence/h62r/e4_profiles.json`). |
| **Physical signature** | azimuth discontinuities **between adjacent straight segments of a traced shoreline run**, at a 2–5 km scale. |
| **Why it is on the list** | MEASURED this session: the per-pixel deflection test returns **0 flagged pixels at all four levels** with a 12 px (1.2 km) lever arm, and the repository had already measured a **null** for the 3 px version (`IR-62-DEFL-01`). Two nulls at two lever arms using the same estimator (the DEM gradient azimuth field) is evidence about *the estimator*, not about the geology: a 5 px-smoothed structure-tensor azimuth cannot kink. Fitting segments to the traced shoreline is a genuinely different estimator. |
| **Why it targets a *missing* fault** | Strike-slip offset of a shoreline is the Pyramid-Lake-fault-zone signature of Briggs & Wesnousky (2004) and of Dong et al. (Geosphere); Smith Valley's two unmapped NW-striking segments (Pierce & Wesnousky, SCEC 2016) are in exactly that class. The catalogue under-maps *lateral* structures relative to range-front normal faults. |
| **Expected ΔDTI** | **low–medium** — it adds seeds, not mass, and the mass is already capped by trace length. |
| **Cost** | medium (segment fitting + a second Hough pass). |

---

## Rank 5 — H62-U  Replace the fitted isobase with a published **GIA** prediction

| | |
| --- | --- |
| **Layers** | a published post-Lahontan glacial-isostatic-adjustment prediction for the western US **plus** the DEM. |
| **Physical signature** | the datum residual computed against a *predicted* rebound surface instead of an empirically fitted one — which is the only way to separate "rebound dome" from "fault step" where the two operate at similar wavelength. |
| **Why it is last** | The empirical isobase already absorbs **smooth** rebound by construction, so this only helps if rebound carries a short-wavelength component that a 4 km tile mode cannot absorb. That is a real possibility (the basin is close to the ice-margin periphery) but it is unmeasured here. |
| **Specific free official source needed** | A published GIA model for the Lahontan basin — e.g. the ICE-6G / ICE-7G ice-history family distributed by the University of Toronto, for which the regional Lahontan rebound literature (Bills, Adams and others, *Quaternary*-era papers on Lahontan shoreline tilt) is the citable anchor. **Obtainability from this sandbox: NOT verified.** Those hosts are not on the sandbox allow-list (`drivendata.org` and the USGS hosts both return HTTP 000 — MEASURED, `evidence/tnm_probe.json`); transport would have to go through the GitHub-runner route that already carries the DEM. |
| **Expected ΔDTI** | low–medium, and **unverifiable without that download**. |
| **Cost** | high (new data + a model). |

---

## What this session measured that changes the next session's starting point

1. **The level window was deleting the signal.** The first version of this lane selected bench
   pixels with a ±10 m window around the level and then looked for steps inside them. MEASURED
   result: 0–6 flagged step pixels per level, and an empty artifact. A bench displaced by 30 m
   falls outside a ±10 m window, so the selection had already removed exactly what the lane is
   for. With a ±45 m window and a robust tile-mode isobase the same test returns **11,211**
   flagged step pixels. Logged as `IR-62-LEVEL-01` in `docs/irregularities.md`.
2. **The catalogue-based holdout is identically zero for a field that obeys the catalogue
   exclusion.** The exclusion radius and the metric kernel radius are both 300 m, so a dot
   ≥300 m from every mapped fault has kernel weight exactly 0 against every mapped fault.
   MEASURED: pooled DTI **0.000000** (20 folds, 81,993 withheld positives) while the equal-budget
   random-dot control scores **0.0446** on the same folds. The number is structural, not
   informative, and it is reported as such.
3. **Mass, not spacing, is the lever once overlap is zero.** MEASURED with a k-d tree: at 300 m
   and at 500 m dot spacing the mean self-kernel is **0.00000** in both cases and the minimum
   nearest-neighbour distance is **exactly** the spacing — i.e. there is no kernel overlap either
   way. The metric is then monotone in mass, so the 300 m field (27,623 dots) is kept over the
   500 m one (15,249 dots). Both files exist as evidence.
4. **Both deflection estimators are null.** 0 flagged deflection pixels at a 12 px lever arm,
   against the repository's earlier null at 3 px.
