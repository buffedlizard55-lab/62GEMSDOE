# Untried geological hypotheses, ranked — and the one that was tested

Written **before** implementing, as the brief requires. Each entry names the layers, the physical
signature and transform, why it should catch a fault the USGS/INGENIOUS catalogue lacks, how it
differs from work already done in this group, and the cost. Evidence classes: **[OFFICIAL]** read
from an organizer/USGS page, **[MEASURED]** computed here from hash-pinned bytes,
**[SIBLING-MEASURED]** measured in a sibling repository whose artifacts are in the registry,
**[CITED-IN-BRIEF]** named in the session brief but not independently verified in this sandbox,
**[BLOCKED]** not obtainable here, with the reason.

---

## 0. The lever that multiplies every hypothesis — and it is not geology

The published metric is `DTI = TP_w / (TP_w + 0.2·FP_w + 0.8·FN_w + ε)` with a 300 m triangular
kernel [OFFICIAL, competition page 967]. Writing `T = TP_w`, `S = FP_w`, `N = T + FN_w`, this is
exactly `DTI = T / (0.2·(T + S) + 0.8·N)` — so with β = 0.8 the denominator is dominated by
**misses**, not by false positives. Known USGS/INGENIOUS pixels are **excluded from evaluation
entirely** [OFFICIAL, thread 11516], so mass placed on the catalogue is neither penalised nor
credited, while a *missed* new fault costs 0.8. The full derivation, including the implied recall
floor of the group's best artifact, is in [`why-h33-scored.md`](why-h33-scored.md).

That makes the emission **density** the highest-leverage variable in the whole problem, and the
break-even condition is computable **without any hidden truth**: adding a dot that earns `p` of
truth credit and `1 − p` of penalty raises the denominator by exactly `0.2`, so it helps iff
**`p > 0.2 · DTI`** (derivation in [`why-h33-scored.md`](why-h33-scored.md) §2). At the group's
best operating point (0.2778) that bar is `p > 0.056`; at a more modest one it is lower still.
`src/gems62/metric.py::marginal_bar` implements it. Calibrating each emitter's density against
that bar is worth more than any single new detector, and it costs hours, not weeks. **Rank it
first by expected DTI gain per unit cost.** Every hypothesis below should be scored *through* it.

*Validation:* the marginal-credit curve is analytically checkable and is reproduced in `tests/`;
the emitted densities are then compared against the sub-totals on the submission page, which is
the only ORGANIZER-CONFIRMED channel that exists.

---

## 1. H-A — LiDAR scarp-composite scarps that the catalogue never captured — **rank 1**

* **Layers [SIBLING-MEASURED, band names read there from `training_features.tif`]:** the 1 m
  GeoDAWN LiDAR scarp composite `lidar_scarp_features_u8.tif`, bands `ex_max`, `step_max`,
  `downface_max`. *Not re-verified in this checkout: the 418 MB feature stack is not cloned here
  ([BLOCKED], see `data.md`).*
* **Physical signature / transform:** the composite already *is* the geomorphic signature of a
  fault — extensional crest, step magnitude, and the downthrown-face direction. The untried
  transform is **asymmetric step polarity across the line**: on a normal-fault scarp the
  `downface_max` field is one-signed across the trace, whereas a shoreline bluff, a terrace riser
  or a channel cut has no consistent downthrown side. Take the scarp composite's ridge response,
  then keep only ridges whose across-trace `downface` sign is coherent over ≥ 300 m.
* **Why it catches a fault missing from the catalogue:** the catalogue is a lineament/state-map
  product built largely from topography and prior mapping. Scarps under young deposits, under
  vegetation, or below the 25 m DEM's resolving power are systematically under-represented —
  precisely the class the brief cites: Pierce and Wesnousky (2016) found **two unmapped
  northwest-striking segments in the centre of Smith Valley** in lidar [CITED-IN-BRIEF].
* **How it differs from prior group work:** sibling H33-A uses these same bands inside an
  8-physics *orientation-consensus* score, i.e. it asks "do several fields agree that a line
  exists?". This asks a different question — "does the scarp have a consistent downthrown side?"
  — which is a physical property of a fault, not of a line, and it suppresses the level-feature
  family that dominates this basin.
* **Cost:** moderate; data already cached in the template. **Validatable locally: yes** — and
  independently of the DEM, because the LiDAR is a separate measurement.

## 2. H-B — Lateral deflection of shoreline ridges: strike-slip faults in basin centres — **rank 2**

* **Layers:** the 25 m USGS 3DEP DEM alone; no new data.
* **Physical signature / transform:** bar-and-swale and spur-and-groove ridges are long, straight,
  near-parallel features fixed at the time of the highstand. Run a structure tensor over the
  *ridge* field, then look for places where ridge azimuth and ridge crest position step
  laterally across a line — a shear offset, with **no scarp at all**.
* **Why it catches a fault missing from the catalogue:** strike-slip faults in basin centres
  produce lateral offsets without building relief, so every lineament/scarp method in use is blind
  to them. The brief's own motivating example is exactly this: Dong and coauthors documented
  Lahontan shorelines displaced along a strike-slip fault outboard of the Wassuk Range front
  [CITED-IN-BRIEF].
* **How it differs from prior group work:** this session's lane measured *vertical* steps in the
  datum (the deflection detector existed in the code as a secondary locus type and never became
  the emission basis). No artifact in the registry is built on lateral offset of a fixed-age
  datum.
* **Cost:** moderate (structure tensor + offset cross-correlation). **Validatable locally: weakly**
  — the catalogue contains few strike-slip traces, so the holdout can only screen.

## 3. H-C — Facet-base lines on range fronts (triangular facets), not facet crests — **rank 3**

* **Layers:** the 25 m DEM alone.
* **Physical signature / transform:** fit a **plane** to each candidate range-front facet surface
  (slope/slope-aspect segmentation), then intersect the fitted plane with the basin floor. The
  result is a line — the base of the facet — which is where the active fault trace is.
* **Why it catches a fault missing from the catalogue:** existing mapping picks lineaments and
  crest lines; the *base* of a faceted spur is a different line, and it is the one that breaks in
  the youngest event. Facet bases are routinely offset from the mapped trace by tens to hundreds
  of metres.
* **How it differs from prior group work:** every emitter in this group scores *edges* (gradient
  ridges, Hessian lines). Plane-fitting a facet is a surface model, not an edge response, and it
  produces geometry at a different location than any existing channel.
* **Cost:** moderate-high (segmentation + plane fits). **Validatable locally: yes** as a screen.

## 4. H-D — Basement-step lineaments from potential fields in catalogue-empty corridors — **rank 4**

* **Layers [SIBLING-MEASURED]:** `iso_grav_anom` (band 13), `depth_to_base_surf` (band 15),
  `cond_surf` (band 17) of the official training stack.
* **Physical signature / transform:** the **inflection / maximum horizontal gradient** of
  `depth_to_base_surf` and of the isostatic gravity residual — a step in the basement surface —
  rather than a ridge in the image. Restrict to corridors with **no catalogue line within 2 km**.
* **Why it catches a fault missing from the catalogue:** a step in the depth-to-basement surface
  under basin fill is invisible in topography and therefore absent from a topography-led lineament
  catalogue, yet it is a mapped-basement fault by construction.
* **How it differs from prior group work:** H33-A asks whether several fields agree that a
  *line* exists; this asks whether a *scalar surface has an inflection*, which can be true where
  no line is visible in any field.
* **Cost:** moderate. **Validatable locally: yes** as a screen, with the caveat below.

## 5. H-E (tested this session — recorded as a negative) — shoreline-datum vertical steps

The assigned lane: pluvial-bench extraction, robust quadratic isobase, Frangi ridge of the datum
residual, cross-cut gate, DEM-ridge trace growth. Delivered as
`docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif`.

* **Mechanism and result:** see [`run-card.md`](run-card.md) — 1,660 dots, 221 traces,
  redundancy against the catalogue 0.279 (down from 0.764 before the cross-cut gate).
* **Why it is ranked last despite being the most defensible:** coverage. 1,641 of 1,660 dots fall
  in one 171 × 110 km sub-region, because the hypothesis only speaks where a pluvial datum exists.
  The lane buys **defensibility, not area** — exactly as the brief predicted.
* **Known confuser, named before the fact:** wave-cut bluffs, berms, fan-head risers and delta
  topsets are level steps in the same band; the flat-pixel histogram contains **15 separate
  stands** between 1175 and 1437 m [MEASURED]. The cross-cut gate removes the contour-parallel
  family; it does not prove the remainder are tectonic.

---

## The validation trap, stated once and clearly

**No instrument available in this checkout can promote any of these hypotheses.** The only local
truth is the USGS/INGENIOUS catalogue, and the competition truth is *precisely the faults absent
from that catalogue*. Measured three ways:

| observation | value | source |
| --- | --- | --- |
| catalogue-hidden proxy vs live leaderboard, 12 artifacts | Spearman ρ = **+0.087** | [SIBLING-MEASURED] |
| a 300 m Poisson control vs the same live artifacts | 0.098 proxy, beating the 0.019 of an artifact that scored 0.2778 | [SIBLING-MEASURED] |
| this repository's own holdout: Poisson(37,654 dots) vs `h33-2-b2-zeros` (OWNER-REPORTED live 0.2778) | **0.0669 vs 0.0067** | [MEASURED], `evidence/calibration_v8.json` |

A random field outscores the best-scoring artifact on both instruments. So the holdout is used for
three things only — **(a)** catching bugs, which it did, **(b)** the leakage canary, and **(c)**
producing a same-density Poisson null so that "novelty" can be reported as a ratio — and never as
a promotion gate. Anything that claims to be promotable must be judged on the leaderboard, using
the weekly slots as the only real experiment.

## New external data: what would be needed and whether it is obtainable here

| hypothesis | needs new data? | free official source | obtainable? |
| --- | --- | --- | --- |
| H-A | no (cached in template) | GeoDAWN lidar scarp composite; USGS 3DEP for the DEM | **yes** — the DEM path is proven: the sandbox gets HTTP 000 from USGS hosts, a GitHub Actions runner does not, and run **38169727207** fetched six 3DEP tiles this way [MEASURED] |
| H-B | no | 25 m 3DEP DEM, already in `evidence/dem/` | yes |
| H-C | no | 25 m 3DEP DEM | yes |
| H-D | no (cached in template); **1 m lidar tiles** if higher resolution is wanted | USGS 3DEP lidar via the TNM API (`tnmaccess.nationalmap.gov`) — 19 products listed for the n40w119 tile alone, S3 download URLs, no use restrictions beyond acknowledgement [OFFICIAL, `evidence/tnm_probe.json`] | yes, via the runner; direct from this sandbox: **no** |
| H-E | no | same DEM | done |

Use restriction for any 3DEP product: acknowledge "Map services and data available from U.S.
Geological Survey, National Geospatial Program" [OFFICIAL, USGS 3DEP].
