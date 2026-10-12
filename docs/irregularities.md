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


## Added 2026-10-12 (session `arena/b7846648-62gemsdoe`)

### IR-62-19 — the organiser's own `sample_submission.tif` fails this lane's format contract

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

1. **A range check written as `0 <= min and max <= 1` is NaN-poisoned.** Min/max over a file whose
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

### IR-62-20 — `int(round(250 / 100))` is 2: a 250 m collar is not what the code meant

The first `run_h62j.py` converted a metres-unit catalogue collar to pixels with `int(round(m / 100))`.
Python's `round` is banker's rounding, so 250 m became **2** cells, not 3 — a Chebyshev-2 collar whose
realised minimum Euclidean dot-to-catalogue distance is **223.6 m**, not 250 m. Nothing raised an error;
the gate silently measured a different quantity than its name claimed. Measured facts after the fix, on
the emitted field: 0 dots on the catalogue, minimum distance to it 223.6 m, 340 of 8,571 within 300 m.

Two rules follow, and both are now how this lane writes code: convert metres to cells with `ceil`, and
**report the realised distance the bytes contain, never the intended one**. A "250 m collar" in a run card
is a claim about arithmetic; a "minimum dot-to-catalogue distance 223.6 m" is a claim about the file.

### IR-62-21 — a JSON manifest that is not JSON: `NaN` is valid in Python and invalid in JSON

`json.dumps` happily writes `NaN` for a non-finite float, and the browser then refuses to parse the file.
The audit records `min`, `max`, `nodata` and `total_mass` straight from NumPy, and `data/sample_submission.tif`
— measured as the reference example — is all four at once (`total_mass: NaN`, because its raw sum includes
7.1 M NaN pixels). Every manifest is now passed through `jsonable()`, which writes `null` and prints that
it did, and the audit records `"NaN"` as a *string* where a value is genuinely non-finite so the field is
readable instead of silently null. Recorded because the same trap has already cost this group a scored
sibling in the mirror, and because a generator that emits unparseable evidence is worse than no generator.

### IR-62-22 — "the DEM covers X % of the footprint" had no X until it had a definition

Three numbers were in circulation for the same raster this session: 55.7 %, 29 %, 9.4 %. All three are
correct of different quantities, measured here on the 100 m grid: the DEM **extent** contains 2,878,929 of
5,167,373 footprint cells (**55.71 %**, matching `IR-62-15`'s 55.74 % under its area definition); **52.24 %**
of footprint cells have a finite elevation; and only **9.42 %** (486,753 cells) sit inside a 4 km isobase
tile that the doublet pipeline can actually measure — which is the number that caps this lane's mass.
A "coverage" claim without its numerator and denominator is not a measurement, and the site now states
all three with their definitions.

### IR-62-23 — the two lane suites cannot be collected in the same pytest process

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

### IR-62-24 — this README asserted the root suite cannot collect; it can, and did, on this checkout

`README.md` (the `lane62-h62a/` addendum, line ~441) states that `pytest tests/` at the repository root
"still cannot collect" because `src/gems62/lahontan.py:50` imports a `PIXEL_M` that `grid.py` never
defines and `tests/test_metric.py:17` imports a `brute_force_components` that `metric.py` never defines.
Both symbols exist now — `PIXEL_M` is restored additively in `src/gems62/grid.py` by the `IR-62-11` fix
and `brute_force_components` is defined at `src/gems62/metric.py:254` — and `pytest tests -q` on this
checkout reports **54 passed** in 8.2 s. The claim was true when written and is now stale; it is
corrected rather than deleted so the sequence is visible, and `.github/workflows/ci.yml` grew a root job
that runs `pytest tests -q` plus the download audit, so the statement cannot silently go stale again.
