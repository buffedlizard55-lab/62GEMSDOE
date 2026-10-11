# Sources and evidence provenance

This page separates organizer specifications, official geospatial data, peer-reviewed regional
context, local measurements, and unverified score claims. No leaderboard projection is presented
as an organizer result.

## Competition specification (official)

| source | use in this repository | evidence class |
|---|---|---|
| [DOE GEMS Prize — competition page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | Metric: distance-weighted Tversky index with `alpha=0.2`, `beta=0.8`, triangular kernel `k(d)=max(1-d/300m,0)`. Format: single-band `float32`, same CRS/bounds/resolution as training data (EPSG:32611, 100 m), values in `[0,1]`, null/NaN allowed or required outside the footprint. This source controls the writer and validator. | OFFICIAL; page fetched 2026-10-11 |
| [FY26 OSTI 96647 competition rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) | Rules include the weekly submission cap (up to three), AI-use disclosure requirements, and Phase 2 expert-review process. These are reasons to document AI assistance and not spend a slot automatically. | OFFICIAL; PDF fetched 2026-10-11 |
| [Public leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) | Retrieved 2026-10-11. The displayed public board did not match the prompt's stated 0.3195 premise. It is not a receipt for this repository's artifact and is not used as one. | PUBLIC-BOARD OBSERVATION, time-stamped; not a candidate score receipt |

No submission-page receipt is present for the historical v8 TIF. Therefore it has no
ORGANIZER-CONFIRMED score.

## Official elevation-data source

| source | use | evidence class |
|---|---|---|
| [USGS The National Map / 3DEP product discovery API](https://tnmaccess.nationalmap.gov/api/v1/products) | Official discovery service for 3DEP elevation and LiDAR products. Prior queries returned nearby product records and download URLs. Exact LiDAR coverage along future shoreline transects is not confirmed. | OFFICIAL source; local query result recorded in `evidence/tnm_probe.json` |
| [USGS 3DEP program](https://www.usgs.gov/3d-elevation-program) | Source attribution and program context for the DEM. | OFFICIAL |

The locally available 25 m Lahontan DEM is tracked at `evidence/dem/lahontan_dem_utm11.tif` with
transport details in `evidence/dem/dem_transport.json`. Direct USGS/TNM HTTP requests from the
sandbox returned HTTP 000; the mosaic was transported via a GitHub Actions runner. This local
transport receipt is not a new organizer data source.

## Lake Lahontan and Walker Lane scientific context

| source | relevant context | evidence class |
|---|---|---|
| [Dong et al. (2014), *Geosphere*, “Strike-slip faulting along the Wassuk Range…”](https://pubs.geoscienceworld.org/gsa/geosphere/article/10/1/40/132152/Strike-slip-faulting-along-the-Wassuk-Range-of-the) | Published Walker Lane/Lake Lahontan shoreline displacement context, motivating a datum-offset lane. | Peer-reviewed regional context; source fetched/read 2026-10-11 |
| [Pierce, Wesnousky & Owen (2016), SCEC Contribution 6917](https://www.scec.org/publication/6917) | Lidar mapping context for faulted fans, stream offsets, and unmapped structures in the northern Walker Lane. | SCEC research contribution; fetched/read 2026-10-11 |
| [Pierce et al. (2021), *Tectonics*, DOI 10.1029/2019TC005612](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019TC005612) | Regional Walker Lane tectonic context. | Peer-reviewed regional context; fetched/read 2026-10-11 |
| [Adams, Wesnousky & Bills (1999), DOI 10.1130/0016-7606(1999)111<1739:IRAFAP>2.3.CO;2](https://doi.org/10.1130/0016-7606(1999)111%3C1739:IRAFAP%3E2.3.CO;2) | Lake Lahontan isostatic rebound and geomorphic effects, relevant to non-fault mimic control and isobase modeling. | Peer-reviewed regional context; bibliographic source verified 2026-10-11 |

These sources support a hypothesis, not an assertion that any rasterized candidate is a fault.
The candidate's stated non-fault mimics include wave-cut bluffs, beach berms, fan-head risers,
delta topsets, shoreline reoccupation, channel incision/avulsion, and spatially variable rebound.

## Internal measurements and score claims

| item | source | status |
|---|---|---|
| Historical v8 HOLDOUT-DTI, CI, withheld-positive count, and canary | `evidence/holdout_v8_strict_review.json` | Local proxy measurement; not an organizer score |
| Strict final-dot registry comparison | `evidence/uniqueness_v8_strict_review.json` | Local comparison against fetched repository artifacts; strict result `DUPLICATE-STOP` |
| Current local GeoTIFF format receipt | produced by `src/gems62/grid.py::check_submission` | Local validator only; historical v8 fails NaN-outside rule |
| User-provided earlier leaderboard numbers | `docs/irregularities.md` | OWNER-REPORTED claims; no submission-page receipt is present |

## Claims this repository does not make

- It does not claim that the historical v8 raster is unique or submission-ready.
- It does not claim a fault has been discovered from the candidate geometry.
- It does not label the catalogue proxy as hidden-new-fault performance.
- It does not claim an ORGANIZER-CONFIRMED score without a submission-page receipt.
