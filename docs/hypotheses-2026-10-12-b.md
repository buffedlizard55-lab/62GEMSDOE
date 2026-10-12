# Candidate hypotheses — 2026-10-12 session (H62-B)

Protocol requirement: **before implementing**, produce 3–5 geological hypotheses not yet tried,
each naming the layers, the physical signature, why it should catch a fault **missing** from the
USGS/INGENIOUS catalogue, and how it differs from everything already implemented. Ranked by
expected ΔDTI against implementation cost.

The five candidates already screened in the 2026-10-11 session (`H62-F` refuted, `H62-I`
quarantined as duplicate-drift, `H62-H`, `H62-J`, `H62-K` untried) are the baseline this list
must beat; they are recorded in [`hypotheses-2026-10-11.md`](hypotheses-2026-10-11.md).

Two things changed since that list, and they change the ranking:

1. **The absolute-elevation defect (IR-62-B-09) is now fixed.** Every previous lane fit its
   isobase on `det_elev` (detrended elevation), because the official stack carries no absolute
   elevation. The 100 m DEM `geodawn_dem_a2_100m.tif` (sha256 `d32762a3…`, 5,165,644 valid
   cells inside the footprint, 1027.9–3138.6 m) is now local. A Lahontan isobase is an
   **absolute** datum; fitting it on a detrended band was a defect, not a choice.
2. **A local instrument has been validated against organizer scores** (Experiment 1,
   [`../evidence/exp1_instrument_calibration.json`](evidence/exp1_instrument_calibration.json)):
   mean 300 m kernel credit per dot measured against *SGMC minus catalogue*, with the catalogue
   +3 px masked, ranks 13 registry artifacts the way the organizer does
   (Spearman **+0.742**, p = 0.0037). The random hard-core control is **0.1190**; the group
   champion `h33` measures **0.1324**; this lane's previous artifact (H62-A, 38,000 dots)
   measures **0.1347**. Screening can now be done against a calibrated bar instead of a hope.

| # | hypothesis | layers | expected ΔDTI | cost | status |
|---|---|---|---|---|---|
| **H62-M** | **Base-level isobase** on the absolute DEM, generalized to every pluvial basin | `geodawn_dem_a2_100m.tif`, `topo_10m_derived_100m_u8` | **high** | medium | **this session** |
| **H62-Q** | Multi-physics corroboration of the datum step | `training_features.tif` bands 3, 18, 4, 7, 15, 2 | medium | **low** | **this session** |
| **H62-P** | Published rebound model as the isobase prior | DEM + Adams/Wesnousky/Bills (1999) | medium | low | deferred (needs the published field) |
| **H62-N** | Drainage deflection across the pluvial datum | DEM + flow routing | medium | **high** | deferred |
| **H62-R** | Bench-width asymmetry across the datum contour | DEM + lidar `step_max` | low | medium | deferred (shares H62-I's duplicate risk) |

---

## H62-M — Base-level isobase of the pluvial depositional datum  ·  **rank 1, implemented**

* **Layers.** `geodawn_dem_a2_100m.tif` (absolute elevation, 100 m, EPSG:32611 — the layer
  IR-62-B-09 says every previous lane lacked); `topo_10m_derived_100m_u8.tif` bands
  `slope_p90` (1), `relief_local` (5), `curv_prof_absmax` (6), `hs_lineament` (8),
  `dem_mean` (9); the competition catalogue only as a mask.
* **Signature.** Not the DEM itself but its **base-level surface** — the morphological floor of
  the topography (a running minimum followed by a smoothing, i.e. the level of the local
  depositional plain). In a pluvial-lake basin that surface *is* the lake floor and its
  shoreline bench system; its height above the local base level (HAB) is the geomorphic
  position of the palaeo-shoreline. The isobase is a σ = 6 km smooth fit of that base-level
  surface, which absorbs waterplane tilt and post-pluvial rebound; the flags are (a) robust
  residual steps (|r| > k·MAD) and (b) azimuth kinks of the base-level contour
  (|Δθ| over 3 px). Each flag seeds a trace that is extended while multi-scale ridge evidence
  holds.
* **Why it should catch a fault the catalogue lacks.** A step in a base-level surface whose
  depositional age is latest Pleistocene is, by construction, deformation younger than that
  surface. The catalogue is compiled from range-front scarps, field mapping and published
  Quaternary-fault studies; the population it systematically misses is **basin-floor and
  basin-margin scarps in young lacustrine and playa deposits**, where the offset is metres, the
  scarp is degraded, and there is no bedrock expression. That is precisely what
  Pierce & Wesnousky (SCEC poster, 2016) reported in Smith Valley: two previously unmapped
  northwest-striking segments in the *basin centre* offsetting Holocene sediments. Briggs &
  Wesnousky (JGR, 2004) and Dong et al. (Geosphere) are the type examples of the same
  population at Pyramid Lake and outboard of the Wassuk Range front.
* **How it differs from everything already implemented.** Three concrete differences, each
  verifiable in the code: (i) every previous lane fit its isobase on `det_elev` — a detrended
  band whose long-wavelength content was *removed by someone else's operator*; (ii) none
  derived a base-level (morphological floor) surface at all — the datum was either the raw
  elevation band or a TPI of it; (iii) previous lanes confined the datum band to Lake Lahontan's
  type area or to a fixed elevation window (1308–1360 m, which measured **0.61× chance**),
  whereas HAB is defined *per basin* and therefore covers every pluvial basin in the footprint
  (Lahontan sub-basins, Carson Sink, Smoke Creek–Black Rock, Winnemucca, Humboldt, Walker).
* **Named non-fault process that could mimic it.** Differential post-pluvial isostatic rebound
  itself: rebound is spatially variable between sub-basins, so a purely isostatic warp produces
  both elevation steps and azimuth kinks in the datum with no fault at all. Secondary mimics:
  alluvial-fan toes and debris-flow lobes (slope breaks in the same TPI band); the
  Truckee/Carson/Walker river and delta margins of ~12–14 ka, which are erosional; and
  bedrock lithologic contacts expressed as differential erosion. The 6 km isobase is the
  control for the first; the HAB band and the ridge-evidence requirement are the controls for
  the others.

## H62-Q — Multi-physics corroboration of the same seeds  ·  **rank 2, implemented as a re-rank**

* **Layers.** `training_features.tif` bands `tmi_hg` (3, total magnetic intensity horizontal
  gradient), `iso_grav_anom_hg` (18, isostatic gravity horizontal gradient), `rtp` (2, reduced
  to pole), `geod_2ndinv` (4, geodetic second invariant of the strain-rate tensor),
  `geod_shearrate` (7), `depth_to_base_surf` (15).
* **Signature.** A datum step that is *also* on a geophysical lineament of the same strike: the
  product of the datum-step evidence with an oriented lineament response on the potential-field
  gradients, evaluated at the local strike of the flag.
* **Why it should catch a missing fault.** A geomorphic step alone can be a fan toe or a beach
  berm. A step that coincides with a subsurface density or magnetization contrast is a
  structure. Structures with a geophysical expression but a sub-metre or buried surface scarp
  are exactly the class an outcrop- and imagery-based catalogue misses.
* **How it differs.** The lanes that used geophysics used it as an *independent* detector
  (ridge/lineament consensus). Here it is used strictly as a **corroborator of a seed the datum
  already produced** — it can only re-rank or suppress H62-M's traces, never create one.
* **Leakage risk, stated before the result.** `geod_2ndinv`, `geod_shearrate` and
  `geod_dilaterate` are derived from GNSS/InSAR strain rates, and strain rate localises on
  *known*, active faults; `deq_n100a15`/`ieq_n100a15` are earthquake-distance and density
  fields. All five are therefore plausible **catalogue proxies** and are tested on the leakage
  canary before being trusted. The potential-field gradients (3, 18, 2) are not.

## H62-P — Published rebound model as the isobase prior  ·  rank 3, **deferred**

Replace the free smooth isobase with (a) a plane plus (b) the published post-Lahontan rebound
deflection field (Adams, Wesnousky & Bills, 1999, attribute ~22 m of post-highstand deflection
to rebound with a small down-to-the-north tilt), so that the residual is interpretable in
metres of *fault* offset rather than in arbitrary detrending units. This is the direct cure for
IR-62-03 (the isobase fit is degenerate in its linear part). **Not implemented this session**
because the published field is a figure and a set of station elevations, not a downloadable
raster, and digitising it by hand would introduce exactly the kind of unverified number this
repository exists to avoid. Named source needed: the station/ shoreline-elevation tables in
Adams, Wesnousky & Bills (1999) and the USGS/GSA data repository that accompanies them.

## H62-N — Drainage deflection across the pluvial datum  ·  rank 4, **deferred**

Channels that cross a post-datum fault are deflected or beheaded. The signature is a systematic
azimuth anomaly of the drainage network *restricted to the HAB band*, measured after flow
routing on the filled DEM. Nothing in this repository computes flow routing, so it is genuinely
new; the cost is a depression-fill and a D8 router over 12.3 M cells, and the named confuser is
**lithology** (a knickzone or deflection at a resistant/weak contact is indistinguishable from
one at a fault without a geologic map). Deferred on cost, and because the SGMC screening
instrument cannot see channel deflection at 1:750 k.

## H62-R — Bench-width asymmetry across the datum contour  ·  rank 5, **deferred**

On a faulted shoreline the bench is wider on the downthrown side, so bench width is asymmetric
across the datum contour. It is a genuinely different observable from a step. Deferred because
it shares H62-I's input (the LiDAR `step_max` composite) and H62-I was quarantined for
**duplicate-drift** against `gemsdoe23-h30-arrangement-matched-habitat` (87.5 % of dots within
3 px); any new hypothesis built on that composite inherits the tripwire and would have to be
justified against it.

---

## Screening protocol for this session

1. **Instrument.** Mean per-dot 300 m kernel credit against SGMC-minus-catalogue, catalogue
   +3 px masked (Experiment 1). Bar: the hard-core Poisson control **0.1190**; references:
   `h33` **0.1324** (0.2778 OWNER-REPORTED), H62-A **0.1347**.
2. **Null.** A Poisson hard-core (300 m) field of the same mass, drawn from the *same* habitat
   mask the candidate is allowed to use — not a uniform-random field — so that a "habitat"
   hypothesis cannot pass by occupying the right geology.
3. **Holdout.** The protocol's hide-and-recover holdout is still run and reported, labelled
   HOLDOUT-DTI, with the leakage canary; but per IR-62-B-11 it is **not** used to promote
   or reject.
4. **Budget.** Three experiments, then stop: E1 instrument calibration (done), E2 hypothesis
   screening, E3 mass calibration and the shipped artifact.
