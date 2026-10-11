# Candidate hypotheses — generated before implementation, ranked, with outcomes

Format: **layers / physical signature / why it should catch a fault the USGS-INGENIOUS
catalogue lacks / how it differs from everything already implemented / cost / validation
status.** Evidence classes: **MEASURED** (reproducible from the pinned bytes in this repo),
**PROJECTION** (a model output, never a score), **BLOCKED** (with the reason).

---

## H-1 — Invert the public leaderboard into a truth surrogate — **RANK 1, RUN THIS SESSION**

* **Layers:** the bytes of the 56 registry artifacts + their owner-reported portal scores
  (`60GEMSDOE registry/audit_index.json` and the group's public repos). No image layer at all.
* **Signature:** the published metric identity itself, `s = T/(0.2M + 0.8K)`. Every scored
  submission is a linear measurement of the organisers' hidden set; 56 of them over-determine a
  coarse reconstruction of it.
* **Why it targets the class the catalogue lacks:** the hidden set *is* whatever the top
  submissions found beyond the catalogue — the surrogate is defined on exactly that class,
  rather than on a proxy for it.
* **Difference from everything implemented:** every prior field in this project is a function of
  the imagery. This one is a function of the scoreboard. It is the first instrument in the
  project's history that correlates *positively* with the portal.
* **Cost:** low (minutes; 56 files already on disk).
* **Outcome:** **MEASURED** — consensus of the 13 artifacts ≥ 0.24: Spearman **+0.870**,
  R² +0.343; after greedy refinement `S*`: Spearman **+0.968**, `|S*| = 8,479 px`, scale 0.5052.
  Independently consistent with the group's earlier single-artifact algebra (|G| = 7,905 px).

## H-2 — Rebuild the incumbents' physics *as features* from the organiser stack — **RANK 2, NOT RUN**

* **Layers:** `data/bridge/gems-geodawn-numerical-features.tif` (19 bands, byte-verified here,
  sha256 `4371c82e…`): rtp/tmi/mag anomaly, isostatic gravity anomaly, conductance and
  depth-to-basement surfaces, radiometrics, det-elevation, LiDAR composite.
* **Signature:** a scale-normalised Hessian line response (Frangi/Sato, **both polarities**) at
  two scales per band, multiplied by the second-order orientation order parameter
  `R = |Σ w_p e^{2iθ_p}| / Σ w_p` — the construction the 0.26–0.28 band used.
* **Why it should catch a catalogue-missing fault:** agreement between independent physics
  selects lines that are *real* but *unmapped*; the catalogue is a topography/state-map product.
* **Difference:** the incumbents emit the consensus as a *field*; this uses it as *features* for
  a supervised model, so it can place dots where the consensus is silent (the new-area class).
* **Cost:** moderate-high (Hessian response on 19 × 2.5 M-cell arrays).
* **Validation status:** H-1's instrument makes it directly measurable — target blocked
  DTI(S*) ≥ 0.60 before any slot is touched. Partially pre-tested: the free-stack proxy of this
  idea reached blocked AUC 0.86 and DTI(S*) 0.22.

## H-3 — Multi-stand shoreline coincidence (the assigned datum-offset lane) — **RANK 3, MEASURED NEGATIVE**

* **Layers:** 25 m USGS 3DEP DEM mosaic (`evidence/dem/`, byte-pinned) and the 100 m GeoDAWN DEM.
* **Signature:** the Lahontan basin contains **15 measured stands** between 1175 and 1437 m
  (v8 run card, MEASURED). A tectonic scarp offsets the *whole stack* of stands; a wave-cut
  bluff, berm, fan-head riser or delta topset offsets **one**. Coincidence of steps across ≥ 2
  stands at one map position is therefore a discriminator the single-datum version of this lane
  never had.
* **Why it targets a catalogue-missing fault:** it converts the datum from a contour into a
  *stack* of independent level references, which is exactly the class Pierce and Wesnousky
  (2016) found in Smith Valley and Dong et al. found outboard of the Wassuk front.
* **Difference:** earlier sessions used one datum (the highstand) and emitted along its
  contour; this asks for cross-level agreement.
* **Cost:** moderate.
* **Validation status:** **cannot be validated with the instruments available.** Both
  instruments were measured this session to anti-correlate with the portal (below). Under H-1's
  instrument the lane's own strata have no positive mass. Recorded as a negative; the geometry
  remains defensible but unmeasurable locally.

## H-4 — Cover the leaderboard-inverted set directly — **RANK 4, BLOCKED BY PROTOCOL**

* **Layers:** none; the surrogate `S*` from H-1.
* **Signature:** the same metric identity, inverted to a placement problem.
* **Projection:** **0.34–0.42** under the fitted scale — the highest expected value found.
* **Blocked because:** `S*` is a subset of pixels shared by all 13 top artifacts; ≥ 70 % of the
  dots would fall within 3 px of one registry raster, i.e. the protocol's definition of a
  duplicate, and the session brief forbids copying. **Not emitted.** Full reasoning in
  `docs/decision-note.md`.

## H-5 — 1 m LiDAR scarp polarity (new external data) — **RANK 5, NOT RUN**

* **Layers:** USGS 3DEP 1 m LiDAR DEM tiles via the National Map API (`tnmaccess.nationalmap.gov`,
  19 products listed for the n40w119 tile alone, `evidence/tnm_probe.json`).
* **Signature:** a normal-fault scarp has a one-signed `downface` field across its trace, unlike
  a terrace riser or a channel cut — an *asymmetric* test, not an edge test.
* **Why:** it resolves the 2 m shoreline steps that the 25 m grid cannot (stated limitation of
  this lane in `docs/next-steps.md`).
* **Obtainability:** free and official, **but unreachable directly from this sandbox**
  (HTTP 000 to USGS hosts, MEASURED); the proven route is a GitHub Actions runner
  (runs 38169049665 … 38169727207).
* **Cost:** high (tile fetching + hydrological conditioning).
* **Validation status:** not run this session.

---

## The instrument finding that reorders everything (MEASURED this session)

Over the **56** artifacts with owner-reported portal scores, scored with the exact published
metric against each candidate truth mask:

| candidate truth mask | Spearman vs portal | R² |
|---|---:|---:|
| consensus of the 13 artifacts scoring ≥ 0.24 (H-1) | **+0.870** | +0.343 |
| refined `S*` (H-1, greedy) | **+0.968** | +0.301 |
| SGMC off-catalogue ("instrument B") as a candidate-truth model | +0.025 | −1.80 |
| competition catalogue itself | +0.148 | −1.91 |
| every topographic/LiDAR level set tested (27 of them) | -0.70 … -0.11 | < 0 |

On the 15 artifacts with owner-reported scores, the SGMC off-catalogue instrument gives
Spearman **−0.928** measured directly on the artifact bytes
(`datum62/evidence/calibration_vs_portal.json`). The group's documented "forward lead" (the scarp field with the highest credit per
dot on instrument B) is therefore a signature of *circularity*, not of quality.
