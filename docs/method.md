# Method — H62-B, the pluvial depositional datum as a strain gauge

## The lane, verbatim

> Map shoreline benches in the DEM and fit a smooth isobase, allowing for post-pluvial isostatic
> rebound. Flag abrupt steps or lateral deflections along strike, seed a trace at each, extend it
> while DEM-ridge evidence supports it, and emit dotted lines.

Every numbered step below implements one clause of that paragraph. Code:
`src/gems62/datum_base.py` (the new physics), `scripts/build_surfaces.py` (surface cache),
`scripts/run_h62b.py` (seeds → traces → dots → mass sweep), `scripts/finalize_h62b.py`
(emit, validate, holdout, run card). Reused from the template without modification:
`gems62.emit.structure_tensor`, `gems62.emit.extend_trace`, `gems62.emit.hard_core_topk`,
`gems62.datum.frangi_ridge`, `gems62.metric`, `gems62.grid.write_submission`,
`gems62.validate`, `gems62.holdout`, `gems62.uniqueness`.

## 1. The datum is a base level, not the DEM

The DEM's elevation at a point on a pluvial-lake margin is

    z = base level (the lake floor / local depositional plain)
      + height above it (the bench, the fan, the spur)
      + noise

The lane's observable is the first term. It is estimated as a **base-level surface**: a running
minimum of the DEM over 1.7 km, then smoothed over 0.9 km — the standard geomorphometric
"base level" construction, which in a pluvial basin is the lake floor and its bench system.

    base     = smooth( min_filter(z, 1.7 km), 0.9 km )
    HAB      = z - base                       # height above base level
    isobase  = smooth(base over the band, 6 km)
    resid    = base - isobase                 # metres of local departure from the datum

This closes **IR-62-DEM-01**: the official 19-band stack contains no absolute elevation, and every
previous lane fit its isobase on `det_elev` — a band whose regional trend had already been removed
by an operator this repository cannot inspect. The absolute DEM is
`data/geodawn_dem_a2_100m.tif`, sha256 `d32762a3…`, 5,165,644 valid cells inside the footprint,
1027.9–3138.6 m, verified on the competition grid.

## 2. The pluvial band

`HAB ≤ 120 m` (the lake was ~120 m deep over the Pyramid Lake sub-basin at the Sehoo highstand, so
every bench it ever cut lies within ~120 m of the local floor) **and** slope ≤ 6° **and** local
relief (900 m window) ≤ 60 m. Result: 2,078,294 cells, 40.2 % of the footprint, covering every
pluvial basin in the grid — Lahontan's sub-basins, Carson Sink, Smoke Creek–Black Rock,
Winnemucca, Humboldt, Walker — not just the type area.

## 3. Flags

* **Step**: standardised residual `|resid − median| / (1.4826 · MAD)`, with the median and MAD
  computed per 50 km tile inside the band (a tile with fewer than 50 band pixels falls back to the
  global value). Flag at `|z| ≥ 2.5`. 305,713 cells (5.9 % of the footprint).
* **Deflection**: the azimuth of the base-level contour, differenced against itself shifted by
  3 px along each of four strike directions; flag where the turn is ≥ 25°. 152,351 cells (3.0 %).
* Union: 439,892 cells (8.5 % of the footprint). Census:
  [`evidence/exp3_h62b_band_flags.json`](../evidence/exp3_h62b_band_flags.json).

Seeds: the union ranked by `|z| · (1 + 0.5·deflection) · percentile(cross-strike relief)`,
mutually suppressed at 600 m, top 34,620.

## 4. Extension — “while DEM-ridge evidence supports it”

Each seed is marched both ways from its own local structure-tensor azimuth
(`gems62.emit.extend_trace`), advancing 200 m per step, turning at most 20° per step, and stopping
at the first step where the cross-strike relief falls below **33.1 m** (the 25th percentile of the
footprint's relief distribution) or the lineament coherence falls below 0.02. Maximum length 15 km.
25,057 traces survive (≥ 3 points), 1,299,529 trace pixels.

The extension is **not** confined to the pluvial band. The lane does not say it should be, and
Experiment 2 showed that confining it is fatal: every band-restricted evidence surface — including
the band's own uniform null — measures 0.26× chance on the calibrated instrument.

## 5. Emission

Trace pixels are ranked by the trace's maximum cross-strike relief, then thinned greedily to a
**300 m hard core**, deleting anything within 3 px (300 m) of a mapped fault. 40,964 candidates
survive; the top 37,654 are shipped (Experiment 3's mass sweep). Mean self-kernel **0.000**: no two
shipped dots are within 300 m of each other.

## 6. Physical basis, and what would make it stronger

Lake Lahontan filled the northwestern Great Basin to its highstand at ~15 ka. Its shoreline is a
near-level datum whose present elevation varies along strike because of waterplane tilt during
loading and post-pluvial isostatic rebound. Briggs & Wesnousky (JGR, 2004) used features displaced
since the highstand to constrain slip on the Pyramid Lake fault zone; Dong et al. (Geosphere)
documented Lahontan shorelines displaced along a strike-slip fault outboard of the Wassuk Range
front; Pierce & Wesnousky (SCEC poster, 2016) reported two previously unmapped NW-striking segments
in Smith Valley's basin centre offsetting Holocene sediments. Adams, Wesnousky & Bills (1999)
attribute ~22 m of post-highstand deflection to rebound with a small down-to-the-north tilt.

The step that would make the residual interpretable in metres of *fault* offset is fitting the
published rebound field instead of a free smooth surface — hypothesis H62-P, written up and
deferred, with the exact source it needs named in
[the hypotheses page](hypotheses-2026-10-12.html).

## 7. Reproduce

```bash
bash scripts/download_data.sh                 # official rasters (hash-pinned)
python3 scripts/fetch_external.py             # DEM, SGMC, lidar, topo packs
python3 scripts/build_surfaces.py             # ~55 s, caches build/surfaces/*.npy
python3 scripts/screen_h62b.py 40000          # Experiment 2
python3 scripts/run_h62b.py --n-seeds 40000 --suppress-px 3 --relief-pct 25 \
        --coherence-min 0.02 --max-len-m 15000 --tag final   # Experiment 3, ~90 s
python3 scripts/finalize_h62b.py 37654        # emit + validate + holdout + run card
python3 scripts/make_figures_h62b.py          # map + profiles
python3 scripts/instrument_calibration.py     # Experiment 1, ~100 s
```

Everything is deterministic: no step draws a random number that affects the shipped raster.
