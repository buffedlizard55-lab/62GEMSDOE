# Irregularities, defects and traps

Flagged rather than smoothed over, ordered by how much damage each could do. New this session are
marked **[NEW]**; the rest were carried forward from earlier sessions and are still live.

---

<a id="IR-62-POISSON"></a>
## 1. [NEW] The group's "Poisson control" is not a control — it is the same file

`GEMSDOE30` reports `d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca` at **0.2600**, and it is
presented as a random (Poisson-disk) control at the same mass as the detector field. Measured here:
that file and `gems25-dotted-h19-5-d28-zeros` have **Jaccard = 1.00000** — 44,090 positives,
identical pixel for pixel, byte-different only because of compression and nodata encoding. The
"control" is the detector re-shipped under a control-sounding name.

**Consequence.** The claim "a random field scores the same as the detector, so placement does not
matter" is **void**: the two scores are the same score. This session therefore built its own
controls — a Matérn hard-core field (`emit.hard_core_topk` on a uniform random surface) and a
uniform field — and measured them at **0.1190** and **0.1075** (same instrument, same mass, same
truth as the artifact: `evidence/exp1_instrument_calibration.json`, `buffer3px` variant; an
independent draw in Experiment 2 with M = 40,000 over a 59,453-px truth gave 0.1197, so the control
is stable to ~0.6 %). Placement *does* matter, by about 1.11× for
the champion and 1.41× for this session's artifact.

<a id="IR-62-LABELS"></a>
## 2. [NEW] `labels.tif` is byte-identical to `existing_faults.tif`

Both files in `data/` have sha256 `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093`
and the same 60,988 positives. So the "labels" this repository holds are the **catalogue of already
mapped faults**, not a training set of new ones. There is therefore **no local ground truth for the
target population at all** — which is the single biggest structural limit on every number in this
repository, and the mechanical reason the proxy instruments behave the way they do.

<a id="IR-62-HOLDOUT-02"></a>
## 3. [NEW] The prescribed holdout is zero by arithmetic, not by lack of skill — fixed in the template

The kernel is `k(d) = max(1 − d/300 m, 0)`, so a dot earns credit against a withheld truth pixel
only inside 300 m. Every competitive emission deletes every dot within 300 m of the mapped
catalogue. A dot set with no dot within 300 m of *any* catalogue pixel therefore has `TP_w = 0`
against withheld *catalogue* pixels necessarily.

Measured: **pooled DTI = 0.000000** for this session's artifact; its minimum distance from any
candidate dot to the catalogue is 400 m. The champion has 1,611 dots inside 300 m and so earns a
little; the better an artifact is at being off-catalogue, the more certain the zero.

**Fix, made once in the shared template** (`src/gems62/holdout.py`, not a private fork):
`evaluate()` now takes a `truth` argument so the withheld population can be an independent fault
set. Version string is now `gems62.holdout.v2`. With SGMC-minus-catalogue as truth the same
evaluator returns 0.0728 for this artifact, 0.0741 for the champion and 0.0496 for a hard-core
control.

<a id="IR-62-H62B-01"></a>
## 4. [NEW] The flagged step magnitudes are too large to be fault offset

Median flagged step 24.4 m, largest 82.7 m (n = 40 stepped loci;
`evidence/figures_h62b.json`). Post-15 ka offset of a single Lahontan shoreline is metres
to a few tens of metres. These numbers are therefore dominated by (a) error in the base-level
construction where the band crosses dissected terrain and (b) the isostatic-rebound signal the
6 km isobase does not absorb. The *rank* of a flag is a robust z-score and is unaffected; the
*metres* are not interpretable. The seed stage of this lane is consequently its weakest link, and
the artifact's measured skill comes substantially from the ridge-relief extension, which is a
general lineament criterion rather than a datum-specific one. Cure: hypothesis H62-P.

<a id="IR-62-UNIQ-02"></a>
## 5. [NEW] The registry harvest contains rasters that are not on the competition grid — fixed

`gems62.uniqueness.compare` raised `ValueError` on `5GEMSDOE__proxy_window.tif` (512×512) and
aborted the whole sweep, so the lane-drift check silently never completed. Fixed in the template:
non-conforming comparators are skipped and counted (`_EntryList.skipped`). Five were skipped:
four 512×512 proxy windows and one 32×48 format test explicitly named `NOT_SUBMISSION`.

<a id="IR-62-BRIEF-01"></a>
## 6. [NEW] The brief's leaderboard number does not match any public row

The brief states "0.3195 is the highest score right now". In the 50-row public leaderboard mirrored
2026-10-11, 0.3195 is **rank 8**; #1 is 0.4133 and the top-5 cut-off is 0.3300. The discrepancy is
recorded, not resolved: this sandbox cannot reach `drivendata.org`, and no organizer receipt exists
for any file in this repository.

<a id="IR-62-TEST-01"></a>
## 7. [NEW] A bare `pytest` at the repo root aborted with 3 collection errors — fixed

`lane62/` and `lane62-h62a/` are *independent re-derivations* of the same lane and each vendors its
**own** copy of the `gems62` package. A root-level `pytest` collected all three, the copies shadowed
each other, and `tests/test_metric.py` clashed by basename with `lane62/tests/test_metric.py`. The
suite therefore could not be run at all from the root — which means it had not been. Fixed with a
root `pytest.ini` (`testpaths = tests`, `pythonpath = src`, `--import-mode=importlib`) plus a
documented per-lane invocation. **All 114 tests pass**: root 27, `lane62` 46, `lane62-h62a` 41.

<a id="IR-62-PROJ-01"></a>
## 8. [NEW] Two different projection formulas coexist in this repository

`scripts/run_h62b.py` projects the score as `c · κ · M / (0.2M + 0.8N)`;
`scripts/finalize_h62b.py` anchors instead on the champion's own implied truth credit,
`T_ch(N) · (c / c_champion) / (0.2M·0.968 + 0.8N)`. At the shipped mass (M = 37,654, N = 10,000)
they give **0.3484** and **0.3530** — a spread of 0.005. Both are `MODEL`, both are printed, and
both are shrunk by the same calibration regression, whose residual is **±0.12**: the disagreement
between the two formulas is 24× smaller than the uncertainty of either. They also agree on the
*decision* — the mass sweep peaks at M = 30,000–37,654 under both. Not fixed, because fixing it
would mean re-running the sweep, and the choice of mass is not what is in doubt.

<a id="IR-62-UNIQ-01"></a>
## 9. The 70 %-within-3-px lane-drift rule is density-blind (carried forward, and it fires here)

A comparator whose own 3 px halo covers most of the footprint trips the rule for *any* emission.
This session's artifact trips it against two distinct fields —
`GEMSDOE3__coverage-v3-wide` (80.0 %; 624,025 dots; its halo covers 66.3 % of the footprint) and
`GEMSDOE22__h23-b-dti-optimal-emission-10pct` (75.8 %; 516,738 dots; halo 59.7 %). A uniform-random
dot would score 0.663 and 0.597 on the same leg, so the ratio is 1.21× and 1.27× chance. The
never-waived legs say the opposite of copying: worst Spearman ρ over 340 comparators **0.022**
(limit 0.90) and worst exact Jaccard **0.0091** (a diagnostic this repository reports; the protocol has no Jaccard leg). Reported, not suppressed; the
selector decides.

<a id="IR-62-DEM-01"></a>
## 10. The official feature stack has no absolute elevation (carried forward, **closed** this session)

Band 12 is `det_elev` — "topography with regional trends removed". A Lahontan isobase is an absolute
datum. Closed by fetching `geodawn_dem_a2_100m.tif` (owner mirror, sha256 `d32762a3…`) and fitting
the isobase on absolute elevation for the first time. Its provenance is an owner mirror, not an
organizer-authenticated file.

## 11. The catalogued "labels" anti-select novelty (IR-62-HOLDOUT-01, carried forward)

Catalogue-based proxies are measured to be anti-correlated with the organizer's score
(Spearman −0.91 over 10 confirmed artifacts in the previous session; −0.85 here). Section 3 above
gives the mechanism. Consequence, enforced everywhere on this site: the catalogue holdout is a bug
screen and a leakage canary, never a promotion gate.

## 12. Owner-reported scores are claims, not receipts

Every score quoted for a sibling artifact (0.2778, 0.2600, 0.2376, …) is **OWNER-REPORTED**. No
organizer receipt, e-mail or exported leaderboard row exists in this repository. They are used only
to rank the group's artifacts against each other.

## 13. The portal error: "Predicted values must be in range [0, 1]"

Two mechanisms produce it while looking correct on screen: a `float32` sentinel such as
`-3.4028235e38` surviving inside the valid footprint, and a NaN nodata tag. Both are structurally
absent from the shipped file (zeros outside the footprint, no nodata tag at all), and every check is
re-run on the bytes read back from disk.

## 14. Submission note length

The stated limit is 140 characters. This session's note is 126.

## 15. Second-hand layer names

Band names and descriptions for `training_features.tif` were read from the file's own `DESCRIPTION`
tags this session (19 bands, listed in `src/gems62/grid.py`), so they are first-hand. The external
packs (`lidar_scarp_features_u8.tif`, `topo_10m_derived_100m_u8.tif`, `derived_sgmc_faults_100m.tif`)
are owner-mirrored; hashing proves mirror consistency, not origin.
