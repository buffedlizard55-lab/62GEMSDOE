# Candidate hypotheses, ranked — 2026-10-12 session

Written by the datum-offset lane after it ran its own hypothesis to the end and got a *negative for
score, positive for information* result (H62-J: 10,870 isolated dots, instrument-B credit 0.040588 =
1.60× its domain-matched control, model DTI 0.0375 — see `run-card.html`). Each candidate below names
the layers it reads, the physical signature it looks for, why that signature should mark a fault the
USGS/INGENIOUS catalogue is missing, how it differs from every field already in the 79-raster registry,
what it costs in this sandbox (3 GB RAM, 2 vCPU, no `drivendata.org`), and the measurement that would
kill it. Ranking is by expected credit per unit effort **given the band table this session measured**
(`evidence/h62j-bands.json`): per-dot credit 0.178 / 0.153 / 0.108 within 500 m of a mapped trace,
0.035–0.057 at 0.5–4 km, 0.018 beyond 4 km (0.51× a same-band control). Anything that places mass in
the far field starts in debt.

| # | hypothesis | expected per-dot credit | cost | status |
| --- | --- | --- | --- | --- |
| H62-K | Along-strike continuation of mapped systems past their catalogued tips | high (bands 0–1.5 km) | one pass over segments | not tried |
| H62-L | Collar ladder: re-emit existing detectors at 200 / 300 / 500 / 1000 m and move mass inward | method-level, applies to every lane | one sweep per lane | not tried |
| H62-M | Shore-platform *width* truncation along strike, not scarp height | medium | 1 day, DEM already on disk | not tried |
| H62-N | The isobase residual field (fitted tile surfaces minus a published rebound model) as the generator | unknown, cheap to test | hours, no new fetch | not tried |
| H62-J | Datum-doublet paired-flank displacement detector | measured 0.041 | — | **done: real signal, capped mass** |
| (geothermal / H62-Q) | Hot springs, wells and vents as structure, at 5/10/20 km | measured 0.79–0.88× control; the one 1.13× is placebo-equal | — | **REFUTED this session, to the other lane's own specification** |

## H62-K — continue the trace, do not buffer it

* **Layers.** `data/labels.tif` (mapped trace geometry: orientation, endpoints, segment lengths),
  `evidence/dem/lahontan_dem_utm11.tif` (25 m), `evidence/h62j/fields_100m.npz` (the isobase surface and
  bench field already computed), plus `qfault_attributes.csv` / `trace_segments_utm11.csv` /
  `gdr_qfaults_traces.csv` for throw-class and segment length.
* **Signature.** Beyond each mapped tip, along the extrapolated strike, a corridor in which the DEM
  response (bench cut, doublet step, or scarp curvature) exceeds the *same* statistic measured at equal
  distance from the trace's middle — i.e. a continuation test, not a proximity test.
* **Why it should catch a missing fault.** Catalogue tips are where mapping stopped (coverage, cloud,
  vegetation, alluvium), not where rupture stopped; offset of an isobase across a *continuation* is the
  classic sub-scarp signature and requires no new geomorphology.
* **How it differs from every registry field.** All 79 registry rasters are driven by perpendicular
  proximity or ridge/hillshade response. None is built on along-strike continuation of the catalogue's
  own geometry — which makes it structurally unique (the duplicate gate cannot fire on it) and keeps it
  inside the datum lane.
* **Kill test.** Instrument-B credit of the continuation dots against mass-matched control dots drawn
  from the same catalogue-distance bands. If the ratio is under ~1.2× at whatever mass survives
  isolation, the lane's geometry is exhausted and this is written up as a second measured negative.

## H62-L — the collar ladder (a measurement about the metric, not about faults)

Every lane here excludes a 250–300 m collar around the catalogue — including, note, one that a
banker's-rounded `int(round(250/100))` silently turned into 223.6 m (`IR-62-20`). The band table says
credit is *highest* exactly where the collars cut. So: hold the detector fixed, emit at collars
{200, 300, 500, 1000} m, and compare model DTI at fixed N. Cost is one sweep per lane, and it settles a
group-wide policy question that has been argued from intuition for weeks. The honest complication is
stated in advance: dots within ~200 m of a mapped trace are masked out of the organiser's truth, so any
gain must come from the flanking damage zone; whether that zone reaches 300 m or 900 m is precisely what
this experiment measures.

## H62-M — measure the platform, not the scarp

A Lake Lahontan bench is a *width* as well as a height: its dip-direction extent scales with stillstand
duration and with the slope it was cut into. A fault that interrupts the stillstand truncates the width
while leaving bench *elevations* comparable on the two sides — the opposite of the doublet criterion that
this session ran, which looks for a vertical offset. Layers: the 25 m DEM and the fitted isobase
surface; signature: a step in bench width (measured perpendicular to the isobase, over a 4–8 km tile)
co-located with a bench score that is high on both sides. Cheap: the fields are already on disk. Kill
test as for H62-K.

## H62-N — the residual is the deformation

This session fitted a robust modal bench elevation per 4 km tile (1,093 tiles with a bench, surface
1,159.05–1,453.25 m, `evidence/h62j/isobase.json`) so that the doublet measurement could subtract
large-scale warp. The *fit residual itself* — measured surface minus a published Lahontan rebound or
tilt model, not a locally smoothed version of the same data — is a deformation field, and its gradients
may localise strain better than a two-flank step test does. Cost is hours and no new fetch; the risk is
circularity, which is why the falsifier is fixed in advance: the residual-gradient field must beat the
doublet field's 1.60× on the same domain and mass, or the lane's conclusion stands as written.

## Two things this card does not propose

**Not thermal occurrences as structure.** The other lane's H62-Q specification (5 / 10 / 20 km buffers
around GDR wells and springs, mass-matched control, "below 1.0× it dies") was run to the letter and it
dies: 0.79× for Hot+Warm at every radius, 0.87–0.88× for Hot-only, 0.83× / 0.87× for vents at 5 and 10 km,
and 1.13× at 20 km — which a placebo of five random 21-point buffer sets reproduces
(0.04757 ± 0.00499 against the real 0.04966, z = +0.42). Occurrence cells themselves score 0.75–0.84×,
600 m corridors 0.77×, mapped vents 0.10–0.21×, and everything *outside* the buffers 0.60–0.64×.
Evidence `evidence/h62j2-geothermal.json`. The only defensible thermal use left is as a *weight* on a
structural candidate, and the burden of proof for that now sits with whoever proposes it.

**Not more mass in the far field.** The arithmetic is closed: DTI → 5 × mean per-dot credit, and this
session's far-field credit is 0.018. Widening gates to reach 20,000–40,000 dots lowers mean credit
further (run 1 → run 2: 8,571 dots at 1.74× became 10,870 at 1.60×); it moves the number, not the score.
