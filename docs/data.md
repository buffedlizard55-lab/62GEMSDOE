# Data provenance and exact reproduction

Nothing heavy is committed: the 418 MB official feature stack, the registry of prior rasters and
the 46 MB DEM mosaic are all reproducible or transportable, not checked in. This file says how.

## 1. Official competition rasters (hash-pinned)

| file | role | sha256 (first 16) | where it lives |
| --- | --- | --- | --- |
| `existing_faults.tif` / `labels.tif` | the USGS/INGENIOUS catalogue — 60,988 positive pixels; **masked out of live scoring** | `7ba308cc…` | `/home/user/work/bridge/` (pinned), copied to `/tmp/gems/labels.tif` for runs |
| `example_submission.tif` | defines the official grid: 3730×3292, 100 m, EPSG:32611, origin (243350, 4508550) | `2176d08e…` | same |
| `training_features.tif` | 418 MB, **19-band** feature stack (band names are in the file's own `band_name` tags — `rtp`, `tmi`, `mag_anom`, …; verified from the bytes 2026-10-11b and again 2026-10-12, sha256 matches the pin) | `4371c82e…` | fetched to `build/ext/` (gitignored) by `scripts/fetch_ext_20261011b.py` or the git-transport mirror in `build/mirrors/` |

The pins come from `data/bridge/manifest.json` in the transport repository. The catalogue is
**read-only ground truth for the proxy holdout and never an emitter input** in this lane: the
lane derives nothing from it, which is why the "derive catalogue-based features only from visible
faults" clause is satisfied by construction rather than by discipline — and the leakage canary is
what verifies that claim instead of assuming it.

## 2. The DEM

| item | value |
| --- | --- |
| source | USGS 3DEP 1/3 arc-second, via the TNM API (see `sources.md` #6) |
| fetch | GitHub Actions run **38169727207**, six tiles: n39w119, n40w119, n40w118, n41w119, n41w120, **n40w120** |
| transport | `evidence/dem/lahontan_dem_utm11.tif`, 45,932,226 bytes, sha256 `90838cbc194576b772c4c11b19b6d37aeb66cbe04818170ccaa3ca46591f40e7` (named `dem_25m_utm11.tif` in the receipt) |
| receipt | `evidence/dem_fetch_receipt_38169727207.json`; `evidence/dem/dem_transport.json` records `resampling: "as-is"` |
| mosaic | 9200×7600, EPSG:32611, **25.0 m**, nodata −32768, origin (240000, 4480000), int16 **decimetres** |
| coverage | valid fraction **0.8088** (56,550,061 cells); z 1028.26–3434.36 m |
| prior runs | 38169049665 (success, **no artifact**), 38169197251 (partial, 5/6 tiles, 0.590 valid), 38169424249 (5 tiles), 38169727207 (6 tiles, current) |

**Why the fetching happens on a runner:** this sandbox cannot reach USGS hosts (`HTTP 000`,
measured, `evidence/tnm_probe.json`). `gh run download` also fails (Azure EOF), so artifacts are
transported through git instead — that is what `evidence/dem/` is.

**Two decode traps, both live in the code:** the raster is **decimetres**, not metres, and the
nodata sentinel was once clipped to −32766 during decimetre rounding. `read_z()` divides by 10 and
masks values ≤ −32000.

## 3. Reproduce the deliverable

```bash
# 0) inputs (DEM + official rasters)
cp evidence/dem/lahontan_dem_utm11.tif /tmp/gems/dem/
#    /tmp/gems/labels.tif and /tmp/gems/sample_submission.tif come from /home/user/work/bridge/

# 1) the lane, end to end (~191 s, 2 cores)
.venv/bin/python scripts/run_lane.py \
    --dem /tmp/gems/dem/lahontan_dem_utm11.tif \
    --catalogue /tmp/gems/labels.tif \
    --sample /tmp/gems/sample_submission.tif \
    --out-dir build/lane --name v8 \
    --min-trace-evidence 0.15 --max-loci 400 --dot-spacing-px 3.5

# 2) format receipt, re-read from the bytes on disk
.venv/bin/python -c "import sys;sys.path.insert(0,'src');from gems62 import grid;\
import json;print(json.dumps(grid.check_submission('build/lane/v8.tif'),indent=1))"

# 3) proxy holdout + leakage canary
.venv/bin/python scripts/run_holdout.py --emission build/lane/v8.tif \
    --catalogue /tmp/gems/labels.tif --sample /tmp/gems/sample_submission.tif \
    --out build/holdout_v8.json

# 4) the null that makes the holdout readable: same density, uniform random
.venv/bin/python scripts/make_control.py --sample /tmp/gems/sample_submission.tif \
    --n 1660 --seed 7 --out build/controls/poisson_1660_seed7.tif
.venv/bin/python scripts/run_holdout.py --emission build/controls/poisson_1660_seed7.tif \
    --catalogue /tmp/gems/labels.tif --sample /tmp/gems/sample_submission.tif \
    --out build/holdout_poisson_1660_seed7.json

# 5) uniqueness vs every registry raster (~10 min for 289 rasters)
.venv/bin/python scripts/check_uniqueness.py --raster build/lane/v8.tif \
    --registry /tmp/registry --footprint /tmp/gems/sample_submission.tif \
    --out build/uniqueness_v8.json
```

To refresh the registry (`/tmp/registry`, 291 files, 209 MB, **not committed**):
`python tools/fetch_registry.py` — see `tools/gh_ls.py`, `gh_tree.py`, `scan_repos.py` for the
listing helpers.

## 4. Environment

`.venv/bin/python` — numpy / scipy / rasterio 1.4.4. The system interpreter is PEP-668 blocked.
Budget note: the sandbox has 3 GB RAM and 2 cores; the lane peaks well inside that, and the only
long-running step is the uniqueness scan.

## 5. Known gaps in the evidence (do not read past them)

* The **per-block coverage map has not been re-verified** since the sixth DEM tile landed in run
  38169727207. The valid fraction is known (0.8088); which blocks are still empty is not.
* `training_features.tif` band names are second-hand (`irregularities.md` §8).
* The registry contains 291 files but only **289** rasters pass the shape check; the two skipped
  ones are named in `build/uniqueness_v8.json` under `results[].skipped`.
