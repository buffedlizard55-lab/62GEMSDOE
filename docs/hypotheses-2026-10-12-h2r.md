# Five candidate hypotheses not yet tried — session `arena/7b275dfb-62gemsdoe` (2026-10-12)

Generated **before** implementation, per the standing brief. Each entry names the specific
layer(s), the physical signature, why it should catch a fault **missing** from the
USGS/INGENIOUS catalogue rather than one already in it, and how it differs from everything
already implemented in this repository. Ranked by expected DTI improvement against
implementation cost. Evidence labels: **MEASURED** (this checkout), **INHERITED** (a prior
session's committed evidence), **OFFICIAL** (organizer pages), **EXPECTATION** (a pre-registered
prediction, falsifiable).

What has already been tried or screened (so the five below are genuinely new): H62-L
13-layer derivative vote (built; probe at 120k dots), H62-O seismicity (rejected, measured),
H62-P radiometrics (folded into H62-L), H62-M/K along-strike catalogue extension (specified
but never run), H62-N mass transfer (specified), H62-Q geothermal *proximity* gate (specified,
never screened), H-1 leaderboard inversion (run; S* recovered at Spearman +0.968), H-2
raw-band supervised detector toward S* (run; blocked DTI(S\*) 0.2178, projection 0.110 —
negative), H-3 multi-stand shoreline coincidence (negative/unmeasurable), H-4 direct S\*
cover (blocked as a protocol duplicate), H-5 LiDAR scarp polarity (blocked on transport),
the datum lane isobase steps (negative), H62-G bench cross-cut (negative), H62-I scarp
cross-cut (duplicate-drift, stopped).

---

## Ranked summary

| # | hypothesis | layers | expected ΔDTI | cost | why not tried yet |
|---|---|---|---|---|---|
| **1. H-2R** | Champion-mechanism lineament consensus rebuilt as *supervised features*, with the kernel defect in the S\* instrument fixed | 19-band official stack (rtp, tmi, mag_anom, iso_grav_anom, det_elev, cond_surf, depth_to_base_surf, tc, radiometrics) | **high** | medium | H-2 used raw bands only; the Frangi/Sato × orientation-order *feature* construction was never rebuilt here |
| **2. H62-Z1** | Hydrothermal-outflow corridor: vent-chemistry-weighted density × lineament consensus **interaction** | `gdr_wellspring_in_footprint.csv` (27,092 rows: temperature, thermal class, geothermometry), `gdr_volcanic_vents_in_footprint.csv`, consensus of #1 | **high if real** | low | H62-Q was proximity-only and never screened; no session used the GDR chemistry/temperature columns |
| **3. H62-Z3** | Depth-to-basement step detector (concealed range-front faults under basin fill) | `depth_to_base_surf`, `cond_surf`, `iso_grav_anom_hg` | medium | low | `depth_to_base_surf` was one vote among 13 in H62-L; never a cross-strike step detector in its own right |
| **4. H62-Z4** | Drainage-deflection / wind-gap detector (tectonic geomorphology of young offsets) | `dem10_chi_100m` (ksn, χ, zmean), `topo_10m_derived` (aspect_coherence, hs_lineament, curv_prof_absmax), DEM | medium-low | medium | χ/ksn entered H62-L only as one ridge voter; channel *deflection asymmetry* was never computed |
| **5. H62-Z5** | Vent–lineament-node point process (intersections/stepovers host permeability) | vent points × lineament crossing density (#1), optional `ieq_n100a15` | low-medium | low | point-process (cross-K) test never run; distinct from Z1's corridor interaction |

---

## 1. H-2R — Champion-mechanism consensus rebuilt as features, toward the fixed S\* instrument

* **Layers:** the byte-verified organiser stack `gems-geodawn-numerical-features.tif`
  (sha256 `4371c82e…`, 19 bands, **MEASURED** this session) — specifically `rtp`, `tmi`,
  `mag_anom`, `iso_grav_anom`, `det_elev`, `cond_surf`, `depth_to_base_surf`, `tc`,
  `TMI_up150` + GeoDAWN radiometrics — plus the 1 m LiDAR scarp composite bands
  (`ex_max`, `step_max`, `downface_max`, `coh100`).
* **Signature:** a scale-normalised Hessian (Frangi/Sato) line response at σ = 1.2 and 2.5 px,
  **both polarities**, multiplied by the second-order orientation order parameter
  `R = |Σ_p w_p e^{2iθ_p}| / Σ_p w_p` — a pixel scores only when independent physics agree a
  line exists *and* agree on its strike. This is the mechanism the 0.26–0.28 band used
  (**SIBLING-MEASURED**, read from GEMSDOE32's research note; quoted in
  `docs/why-h33-scored.md`).
* **Why it should catch a *missing* fault:** the catalogue is a topography/state-map product;
  agreement between independent *potential-field* physics selects lineaments that are real
  (a density or susceptibility contrast exists) but were never mapped — exactly the
  "newly mapped geometry of existing systems" class the organizers include
  (**OFFICIAL**, thread 11536, quoted in `docs/sources.md`).
* **How it differs from everything implemented here:** H-2 (the only prior supervised attempt)
  fed raw bands to a gradient booster and reached blocked DTI(S\*) 0.2178 / AUC 0.863
  (**INHERITED**, `datum62/evidence/detector2_cv.json`). The incumbent mechanism was never
  rebuilt *as features*. Additionally, this session found and fixes a **kernel defect in the
  S\* instrument itself** (see IR-62-2026-10-12-01 in `docs/irregularities.md`): the shared
  inversion quantised distances on a quarter-pixel lattice but divided by 3 instead of 12,
  fitting a 75 m triangle instead of the published 300 m one. The fixed instrument is the
  target this hypothesis is scored against.
* **Named non-fault mimic:** dykes, lithologic contacts and alteration fronts produce
  magnetic/conductivity line responses with coherent strike but are not faults.
* **EXPECTATION (pre-registered):** blocked DTI(S\*_fixed) ≥ 0.30 and AUC ≤ 0.90 (leakage
  canary). Failure to beat H-2's 0.2178 is a negative result and is reported as one.

## 2. H62-Z1 — Hydrothermal-outflow corridor (vent chemistry × lineament consensus interaction)

* **Layers:** `gdr_wellspring_in_footprint.csv` — **27,092** well/spring rows inside the
  footprint with `temp_c`, `thermalclass`, quartz/chalcedony/cation geothermometry
  (**MEASURED** this session: file present in the 60GEMSDOE mirror, columns verified);
  `gdr_volcanic_vents_in_footprint.csv` (22 rows); the consensus field of hypothesis #1.
* **Signature:** a **multiplicative interaction** — lineament-consensus score × local
  discharge intensity (temperature- and chemistry-weighted kernel density of thermal
  springs at 2/5/10 km), not proximity alone. Faults are permeable conduits: hydrothermal
  outflow concentrates where structure vents.
* **Why it should catch a *missing* fault:** the hidden fault feeding a known hot spring need
  not have surface expression — the spring *is* the surface expression. The competition asks
  for "structures indicative of geothermal resources" (**OFFICIAL**, page 967); the
  permeable conduit class is definitionally under-represented in a topographic catalogue.
* **How it differs:** H62-Q (proximity gate on the vote) was specified but never screened;
  nothing in this repository has opened the GDR files. GEMSDOE36's `anderson-geothermal-pinn`
  (0.2750, **OWNER-REPORTED**) is a learned density, not a chemistry-weighted interaction —
  this must differ mechanically to not be a re-run.
* **Named non-fault mimic:** hydrologic discharge on playa margins and lava-flow fronts;
  hot springs cluster on basin fill for hydrologic reasons as well as structural ones.
* **Test, fixed in advance:** per-dot credit (SGMC-off-catalogue instrument, 300 m kernel)
  inside vs outside 5/10/20 km of a thermal feature, mass-matched isolated-random control.
  Ratio < 1.0 kills the hypothesis; > 1.5 it is adopted as a gate on #1.

## 3. H62-Z3 — Depth-to-basement step detector

* **Layers:** `depth_to_base_surf`, `cond_surf`, `iso_grav_anom_hg`, `iso_grav_anom_slope`.
* **Signature:** cross-strike discontinuity in the *depth to basement* surface — a fault
  juxtaposes blocks with different sediment thickness, so the horizontal gradient of
  `depth_to_base_surf` peaks along the structure even where topography is flat.
* **Why missing faults:** buried fault scarps under basin fill have no topographic
  expression, so a topography-derived catalogue systematically lacks them; the Pyramid Lake
  and Wassuk-adjacent structures the lane cites are precisely basin-margin structures under
  partial fill.
* **How it differs:** H62-L used `det_elev_slope` as one of 13 equal votes; no session
  detected *steps in the basement surface itself*.
* **Named non-fault mimic:** depositional pinch-outs and progradational sediment wedges
  create depth gradients without faulting.

## 4. H62-Z4 — Drainage-deflection / wind-gap detector

* **Layers:** `dem10_chi_100m` (`ksn_max_m0.9`, `log10_area_m2_x1000`, `zmean_m`),
  `topo_10m_derived` (`aspect_coherence`, `hs_lineament`, `curv_prof_absmax`), 100 m DEM.
* **Signature:** lateral channel deflections, beheaded channels and wind gaps — a step in
  χ or in drainage area across a lineament, with aspect coherence flipping across it.
* **Why missing faults:** offsets of Holocene drainages are the classic expression of *young*
  faults missing from compilations — Pierce and Wesnousky (2016) found exactly this class in
  Smith Valley's basin centre (the lane's own citation).
* **How it differs:** χ/ksn entered H62-L as a ridge voter only; the *deflection asymmetry*
  statistic was never computed here.
* **Named non-fault mimic:** lithologic knickzones, landslide dams, and glacial/ lacustrine
  reorganisation of drainages (the Lahontan highstand itself re-routed drainages).

## 5. H62-Z5 — Vent–lineament-node point process

* **Layers:** vent/spring points (as #2) × lineament crossing density (from #1's orientation
  field), optionally `ieq_n100a15` as a prior-weighted variant.
* **Signature:** point-process interaction — do thermal discharge points sit on lineament
  *nodes* (intersections, stepovers) more often than a mass-matched null? Cross-K / nearest-
  neighbour test, then a node-density × vent gate.
* **Why missing faults:** permeability at fault intersections is the standard conceptual
  model for geothermal systems (Curewitz & Karson, 1997, *J. Volcanol. Geotherm. Res.* 79,
  149–168, "Structural settings of hydrothermal outflow"; Faulds & Hinz, 2015, Great Basin
  play-fairway work — both listed in `research/geothermal_vent_knowledge.md` with links for
  manual review); the intersecting fault is often the unmapped one.
* **How it differs:** Z1 is corridor-level interaction; Z5 is a point-process test on nodes.
* **Named non-fault mimic:** volcanic vent alignments (crater ridges) and hydrothermal
  alteration at shallow intrusions need no through-going fault.

---

### Where the geothermal-vent science is stored

`research/geothermal_vent_knowledge.md` (this session) collects the official, free sources
used above — GDR/NGDS inventories, USGS/INGENIOUS, and the structural-permeability
literature — as the reusable knowledge base the standing brief asks for. Every row in the
GDR CSVs is traceable to `https://gdr.openei.org/` (**OFFICIAL**, free, public; mirror
provenance in `registry/data_pins.json` style receipts in `build/ext/fetch_receipt.json`).
