# Geothermal-vent science knowledge base — official, free sources

Maintained by session `arena/7b275dfb-62gemsdoe`, 2026-10-12. This is the reusable
knowledge base the standing brief asks for: every claim below is either a measured fact
from this checkout or attributed to a named official/peer-reviewed source with a link for
manual review. **No paywalled or unverifiable claims.** Flags mark what still needs manual
confirmation.

## 1. Why vents matter for this competition

The DOE GEMS prize asks for "structures indicative of geothermal resources"
(competition overview, [DrivenData #306](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).
A geothermal system needs three ingredients (standard conceptual model, sources below):
**heat, fluid, and permeability**. In the Great Basin the permeability ingredient is
structurally controlled — hydrothermal upflow resides in fault-intersection and
fault-interaction zones (Curewitz & Karson, 1997; Faulds & Hinz, 2015). The *unmapped*
fault in an interaction zone is therefore a "structure indicative of geothermal resources"
even before a spring is drilled.

## 2. Official data sources (all free, all public)

| source | what it provides | link | status here |
| --- | --- | --- | --- |
| DOE Geothermal Data Repository (GDR) | submission point for DOE Geothermal Technologies Office data; wells, springs, geochemistry, temperature, play-fairway products | <https://gdr.openei.org/> | **in hand**: `build/ext/gdr_wellspring_in_footprint.csv` (27,092 rows in-footprint, with `temp_c`, `thermalclass`, quartz/chalcedony/cation geothermometry) and `gdr_volcanic_vents_in_footprint.csv` (22 rows), mirrored via the 60GEMSDOE data bridge with receipts |
| GDR: "Structural and Tectonic Controls of Geothermal Activity in the Basin and Range Province" | inventory of structural settings of >400 Great Basin geothermal systems | <https://gdr.openei.org/search?q=great+basin> (search "Structural and Tectonic Controls") | **flagged for manual review**: the inventory is the direct prior for H62-Z1/Z5; download requires an unrestricted machine (this sandbox cannot reach gdr.openei.org directly; the CSV mirror above is the transport) |
| National Geothermal Data System (NGDS) / OpenEI | federated catalog incl. USGS spring and well data | <https://openei.org/wiki/NGDS> | catalog only; same transport constraint |
| USGS Quaternary Fault and Fold Database (Qfaults) | the mapped-fault catalogue class the competition's "known faults" belong to | <https://www.usgs.gov/programs/earthquake-hazards/faults> | in hand as `build/ext/qfault_attributes.csv` + `trace_segments_utm11.csv` (84,331 segments, via 60GEMSDOE mirror) |
| GeoDAWN airborne geophysics (USGS) | the magnetic/gravity/radiometric layers the competition stack is built from | <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and> | in hand: organiser 19-band stack, sha256 `4371c82e…` byte-verified |
| INGENIOUS / Great Basin Center for Geothermal Energy | the research programme behind the hidden label set | <https://gbcge.org/current-projects/ingenious/> | context only |

## 3. Peer-reviewed structural-permeability literature (verified citations)

* **Curewitz, D., and Karson, J.A., 1997**, "Structural settings of hydrothermal outflow:
  Fracture permeability maintained by fault propagation and interaction", *Journal of
  Volcanology and Geothermal Research*, v. 79, p. 149–168. — fault propagation/interactions
  maintain fracture permeability; outflow sits at interacting fault tips. (Verified via
  multiple independent citing sources, e.g. Stanford SGW 2025 proceedings,
  <https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf>.)
* **Faulds, J.E., and Hinz, N.H., 2015**, Great Basin geothermal play-fairway analysis
  (DOE/GTO; widely cited as the structural-setting framework for blind Great Basin systems).
  **flagged for manual review of exact report number** — start at
  <https://gdr.openei.org/search?q=play+fairway+great+basin>.
* **Siler, D.L., et al., 2018**, machine-learning play-fairway for the Great Basin
  (USGS/GTO), cited in the Stanford SGW 2025 review above for fault-interaction controls.
* Competition organizers' own definitions (OFFICIAL, quoted in `docs/sources.md`):
  known USGS/INGENIOUS faults are **masked out of scoring** (thread 11516); a "new fault"
  includes **newly mapped geometry of existing systems** (thread 11536); Phase-2 labels
  were updated by expert review of Phase-1 submissions (thread 11527).

## 4. What the GDR inventory says that the competition catalogue does not

1. **Discharge ≠ mapped fault.** Hot springs in the Great Basin commonly sit *hundreds of
   metres to kilometres* off the mapped trace, along the damage zone or at the intersection
   with a cross structure. The CSV in hand records `dist_known_fault_px` per feature —
   **MEASURED this session** (values in the file, e.g. Beowawe row: 61.7 px ≈ 6.2 km from
   the known-fault mask used by the sibling bridge).
2. **Temperature and chemistry are free structure detectors.** Quartz/chalcedony/cation
   geothermometry estimate *reservoir* temperature (depth), so a cluster of high
   geothermometry springs marks a deep permeable conduit — the conduit is the fault, and
   its surface trace may be invisible.
3. **Volcanic vents are a different population** (22 rows in-footprint, basaltic, mostly
   young) — they mark crustal thinning/extension, useful as a *prior* but not as a fault
   map.

## 5. Hypotheses this knowledge base generated (session 2026-10-12)

`docs/hypotheses-2026-10-12.md`: H62-Z1 (vent-chemistry × lineament interaction),
H62-Z5 (vent–lineament-node point process), plus the structural H-2R/Z3/Z4. Screening
results are in `evidence/e5_screen_20261012.json`; the vent *proximity* placement layer
measured **0.64×** an isolated-random control on the SGMC-off-catalogue credit instrument
(MEASURED) — recorded as a refutation of proximity-as-placement, not of the interaction.

## 6. Limitations

* The GDR rows here are a **mirror** transported by the sibling repository; provenance is
  owner-mirrored bytes (receipts in `build/ext/`), not organizer-authenticated.
* gdr.openei.org, usgs.gov and drivendata.org are unreachable from this sandbox
  (HTTP 000, MEASURED in prior sessions); every fetch goes through GitHub transport.
* Geothermometry columns are sparse; the thermal subset rule used here (T ≥ 40 °C, or
  Hot/Warm class, or geothermometry ≥ 60 °C) is a **choice**, documented in
  `scripts/exp5_features_20261012.py`, and is a potential sensitivity.
