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

## Added 2026-10-11 by session `arena/d0303476-62gemsdoe`

| ID | Irregularity |
| --- | --- |
| **IR-62-19** | **The protocol's rank-correlation leg was computed with ordinal ranks.** `np.argsort(np.argsort(mask))` on two sparse binary rasters over 12,279,160 cells is dominated by the arbitrary ordering of the ~12M tied zeros: measured values were **0.95–0.976 for every comparator pair**, i.e. the statistic reported "ρ ≈ 0.97" between fields that share 1.1 % of their pixels. Re-computed tie-aware on a fixed 300,000-pixel sample (average ranks), the same comparison gives **max \|ρ\| = 0.035**. `scripts/build_final_field.py` now uses the tie-aware form; earlier reports of this statistic in this repository should be re-read with this in mind. The superseded 120 k probe that carried the old check (`docs/downloads/probe-120k.tif`) has been removed from the download directory — the field it probed is now the shipped artifact, and its receipt survives at `evidence/final_field_probe-120k.json`. |
| **IR-62-20** | **The SGMC 1:750 k instrument cannot rank fields.** Over 20 owner-reported scores, its per-dot credit correlates **+0.617** with the leaderboard but the published DTI evaluated on it correlates **−0.442** (p = 0.0513). The repository's previous rank-1 next step ("submit the never-scored high-credit field") rests on the first quantity and is downgraded here. Evidence: `evidence/e2b_reference_frame_20261011b.json`, `evidence/e4_gates_20261011b.json`. |
| **IR-62-21** | **`docs/data.md` §1 says the official feature stack is 35 bands.** The file says 19 (`count = 19`, sha256 `4371c82e…` = the pin), and each band carries its own `band_name` tag — so the band names are no longer second-hand (contradicting `docs/data.md` §5 and `docs/research/sources.md` §1). One-line doc fix outstanding. |
| **IR-62-22** | **The 3-px overlap leg of the lane rule is vacuous for every field.** Measured on `r13_lattice_s5_00904.tif` (5 px lattice, 206,895 dots): a *uniform-random* field of 120,000 dots scores **0.9987** and a 3 px lattice scores **0.9988** — both higher than any real field's 0.995. Any submission trips the "duplicate" leg against that comparator, so the leg carries no information about copying. Confirms and quantifies `IR-62-UNIQ-01`. |
| **IR-62-23** | **Three copies of the holdout evaluator existed** (`src/gems62/holdout.py`, `lane62/src/…`, `lane62-h62a/src/…`), each with a different API — the "private fork" the protocol forbids, in the same repository. Promoted to one: `src/gems62/holdout_segmented.py` (from the copy that produced every quoted HOLDOUT-DTI), with `tests/test_holdout_segmented.py` asserting elementwise equality between the promoted module and the original on a synthetic fixture. `src/gems62/metric.py::dti_binary` gained the `valid=`/`known=` keywords additively so only one call signature exists. |
| **IR-62-24** | **One defect ID was reused.** `src/gems62/metric.py` cites its keyword-form fix as `IR-62-13`, and this register's `IR-62-13` is the GitHub Pages directory. The citation in the code was stale; it is corrected to `IR-62-18`, which is the entry describing the unification of the holdout evaluator that the fix belongs to. Rule for the next session: **the register is authoritative for IDs; code cites the register, never its own numbering.** |

## Added 2026-10-12 (session `arena/778884cc-62gemsdoe`)

### IR-62-25 — the group's best local instrument (the S* leaderboard inversion) had a kernel-radius bug — FOUND, FIXED ONCE IN THE TEMPLATE, RE-RUN
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

### IR-62-26 — the standing "selector rank-1" recommendation is retracted
`docs/next-steps.md` item 1 and `docs/research/leaderboard-arithmetic.md` §5 told the selector to
submit `gems32-bayesopt-dilation-scarp-d28` (45,000 dots) because it measures 0.29294 credit/dot on
the SGMC off-catalogue instrument — 3× the champion family. That instrument is measured
**anti-correlated** with the portal (Spearman −0.928 over 15 owner-reported scores; datum62's own
finding). On the kernel-fixed portal-calibrated instrument the same file measures **0.0408
credit/dot, DTI(S*†) 0.0766, projection 0.0295** — below this session's lane file (0.0593/dot) and
10× below the h33 family (0.42/dot). The rank-1 advice is retracted wherever it appears; the pages
carry the retraction inline. Do not spend a slot on the bayesopt field on the strength of the old
number. Convergent finding: session `arena/d0303476` independently downgraded the same rank-1
advice from the correlation side (their IR-62-20: SGMC per-dot credit ρ = +0.617 with the
leaderboard but SGMC-evaluated DTI ρ = −0.442); this entry adds the direct measurement on the
portal-calibrated instrument.

### IR-62-27 — two disclosures about this session's artifact
(a) **Southern-block loci are not necessarily Lahontan.** The z-band gate (1189–1463 m) plus the
bench gate cannot distinguish Lake Lahontan's own margins from other pluvial-lake benches and playas
at similar elevations in the southern blocks (822 + 2,688 dots). The lane's coverage statement is
"pluvial-lake margins", so this is inside the lane, but a Lahontan-only reading of those dots would
be wrong. (b) **`tools/fetch_registry.py` clobbers same-named files across repositories**
(dest = `repo__basename`); 334 fetched rasters land as 290 files. Not fixed this session (budget);
the S* work used the 60GEMSDOE normalized registry instead, whose bytes are sha-verified against
`research/registry_index.json` pins.

### IR-62-28 — corridor headroom is now measured, not speculated
gate_ortho (OWNER-REPORTED 0.2376) keeps only **43.4 %** of its dots within 3 px of h33-2-b2 and
**22.5 %** within 3 px of S*†, with median nearest-neighbour distance 3.6 px — i.e. a field can sit
*beside* the champion's corridors, pass the protocol's 70 % tripwire with room to spare, and still
score within 0.04 of the champion. The hidden truth is therefore spatially broader than the group's
consensus, and *unique* fields are not doomed to low scores. This is the strongest argument the
registry offers for continuing to emit novel placements, and it is the frame in which this
session's negative verdict should be read: negative on the measured projection, not on the design.

---
## Added 2026-10-12 (session `arena/b7846648-62gemsdoe`) — numbered `IR-62-J-nn`, see the note above

**Two ID collisions in one day, flagged rather than smoothed over.** This session allocated
`IR-62-19` … `IR-62-24` while session `arena/d0303476` was merging the same six numbers into the same
register from the other direction; those were renumbered, and then session `arena/778884cc` merged
`IR-62-25` … `IR-62-28` from a *third* lane, colliding with the renumbering. The entries below therefore
carry **lane-namespaced IDs `IR-62-J-nn`** and claim no numbers at all: the register in `main` is
authoritative for numbering (the rule `IR-62-24` states), four sessions were writing to it inside
twenty-four hours, and `IR-62-J-nn` is the only allocation a concurrent lane cannot hit. The collision is
itself the irregularity — two duplicate ranges in a day, each caught only by a merge conflict — so the
convention going forward is stated in `IR-62-J-09` below: allocate from merged `main`, or namespace.


### IR-62-J-01 — the organiser's own `sample_submission.tif` fails this lane's format contract

Measured on the committed bytes (sha256 `2176d08e485aa2cd…`, 1,599,597 B) with the two validators this
repository ships, which disagree with each other:

| property | value |
| --- | --- |
| bands / dtype / CRS / geotransform | 1, `float32`, EPSG:32611, identical to every file here |
| `nodata` tag | **NaN** |
| non-finite pixels | **7,111,787** — every cell outside the footprint |
| finite min / max, and cells outside [0,1] | 0.0 / 1.0, and **0** |
| positive cells | **60,988 — exactly the public catalogue** |
| `validate_submission` (the published contract) | **passes**; 0 NaN inside the footprint |
| `check_submission["legal"]` (this lane's rule) | **False** — it demands `all_finite` and `nodata is None` |

Three consequences, now machine-enforced rather than remembered.

1. **A range check written as `0 ≤ min` and `max ≤ 1` is NaN-poisoned.** Min/max over a file whose
   non-footprint cells are NaN are themselves NaN, so a file that satisfies the portal's stated rule is
   reported as violating it. `scripts/audit_downloads.py` now measures the range over finite pixels and
   reports `portal_range_risk` separately: `none`, `low` (non-finite pixels *with* a nodata tag, so a
   masked reader never sees them) or `high` (non-finite *without* a tag — the mechanism that actually
   produces *"Predicted values must be in range [0, 1]"*).
2. **This repository's own verdict on its `-nan` probe was wrong and is corrected.** With a NaN nodata
   tag the probe passes the published contract; sibling files written the same way carry scores up to
   0.275 in the registry mirror. "NaN tag ⇒ rejection" was never supported by any measurement here, and
   the download page no longer says it.
3. **`no_nodata_tag` and `no_nan_anywhere` are labelled as what they are** — this lane's convention,
   stricter than the example the organiser ships. `docs/downloads/manifest.json` lists them under
   `strict_checks` and carries the organiser's file itself as `reference_example`, so the asymmetry is
   visible in the machine record rather than only in prose.

### IR-62-J-02 — `int(round(250 / 100))` is 2: a 250 m collar is not what the code meant

The first `run_h62j.py` converted a metres-unit catalogue collar to pixels with `int(round(m / 100))`.
Python's `round` is banker's rounding, so 250 m became **2** cells, not 3 — a Chebyshev-2 collar whose
realised minimum Euclidean dot-to-catalogue distance is **223.6 m**, not 250 m. Nothing raised an error;
the gate silently measured a different quantity than its name claimed. Measured facts after the fix, on
the emitted field: 0 dots on the catalogue, minimum distance to it 223.6 m, 340 of 8,571 within 300 m.

Two rules follow, and both are now how this lane writes code: convert metres to cells with `ceil`, and
**report the realised distance the bytes contain, never the intended one**. A "250 m collar" in a run card
is a claim about arithmetic; a "minimum dot-to-catalogue distance 223.6 m" is a claim about the file.

### IR-62-J-03 — a JSON manifest that is not JSON: `NaN` is valid in Python and invalid in JSON

`json.dumps` happily writes `NaN` for a non-finite float, and the browser then refuses to parse the file.
The audit records `min`, `max`, `nodata` and `total_mass` straight from NumPy, and `data/sample_submission.tif`
— measured as the reference example — is all four at once (`total_mass: NaN`, because its raw sum includes
7.1 M NaN pixels). Every manifest is now passed through `jsonable()`, which writes `null` and prints that
it did, and the audit records `"NaN"` as a *string* where a value is genuinely non-finite so the field is
readable instead of silently null. Recorded because the same trap has already cost this group a scored
sibling in the mirror, and because a generator that emits unparseable evidence is worse than no generator.

### IR-62-J-04 — "the DEM covers X % of the footprint" had no X until it had a definition

Three numbers were in circulation for the same raster this session: 55.7 %, 29 %, 9.4 %. All three are
correct of different quantities, measured here on the 100 m grid: the DEM **extent** contains 2,878,929 of
5,167,373 footprint cells (**55.71 %**, matching `IR-62-15`'s 55.74 % under its area definition); **52.24 %**
of footprint cells have a finite elevation; and only **9.42 %** (486,753 cells) sit inside a 4 km isobase
tile that the doublet pipeline can actually measure — which is the number that caps this lane's mass.
A "coverage" claim without its numerator and denominator is not a measurement, and the site now states
all three with their definitions.

### IR-62-J-05 — the two lane suites cannot be collected in the same pytest process

`pytest lane62/tests -q` passes 46; `pytest lane62-h62a/tests -q` passes 41; together they fail during
collection with `ImportError: cannot import name 'emission' from 'gems62' (/…/lane62/src/gems62/__init__.py)`.
Both lanes put their own `src` on `sys.path` in a `conftest.py` and both ship a module named
`tests/test_gems62.py`, so in one process the second lane's import resolves against the *first* lane's
package. Pre-existing (it is not caused by anything this session changed) and it only bites a combined
invocation, which no workflow in this repository makes — but it is a trap for anyone who runs
`pytest tests lane62/tests lane62-h62a/tests`, and the fix belongs to the lanes: unique test basenames,
or `importmode=importlib` plus per-lane rootdirs. Until then: **run each suite separately.** Recorded
here because "the suites are green" is only true under that qualifier, and a reader who runs one
combined command would otherwise conclude the repository had regressed.

### IR-62-J-06 — this README asserted the root suite cannot collect; it can, and did, on this checkout

`README.md` (the `lane62-h62a/` addendum, line ~441) states that `pytest tests/` at the repository root
"still cannot collect" because `src/gems62/lahontan.py:50` imports a `PIXEL_M` that `grid.py` never
defines and `tests/test_metric.py:17` imports a `brute_force_components` that `metric.py` never defines.
Both symbols exist now — `PIXEL_M` is restored additively in `src/gems62/grid.py` by the `IR-62-11` fix
and `brute_force_components` is defined at `src/gems62/metric.py:254` — and `pytest tests -q` on this
checkout reports **54 passed** in 8.2 s. The claim was true when written and is now stale; it is
corrected rather than deleted so the sequence is visible, and `.github/workflows/ci.yml` grew a root job
that runs `pytest tests -q` plus the download audit, so the statement cannot silently go stale again.

## IR-62-J-07 — one lane's run card existed only as HTML, and its own test pinned the HTML-only string

**Found:** 2026-10-12, while resolving the merge of `origin/main` into this lane. `docs/run-card.md` was
rendered to `docs/run-card.html`; the other lane's `2026-10-11b` section existed **only in the HTML**. Its
markdown was never written, and `tests/test_docs_20261011b.py` asserted a phrase ("max dots in any 300 m
disc") that lived in the page but not in the source. My renderer then did exactly what it is built to do —
rebuild the page from the markdown — and dropped a whole section of a colleague's published verdict.

**Why it was not obvious:** both lanes could produce a consistent-looking `run-card.{md,html}` pair, and
nothing in CI compared them. The phrase *was* findable, in a file. Half the run card was in one file and
half in another, with the difference invisible unless someone regenerated the page from its source.

**Fix applied:** their section was ported into `run-card.md` verbatim (converted to markdown table rows,
marked as restored from the committed HTML, not as this lane's claim), then re-rendered. The
render/check machinery in `scripts/render_doc_pages.py` plus `tests/test_doc_render.py` makes the pair
CI-enforced for both lanes' pages.

**The rule:** **a page whose text is not its markdown's text is a defect in the markdown**, not a detail.
Hand-editing generated HTML is how the *first* session went wrong (IR-62-02), the pattern survived a merge
because the guard was not in `main` yet, and the fix is one command (`render_doc_pages.py PAGE`) plus one
test that refuses to let the pair drift. When the guard fires on content you did not write, read the other
side before you assume the render lost something — here the render was right and the source was short.

**One more trap, found the same hour:** the page renderer is deliberately minimal and does **not** escape
code spans, so a raw less-than or greater-than sign, or a closing anchor tag, written inside backticks is
swallowed as markup and the page loses it silently — this is what happened to the range-check line above,
which had to be rewritten with a Unicode ≤. The guard refused to write in both cases, which is the
point; the source was rewritten with `≤` and prose instead of angle brackets. **Rule: no raw angle brackets
in a markdown source that a minimal renderer will pass through.** If `--check` refuses, fix the markdown, not
the exception list.

**Also fixed while here:** the guard itself, which compared *word lists*. Three legitimate constructs
produced false alarms — `(0.24073)` written as `(**0.24073**)`, a code span containing a `*`
(`docs/downloads/*.verdict.json`), and a full stop that follows a link, which the renderer emits as text plus a closing anchor — because tag boundaries
insert spaces on one side only. It now compares normalised **character streams** (markup, emphasis ticks and
punctuation removed on both sides, link targets dropped on the markdown side), and reports the nearest word
for context. The deletion-detection test still passes, so the guard is both quieter and unchanged in power.

## IR-62-J-08 — the download audit read a *session id* as a stale hash claim

**Found:** 2026-10-12, running `scripts/audit_downloads.py --write` after adding the other lane's file to
the manifest. It refused to pass, reporting that `docs/index.html` "prints hash `d0303476` for
gems62b-…, whose sha256 starts 42bffef1…" — inside a row I had generated a minute earlier, where the only
hex token is the correct 16-char prefix and `d0303476` is the *lane's session identifier* in the verdict text.

**Root cause:** the cross-check scanned every table row that mentions a file name for `\b[0-9a-f]{8,64}\b`. Eight
hex characters is a normal Git short-id length, and short ids appear in prose about provenance; a gate that
fires on prose is a gate people will switch off.

**Fix applied:** a token counts as a hash claim only at **16+ hex characters** and not preceded by `/`
(which excludes `arena/d0303476` and paths generally). Any truncated sha printed for a bytes claim is 16 or
more in this repo; a stale 16-char prefix is still caught, and the test in `tests/test_download_manifest.py`
covers the file-name-and-bytes matching.

**The rule:** **a consistency gate must not fire on the things a page legitimately says.** Encode the claim
types you mean to police (digest, byte count, dot count), not every token that *looks* like one — the value
of an audit that runs in CI is exactly its false-positive rate.


### IR-62-J-09 — two lanes created the *same filename* for the same day, and the register has no owner

**Found:** 2026-10-12, merging `origin/main` (PR #20, sessions `arena/d4d2e53a` + `arena/778884cc`).
`docs/hypotheses-2026-10-12.md` and its `.html` came back as **add/add conflicts**: that lane wrote a
four-ranked-hypotheses page for 2026-10-12, this lane wrote one too, and git reported 1,000 lines of
"conflict" between two documents that never intended to be the same document. The register collision above
is the same failure one level down: six documents, three lanes, one shared counter.

**Why it was not obvious:** `docs/` files are named by *date*, which is a unique key only while one session
runs per day. Nothing in the tree declares an owner for `IR-62-25` or for `hypotheses-2026-10-12.md`, and
`main` had moved twice since either branch was cut, so each lane's "next free ID" was computed against a
different base.

**Fix applied:** the numeric IDs are theirs — `main` is authoritative — and this lane's page is renamed
`hypotheses-2026-10-12-j.{md,html}`, with a cross-reference at the top of each so a reader who arrives from
the index finds both rankings instead of assuming the other does not exist. This lane's own entries move to
`IR-62-J-nn` and claim no numbers.

**The rule:** **a date is not an identity.** Anything named by a calendar day or by a counter is shared
property in this repository; a lane writing a new one appends its lane suffix (`-j`, `IR-62-J-nn`) *before*
it commits, not after a conflict. Renaming my side was chosen over renaming theirs for one reason: their
page is already cited from `main` and from the README tree, and re-pointing someone else's citations is the
expensive direction.

### IR-62-J-10 — a maths block written in LaTeX reached a page with no maths renderer

**Found:** the same merge. The other lane's `docs/index.html` explained the metric with
`$\text{DTI} = \frac{\text{TP}_w}{0.2(\text{TP}_w + \text{FP}_w) + 0.8 K}$` — correct as notation, and
rendered by every browser as exactly that string, because no page in this repository loads MathJax or KaTeX.
The same block used `K` for the normaliser where every other document here uses `N`, and `k >` for the
marginal bar, so the page disagreed with `docs/why-h33-scored.md` on top of being unreadable.

**Fix applied:** the block is now plain text (`DTI = TP / (0.2·(TP + FP) + 0.8·N)`, the 4:1 asymmetry named,
`N` used consistently), with their numbers and their argument untouched. Not fixed: adding a maths library
to a site that is otherwise dependency-free would cost more than it buys.

**The rule:** **a claim in markup the page cannot render is a claim nobody reads.** Pages here are static,
dependency-free HTML, so notation is written in the characters the browser already has — `≤`, `·`, `×` — or
as an inline code span. If a page ever needs real TeX, that is a decision to record here first.

### IR-62-J-11 — CI, the test and the renderer each carried their own list of pages to check

**Found:** 2026-10-12, minutes before committing the merge that renamed this lane's hypotheses page. Local
tests were green (92 passed), `render_doc_pages.py --check run-card … irregularities …` was green, and the
audit was green. `.github/workflows/ci.yml` nevertheless said:

> `python scripts/render_doc_pages.py --check run-card next-steps irregularities hypotheses-2026-10-12 hypotheses-2026-10-11`

That list — hand-copied into the workflow on an earlier day — still named `hypotheses-2026-10-12`, which
after the merge is **the other lane's hand-styled page** whose markdown this tool refuses to render (their
`.md` is a separate draft with autolinks and a different structure). CI would have failed on a branch that
passed every local check, and the fix was not "add `--no-verify`": it was to stop having three lists.

**Why it was not obvious:** the three lists were *equivalent when written* — that is precisely the shape of
defect that survives review — and each file justified itself separately: the workflow "just" runs the tool,
the test "just" parametrizes over pages, the tool "just" has a default. Nothing said which one is the
definition. The workflow's copy also could not express the exemption the merge required, so any attempt to
fix CI by editing the workflow alone would have left the test and the tool disagreeing again.

**Fix applied:** the page list now lives in exactly one place, `RENDERED` in `scripts/render_doc_pages.py`,
next to `HAND_WRITTEN` (a dict of page → *why it is exempt*, because an exemption without a reason is how a
drift becomes permanent). `tests/test_doc_render.py` imports both, `--check` with no arguments uses
`RENDERED`, CI runs `--check` with no arguments, and
`test_the_declared_lists_stay_disjoint_and_honest` fails if a page is in both lists, if a declared page has
no pair, or if an exempt page has no recorded reason.

**The rule:** **one list, imported; no copied lists in CI.** If a workflow names files, it will drift the
first time a file is renamed — and a rename is exactly what a collision (IR-62-J-09) forces. When you fix a
CI-only failure, ask which of the copies was authoritative, then delete the copies rather than the check.

---

## Added 2026-10-12 (session `arena/fd6c719c-62gemsdoe`) — numbered `IR-62-B-nn`

Same lane, same date, one of four parallel sessions: the *datum-offset* lane run as **H62-B**, the
pluvial depositional datum as a strain gauge. Its artifact is
`docs/downloads/gems62-h62b-lahontan-datumstep-trace-37654dots-20261012T000000Z-zeros.tif`
(231,909 B, 37,654 dots, sha256 `e56752ba…`). Its write-up is
[`results-h62b.md`](results-h62b.md) and its card is
[`run-card-2026-10-12-h62b.md`](run-card-2026-10-12-h62b.md). Every number below is MEASURED unless
labelled otherwise.

### IR-62-B-01 — the group's "Poisson control" is not a control; it is the detector

`GEMSDOE30` reports `d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca` at **0.2600** and
presents it as a random control. Measured here: that file and `gems25-dotted-h19-5-d28-zeros` have
**Jaccard = 1.00000** — 44,090 positives, identical pixel for pixel, differing only in compression
and nodata encoding. So the claim "a random field scores the same as the detector, so placement does
not matter" is **void**: the two scores are the same score. Controls rebuilt here on the same
instrument, truth and mass: hard-core **0.1190**, uniform **0.1075**
(`evidence/exp1_instrument_calibration.json`, `buffer3px` variant). An independent 40,000-dot draw
in Experiment 2 over a 59,453-px truth gave 0.1197, so the bar is stable to ~0.6 %.

### IR-62-B-02 — `labels.tif` is byte-identical to `existing_faults.tif`

Both files in `data/` hash to `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093`
and hold the same 60,988 positives. The "labels" this repository holds are therefore the **catalogue
of already mapped faults**, not a training set of new ones: there is no local ground truth for the
target population at all. That is the single largest structural limit on every number here.

### IR-62-B-03 — the prescribed catalogue holdout is zero by arithmetic, not by lack of skill (fixed in the template)

The kernel is `k(d) = max(1 − d/300 m, 0)`, so a dot earns credit against a withheld truth pixel only
inside 300 m. Every competitive emission deletes every dot within 300 m of the mapped catalogue. A
dot set with no dot within 300 m of *any* catalogue pixel therefore has `TP_w = 0` against withheld
*catalogue* pixels **necessarily**. Measured: pooled DTI **0.000000** for this artifact (its minimum
distance to the catalogue is 400 m); the champion has 1,611 dots inside 300 m and so earns a little.
The better an artifact is at being off-catalogue, the more certain the zero.

Fixed **once, in the shared template**: `gems62.holdout.evaluate` now takes a `truth` argument so the
withheld population can be an independent fault set (evaluator string `gems62.holdout.v2`). With
SGMC-minus-catalogue truth the same evaluator returns 0.0728 for this artifact, 0.0741 for the
champion and 0.0496 for a hard-core control.

### IR-62-B-04 — the flagged step magnitudes are too large to be fault offset

Median flagged step **24.4 m**, largest **82.7 m** (n = 40 stepped loci; `evidence/figures_h62b.json`).
Post-15 ka offset of a single Lahontan shoreline is metres to a few tens of metres. These numbers are
dominated by (a) error in the base-level construction where the band crosses dissected terrain and
(b) the isostatic-rebound signal the 6 km isobase does not absorb. The *rank* of a flag is a robust
z-score and is unaffected; the *metres* are not interpretable. The seed stage of this lane is
consequently its weakest link, and the artifact's measured skill comes substantially from the
ridge-relief extension, which is a general lineament criterion rather than a datum-specific one.
Cure: fit the published rebound field instead of a free smooth surface (a named hypothesis, deferred
— the station tables are not obtainable from this sandbox, which reaches five hosts).

### IR-62-B-05 — the registry harvest contains rasters that are not on the competition grid (fixed)

`gems62.uniqueness.compare` raised `ValueError` on `5GEMSDOE__proxy_window.tif` (512×512) and aborted
the whole sweep, so the lane-drift check silently never completed. Fixed in the template:
non-conforming comparators are skipped and counted (`_EntryList.skipped`). Five were skipped: four
512×512 proxy windows and one 32×48 format test explicitly named `NOT_SUBMISSION`.

### IR-62-B-06 — the brief's leaderboard number does not match any public row

The brief states "0.3195 is the highest score right now". In the 50-row public leaderboard mirrored
2026-10-11 (`research/leaderboard_latest_2026-10-11_60GEMSDOE.json`), 0.3195 is **rank 8**; #1 is
**0.4133** and the top-5 cut-off is **0.3300**. Recorded, not resolved: this sandbox cannot reach
`drivendata.org`, and no organizer receipt exists for any file in this repository.

### IR-62-B-07 — a bare `pytest` at the repo root aborted with 3 collection errors (fixed)

`lane62/` and `lane62-h62a/` are *independent re-derivations* of the same lane and each vendors its
**own** copy of the `gems62` package. A root-level `pytest` collected all three, the copies shadowed
each other, and `tests/test_metric.py` clashed by basename with `lane62/tests/test_metric.py`. The
suite therefore could not be run at all from the root — which means it had not been. Fixed with a
root `pytest.ini` (`testpaths = tests`, `pythonpath = src`, `--import-mode=importlib`) plus a
documented per-lane invocation. **All 114 tests pass**: root 27, `lane62` 46, `lane62-h62a` 41.

### IR-62-B-08 — two different projection formulas coexist in this repository

`scripts/run_h62b.py` projects the score as `c · κ · M / (0.2M + 0.8N)`; `scripts/finalize_h62b.py`
anchors instead on the champion's own implied truth credit, `T_ch(N) · (c / c_champion) /
(0.2M·0.968 + 0.8N)`. At the shipped mass (M = 37,654, N = 10,000) they give **0.3484** and
**0.3530** — a spread of 0.005. Both are `MODEL`, both are printed, and both are shrunk by the same
calibration regression, whose residual is **±0.12**: the disagreement between the two formulas is
24× smaller than the uncertainty of either. They also agree on the *decision* — the mass sweep peaks
at M = 30,000–37,654 under both. Not fixed, because fixing it would mean re-running the sweep, and
the choice of mass is not what is in doubt.

### IR-62-B-09 — IR-62-DEM-01 is closed: absolute elevation is now available

Band 12 of the official stack is `det_elev`, "topography with regional trends removed" — trend removed
by an operator this repository cannot inspect. A Lahontan isobase is an absolute datum. Closed by
fetching `geodawn_dem_a2_100m.tif` (sha256 `d32762a3…`, 5,165,644 valid cells inside the footprint,
1027.9–3138.6 m, verified on the competition grid) and fitting the isobase on absolute elevation for
the first time. Its provenance is an owner mirror of the GeoDAWN compilation, not an
organizer-authenticated file.

### IR-62-B-10 — a third independent quantification of IR-62-UNIQ-01 (the 70 %-within-3-px leg is density-blind)

Over 340 registry comparators this artifact trips the overlap leg against exactly two distinct fields:
`GEMSDOE3__coverage-v3-wide` (**80.0 %**; 624,025 dots; its own 3 px halo covers 66.3 % of the
footprint) and `GEMSDOE22__h23-b-dti-optimal-emission-10pct` (**75.8 %**; 516,738 dots; halo 59.7 %).
A uniform-random dot would score 0.663 and 0.597 on the same leg, so the ratios are **1.21×** and
**1.27×** chance. This matches the direction of `IR-62-22` and adds the containment-to-null ratio as
the quantity to report. The never-waived legs say the opposite of copying: worst Spearman ρ over 340
comparators **0.0222** (limit 0.90) and worst exact Jaccard **0.00909** (`evidence/uniqueness_h62b.json`,
`evidence/uniqueness_h62b_verdict.json`). 32 of the 340 comparators are formally vacuous. Reported,
not suppressed; the selector decides.

### IR-62-B-12 — the shared renderer emitted a `DeprecationWarning` on every run (fixed)

`scripts/render_doc_pages.py` had `x.replace("\|", "|")`. `"\|"` is not a recognised Python escape,
so CPython keeps it as backslash-pipe and warns — `DeprecationWarning: invalid escape sequence`
(3.12+ promotes it to `SyntaxWarning`). The call is a no-op duplicate of the `.replace("\\|", "|")`
immediately before it, so the fix is behaviour-preserving: write it as a raw string, `r"\|"`.
Found because the root test suite now runs cleanly enough for one warning to be visible.
