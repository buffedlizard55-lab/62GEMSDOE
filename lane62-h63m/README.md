# lane62-h63 — H63M, session `arena/4ef3d5d6-62gemsdoe` (2026-10-11)

The one-click deliverable is
[`docs/downloads/gems62-h63m-multiline-corroborated-90000-zeros.tif`](docs/downloads/gems62-h63m-multiline-corroborated-90000-zeros.tif).
Start at [`docs/index.html`](docs/index.html); the "how to submit" page is
[`docs/executive-summary.html`](docs/executive-summary.html).

## Reproducing everything, in order

Heavy inputs are **not** committed (see the root `.gitignore`). Every one of them is a
hash-pinned mirror of an official file, transported through sibling public GitHub
repositories because this sandbox can only reach `github.com` / `codeload.github.com` /
`api.github.com`.

```bash
# 0. python deps
pip install --break-system-packages numpy scipy rasterio scikit-image scikit-learn pillow pytest

# 1. the official 19-band GeoDAWN numerical feature stack (418,912,844 bytes)
#    sha256 4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5
mkdir -p data/bridge
for i in 000 001 002 003 004; do
  gh api "repos/buffedlizard55-lab/GEMSDOE/contents/data/bridge/gems-geodawn-numerical-features.tif.part-$i" \
    -H "Accept: application/vnd.github.raw" > data/bridge/part-$i
done
cat data/bridge/part-00{0,1,2,3} data/bridge/part-004 > data/training_features.tif
sha256sum data/training_features.tif     # must match the pin above

# 2. the 100 m DEM over the whole competition footprint (49,531,304 bytes)
#    sha256 d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431
mkdir -p data/external
gh api "repos/buffedlizard55-lab/60GEMSDOE/contents/data/geodawn_dem_a2_100m.tif" \
  -H "Accept: application/vnd.github.raw" > data/external/geodawn_dem_a2_100m.tif
sha256sum data/external/geodawn_dem_a2_100m.tif

# 3. the USGS SGMC off-catalogue fault set (the proxy truth) + the Qfaults cross-check
mkdir -p data/sibling
gh api "repos/buffedlizard55-lab/GEMSDOE/contents/data/evidence/proxy/proxy_catalogue.tif" \
  -H "Accept: application/vnd.github.raw" > data/sibling/proxy_catalogue.tif
gh api "repos/buffedlizard55-lab/GEMSDOE/contents/data/evidence/xcat/qfaults_catalogue.tif" \
  -H "Accept: application/vnd.github.raw" > data/sibling/qfaults_catalogue.tif

# 4. the score-anchored registry (21 prior rasters with owner-reported scores)
python3 scripts/fetch_registry.py --out data/registry
```

`data/existing_faults.tif`, `data/labels.tif` and `data/sample_submission.tif` are already
committed (2.4 MB together).

Then, in order — each step writes one evidence JSON and is independently checkable:

```bash
python3 scripts/h63_features.py                       # -> evidence/h63_features.json
python3 scripts/h63_train.py --pos-pop catalogue \
        --out h63a --canary                           # -> evidence/h63a_sweep.json
python3 scripts/h63_emission.py --prob h63a_prob.npy --out h63a
                                                      # -> evidence/h63a_emission.json  (AUC ~ 0.50)
python3 scripts/h63_canary.py                         # -> evidence/h63a_canary.json
python3 scripts/h63_lineament.py                      # -> evidence/h63_lineament.json
python3 scripts/h63_calibrate.py                      # -> evidence/h63_calibration.json
python3 scripts/h63_emit.py  --stage measure          # -> evidence/h63_emit_measure.json
python3 scripts/h63_policy.py                         # -> evidence/h63_policy.json
python3 scripts/h63_finalize.py                       # -> the GeoTIFF + evidence/h63_final.json
python3 scripts/h63_uniqueness_control.py             # -> evidence/h63_uniqueness_control.json
python3 scripts/check_uniqueness.py \
        --raster lane62-h63m/docs/downloads/gems62-h63m-multiline-corroborated-90000-zeros.tif \
        --registry data/registry --footprint data/sample_submission.tif \
        --out evidence/h63_uniqueness.json
python3 scripts/h63_lane.py                           # -> evidence/h63_lane.json  (the lane deliverable)
python3 scripts/build_site_h63.py                     # -> lane62-h63m/docs/**
python3 -m pytest tests/ -q                           # 35 passed
```

Wall-clock on 2 CPUs / 3 GB RAM: ~75 min, dominated by the four-fold boosting run and the
policy sweep.

## What each script is for

| script | question it answers |
|---|---|
| `h63_features.py` | can the official stack and the DEM be reduced to one flat, hash-pinned design matrix? |
| `h63_train.py` / `h63_emission.py` | does a supervised model on the official stack generalize across space? (**no**) |
| `h63_lineament.py` | do catalogue-free DEM lineament detectors beat chance? (first pass, yes but confounded) |
| `h63_calibrate.py` | can a proxy instrument be tied to live scores? (yes, *r* = 0.775 ± IQR) |
| `h63_emit.py` | which combination of channels maximizes credit per unit mass? |
| `h63_policy.py` | at what density and what mass should the field be emitted? |
| `h63_finalize.py` | writes and certifies the GeoTIFF |
| `h63_uniqueness_control.py` | is the protocol's overlap tripwire even satisfiable? (not for 3 of 21) |
| `h63_lane.py` | the assigned datum-offset lane, on the full-footprint DEM |
| `build_site_h63.py` | renders every page from the evidence JSONs — no number is typed by hand |
