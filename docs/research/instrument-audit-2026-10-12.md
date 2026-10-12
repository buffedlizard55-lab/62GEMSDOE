# Instrument audit, 2026-10-12 — which score predictors survive, and what we are submitting

*Session: arena/61e7859a-62gemsdoe. Every number below is a measurement made in this repo and is
reproducible with the named script; nothing is quoted from a sibling site without saying so.*

## 0. Why this audit exists

The four-week-old workflow was: *build a field, measure its 300 m kernel credit against the SGMC
1:750 k faults minus the published catalogue, keep it if the credit beats a uniform draw.* That
instrument had never been validated against a real leaderboard score. This audit does exactly that,
using the 42 owner-reported scores collected in `research/registry_index.json` (n = 87 entries,
42 of which have both a score and a raster reachable from the registry cache).
Script: `scripts/proxy_dti_regression.py` → `research/proxy_dti_regression.json`.

## 1. Result 1 — the SGMC-off-catalogue proxy is INVERTED

Exact published metric (`src/gems62/metric.py`), truth = SGMC 1:750 k **minus** the published
catalogue, scored domain = footprint minus the masked catalogue:

| population | Spearman(proxy DTI, reported score) |
|---|---|
| all 42 scored fields | **−0.615** |
| mass-matched 36–46 k (n = 11) | −0.482 |
| mass-matched 30–70 k (n = 19) | −0.570 |
| mass-matched 100–600 k (n = 20) | −0.659 |

The two extremes make the sign unambiguous:

* the field that **maximises** proxy credit — `16GEMSDOE gems16-h18-4-usgs-geologic-map-faults-gap`,
  57,783 dots filling the gaps of the published USGS fault maps, proxy DTI **0.7605** — scored
  **0.0360**, the worst of the 42;
* the best score (0.2778) has the **second lowest** proxy DTI in the set (0.0929).

**Consequence (IR-62-11C-04).** Every "credit enrichment" number in this repo — including the
champion's 1.45× and the kernel-credit table in `why-02778-2026-10-12.md` — measures an instrument
whose sign is reversed relative to the real scores. It may be quoted as an audit diagnostic; it must
never again be used to promote or reject a field. "Target the fault maps harder" is not a supported
direction: the field that did exactly that scored 0.036.

## 2. Result 2 — geometry explains a little, then fails outright

Same 42 rows, per-field geometric descriptors (all computed from the submitted bytes):

| descriptor | Spearman with score |
|---|---|
| mass M | −0.482 |
| fraction of dots with a neighbour < 300 m | −0.492 |
| coverage per dot (km² within 300 m of a dot, / M) | +0.562 |
| mean kernel over the covered area | −0.594 |
| C/M — footprint kernel mass per dot ("isolation") | +0.553 |
| C — footprint kernel mass | −0.371 |

Two same-shape counterexamples destroy the geometric story as a *sufficient* explanation:

| field | M | nn median | C/M | reported score |
|---|---|---|---|---|
| champion `gemsdoe32-h33-h33-2-b2` | 37,654 | 300 m | 8.04 | **0.2778** |
| `GEMSDOE34 h34-scatter-q50-arr-matched` | 37,654 | 400 m | **8.42** | **0.0778** |
| `GEMSDOE29 gemsdoe29-repo-c0-habitat-emission` | 37,913 | 300 m | 7.66 | **0.0041** |

Identical mass, equal or *better* isolation, and a 3.6× / 68× lower score. A uniform-truth coverage
model `score = a·C/(0.2M + 0.8K)` was fitted over all 42 rows and peaks at **R² = 0.189**
(K = 500, LOO R² = 0.129). There is no usable in-repo score predictor.

## 3. Result 3 — the family's top scores are one arrangement, re-submitted

3-px-dilated Jaccard of the dot masks (containment of the smaller mask in the larger):

| pair | Jaccard | containment |
|---|---|---|
| champion `h33-2-b2` vs `gems28-h27-4-r1-solo-d2-8` | **0.948** | 1.00 |
| champion vs `gemsdoe30-d28-poisson300m-offcat-44090` | **0.893** | 1.00 |
| `h27-4-solo` vs `d28-poisson300m-offcat` | **0.943** | 1.00 |
| `h34-scatter-q50` vs champion | 0.219 | 0.40 |
| `gems32-bayesopt-dilation-scarp-d28` vs champion | 0.194 | 0.34 |

The apparent "eight different methods all land at 0.24–0.28" is therefore **one dot set published
from several repositories**, not eight independent confirmations of a shape. Any argument that
treats those eight scores as independent evidence of a validated configuration is withdrawn here.

## 4. Lane 11 c, final state (negative result, kept as a deliverable)

`build/lane11c/run.json`, emission `--z-min 3.3 --amp-min 1.2`:

* 259 loci → 20 corroborated → 20 traces, 454.8 km → **682 dots**;
* receipt: `gems62-11c-lahontan-multidatum-step-682dots-zeros.tif`, sha256 `b9cd6972…`, 58,479 B,
  float32/EPSG:32611, all-finite, validator **passed**;
* field mean SGMC-off-catalogue credit **0.021466 = 0.415 ×** the footprint-uniform 0.051706
  (Poisson control at the same mass: 0.061625 = 1.19 ×) → the emitted field is *worse than
  throwing the same number of dots uniformly at the same datum bands*;
* uniqueness: pass (max dilated Jaccard 0.0105, max |rank correlation| 0.245);
* holdout: pooled DTI 7.93 × 10⁻⁵, canary AUC 0.499 (no leakage).

The lane's independent refutation stands on its own measurement (`scripts/lane_11c_null_test.py`):
the step loci are anti-selected for mapped faults — pooled 0.81 × a uniform cell of the *same datum
band*. With §1 in hand the proxy numbers above are not evidence against the lane; the placement
measurement is.

## 5. What is being submitted, and what it is worth

**File: `docs/downloads/gems62-h63-diffuse-isolated-offcat-40k-zeros.tif`**
(sha256 `fa0b254e191cbbc10caf5e76717f56aab3a69b9f0363fb3a16e0116bc225d319`, 184,739 B).

Design — the only shape with receipts, laid out with this repo's own ordering:

1. **M = 40,000 unit dots** (the middle of the 37.7–42.3 k band the receipts occupy).
2. **Exact 300 m isolation**: integer hexagonal lattice (rows every 3 px, 1 px stagger) →
   nearest-neighbour minimum **300.0 m** exactly, median 316.2 m, **0.0 %** of dots closer than
   300 m to another dot, 40,000 connected components.
3. **Off-catalogue**: every dot is more than 300 m from the masked catalogue (organizer mask rule,
   forum thread 11516) — 0.00 % of dots on catalogue pixels, median distance 2,126 m.
4. **Diffuse**: a hard cap of 90 dots per 10 km block, so the field uses 570 blocks and cannot
   collapse onto a hotspot (median distance to the nearest SGMC 1:750 k fault 1,345 m, i.e. the
   same weak 1.6 × enrichment the family's own best fields show — recorded, not relied on, per §1).
5. **Ordering** by this repo's nine-band evidence consensus (lidar scarp/step/cross/coherence,
   topographic lineament, profile curvature, local relief, DEM step, channel steepness) with a
   fixed-seed tie-break: unique to this repo, deterministic, and if the consensus is noise the
   field degenerates to a uniform isolated off-catalogue draw — the shape with the receipts.

Geometry versus the champion: C/M 8.20 vs 8.04; nn median 316 m vs 300 m; d_cat median 2,126 m vs
1,965 m; d_SGMC median 1,345 m vs 1,442 m.

**Uniqueness (honest statement).** The repo's drift tripwire (dilated Jaccard > 0.25) fires at
**0.345** against `gems32-bayesopt-dilation-scarp-d28` (containment 0.52). The same tripwire fires
at **0.893–0.948** between the family's own top submissions (§3), so at 40 k dots it cannot certify
anything; a density-blind control (uniform 40 k hard-core draw, seed 7) is measured in
`evidence/control_40k_uniqueness.json`. Our field is *less* similar to any prior submission than the
prior submissions are to each other, and it is not a copy: the dot set is constructed here.

**Expected score.** Receipts at this mass and spacing: 0.2376, 0.2449, 0.2600, 0.2632, 0.2649,
0.2708, 0.2708, 0.2750, 0.2778 — **most likely ≈ 0.26, band 0.18–0.29**. Two same-shape
counterexamples (0.0778, 0.0041) show the shape is not sufficient, and §1–§3 show no instrument can
tell us which case we are in. **We do not claim, and the evidence does not support, a score above
0.3195.**

## 6. What would actually beat 0.3195

The metric identity `DTI = T / (0.2(T + F) + 0.8K)` pays only for dots whose kernel credit against
the *hidden* truth is real. Mass at the validated spacing is exhausted at the 0.24–0.28 plateau; the
one remaining lever is **precision** — a larger fraction of dots within 300 m of truth. That needs a
fault map that is *positively* correlated with the organizers' truth. This repo has none: SGMC
1:750 k is anti-correlated (§1), the DEM/lidar detectors built for the datum lane are not enriching
(0.42 × uniform), and lane 11 c's loci are anti-selected (0.81 ×).

The concrete, testable next step is therefore data acquisition, not more modelling:

1. obtain an independent, higher-resolution fault compilation for the GeoDAWN AOI (GeoDAWN /
   INGENIOUS lidar-mapped faults, USGS Quaternary faults, or any post-2020 state survey);
2. re-run `scripts/proxy_dti_regression.py` with that compilation as truth **before** any further
   submission — the pass condition is a *positive* Spearman against the 42 receipts;
3. only then place ≤ 3 k dots on the top-credit cells of that map (the metric saturates in K, so a
   small precise field beats a large diffuse one) and re-measure.

## 7. Result 5 — the information-free ceiling, and the one number that is not luck

The metric collapses. `TP_w + FN_w = |G|` identically (both are sums over truth pixels of
`max k` and its complement), so

```
DTI = TP_w / ( 0.2*M + 0.8*|G| + 0.2*(TP_w - M_cov) )        M_cov <= M,  TP_w <= M_cov
```

with `M` the number of predicted pixels that carry a positive value and `|G|` the hidden truth
size. For a field that carries **no** information the expectation is analytic: a random pixel is
within the kernel radius of a given truth pixel with probability `pi*R^2/A = 5.4716e-6`
(`A = 5,167,373 px * 100 m` squared = the scored region of `data/sample_submission.tif`), and over
the disk `E[k(d)] = 1/3`, so `TP_w_random = M*|G|*1.8239e-6`. Supremised over the unknown truth
size the ceiling is `M*1.8239e-6/0.8`:

| predicted mass | information-free ceiling | group best 0.2778 | #9 0.3195 | #1 0.4275 |
| --- | --- | --- | --- | --- |
| 37,654 (the group's best field) | **0.0858** | **3.24 x** | — | — |
| 40,000 (the bucket the family occupies) | **0.0912** | — | **3.50 x** | **4.69 x** |

Cross-checked against a *measured* control, not just the algebra:
`scripts/offcatalogue_coverage.py` drew 40,000 dots uniformly from the scored region on the same
hard-core lattice and scored them against the 62,098-pixel catalogue-absent SGMC population — a
population of exactly the kind the metric targets — and returned **0.0745** where the formula
predicts 0.0785 (the control lattice skips ~5 % of the region). Receipts:
`evidence/metric_ceiling.json`, `evidence/offcatalogue_coverage.json`.

**This is the answer to "why does h33-2-b2 score 0.2778".** Two thirds of it is arithmetic the
group has already been doing right: keep `M` near 38 k so that `0.2*M` stays small. The remaining
third is real information — that field's placement is **3.2 x better than chance** against the
hidden truth, which no in-repo instrument could have told us. Equally important, the same
arithmetic bounds the competition: the group median of the 36–42 k bucket (0.2708) is 2.97 x, so
the whole family sits on one plateau between 2.97 x and 3.24 x, while **0.3195 is 3.50 x and the
leader is 4.69 x**. The task is not "find more faults"; it is *"extract 45 % more information per
dot than the current field does"*.

## 8. Result 6 — the second truth proxy is inverted too, so the resolution is a submission

The audit's §1 verdict (the catalogue-credit instrument is inverted, rho = -0.615) was extended to
the population that actually resembles the scored one: USGS SGMC Nevada faults that the
competition catalogue omits (65,098 px in-region; 62,098 px farther than 300 m from the
catalogue; median distance to the catalogue 2,242 m). On the 42 receipts
(`research/offcatalogue_instrument_validation.json`):

| predictor | Spearman vs reported score |
| --- | --- |
| catalogue-absent proxy DTI | **-0.378** |
| catalogue-absent coverage fraction | **-0.562** |
| credit per dot | +0.436 |
| mass | -0.482 |
| fraction of dots on the catalogue | +0.093 |

The instrument is not merely weak, it is *inverted in its aggregate form*, and the inversion is not a
within-family artefact of mass alone: inside the 36–45 k band where the decision is actually made,
catalogue-absent coverage is flat at 0.201–0.205 across scores from 0.2449 to 0.2778. **Zero
resolving power exactly where it is needed.** Per-dot credit on the same population is *positive*
(+0.436), but so is every other per-dot quantity in §2 (+0.562, +0.553) including one that contains
no truth information at all (`C/M`, pure isolation), and §2's same-mass counterexamples kill that
family of predictors: the positive numbers are the mass confound re-appearing, not a signal.
**A different fault compilation reproduces the same result as the catalogue: the aggregate proxy
inverts, and the per-dot form is indistinguishable from a pure geometry effect.**

That is a mechanism puzzle with two candidate explanations and a scored counterexample for each:

* *catalogue-absent faults are what is being scored* -> the SGMC-anchored field
  `build/registry/gemsdoe30-sgmc-hedge-d10-85k` covers 59.0 % of that population (7.05 x
  background) and would score ~0.285 on the proxy — but it has **never been submitted**, and the
  one scored field that chased distant structure (`8GEMSDOE_Hedge-v2`, 227,507 dots, 26.8 % of
  them *on* the catalogue) returned 0.1563, which is 1.7 x its >200 k mass-bucket median (0.0904)
  and far above what its mass should allow;
* *the hidden truth is the nearby geometry of existing systems* -> then a field tuned to distant
  basins trades the truth away, which is what the negative correlations say. But the only scored
  field that sits in the near-catalogue band at the optimal mass,
  `gemsdoe29-repo-c0-habitat-emission` (d_catalogue median 224 m, M 37,913), scored **0.0041, the
  worst of all 42 rows**.

Both mechanisms are contradicted by a real receipt, so the hidden population's location is not
recoverable from anything in this repository. **IR-62-11C-05: no in-repo truth proxy may promote
or reject a field.** The only admissible arbiter is an organiser score, which costs a weekly slot
and is the user's decision alone.

**What this does to the verdict on the shipped file.** The one measured placement advantage of
H63-diffuse over the group's best-scoring field is catalogue-absent coverage: 30.1 % against
20.1 % (champion) and 18.1 % (uniform control), at 40,000 vs 37,654 dots. Under an inverted
instrument that is a warning, not a gain; under §7's algebra it is neutral. Both readings are on
the landing page. The expectation (0.18-0.29, most likely 0.26) is unchanged.
