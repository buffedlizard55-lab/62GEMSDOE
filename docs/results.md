# Results — 2026-10-12 session (H62-B)

Every number below is `MEASURED` in this checkout (the script that produced it is named),
`OWNER-REPORTED` (a score the owner quoted; there is no organizer receipt for any file in this
repository), `OFFICIAL` (quoted from the competition pages) or `MODEL` (algebra on the published
metric). A `MODEL` number is never written as a score.

---

## 1. The question the brief asked: why did `h33-2-b2` score 0.2778?

Three separate things, and only the third is a property of the geology.

**(a) The metric is recall-dominated and the marginal bar is low.**
`DTI = TP_w / (TP_w + 0.2·FP_w + 0.8·FN_w)` with `k(d) = max(1 − d/300 m, 0)`
[OFFICIAL, page 967]. Adding one unit dot that realises kernel weight `k` raises the numerator by
`k` and the denominator by exactly `0.2`, so a dot pays for itself whenever `k > 0.2·DTI`. At 0.2778
that bar is **0.0556** — any dot with better than a 5.6 % chance of landing within 300 m of a hidden
new fault raises the score [MODEL].

**(b) Half the variance of the group's scores is structure, not geology.**
Regressing the owner-reported scores of the 87 distinct registry rasters on ten *structural*
measurements — no geology at all — gives leave-one-out **R² = 0.586**, Spearman 0.781
[MEASURED, `research/registry_measurements.json`]. The signs are exactly what the algebra predicts:

| property | Spearman vs score |
|---|---|
| number of dots `M` | −0.52 |
| mean self-kernel (dot-to-dot redundancy) | −0.55 |
| largest connected-component fraction | −0.56 |
| fraction of dots sitting on the catalogue | −0.49 |
| 90th percentile of distance-to-catalogue | +0.46 |

So: isolated single pixels, off the catalogue, spread over the whole grid, and *not too many of
them*. The top nine distinct score levels all have mean self-kernel 0.016–0.018; every raster with
self-kernel ≥ 0.23 scores ≤ 0.2477.

**(c) Within that structure, placement still matters — by about 1.1× for the champion.**
Against an independent truth set (below), the champion's dots earn **0.1324** credit per dot when a
hard-core random field of the same mass earns **0.1190**: an 11 % edge. That edge is what this
session set out to widen.

## 2. Building an instrument that is actually calibrated

The holdout the protocol prescribes was measured to be **anti-correlated** with the organizer's
score (IR-62-HOLDOUT-01: Spearman −0.91 over 10 confirmed artifacts). This session found the
mechanism and fixed it.

**IR-62-HOLDOUT-02 — the catalogue holdout is unsatisfiable by arithmetic, not by lack of skill.**
The kernel reaches 300 m. Every competitive emission deletes every dot within 300 m of the mapped
catalogue, because the organizer does not score mapped faults and the group has an
organizer-confirmed +0.0178 for deleting them (`h33`: 0 % within 200 m; this session's file: 0 %
within 300 m, minimum 400 m). A dot set with no dot within 300 m of *any* catalogue pixel therefore
has `TP_w = 0` against withheld *catalogue* pixels necessarily. Measured: **pooled DTI = 0.000000**
for this session's artifact. The better an artifact is at being off-catalogue, the more certainly it
scores zero. Fixed once, in the template: `gems62.holdout.evaluate` now takes a `truth` argument so
the withheld population can be an independent fault set.

**The instrument that is validated.** Truth = the USGS State Geologic Map Compilation (1:750 k)
rasterised on the competition grid, **minus** the competition catalogue (79,615 px; only 4.8 % of it
falls on catalogue pixels, so it is not a re-digitisation of the same lines). Scoring domain =
footprint minus catalogue ± 3 px. Quantity = **mean 300 m kernel credit per dot**, i.e. `TP_w / M`.

Validation, `scripts/instrument_calibration.py` → `evidence/exp1_instrument_calibration.json`:

| form of the instrument | Spearman vs owner-reported score | verdict |
|---|---|---|
| **mean credit per dot** vs SGMC-minus-catalogue | **+0.742** (p = 0.0037, n = 13) | **validated** |
| same, restricted to the nine isolated-dot artifacts | monotone in 8 of 9 | validated |
| pooled DTI vs SGMC-minus-catalogue | **−0.851** (p = 0.0002) | **refuted** |
| pooled DTI vs the catalogue (the old holdout) | −0.85 … −0.91 | refuted (IR-62-HOLDOUT-01) |

The DTI form fails because its denominator is dominated by the SGMC truth mass (79,615 px), so it
mostly re-measures `M`, and `M` anti-correlates with the score. The **per-dot credit** is the usable
form. Bars, all MEASURED on the same truth and the same mass as the artifact: hard-core Poisson control **0.1190** (an independent 40,000-dot draw in Experiment 2 gave 0.1197, so the bar is stable to ~0.6 %); uniform random control **0.1075**; champion `h33` **0.1324**; this
lane's previous artifact H62-A **0.1347**.

## 3. What the instrument says about where off-catalogue faults are

120,000 random dots were drawn over the footprint and each dot's kernel credit binned against nine
surfaces (`scripts/screen_h62b.py`, the diagnostic in `evidence/exp2_h62b_screen.json`):

| surface | credit in the flattest / lowest decile | in the steepest / highest decile | gradient |
|---|---|---|---|
| height above base level | 0.0058 | 0.2699 | **47×** |
| slope | 0.0024 | 0.2756 | 115× |
| local relief (900 m) | 0.0022 | 0.2930 | 133× |
| elevation | 0.0045 | 0.2848 | 63× |
| depth to basement (thinnest → thickest cover) | 0.2650 | 0.0445 | **inverted, 6×** |
| lineament coherence | 0.1485 (low) | 0.0217 (high) | **inverted, 7×** |

Two readings, and both are stated because they cannot be separated here. Either off-catalogue faults
really do live on steep, high, thin-cover ground and not on the pluvial lake plains — or the SGMC
compilation is a **bedrock** map that simply does not map basin-floor faults, and the instrument is
blind to the population this lane exists to find. The four-times-repeated measurement that the
pluvial band is *below chance* (previous sessions: 0.03× and 0.61×; this session, with a completely
different band construction and a different base-level estimator: 0.026× on the band and **0.26×**
for its own habitat null) is consistent with both.

This is the honest limit of the whole exercise, and it is why the lane's verdicts have been negative:
**the lane's target population is exactly the population no local truth set contains.**

## 4. Experiment 2 — screening the five hypotheses (`scripts/screen_h62b.py`)

Each evidence surface hard-core thinned to 40,000 dots, ≥ 300 m off the catalogue, credit measured
against the instrument. Bars: hard-core control 0.1190, champion 0.1324.

| surface | credit | vs control |
|---|---|---|
| `S11` hard-core (300 m) random over the whole footprint — the null | 0.1197 | 1.00× |
| `S12` fixed elevation window 1308–1360 m | 0.1155 | 0.96× |
| `S10` **uniform inside the pluvial band (strong null)** | 0.0314 | **0.26×** |
| `S8` geophysical corroboration only, inside the band | 0.0314 | 0.26× |
| `S1` datum step, robust z-score | 0.0313 | 0.26× |
| `S5` Frangi ridgeness of the datum residual | 0.0311 | 0.26× |
| `S6` step × ridge coherence | 0.0303 | 0.25× |
| `S7` step × ridge × geophysics (H62-Q) | 0.0301 | 0.25× |

Every band-restricted hypothesis, including its own habitat null, sits at ~0.26× chance, and the
geophysical corroborator adds nothing inside the band (0.0314, identical to the null). **H62-M as a
*habitat* is refuted a fourth time; H62-Q as an in-band corroborator is refuted.** What survived is
the part of the lane that is not a habitat: the *trace*, which may leave the band wherever the
DEM-ridge evidence carries it.

## 5. Experiment 3 — the artifact (`scripts/run_h62b.py`, `scripts/finalize_h62b.py`)

34,620 seeds → 25,057 traces (1.30 M trace pixels) → 40,964 hard-core candidates. Walking down the
ranked list and measuring credit at each prefix:

| dots | credit/dot | coverage of SGMC off-cat | MODEL projection |
|---|---|---|---|
| 8,000 | 0.2037 | 0.027 | 0.145 |
| 12,000 | 0.2158 | 0.044 | 0.213 |
| 16,000 | 0.2190 | 0.059 | 0.267 |
| 20,000 | 0.2105 | 0.071 | 0.300 |
| 25,000 | 0.1952 | 0.082 | 0.321 |
| 30,000 | 0.1882 | 0.095 | 0.344 |
| **37,654** | **0.1683** | **0.107** | **0.348** |
| 40,964 (all) | 0.1582 | 0.109 | 0.342 |

The mean credit is *non-monotone* in the first few thousand dots (it rises from 0.2037 to 0.2190
before falling), which is a real property of the ranking rather than a transcription error: the
top-ranked candidates are the traces with the largest single cross-strike relief, and those are not
the traces that pass through the most fault-rich ground. It costs nothing — the projection is
maximised at 37,654 either way.

37,654 is chosen: the projection peaks there, and it is also the mass of the group's
organizer-confirmed best.

The projection is **stable across the entire plausible truth-mass range** (0.353 at N = 6,000,
10,000 and 13,704) because the champion's implied credit and the denominator both scale with N —
which is why it is reported as a ratio to the champion rather than an absolute. A second, simpler
projection used in the mass sweep gives 0.3484 at the shipped mass; the 0.005 spread between the two
is [IR-62-PROJ-01](irregularities.html#IR-62-PROJ-01) and is 24× smaller than the ±0.12 residual of
the calibration regression that shrinks them both.

## 6. Calibrating the projection against reality

Applying the identical projection to the 12 other registry artifacts whose scores are known, and
regressing actual on projected: **slope 0.325, intercept 0.175, r = 0.826, p = 0.0005**
(through-origin slope 1.076). So the projection is a real predictor but heavily compressed, and the
shrunk expectation for this file is

    0.175 + 0.325 × 0.353 = 0.290

Residuals are large (±0.12). The worst case is `p49`: credit 0.1759 (1.33× the champion, *higher*
than this file's 1.27×), projection 0.359, **actual 0.2376** — an over-prediction of 0.121. The
eight isolated-dot artifacts other than `p49` are all *under*-predicted, by 0.004 to 0.074.

## 7. Holdout (reported, never used to promote or reject)

| holdout | this file | champion `h33` | hard-core control |
|---|---|---|---|
| B — withheld segments of an independent fault set (SGMC−catalogue) | 0.0728 | 0.0741 | 0.0496 |
| A — withheld catalogue segments (the protocol's literal form) | 0.000000 | — | — |

Label: **HOLDOUT-DTI** (`gems62.holdout.v2`, 4 spatial quadrants, whole segments withheld, 300 m
buffer). The file beats chance by 1.47× on the satisfiable form and is on par with the champion.

## 8. Where that puts it

Public leaderboard mirrored 2026-10-11 (50 rows): #1 **0.4133**, top-5 cut-off **0.3300**,
0.3195 is **rank 8**, the group's 0.2778 is **rank 23**. A shrunk expectation of 0.290 would move
the group's best by roughly +0.012 and would not, by itself, reach the top five. The un-shrunk
0.353 would be rank 2–3. Both are `MODEL`.
