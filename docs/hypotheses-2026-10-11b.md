# Five candidate hypotheses, ranked — session `arena/d0303476-62gemsdoe`

The brief asks for 3–5 candidates not yet tried, each naming the layers, the physical signature, why
it should catch a fault **missing** from the USGS/INGENIOUS catalogue rather than one already in it,
and how it differs from anything already in this repository; then ranked by expected DTI improvement
against implementation cost, with the top candidate validated on the spatially-blocked holdout before
any weekly slot is touched.

Everything below is either **MEASURED** in this checkout (script named) or explicitly labelled as an
expectation.  The screening table that produced the layer lists is
`evidence/e1_layer_screen_20261011b.json` — 54 layers × a structure-tensor edge-line response at
σ = 1.2 px (120 m, matched to the metric's 300 m kernel), each scored three ways: credit per dot
against the mapped catalogue, credit per dot against **SGMC 1:750 k minus the catalogue** (an
independent public compilation of faults the competition catalogue does not contain), and the
fraction of its top-38,000 line pixels falling within 3 px of the incumbent fields.

| # | hypothesis | layers | expected ΔDTI | cost | status this session |
|---|---|---|---|---|---|
| **H62-L** | Derivative-field consensus (below) | official-stack gradients + `tc` + ratios + χ-ksn | **medium-high** | medium | **built, emitted, measured — negative as a lead, kept as a probe** |
| **H62-M** | Along-strike catalogue extension into gaps (H62-K, still untried) | catalogue geometry + 10 m lineaments | **high** | medium | **specified, not run (budget)** |
| **H62-N** | Same-mass credit transfer: re-emit an incumbent mechanism at 2–3× mass | any of the dotted family's score rasters | high **if** the credit floor holds | low | **specified; blocked by the copying rule except from an own field** |
| **H62-O** | Seismicity-alignment detector | `ieq_n100a15`, `deq_n100a15` | low-medium | low | **screened and rejected** (see below) |
| **H62-Q** | Geothermal-proximity prior × structural evidence (below) | GDR well/spring inventory + H62-L vote | medium **if** real | low-medium (needs a runner fetch) | **specified, not screened (budget)** |
| **H62-P** | Radiometric alteration lineaments (K enrichment / Th-U ratios) | `rad_K/Th/U/TC`, `ThK`, `UK`, `UTh` | low-medium | low | **screened; folded into H62-L as 3 of 13 voters** |

---

## H62-L — Derivative-field consensus, corroborated scarps  ·  **run this session**

* **Layers (13, one vote each):** `tc` (magnetic tilt angle), `tmi_vg`, `tmi_hg`, `iso_grav_anom_hg`,
  `iso_grav_anom_vg`, `iso_grav_anom_slope`, `TMI_up150`, `ThK`, `UK`, `rad_K`, `chi10:ksn_max_m0.9`,
  `topo10:curv_prof_absmax`, `det_elev_slope`; plus scarp evidence from the 1 m LiDAR composite
  (7 bands) and the 3 m scarp product (4 bands).
* **Physical signature:** the structure-tensor edge-line response `L = √λ₁·(λ₁−λ₂)/(λ₁+λ₂)`.
  A lineament on the **edge** of a magnetised or dense body is a different, sharper object than the
  ridge of the potential itself — the incumbent family filters the *potential* fields with a Hessian
  (Frangi/Sato) response at σ = 1.2/2.5 px, so the two are not the same measurement of the same
  structure.
* **Why it should catch a *missing* fault:** the organizers state a "new fault" includes newly
  mapped geometry of existing systems **[OFFICIAL, thread 11536]**; gradient maxima sit on the
  contact/source edge, which is where a fault plane intersects a layer, and the derivation is
  independent of any map.  Measured: the 13 voters' top deciles lie **farther** from the mapped
  catalogue than the incumbent's dots (median 2.2 km vs the champion's 1.96 km), i.e. this family
  does not re-find what is already mapped.
* **How it differs from the repository:** nothing here had used `tc`, the five gradient bands,
  the radiometric *ratios*, or the χ/ksn layer as voters; the incumbent's orientation order
  parameter is replaced by a discrete k-of-N vote with a doubled-angle agreement factor, so one
  layer family cannot outvote another.
* **Result (MEASURED, `evidence/e3_emission_profile_20261011b.json`,
  `evidence/final_field_gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.json`):** at 120,000 dots,
  credit per dot 0.0621 against SGMC-off-catalogue (95 % of the champion's 0.0655 on the same
  instrument) and 0.0008 against the mapped catalogue (0.02× a uniform field).  Holdout DTI
  **0.00073** — the protocol gate is **FAILED**, for the measured reason recorded in §3 of
  `docs/research/beating-02778-2026-10-11b.md`: that gate rewards catalogue proximity (−0.60 with
  the leaderboard).  **Verdict: legal, unique, provably isolated — negative as a lead horse.**
* **Named non-fault mimic:** fluvial and hillslope breaks — terrace risers, fan-head trenches,
  channel knickzones (the χ-ksn voter is *expected* to fire at lithologic contacts), and
  intrabasement gravity/magnetic contacts that are not faults.

## H62-M — Along-strike catalogue extension into DEM-supported gaps  ·  **the one to run next**

* **Layers:** `data/labels.tif` **geometry only** (segment endpoints and strike, from
  `60GEMSDOE/data/external/trace_segments_utm11.csv`, 84,331 segments with slip rates), plus
  `topo10:hs_lineament` / `topo10:slope_p90` as DEM support, plus the strike fan score sketched in
  `scripts/exp2_arms.py` (ARM B — built but not profiled before the budget closed).
* **Signature:** for every mapped segment, extend the strike beyond each endpoint and score the
  corridor by DEM lineament continuity; emit isolated dots where the corridor has DEM support and the
  catalogue does not.
* **Why it targets *missing* faults rather than mapped ones:** it is defined on the *gaps* between
  and beyond mapped traces, so it cannot re-find a mapped fault by construction, and it inherits the
  strike of a population known to be real.
* **Risk, stated before the result:** it is the one family that *should* pass the segmented holdout
  gate (the withheld segments lie along the same strikes), and §3 of the beating-0.2778 page shows
  the segmented gate anti-predicts the leaderboard.  A high score there would therefore be
  uninformative — the field must be judged on whether its dots are **off** the mapped catalogue,
  which is exactly what this construction guarantees.

## H62-N — Same-mass credit transfer (mass as an explicit, budgeted experiment)

* **Mechanism:** take any field whose per-dot credit is known (this session's, or the champion's
  mechanism re-derived from scratch — never the previous submission's bytes), and re-emit the same
  score ranking at 2–3× the mass with the identical hard-core emitter.
* **Why:** §2(c) of the beating-0.2778 page: at constant credit, `DTI` scales as
  `1/(0.2 + 0.8K/M)`, which predicts **+47 %** for 37,654 → 120,000 at constant credit.  The group's
  history shows the family failed to keep the credit (the mass–score relation is inverted within it),
  which is exactly why the experiment is worth spending a slot on: it measures `dc/dM`, the one
  quantity the whole project needs and no local instrument can supply.
* **Cost:** low (re-emission + validation only).  **Blocked locally by** the copying rule for prior
  submissions; admissible for an own field, which is what this session's artifact is.

## H62-Q — Geothermal-proximity prior × structural evidence  ·  **specified, not screened (budget)**

* **Why it is on this list at all.**  The competition asks for "structures indicative of geothermal
  resources" and the project that produced the hidden labels is a *geothermal* mapping programme; if
  the new faults were curated where the project had exploration interest, a proximity prior is a
  real, testable effect — and if they were curated uniformly, it is worth nothing.  Both outcomes
  are informative, which is why it is worth one experiment.
* **Layers:** the DOE Geothermal Data Repository well/spring inventory (free, official, public:
  <https://gdr.openei.org/>, query endpoint open to anonymous requests) as a distance-to-feature
  raster, combined with the structural vote from H62-L.  **Obtainability from this sandbox: not
  verified.**  `gdr.openei.org` is not on the sandbox's allow-list, so the file must be transported
  the same way the DEM was — by a GitHub runner through `.github/workflows/dem-fetch.yml`, which is
  already built and proven for a USGS host.
* **The test, fixed in advance:** per-dot credit against SGMC-off-catalogue (the only local quantity
  measured to track the leaderboard positively, ρ = +0.617) inside versus outside a 5, 10 and 20 km
  buffer of a GDR feature, with a mass-matched isolated-random control and a catalogue-matched null.
  A ratio below 1.0 kills the hypothesis; above 1.5 it becomes a multiplier on the H62-L score.
* **Prior art inside this group, and the reason this is not rank 1:** `GEMSDOE36` already ships
  `anderson-geothermal-pinn-38854` at **0.2750** (OWNER-REPORTED), i.e. a geothermal-flavoured
  submission at the group's existing band.  A new field must therefore differ **mechanically** —
  proximity as a *gate on a lineament consensus*, not as a learned density — or it is a re-run.
* **Named non-fault mimic:** geothermal features concentrate on playa margins and along range-fronts
  for hydrologic reasons (discharge sites) as well as structural ones, so the prior partly encodes
  hydrography rather than faults.

## H62-O — Seismicity-alignment detector  ·  **screened and rejected**

* **Layers:** `ieq_n100a15` (earthquake intensity/density) and `deq_n100a15` (distance to earthquake),
  both in the official stack.
* **Why it was attractive:** aligning hypocentres is a classical way to find blind faults, and no
  session in this repository had used the seismic bands.
* **Measured reason to drop it:** as a line-response layer, `ieq_n100a15` gives credit per dot
  0.0616/0.0279 (catalogue/SGMC) — below the topographic layers on both — and `deq_n100a15` is the
  **worst** layer in the whole screen on the off-catalogue compilation (0.0139, enrichment 0.8×, i.e.
  indistinguishable from a uniform field).  Both are n = 100 km, a = 15° counting fields, whose
  smoothing length (100 km) is 1,000× the metric's kernel radius (300 m); they cannot localise a
  feature at the scale the metric scores.

## H62-P — Radiometric alteration lineaments  ·  **screened; partially adopted**

* **Layers:** `rad_K`, `rad_Th`, `rad_U`, `rad_TC`, `radext_ThK`, `radext_UK`, `radext_UTh`.
* **Signature:** K enrichment and Th/U change along a fault-controlled hydrothermal pathway — the
  physics the competition is actually about (structures indicative of geothermal resources).
* **Measured:** `rad_K` is the **third**-best layer in the screen on the off-catalogue compilation
  (0.0840, 4.9× a uniform field) while being **anti**-aligned with the mapped catalogue (0.0345,
  0.8×) — a rare combination, and the reason three of the ratios are voters in H62-L.  The Th/U
  ratio on its own is not better than its parts (0.0484), so no separate arm is warranted.
* **Named mimic:** agricultural K (fertiliser) and playa evaporite chemistry both produce K
  lineaments without a fault; 75 % of the grid is not airborne-radiometric-quality in these
  products, and the coverage mask itself scores 0.0709 on the off-catalogue compilation
  (`lidar:valid`), which is a warning that coverage correlates with mapped fault density.

---

## What the screening says about the instrument (stated, not buried)

Credit per dot against SGMC-off-catalogue correlates **+0.62** with the leaderboard over 20
owner-reported scores, and credit per dot against the *mapped* catalogue correlates **−0.60**; but
the published DTI evaluated on the SGMC instrument correlates **−0.44**.  Every ranking above is
therefore a ranking **on a per-dot quantity**, and every *score* projection built from it is
labelled MODEL and must not be promoted.  Full numbers:
`docs/research/beating-02778-2026-10-11b.md` §3.
