# Lake Lahontan datum-offset hypotheses — ranked before any new experiment

**Scope lock:** this is the assigned datum-offset / Lake Lahontan shoreline lane only. These are
four candidate tests of shoreline-marker displacement, not general fault detectors. The ranking is
a qualitative priority by expected usefulness in this lane and implementation cost; it is not an
estimated DTI or leaderboard score. The catalogue-based holdout cannot validate faults absent from
the catalogue. No slot is recommended, and the top untried hypothesis below has not yet been run.

The reviewed historical v8 result is stopped by the literal registry rule and has a format defect.
Accordingly this file ranks possible future experiments but does not authorize any raster emission.

## Shared inputs and availability

- **Available now:** the repository's 25 m USGS 3DEP Lahontan DEM mosaic at
  [`../evidence/dem/lahontan_dem_utm11.tif`](../evidence/dem/lahontan_dem_utm11.tif) (about 45.9 MB),
  with transport receipt [`../evidence/dem/dem_transport.json`](../evidence/dem/dem_transport.json).
  The receipt identifies the six-tile mosaic as EPSG:32611 at 25 m, transported as-is. The bytes
  are local and hash-tracked; USGS/TNM hosts themselves returned HTTP 000 from the sandbox.
- **Official discovery source:** [USGS The National Map 3DEP product API](https://tnmaccess.nationalmap.gov/api/v1/products).
  The API returned LiDAR product records and download URLs for a nearby n40w119 query, but exact
  LiDAR coverage over each shoreline transect has **not** been verified. No hypothesis below
  requires that unverified LiDAR layer to be viable.
- **Official format/metric:** [competition page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).
- **Scientific context:** [Dong et al. (2014), *Geosphere*](https://pubs.geoscienceworld.org/gsa/geosphere/article/10/1/40/132152/Strike-slip-faulting-along-the-Wassuk-Range-of-the);
  [Pierce, Wesnousky & Owen (2016), SCEC 6917](https://www.scec.org/publication/6917);
  [Pierce et al. (2021), *Tectonics*](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019TC005612);
  [Adams, Wesnousky & Bills (1999), DOI](https://doi.org/10.1130/0016-7606(1999)111%3C1739:IRAFAP%3E2.3.CO;2).
  These references support the regional geologic setting, not the truth of any pixel emitted here.

## Ranked, previously untested variants

| rank | hypothesis | directional expectation (not a score) | cost | source availability |
|---:|---|---|---|---|
| 1 | **Multi-strand co-displacement coherence** | Highest expected usefulness: a tectonic break should recur with compatible sign/position on multiple elevation-separated Lahontan strands; isolated shoreline constructional forms should fail the cross-strand test. | Medium; DEM derivatives, strand association, spatial clustering, and block holdout. | 25 m USGS 3DEP DEM is local and sufficient for a screening experiment. |
| 2 | **Strand-specific isobases and piecewise-kink residuals** | Moderate: fitting the shoreline levels separately may expose localized slope changes that a basin-wide quadratic smooths over, while rebound remains a long-wavelength component. | Medium-high; fit and compare robust piecewise models, control for stand mixing. | Same local 25 m DEM; no new external layer required. |
| 3 | **Matched lateral offsets across age/elevation-separated shorelines** | Moderate but resolution-limited: matched ridge/bench patterns with a common displacement vector would support strike-slip offset more strongly than a one-strand deflection. | High; DEM ridge descriptors and cross-correlation, then uncertainty and null tests. | 25 m DEM permits a first screen; exact LiDAR tiles would need a separate USGS TNM footprint check before claiming higher-resolution validation. |
| 4 | **Co-offset shoreline marker and incised paleochannel test** | Lower-to-moderate: a fault should displace both a shoreline marker and an older channel crossing it; independent channel avulsion or fan incision is a named confuser. | High; extract channel networks, pair them with mapped strand crossings, and assess spatial blocks. | 25 m DEM supports a coarse screen. LiDAR is optional, not assumed available. |

### 1. Multi-strand co-displacement coherence (top candidate; not run)

- **Layers:** 25 m elevation, slope, curvature, and the derived strand masks from the cached USGS
  3DEP DEM.
- **Signature:** estimate residual steps on each separated shoreline strand; link candidates only
  when their mapped traces are co-located within a specified corridor and the inferred vertical
  polarity is physically compatible across at least two strands. Report each strand's elevation,
  residual, and signed step versus along-strike distance.
- **Why a missing fault could produce it:** a fault that cuts the deformed shoreline datum can
  offset several markers of different elevation/age. A single wave-cut bluff, beach berm, delta
  topset, or fan-head riser normally affects one local landform and should not reproduce the same
  cross-cut break across separated shoreline levels.
- **Difference from repository work:** historical v8 fit a robust quadratic and emitted from a
  per-location residual/step score; it did not require a repeated, same-corridor displacement
  across multiple distinct strands. This tests a cross-marker tectonic consistency constraint.
- **Validation/cost:** run the existing six-fold spatial holdout as a bug/leakage screen and
  report fold-level results/cluster CI; also use translated-strand and randomized-corridor nulls.
  This remains a proxy and cannot establish hidden-new-fault performance. Estimated implementation
  cost: medium. **No experiment has been started** because the prior artifact hit the strict stop.

### 2. Strand-specific isobases and piecewise-kink residuals

- **Layers:** 25 m elevation and slope-derived flat/bench candidates, split into elevation-defined
  Lahontan strands.
- **Signature:** independently fit robust smooth isobases to each strand, then compare the local
  slope/curvature of residual-versus-distance profiles to a piecewise-linear kink model. Seek a
  localized, spatially aligned break that persists after removing the long-wavelength rebound fit.
- **Why a missing fault could produce it:** differential displacement can create a localized
  change in marker elevation or gradient, while rebound should be smoother at this scale.
- **Named mimics:** local fan progradation, stream incision, strand miscorrelation, and wave erosion
  can create apparent profile kinks. A kink alone is not a fault.
- **Difference from repository work:** historical v8 used a single robust quadratic surface and
  thresholded residual/gradient evidence, not model selection between strand-local smooth and
  piecewise-kink profiles.
- **Availability/cost:** existing DEM; medium-high implementation and sensitivity-analysis cost.

### 3. Matched lateral offsets across separated shoreline markers

- **Layers:** DEM-derived shoreline ridge/bench masks and local relief; optionally USGS 3DEP LiDAR
  only after checking the exact tile footprint.
- **Signature:** cross-correlate ridge texture and bench-edge geometry on opposite sides of a
  candidate shear corridor. Require a consistent lateral displacement vector on two or more
  elevation-separated strand segments, with confidence bounds against nearby control corridors.
- **Why a missing fault could produce it:** strike-slip displacement can shift markers without a
  strong scarp. Dong et al. (2014) supplies regional motivation for investigating displaced
  Lahontan shoreline features.
- **Named mimics:** shoreline embayment geometry, tributary mouths, channel migration, and
  mismatched strand ages can imitate lateral offsets.
- **Difference from repository work:** the v8 lane's lateral-deflection flag was a secondary local
  locus type; this tests cross-marker displacement consistency as the primary signal.
- **Availability/cost:** 25 m DEM is available for an initial screen; LiDAR tile coverage for the
  exact corridor is unverified and is not counted as available. High implementation cost.

### 4. Co-offset shoreline marker and incised paleochannel test

- **Layers:** 25 m DEM, profile-derived shoreline markers, curvature/flow accumulation, and channel
  centerlines extracted from the same terrain.
- **Signature:** test whether an older channel crossing a shoreline marker has a matched offset
  across the same corridor, with compatible direction and a plausible cumulative vertical/lateral
  relationship.
- **Why a missing fault could produce it:** a fault can displace both a shoreline and a channel;
  agreement between independent geomorphic markers is harder for a single shoreline process to
  mimic.
- **Named mimics:** channel avulsion, alluvial-fan incision, capture, and erosional asymmetry.
- **Difference from repository work:** no existing lane emission requires paired channel-plus-
  shoreline displacement; v8 evaluates shoreline/datum geometry alone.
- **Availability/cost:** 25 m DEM is cached; high cost because marker matching and non-fault controls
  are essential.

## Validation and stop criteria

Before any future candidate is emitted, retain a pre-placement surface and run the shared strict
registry comparison on it. After emission, run the same strict test on final dots. A rank
correlation above 0.90 or **more than 70%** of candidate-positive cells within Euclidean 3 px of
any single registry raster is a hard `DUPLICATE-STOP`; high comparator coverage is a diagnostic,
not an exemption. A feature-alone holdout AUC above 0.90 is leakage until proven otherwise.

The top candidate above has not been validated. There is no slot recommendation, no promotion, and
no projection reported as a score. The current negative run card is
[`evidence/lahontan_run_card_20261011.json`](evidence/lahontan_run_card_20261011.json).
