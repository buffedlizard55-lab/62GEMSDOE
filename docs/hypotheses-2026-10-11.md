# Candidate hypotheses, ranked — 2026-10-11 session

The brief asks for 3–5 candidates not yet tried, each naming its layers, its physical signature, why
it should catch a fault **missing** from the USGS/INGENIOUS catalogue, and how it differs from
anything already implemented. Ranked by expected DTI improvement against implementation cost.

Two of the five were screened in this session and are **reported with their measured result**, not
with a hope. Screening instrument: SGMC 1:750 k off-catalogue truth (79,615 px, catalogue masked),
emission of 44,090 dots under a 300 m hard-core, compared against an **isolated-random control that
scores 0.04281** on the same instrument. `evidence/h62g/exp2.json`, MEASURED.

| # | hypothesis | expected ΔDTI | cost | status |
|---|---|---|---|---|
| **H62-K** | Along-strike continuation of mapped systems into DEM-evident gaps | **high** | medium | not tried |
| **H62-J** | Differential-rebound gradient of the fitted isobase | medium | low | not tried |
| **H62-I** | Scarp steps, cross-cut gated against the palaeo-contour | medium (measured 2.2× control) | **done** | **duplicate-drift** |
| **H62-H** | Channel-steepness (χ) knickzones on range fronts | medium | medium | not tried |
| **H62-F** | Pluvial lake-flat scarp habitat | high a priori | **done** | **REFUTED, 0.03× control** |

---

## H62-K — Along-strike continuation into catalogue gaps  ·  **rank 1**

* **Layers:** `existing_faults.tif` (mapped trace geometry only — orientation and endpoints, *not*
  fault presence), the 100 m DEM (`geodawn_dem_a2_100m.tif`, 99.97 % footprint coverage),
  and `topo_10m_derived_100m_u8.tif` bands `hs_lineament` (8) and `curv_prof_absmax` (6).
* **Signature:** for every mapped segment, extrapolate its strike beyond each endpoint and score the
  corridor by DEM lineament response and along-corridor profile-curvature continuity; emit dots
  where the corridor has DEM support and the catalogue does not.
* **Why it catches a *missing* fault:** the organizers state that a "new fault" includes *newly
  mapped geometry of existing systems* (thread 11536, quoted in `research/sources.md`). This is the
  only hypothesis that targets that population *by construction*: it is defined on catalogue
  **gaps**, so it cannot re-find a mapped fault, and it inherits the strike information of a
  population that is known to be real.
* **How it differs from this repo:** every lane here treats the catalogue as a mask to be excluded.
  None uses its *geometry* as a prior. `emit.py` computes a catalogue distance transform, but only to
  push dots away, never to orient them.
* **Risk:** the corridor prior can be wrong where a mapped segment terminates because the fault
  genuinely ends (a transfer zone or a bend), and the DEM's 100 m posting smooths the very
  low-amplitude scarps that matter.

## H62-J — Differential-rebound gradient  ·  **rank 2, cheapest**

* **Layers:** the fitted isobase itself (`src/gems62/datum.py`), plus the 100 m DEM.
* **Signature:** the second spatial derivative (Laplacian and maximum directional curvature) of the
  fitted rebound surface. Adams, Wesnousky & Bills (1999) attribute ~22 m of post-highstand
  deflection mostly to isostatic rebound with a small down-to-the-north tilt; the *gradient* of that
  field is largest where crustal load changed most, and strain localises at load gradients.
* **Why it catches a missing fault:** it is a *stress* proxy rather than a geomorphic one, so it
  fires where displacement has not yet produced a mappable scarp — precisely the population the
  catalogue lacks.
* **How it differs:** `datum.py` fits the isobase and only ever uses its *residual* to find steps.
  Its gradient field is computed nowhere.
* **Caveat that must be stated before any result is trusted:** `IR-62-03` records that the isobase
  fit is degenerate in its linear part. Taking a second derivative of a degenerate fit is exactly how
  a phantom signal is manufactured. This hypothesis is only admissible after the fit is replaced by a
  published rebound/viscosity model.

## H62-I — Scarp steps, cross-cut gated  ·  **rank 3 — screened, and quarantined**

* **Layers:** `lidar_scarp_features_u8.tif` bands `step_max` (3) and `cross_max` (8), gated by
  `valid` (12); 100 m DEM for the contour orientation.
* **Signature:** a metre-scale vertical step whose *orientation cuts across* the local
  palaeo-contour. `|sin(θ_line − θ_contour)|` separates a fault crossing the shoreline from a beach
  berm or delta topset running along it.
* **Result, MEASURED:** `step_max` alone 0.09255 (**2.16× control**), `cross_max` alone 0.09524
  (**2.22× control**), the gated combination at 60,000 dots 0.086663 (**2.00× control**). The gate
  does not raise credit over the ungated band — an honest negative within a positive result.
* **Why it is quarantined:** 87.5 % of its dots fall within 3 px of `gemsdoe23-h30-arrangement-matched
  -habitat` and the symmetric Jaccard of the two 3-px halos is **0.4465** (limit 0.25). Both fields
  are driven by the same LiDAR composite, so this is real lane drift. Logged and stopped.
* **Coverage limit:** the LiDAR composite is non-zero over only **31.72 %** of the grid, which is the
  binding constraint on this family's spread — not the geology.

## H62-H — Channel-steepness (χ) knickzones  ·  **rank 4**

* **Layers:** 100 m DEM; flow accumulation and the χ transform
  `χ = ∫ (A₀/A)^θ dℓ` with θ ≈ 0.45; optionally `slope_p90` (band 1) for corroboration.
* **Signature:** linear χ anomalies and knickzone clusters — a channel response that integrates
  displacement over a whole catchment rather than expressing it at one pixel.
* **Why it catches a missing fault:** low-slip or blanket-covered scarps leave no mappable trace but
  do perturb drainage. The catalogue is map-based; χ is not.
* **How it differs:** nothing in this repository computes flow routing. The named non-fault mimic is
  **lithology** — a knickzone at a contact between resistant and weak rock is indistinguishable from
  one at a fault without a geologic map, which is why this must be reported *with* that confuser.
* **Cost:** medium. Needs a depression-filled DEM and a χ implementation; both are standard.

## H62-F — Pluvial lake-flat scarp habitat  ·  **REFUTED, kept as a negative result**

* **Layers:** 100 m DEM (slope, local relief, elevation relative to the datum).
* **Hypothesis as stated:** post-pluvial scarps are best preserved where the pre-fault surface is
  young, flat and unvegetated — the Lahontan lake plains and deltas — so a hard-core dot field over
  that habitat should earn credit above chance.
* **Result, MEASURED:** **0.00118**, i.e. **0.03× the isolated-random control**. The most decisively
  refuted field screened this session, by a factor of ~36 below chance.
* **What it rules out:** the "habitat" argument in its simple form. Lake flats are not where the
  off-catalogue fault population lives — or, more cautiously, the instrument used cannot see them
  there. The Lahontan datum band itself (1308–1360 m) also came in **below** chance at 0.02614
  (0.61× control), which is the direct measurement behind this lane's repeated negative verdicts.

---

## What the screening says about the instrument itself — stated, not buried

Every number above comes from **SGMC 1:750 k off-catalogue**, a public geological compilation. Two
facts limit it. First, a compilation is biased toward geomorphology its compilers could already see,
so a 1 m LiDAR scarp response is expected to score well against it partly by construction. Second,
the same repository records (`docs/irregularities.md` §4) that catalogue-like proxies
**anti-select novelty**: a Poisson control beat an artifact that scored 0.2778 live. The honest
reading of the table is therefore *"this is the ranking this instrument gives"*, not *"this is the
ranking the organizer gives"*. Only a submission-page receipt can settle it, and this repository
holds none.
