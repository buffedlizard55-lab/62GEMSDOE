# Data provenance, availability, and safe reproduction notes

This review makes no submission recommendation. The generated historical v8 TIFF is stopped by a
strict registry overlap and a format failure; do not use the commands below to create a submission
without adding and passing the pre-placement registry gate first.

## 1. Official competition inputs available in this checkout

| file | role | SHA-256 | status |
|---|---|---|---|
| `data/existing_faults.tif` | USGS/INGENIOUS catalogue used only as proxy holdout truth | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` | tracked local mirror |
| `data/labels.tif` | byte-identical catalogue mirror | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` | tracked local mirror |
| `data/sample_submission.tif` | official template grid and footprint | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` | tracked local mirror |
| `evidence/dem/lahontan_dem_utm11.tif` | USGS 3DEP Lahontan DEM used by the lane | `90838cbc194576b772c4c11b19b6d37aeb66cbe04818170ccaa3ca46591f40e7` | tracked local mirror, 25 m |
| `training_features.tif` | competition feature stack | `4371c82e…` (pin recorded in `src/gems62/grid.py`) | not in this checkout; do not assume availability |

The template defines EPSG:32611, 3730×3292, 100 m resolution, bounds
(243350, 4135550, 572550, 4508550). The official format permits/requires null/NaN outside the
training footprint; inside values must be finite and in `[0,1]`, and the output is a single-band
`float32` GeoTIFF. See the [official competition page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).

## 2. DEM provenance and limitations

The existing 25 m raster is a six-tile USGS 3DEP mosaic, EPSG:32611, 9200×7600, nodata −32768,
with a valid-data fraction of 0.8088 in its recorded transport receipt. The stored transport
receipt identifies `resampling: "as-is"`. Pixel values are integer decimetres; `scripts/run_lane.py`
decodes them to metres and masks the nodata sentinel.

USGS/TNM hosts returned HTTP 000 from the sandbox during the prior fetch. The existing mosaic was
transported through a GitHub Actions runner; new external USGS data may require the same route.
Official discovery endpoint: [USGS TNM 3DEP API](https://tnmaccess.nationalmap.gov/api/v1/products).
The API returned LiDAR product records for a nearby query, but exact 1 m coverage of any proposed
shoreline transect remains unverified. The ranked hypotheses in `hypotheses.md` use the cached 25 m
DEM and do not assume LiDAR access.

## 3. Registry snapshot and reproducibility

The completed fetch wrote outside the repository to `/tmp/gems62_registry_review`. Its manifest
records 100 repository entries: 88 fetched, 12 skipped because their archives exceeded the 90 MB
cap. It contains 525 GeoTIFFs. `/tmp` is transient and is not committed, so the registry cannot be
reproduced from this checkout alone. Current review evidence retains the exact blocking comparator
hash and the strict-check output in `evidence/uniqueness_v8_strict_review.json`.

The scan deliberately stopped once a literal strict overlap failure was established. The 12
skipped repositories are an incompleteness note, not a reason to waive the stop.

## 4. Shared validation tools

- `src/gems62/grid.py::write_submission` writes NaN outside the pinned footprint, refuses a
  nodata tag, reopens the GeoTIFF, and verifies grid/inside/outside conditions.
- `scripts/run_holdout.py` performs a catalogue hide-and-recover proxy, records the evaluator
  version and a spatial-fold cluster-bootstrap interval, and runs a feature-alone leakage canary.
- `scripts/check_uniqueness.py` is the CLI for the shared strict implementation in
  `src/gems62/uniqueness.py`. It recursively reads registry GeoTIFFs and stops if rank rho exceeds
  0.90 or more than 70% of candidate-positive cells lie within 3 Euclidean pixels of any one
  comparator. Footprint coverage is diagnostic only; it does not exempt a raster.

## 5. Safe future workflow

Do not treat the historical `run_lane.py` output as submission-ready. A future candidate workflow
must persist its pre-placement surface, apply the strict registry gate before dot placement, emit
only if that gate passes, re-run the strict gate on final dots, validate the written GeoTIFF, and
then stop if any check fails. A passing local validator is not an organizer receipt, and the
catalogue proxy is not an evaluation of hidden new faults.
