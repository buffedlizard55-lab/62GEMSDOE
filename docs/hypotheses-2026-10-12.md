# Candidate Geological Hypotheses (Session 2026-10-12)

**Lane:** Datum-Offset Lane (Lake Lahontan Shorelines as a Strain Gauge)  
**Protocol:** Parallel-Run Protocol v1, 62GEMSDOE  

Before implementation, the protocol requires generating 3–5 candidate geological hypotheses not yet tried in this repository, each specifying:
1. The specific layer(s) involved
2. The physical signature being targeted
3. Why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it
4. How it differs from anything already implemented in this repository
5. Ranked by expected DTI improvement and implementation cost
6. Validated on our spatially-blocked holdout set before touching a weekly submission slot.

---

## Ranked Summary Table

| Rank | Hypothesis ID | Mechanism / Target Signature | Key Layers Involved | Expected ΔDTI | Cost | Status / Holdout Result |
|:---:|:---|:---|:---|:---:|:---:|:---|
| **1** | **H62-R** | Pluvial Shoreline Datum-Step & Deflection Trace Seeding with Multi-Sensor Ridge Corroboration | 100m DEM (elevation, slope, curvature), 3DEP 25m DEM, magnetic tilt (`tc`), gravity horizontal gradient | **High Defensibility** | Low-Medium | **Implemented, validated, emitted 440 dots. Holdout DTI: 0.000200, Canary AUC: 0.4997 (ok).** |
| **2** | **H62-S** | Active Quaternary Structural Relays & Strike-Slip Stepover Linking in Lahontan Basins | Detrended DEM (`det_elev`), 10m channel steepness ($\chi, k_{sn}$), horizontal gravity gradients (`iso_grav_anom_hg`), catalogue fault tips | **High Recall** | Medium | Specified; tested on synthetic relays. |
| **3** | **H62-U** | Basement Reactivation via High-Pass Magnetic Anomaly Residual & Topographic Scarp Colinearity | Reduced-to-pole magnetics (`rtp`), upward-continued magnetics (`rtp_up150`), DEM slope & curvature | **Medium** | Medium | Specified; candidate for multi-band fusion. |
| **4** | **H62-T** | Geothermal Blind-Fault Hydrothermal Alteration & Thermal Discharge Corridors (DOE GDR + Radiometrics) | DOE Geothermal Data Repository wells/springs (GDR OpenEI), airborne radiometrics (`rad_K`, `radext_ThK`, `radext_UK`), ASTER thermal | **Medium** | High (requires external GDR fetch) | External dataset identified (<https://gdr.openei.org/>, public domain). |

---

## Detailed Hypothesis Specifications

### Rank 1: H62-R — Pluvial Shoreline Datum-Step & Deflection Trace Seeding with Multi-Sensor Ridge Corroboration

- **Specific Layers Involved:**
  - 100 m USGS 3DEP / GeoDAWN DEM (`data/geodawn_dem_a2_100m.tif`)
  - 25 m 3DEP transport mosaic (`evidence/dem/lahontan_dem_utm11.tif`)
  - Magnetic tilt derivative (`tc`) and isostatic gravity horizontal gradient (`iso_grav_anom_hg`)
  - Official catalogue exclusion mask (`data/labels.tif`).
- **Physical Signature Targeted:**
  - Detection of wave-planed shoreline terraces within the deformed late-Pleistocene Lahontan highstand elevation band ($1313.5 - 1345.8\text{ m}$).
  - Fitting a robust 2-D polynomial smooth isobase ($N=3$) plus local strand plane ($R=15\text{ km}$) to remove post-pluvial isostatic rebound dome ($\sim 22\text{ m}$ deflection across the basin) and regional northward tilt.
  - Identification of statistically significant vertical offsets ($|jump| \ge z_{\text{min}} \sqrt{2} \sigma_{\text{pairs}} \approx 10.55\text{ m}$) and sharp lateral azimuth kinks ($> 30^\circ$).
  - Bilateral trace extension guided by terrain structure-tensor eigenvectors while lineament coherence $\ge 0.15$ and relief $\ge 4\text{ m}$.
  - Kernel-matched dot emission at $300\text{ m}$ spacing with $200\text{ m}$ catalogue exclusion.
- **Why It Catches Missing Faults:**
  - The USGS Quaternary fault database predominantly features bedrock range-front escarpments. Active faults cutting unconsolidated basin sediments lack bedrock topography and were historically overlooked (Briggs & Wesnousky 2004; Dong et al., Geosphere; Pierce & Wesnousky 2016).
  - Because the Lake Lahontan highstand was formed synchronously at $\sim 13-15\text{ ka}$, any persistent shoreline step or lateral offset directly documents active post-15 ka fault rupture.
- **How It Differs From Anything in Repo:**
  - Unlike earlier sessions that either emitted ultra-conservative 99 dots (missing valid traces) or abandoned the datum lane to run generic derivative votes (120k dots), H62-R stays strictly inside the assigned lane, implements the full significance-gated clustering, produces the first deliverable (elevation-distance profiles with 11 steps and 13 deflections), and emits 440 kernel-spaced dots with zero catalogue overlap.
- **Validation Outcome:**
  - Standard GeoTIFF generated: `docs/downloads/gems62-datum-lahontan-strain-gauge-defensible-440dots-zeros.tif`.
  - Format validation: 14/14 checks passed, 0 NaNs inside/outside, all-finite float32 in $[0, 1]$.
  - Uniqueness: $|\rho| = 0.0016 \ll 0.90$, non-vacuous overlap $0.4000 \ll 0.70$ vs 21 registry rasters.
  - Holdout DTI: $0.000200$, CI95: $[0.000170, 0.000231]$, Canary AUC: $0.4997$ (verdict: ok).

---

### Rank 2: H62-S — Active Quaternary Structural Relays & Strike-Slip Stepover Linking

- **Specific Layers Involved:**
  - Detrended elevation (`det_elev`), 10 m channel steepness ($\chi, k_{sn}$), horizontal gravity gradients (`iso_grav_anom_hg`), mapped catalogue endpoints (`trace_segments_utm11.csv`).
- **Physical Signature Targeted:**
  - Dilatational fault stepovers and relay ramps between en-echelon fault segments. Extensional stepovers generate localized subsidence, sag ponds, and knickpoint perturbations in alluvial channels.
- **Why It Catches Missing Faults:**
  - Existing catalogues map major fault segments but consistently omit the soft-linked transfer zones and connecting relays between them.
- **How It Differs From Anything in Repo:**
  - Rather than treating fault tips as endpoints to dilate uniformly, H62-S projects strike vectors into the gap between segment tips and scores the relay zone by channel steepness anomalies and localized gravity gradient discontinuities.

---

### Rank 3: H62-U — Basement Fault Reactivation via High-Pass Magnetic Anomaly Residual

- **Specific Layers Involved:**
  - Reduced-to-pole total magnetic intensity (`rtp`), upward-continued magnetics at 150 m (`rtp_up150`), terrain slope, detrended elevation.
- **Physical Signature Targeted:**
  - Upward continuation isolates deep regional magnetic sources. The high-pass residual $rtp_{\text{residual}} = rtp - rtp_{\text{up150}}$ isolates shallow basement contrasts. Colinearity between shallow magnetic gradients and subtle Quaternary surface scarps identifies reactivated basement faults.
- **Why It Catches Missing Faults:**
  - Subtle scarps in basin alluvium are frequently dismissed as erosional stream banks; demonstration of deep basement magnetic continuity confirms their tectonic origin.
- **How It Differs From Anything in Repo:**
  - Uses explicit spectral filtering (upward continuation subtraction) rather than generic multi-scale spatial filters.

---

### Rank 4: H62-T — Geothermal Blind-Fault Hydrothermal Alteration & Thermal Discharge Corridors

- **Specific Layers Involved:**
  - DOE Geothermal Data Repository (GDR) wells and springs inventory (<https://gdr.openei.org/>, public domain, open query API).
  - GeoDAWN airborne radiometric potassium (`rad_K`), thorium-uranium ratios (`radext_ThK`, `radext_UK`), and thermal infrared imagery.
- **Physical Signature Targeted:**
  - Permeable geothermal conduits produce potassium metasomatism (hydrothermal adularia/illite alteration) and thermal spring discharge along structural corridors.
- **Why It Catches Missing Faults:**
  - "Blind" geothermal systems lack surface topographic scarps entirely. Topographic mapping misses them 100% of the time.
- **How It Differs From Anything in Repo:**
  - Introduces direct geothermal hydrothermal feature conditioning rather than purely structural or topographic evidence.
- **External Data Source & Obtainability:**
  - Source: DOE Geothermal Data Repository (<https://gdr.openei.org/>, public domain). Obtainable via GitHub Actions runner workflow (similar to `.github/workflows/dem-fetch.yml`).
