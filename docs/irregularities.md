# Irregularities, defects and traps — flagged, with what was done about each

The brief asks for irregularities to be flagged rather than smoothed over. These are ordered by
how much damage they could do.

## 1. The portal error you hit: "Predicted values must be in range [0, 1]"

**Diagnosis.** The official spec asks for a single-band `float32` raster with values in `[0, 1]`
[OFFICIAL, competition page 967]. Two writing habits violate it while looking correct on screen:
a `float32` **sentinel** such as `-3.4028235e38` (survives as an outlier inside the valid
footprint), and a **NaN nodata tag** (the reader returns NaN, which is not in `[0, 1]`).
The defective artifact from the earlier session — `gems32-h19-5-smoothmaxcov-44090.tif` — is one
of these, and it is **quarantined by standing rule: never ship, never re-emit.**

**What is done about it.** One writer, one code path, and the file is **re-opened from disk and
re-counted** before anything is published (`grid.check_submission`). The current file reports
`nodata = null`, `nan_count = 0`, `n_outside_0_1 = 0`, `all_finite = true`. The two mechanisms are
structurally absent, not merely avoided.

## 2. This session's own holdout instrument was wrong three times

Reported in full, because the numbers above are only trustworthy if the failures are visible.

| defect | symptom | fix |
| --- | --- | --- |
| fold did not confine scoring (`active = footprint & ~visible`) | `n_pred = 1660` in *every* fold; the whole footprint was scored each time | score only inside the eroded block |
| canary negatives drawn basin-wide while positives were fold-local | AUC pinned at exactly ~0.500 in every fold — a degenerate tie, not a clean bill of health | negatives from the same fold interior |
| "wholly inside the block" component rule | `n_truth = 0` in all 6 folds — the catalogue is one basin-scale connected component, so nothing is ever "wholly inside" | block-scale withholding with a 3 px erosion |
| `metric.dti_binary(pred, truth & active, active)` | truth silently zeroed (the module applies `active` to truth itself) | pass the block as the scored domain, not the block minus the catalogue |

Then a fifth, of a different kind: a run crashed on an undefined variable, its stdout/stderr were
suppressed to `/dev/null`, and the **stale JSON from the previous run was read as the result**.
The lesson is recorded in the commands: never suppress output when the artefact is the evidence.

The evaluator version that produced the numbers in `run-card.md` is the one *after* all five
fixes, and the fold arithmetic is asserted (`a withheld pixel survived inside the scoring zone`
raises).

## 3. The registry uniqueness tripwire is density-blind — a shared-tool defect, fixed and reported

**Defect.** The brief's tripwire is "> 70 % of your dots within 3 px of one registry raster's
dots ⇒ duplicate". Measured here: `13gems_20261001_r13-lattice-s5_v2` carries **206,895 dots**,
which dilates to 112 % of the 5.17 M-cell footprint, so its 3 px neighbourhood covers the map and
**any** emission scores ≈ 1.0 on the tripwire.

**Proof, not assertion.** A uniform-random 1,660-dot control (`build/controls/poisson_1660_seed7.tif`,
seed 7) scores `dot_overlap_within_kernel = 0.9982` against that same raster. A tripwire that
fires on Poisson noise cannot certify a duplicate.

**Fix (in `scripts/check_uniqueness.py`, reported here rather than forked).** The verdict now
additionally requires a **symmetric** overlap — the Jaccard index of the two 3 px-dilated dot
masks, `|A ∩ B| / |A ∪ B|`, threshold 0.25. It is 1.0 for a re-run of the same lane and ~0.01 for
a sparse emission against a dense lattice. The asymmetric fraction is still reported as a
diagnostic, because it is what the brief names.

**Result for the current file:** `UNIQUE-VS-REGISTRY` across 289 rasters — worst rank correlation
**−0.065**, worst Jaccard **0.030**, and the asymmetric maximum of 1.00 attributable to the
lattice raster above.

## 4. The catalogue-based holdout anti-selects novelty — so it is not a score

Measured three independent ways (`hypotheses.md`, "the validation trap"): a sibling repository
measured ρ = **+0.087** between its catalogue-hidden proxy and the live leaderboard; its Poisson
control (0.098) beats an artifact that scored 0.2778 live (0.019); and this repository's own
Poisson control (0.0669) beats the same artifact (0.0067) by 10×.

**Consequence, stated in every document that carries the number:** the holdout is a bug screen, a
leakage canary and a null generator. It is **never** written as a score, and it is never used to
promote or reject a file.

## 5. Owner-reported scores are claims, not receipts

The scores the user has quoted (0.2778, 0.3774, …) are recorded here as **OWNER-REPORTED**. No
organizer receipt, e-mail or exported leaderboard row is present in this repository, and the
competition pages do not expose them to this sandbox. They are used only to *rank the group's own
artifacts against each other*, which is what the user asked for, and never as an evaluation of a
file produced here. If a receipt exists, it should be committed as `evidence/` and this file
updated — it would be the first ORGANIZER-CONFIRMED number in the repository.

## 6. Submission note length

The stated limit is 140 characters; the site has previously accepted 177–200 [OWNER-REPORTED].
This repository keeps **≤ 140** because that is the stated limit. The current note is 128
characters.

## 7. DEM transport and format traps

* The 3DEP transport GeoTIFF is **int16 decimetres**, not metres, and the first fetch clipped the
  −32767 nodata sentinel to −32766 when rounding to decimetres. Handling it as metres made every
  elevation gate false; the fix is in `read_z()` and in the fetch writer (sentinel written *after*
  the clip, readers mask ≤ −32000).
* Run **38169049665** is recorded as **success with no artifact** — a silent-empty result. It is
  kept in `evidence/` precisely because "success" was not the same as "produced data".
* `dem_transport.json` records `resampling: "as-is"`, i.e. the mosaic is not reprojected here; the
  tiles are already EPSG:32611 at 25 m.
* Coverage after run **38169727207**: 6 tiles, valid fraction **0.8088** (was 0.590 with 5). The
  per-block coverage map has not been re-verified since the 6th tile landed — a gap in this
  session's evidence, listed in `next-steps.md`.

## 8. Second-hand layer names

The band names used for hypotheses H-A and H-D (`lidar_scarp_features_u8.tif`, `geodawn_rad_u8.tif`,
`training_features.tif` bands 13/15/17) are **[SIBLING-MEASURED]** — read from band descriptions in
a sibling checkout. This repository does not clone the 418 MB feature stack, so they are **not
re-verified here**. Treat them as a lead to confirm before building on.

## 9. What the organizers will and will not tell us — read this before trusting any local score

* They will **not** share the data sources, fault types or coverage behind the test faults beyond
  the problem description [OFFICIAL, thread 11527 — chrisk-dd, 2026-09-23].
* **Phase 2 uses a test set updated by expert review of all Phase 1 submissions** [OFFICIAL, same
  post]. Phase 1 predictions therefore influence final evaluation even when they do not score
  well — which is the only sound argument for spending a Phase-1 slot on a file whose local
  evidence is thin, and which is why this file's verdict is "low-risk novelty probe" rather than
  "do not submit".

## 10. A suspicious statistic in this file's own output

The 221 traces have a **median length of 1.3 km** (max 5.6 km). Real fault traces are usually
longer, so the binding constraint is probably the trace-stopping rule rather than the geology.
Flagged as unresolved; see `next-steps.md`.


---

## Added 2026-10-11 (session `arena/2b64062a-62gemsdoe`)

### IR-62-11 — six of nine root modules did not import on a clean checkout — FIXED

`src/gems62/grid.py` was rewritten at some point to keep only `GRID`/`TRANSFORM`/`BOUNDS`/`PINS`,
while `emit`, `holdout`, `lahontan`, `uniqueness`, `validate` and `score_model` all imported
`PIXEL_M` / `CRS` / `HEIGHT` / `WIDTH` / `read_dem` / `read_labels` / `FOOTPRINT_CELLS` from it, and
`score_model` imported `RADIUS_M` from `metric`. Verified here on a clean worktree:

```
gems62.validate     ImportError: cannot import name 'CRS' from 'gems62.grid'
gems62.uniqueness   ImportError: cannot import name 'PIXEL_M' from 'gems62.grid'
gems62.score_model  ImportError: cannot import name 'RADIUS_M' from 'gems62.metric'
gems62.emit         ImportError: cannot import name 'PIXEL_M' from 'gems62.grid'
gems62.lahontan     ImportError: cannot import name 'PIXEL_M' from 'gems62.grid'
gems62.holdout      ImportError: cannot import name 'PIXEL_M' from 'gems62.grid'
```

Fixed **once, in the template, additively**: the missing constants and readers are restored to
`grid.py`, the metres-based metric API (`dti_components`, `brute_force_components`,
`maximum_useful_distance_m`, `unit_dot_dti`) is restored to `metric.py` from the archived variant in
`superseded_20261011/`, and the two diagnostic-figure writers are extracted to a new shared module
`src/gems62/figures.py` (they had been dropped from `scripts/run_lane.py`, which made
`tests/test_lane_instruments.py::test_map_writer_rejects_wrong_units` fail with `AttributeError`).
Every value added is a number `grid.py` already carried in another spelling. **No existing logic was
overwritten and no private fork was kept.** Root suite: **18 passed → 18 passed** (one previously
failing test now passes); `lane62/` suite **46 passed**.

### IR-62-12 — `lane62` tests errored on a fresh checkout for a file that was present — FIXED

`lane62/src/gems62/grid.load_grid` hard-coded `data/official/`, which only exists after
`download_competition_data.sh` has run *inside* `lane62/`. 14 tests errored with
`No such file or directory` even though the same three rasters are committed (hash-pinned) at the
repository root. A fallback chain was added, plus a bug found while testing it: **`Path(".").parent`
is `Path(".")`**, so the first version of the fallback silently pointed back at the lane root. The
resolver now calls `.resolve()` first. `lane62` suite: **2 failed, 12 errored → 46 passed**.

### IR-62-13 — GitHub Pages is enabled but serves the wrong directory

`GET /repos/buffedlizard55-lab/62GEMSDOE/pages` returns `{"source":{"branch":"main","path":"/"},
"status":"built"}`, i.e. the site is served from the **repository root**, while every page lives in
`docs/`. The published URL therefore 404s, which is why the owner's site list shows an empty entry
for `62GEMSDOE`. `PUT /repos/.../pages` returns **HTTP 403 "Resource not accessible by integration"** —
the sandbox token lacks the `pages` scope, so this cannot be fixed from here. **Mitigation applied:**
a root `index.html` that redirects to `docs/index.html`, so the published URL resolves. The durable
fix is one manual step: repo **Settings → Pages → Source = `main` / `/docs`**.

### IR-62-14 — `labels.tif` and `existing_faults.tif` are byte-identical

Both are 425,830 bytes with sha256 `7ba308ccdc4418b3…`, verified with `cmp`. This is already recorded
in `registry/data_pins.json` ("byte-identical to labels.tif") and it is *consistent* with the task
definition — the training labels **are** the mapped catalogue, and the competition target is the
faults **absent** from it. Flagged here because it is the single fact that makes the local holdout
structurally incapable of measuring the real target, and every holdout number in this repository
inherits that limit.

### IR-62-15 — the 25 m DEM mosaic covers only 55.74 % of the competition footprint

`evidence/dem/lahontan_dem_utm11.tif` is 9200×7600 at 25 m, EPSG:32611, spanning x 240 000–430 000,
y 4 250 000–4 480 000 — a **sub-window** of the competition grid (x to 572 550, y to 4 135 550).
Measured: it reaches grid rows 285:2586, cols 0:1867 and covers **2,880,158 of 5,167,373 footprint
cells (55.74 %)** and 62.06 % of catalogue cells. Two further defects: it is **int16 decimetres**,
so elevations above **3276.7 m cannot be represented** (the eastern Sierra is clipped —
`z.max() == 32767`), and its earlier "valid fraction 0.8088" was computed *within the mosaic window*,
not over the competition footprint. Consequence: **the 25 m mosaic cannot support a basin-wide lane.**
The 100 m mirror `geodawn_dem_a2_100m.tif` covers 5,165,644 footprint cells (99.97 %) and was used
instead; its sha256 matches the pin in `registry/data_pins.json`.

### IR-62-16 — the protocol's 3-px uniqueness leg is unsatisfiable; independently re-proven

A **pure-random** 10,000-dot off-catalogue field (seed 11, zero geological information) puts
**84.12 %** of its dots within 3 px of `13gems_20261001_r13-lattice-s5_v2`, 84.12 % of
`…zerofill`, and 76.58 % of `13gems-composite-plus` — i.e. it trips the protocol's 70 % duplicate
rule against **3 of 79** comparators. That comparator's 3-px halo alone covers **83.91 %** of the
footprint. A tripwire that fires on Poisson noise cannot certify a duplicate. Uniqueness in this
repository is therefore judged on the two legs that do discriminate — the symmetric Jaccard of the
3-px halos and the footprint Spearman correlation — with the asymmetric fraction still reported.
Evidence: `evidence/h62g/tripwire_satisfiability.json`. This independently reproduces
`GEMSDOE54` IR-54-016.

### IR-62-17 — the brief's own leaderboard numbers are stale by nine days

The brief states "0.3195 is the highest score right now". The official public leaderboard, scraped
2026-10-11T20:57:47Z, puts 0.3195 at **rank 9** and #1 at **0.4133**; the top-5 cut-off is
**0.3333**. The group's best (0.2778) is **rank 23 of 50**. Any target set against 0.3195 is aiming
at ninth place. Series: `research/leaderboard_series.json` (37 snapshots).

### IR-62-18 — this session's own uniqueness gate had a direction bug, found by running it

The first implementation computed `|dilated_mine ∩ theirs| / |mine|` instead of the protocol's
`|mine ∩ dilated_theirs| / |mine|`, and compared the submission against **itself** (returning a
spurious ρ = 1.0, Jaccard = 1.0, "DUPLICATE-DRIFT"). Both were wrong. Fixed and re-run; the
corrected numbers are the ones published. Recorded because the first (wrong) verdict was already
printed, and a reader comparing the two would otherwise be misled.

## Added 2026-10-12 (session `arena/778884cc-62gemsdoe`)

### IR-62-19 — the group's best local instrument (the S* leaderboard inversion) had a kernel-radius bug — FOUND, FIXED ONCE IN THE TEMPLATE, RE-RUN
`datum62/scripts/invert.py` built the kernel table in **pixel** units (`KERN[j] = max(1 − j/3, 0)`,
zero at j ≥ 3 px = 300 m) but indexed it with **quarter-pixel** indices (`KERN[(dm*4).astype(int)]`),
so every dot-to-truth distance ≥ 0.75 px (75 m) contributed **zero** credit. The committed evidence
reproduces the defect: the inversion's own output under-predicts every high-scoring artifact outside
the 13-field consensus by 4×–37× (gate_ortho: predicted 0.0064 vs OWNER-REPORTED 0.2376; h59-cover:
0.0219 vs 0.2296; Hedge-v2: 0.0067 vs 0.1563) while fitting the consensus family well (h33: 0.2992
vs 0.2778) — the signature of an exact-pixel-overlap model. Fixed once (comment + corrected table in
`invert.py`; re-run as the shared tool `scripts/reconstruct_sstar.py`, no private fork): with the
official 300 m kernel the same protocol converges to K = 18,721 px, Spearman **+0.9641**, R²
**0.3007 → 0.7007**, RMSE 0.0768 → 0.0503, scale 0.5052 → 0.3848. Consequences: (a) every
projection ever written from `0.5052 × DTI(S*)` — including the datum62 detector's 0.110 and this
lane's v8 0.0012 — is superseded; (b) S*† is now provably a subset of the exact h33-2-b2 dot pixels
(18,721 of 37,654), so the duplicate block on emitting it stands, unchanged; (c) the fixed
instrument still under-predicts out-of-family fields (gate_ortho 0.0557 projected vs 0.2376
observed) — it is a **floor** instrument for novel placements, never a ceiling. Evidence:
`evidence/sstar_fixed/inverse_truth_fixed.json`, `evidence/h62n_forensics.json`.

### IR-62-20 — the standing "selector rank-1" recommendation is retracted
`docs/next-steps.md` item 1 and `docs/research/leaderboard-arithmetic.md` §5 told the selector to
submit `gems32-bayesopt-dilation-scarp-d28` (45,000 dots) because it measures 0.29294 credit/dot on
the SGMC off-catalogue instrument — 3× the champion family. That instrument is measured
**anti-correlated** with the portal (Spearman −0.928 over 15 owner-reported scores; datum62's own
finding). On the kernel-fixed portal-calibrated instrument the same file measures **0.0408
credit/dot, DTI(S*†) 0.0766, projection 0.0295** — below this session's lane file (0.0593/dot) and
10× below the h33 family (0.42/dot). The rank-1 advice is retracted wherever it appears; the pages
carry the retraction inline. Do not spend a slot on the bayesopt field on the strength of the old
number.

### IR-62-21 — two disclosures about this session's artifact
(a) **Southern-block loci are not necessarily Lahontan.** The z-band gate (1189–1463 m) plus the
bench gate cannot distinguish Lake Lahontan's own margins from other pluvial-lake benches and playas
at similar elevations in the southern blocks (822 + 2,688 dots). The lane's coverage statement is
"pluvial-lake margins", so this is inside the lane, but a Lahontan-only reading of those dots would
be wrong. (b) **`tools/fetch_registry.py` clobbers same-named files across repositories**
(dest = `repo__basename`); 334 fetched rasters land as 290 files. Not fixed this session (budget);
the S* work used the 60GEMSDOE normalized registry instead, whose bytes are sha-verified against
`research/registry_index.json` pins.

### IR-62-22 — corridor headroom is now measured, not speculated
gate_ortho (OWNER-REPORTED 0.2376) keeps only **43.4 %** of its dots within 3 px of h33-2-b2 and
**22.5 %** within 3 px of S*†, with median nearest-neighbour distance 3.6 px — i.e. a field can sit
*beside* the champion's corridors, pass the protocol's 70 % tripwire with room to spare, and still
score within 0.04 of the champion. The hidden truth is therefore spatially broader than the group's
consensus, and *unique* fields are not doomed to low scores. This is the strongest argument the
registry offers for continuing to emit novel placements, and it is the frame in which this
session's negative verdict should be read: negative on the measured projection, not on the design.
