# Four geological hypotheses and one acquisition hypothesis — 2026-10-12

Session `arena/61e7859a-62gemsdoe`. Companion to
[the instrument audit](instrument-audit-2026-10-12.html); every number below is either an OFFICIAL
statement (cited) or a measurement with a receipt in `evidence/`.

## 0. The bar these hypotheses have to clear, stated numerically

The audit's §7 fixes the target better than the leaderboard does. Because
`DTI = TP_w / (0.2*M + 0.8*|G| + 0.2*(TP_w - M_cov))`, a field with no information scores at most
`M * 1.8239e-6 / 0.8`; at the group's mass that is **0.086–0.091**. The receipts therefore say:

| field | organiser score | information multiple over chance |
| --- | --- | --- |
| group best `h33-2-b2` (0.2778) | 0.2778 | **3.24 x** |
| the 36–42 k family as a whole | 0.2376–0.2778 | 2.97–3.24 x |
| leaderboard #9 (the user's target) | 0.3195 | **3.50 x** |
| leaderboard #1 (2026-10-12) | 0.4275 | **4.69 x** |

So the question for every hypothesis below is not "is this geology true" but **"does it raise
information per dot by ~45 % over the current field?"** A hypothesis that only re-shuffles which
random-looking dots are emitted cannot clear the bar, no matter how sound the physics.

**The brief's standing requirement is a holdout pass before a slot. That requirement cannot be met
with the instruments in this repository, and this is a flagged irregularity, not an oversight:**
two independent truth proxies are *inverted* against the 42 organiser receipts (masked-catalogue
credit, rho = -0.615; catalogue-absent SGMC coverage, rho = -0.562), and inside the 36–45 k band
the best of them is flat at 0.201–0.205 coverage across scores from 0.2449 to 0.2778
(`research/offcatalogue_instrument_validation.json`). From here a design can be *screened* in-repo
but only a submission can *validate*. Per the brief's own selector rule, no slot is spent by this
session.

## 1. Ranked set

| # | hypothesis | inputs / physical signature | why it should beat a catalogue-mirroring field | what is new vs this repo's own history | cost | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| **H64** | **Rarity-selected shoreline-offset faults** (the assigned lane, sharpened) | 3DEP 1/3" DEM (in repo, 25 m, decimetres) + `src/gems62/datum11c.py` datums (Sehoo 1313–1348 m, Younger Dryas 1222–1242 m, late Holocene 1196–1212 m). Signature: a step locus that (a) sits within +/-6 m of a known Lahontan datum, (b) is strike-coherent over >=3 km, (c) is off-catalogue by >300 m | the scored truth is *newly identified* faults (OFFICIAL, page 967); a scarp that cuts a 15 ka pluvial shoreline is by construction young and, where the catalogue has nothing, newly identifiable. Frequency alone selects density, not youth | lane 11 c emitted 682 dots from datums with no intersection test and returned 0.415 x uniform credit; H62-L/H62-M used derivative consensus and catalogue extension, neither of which uses a *datum elevation* as a hard filter. The intersection (step AND datum AND strike AND off-catalogue) is new | ~1 session, code exists | **run next**; screened in-repo by the information multiple of its own output, validated only by a slot |
| **H65** | **Discharge-graded thermal prior** | `build/ext/gdr_wellspring_in_footprint.csv` — 27,093 GDR/INGENIOUS wells and springs with `temp_c`, `geothermquartz_c`, `dist_known_fault_px` (already in the repo, free, official). Signature: hot upflow (quartz geothermometer > 150 °C) must vent along a permeable fault within a few hundred metres of the discharge point; order candidate traces by the geothermometer temperature of their nearest discharge | the object being scored is a *geothermal* fault; a discharge point is direct evidence of a deep permeable structure and is independent of whether anyone mapped it. Proximity priors alone mirror the catalogue because springs cluster where faults are already mapped | H62-Q proposed "geothermal proximity x structural evidence" and was never screened; this replaces proximity with a *graded* geothermometer field and the discharge-to-trace geometry, which is a different ranking function on the same data | ~0.5 session, data in hand | screened next; cheap |
| **H66** | **Concealed range-front hinge from chi/ksn step** | `build/ext/dem10_chi_100m_i16.tif` (ksn, log10 drainage area, step_max) + `topo_10m_derived_100m_u8.tif` (relief_local, aspect_coherence). Signature: a *step* in channel steepness across a range front with a migrating divide implies a buried fault hinge; the step direction gives the dip | the catalogue over-represents faults with bedrock exposure; a fault buried by its own alluvial fans is exactly the "not included in the existing USGS fault database" case, and chi is a dynamic (erosion-rate) witness that does not require the scarp to survive | chi was previously one of nine consensus bands, which dilutes it; here it is used as a *step detector along the range front* with the step sign imposing dip — an operator the repo has never run | ~1–2 sessions | screened, lower priority |
| **H67** | **Post-pluvial rebound as a vertical strain gauge** | DEM + the lane's isobase surface. Signature: Lahontan rebound is a water-load column, so its magnitude is predictable; the *residual* of measured shoreline elevation against the predicted rebound curve is a per-fault vertical-slip estimate in metres | converts topography into slip *rates* with a physical scale, which no density-based field in this group has; late Quaternary faults with the largest post-15 ka slip are the ones an expert labels first | the lane fitted a smooth isobase as a *shape* correction and never converted it to slip or used slip to rank faults | ~2 sessions | conceptually strongest, most expensive |

### Acquisition hypothesis (not geology, and the one with the largest expected value)

**H68 — get an independent post-2020 fault compilation for the AOI, then re-run the receipts test.**
The audit's §6 pass condition is a *positive* Spearman of a new truth stand-in against the 42
organiser scores; nothing in this repository passes it. Candidate sources, all free and official:
USGS Quaternary Fault and Fold Database (<https://usgs.github.io/faults/>, also the `qfault_attributes.csv`
already fetched), the GeoDAWN lidar/magnetic products
(<https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and>,
DOI 10.5066/P93LGLVQ), and GDR submission 1391 (`gdr.openei.org/submissions/1391`, already harvested
as the CSV in H65). **Flagged irregularity: all of these hosts return HTTP 000 from this sandbox**
(measured repeatedly in this repo's `docs/data.md`), so the fetch has to run on a GitHub runner or
from the user's machine — which is exactly how the 3DEP DEM and the 418 MB feature stack were
obtained before.

## 2. What would falsify each one

* **H64** — output whose information multiple against the *SGMC-absent* population is not
  distinguishable from the uniform control's (measured today: champion 0.0954, uniform 0.0745,
  H63-diffuse 0.1400 on that proxy). Any output in the 0.07–0.10 band is a re-shuffle.
* **H65** — a Spearman between the geothermometer prior and the SGMC-absent population that is not
  positive; or a top-40 k set that overlaps the current field's by more than 70 % (the protocol's
  own drift tripwire), which would mean the prior changed nothing.
* **H66** — chi steps that coincide with the catalogue as often as with catalogue-absent faults
  (measured: catalogue-dense cells carry the same chi range), i.e. no selectivity.
* **H67** — residual rebound correlated with shoreline *distance from the basin centre* rather than
  with fault position; that would mean the residual is datum noise, not slip.

## 3. Why no slot was spent today

The brief's selector rule is explicit: a weekly slot is for an idea that has already beaten the
current holdout best, and the audit shows no in-repo instrument can establish that (IR-62-11C-04,
IR-62-11C-05). The published artifact therefore carries its expectation as a *band*
(0.18–0.29, most likely 0.26) and an explicit statement that **no in-repo evidence supports a score
above 0.3195**. Spending a slot is a decision the user makes with that statement in front of them.
