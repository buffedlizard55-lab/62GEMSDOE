# Remaining work and limitations

> Updated 2026-10-11 by session `arena/2b64062a-62gemsdoe`. The ranking below replaces the earlier
> one; the earlier text is preserved in git history. Everything here is either MEASURED in this
> checkout or explicitly labelled as a lead.

## What this session finished

* **The shared tools are fixed, once, in the template** — not forked. 6 of 9 root modules did not
  import on a clean checkout (`IR-62-11`); `lane62` errored on 14 tests for a file that was present
  (`IR-62-12`). Root suite **18 passed**, `lane62` suite **46 passed**, plus **9 new tests** that
  execute the shipped rasters and the leaderboard arithmetic.
* **A score-anchored registry now exists** — `research/registry_index.json` (87 distinct group
  rasters with owner-reported scores, harvested from 73 public repositories, 1,459 `.tif` blobs,
  166 registry/ledger JSONs) and `research/registry_measurements.json` (18 structural properties
  measured from each one's bytes). This is the dataset the group has been reasoning about anecdotally.
* **The leaderboard is now a committed time series** — 37 timestamped snapshots of the official
  public page, `research/leaderboard_series.json`.
* **Two hypotheses screened and reported, one refuted** — `docs/hypotheses-2026-10-11.md`.
* **A unique, legal, validated GeoTIFF is downloadable**, with an unambiguous negative verdict.

## Ranked next work

> **2026-10-12 correction (session `arena/778884cc`):** item 1 below is **RETRACTED** — see
> `docs/irregularities.md` IR-62-26. The bayesopt field's 0.293 credit/dot was measured on the
> SGMC instrument (Spearman −0.928 vs the portal); on the kernel-fixed portal-calibrated instrument
> (IR-62-25) it measures 0.0408 credit/dot, projection 0.0295. The corrected rank 1 is the new
> item 0.

### 0. (2026-10-12) Exploit the measured corridor headroom — the only evidence-backed path above 0.2778
gate_ortho scored 0.2376 with only 43.4 % of its dots inside the h33 3-px halo (IR-62-28): the
hidden truth is spatially broader than the group's consensus, and unique fields can score in the
top band. The instrument to design against is now `evidence/sstar_fixed/` (R² 0.70). Concretely:
rebuild the multi-physics oriented-lineament consensus **from the organiser 19-band stack** (H-2,
datum62) *including* the pixels the consensus family never sampled, and rank candidates by
DTI(S*†) per dot (champion family: 0.42; this lane: 0.059; do not ship below ~0.15/dot).

### 1. ~~Submit the never-scored high-credit field~~ — RETRACTED (IR-62-26), kept for the record
`GEMSDOE32 → docs/downloads/gems32-bayesopt-dilation-scarp-d28-20261004-zeros.tif` (302,357 bytes,
45,000 dots) measures **0.29294** mean 300 m credit per dot on the same instrument that scores the
submitted champion family at **0.09892** — 3.0×. It is absent from the 87-artifact score registry,
i.e. never submitted. **This is a selector decision, not a lane decision**, and the number must be
discounted hard (the closed form turns it into an implausible 0.71). Even at a 4× discount it clears
the top-5 cut-off.

### 2. H62-K — along-strike continuation into catalogue gaps
The only hypothesis that targets the population the organizers actually describe ("newly mapped
geometry of existing systems"). Nothing in this repository uses the catalogue's *geometry* as a
prior; every lane uses it only as a mask. Spec and risk in `docs/hypotheses-2026-10-11.md`.

### 3. Get one ORGANIZER-CONFIRMED number into `evidence/`
Still zero. The submission page is the only channel that exists. Until one receipt is committed,
every comparison in this repository is a proxy argument.

### 4. Replace the fitted isobase with a published rebound model
Blocks H62-J and repairs `IR-62-03`. Taking a second derivative of a degenerate fit is how phantom
signals are made.

### 5. Raise LiDAR coverage or drop the layer
`lidar_scarp_features_u8.tif` is non-zero over **31.72 %** of the grid. That — not the geology — is
what caps every LiDAR-driven field in this group, including the 0.2778 family. Either extend the
composite (USGS 3DEP 1 m, public domain) or stop treating it as basin-wide.

## Limitations — stated as limitations, not as future work

1. **No local instrument can certify novelty or competitiveness.** This session's own screening
   refuted a hypothesis that looked obvious (lake flats, 0.03× control) and confirmed one that is
   then unusable (LiDAR scarps, 2.2× control, duplicate-drift). Both outcomes came from a proxy.
2. **The datum lane is dominated, and now for a measured reason.** The Lahontan datum band scores
   **0.61× the isolated-random control** on the off-catalogue instrument. Either the band is not
   fault-rich, or a 1:750 k compilation cannot see 2 m datum offsets. The two cannot be separated
   without the organizer's truth.
3. **Coverage of the delivered file is one sub-region of one physical process.** 10,000 dots on
   shoreline benches. The metric needs ~40,000 isolated dots to matter at all.
4. **The 25 m DEM mosaic is unusable basin-wide** (`IR-62-15`): 55.74 % footprint coverage and an
   int16-decimetre ceiling at 3276.7 m that clips the eastern Sierra. The 100 m mirror was used
   instead (99.97 % coverage, sha256 matches the pin).
5. **The weekly slot decision is not made here.** Per the brief, promotion is a separate selector
   step within the weekly cap.
6. **Sandbox reachability is a hard constraint.** `drivendata.org` returns HTTP 000; the USGS hosts
   are unreachable. `github.com`, `api.github.com` and `codeload.github.com` work, which is how the
   registry and the external layers were obtained. Every competition-page citation in this
   repository is therefore either an owner-supplied link or a mirror with a read date.
7. **No file in this repository has ever been scored.** `organizer_score` is `null` everywhere.


## Added 2026-10-11 by session `arena/dfc9787b-62gemsdoe` (d-lane extension)

* **New artifact (legal, unique, disclosed probe):**
  `docs/downloads/gems62d-org-stack-inverted-truth-detector-46598-zeros.tif` — 46,598 dots,
  sha256 `4d83efff…`, 14/14 checks, worst informative Jaccard 0.069 over 100 comparators,
  DTI(`S*`) 0.21777 → projection 0.110. 89× better than the previous v8 file on the calibrated
  instrument, still below the 0.24–0.28 incumbent band.
* **New instrument (the real deliverable):** `datum62/scripts/invert.py` + `datum62/evidence/` —
  inverting 56 owner-reported scores recovers a truth surrogate `S*` reproducing them at
  Spearman **+0.968**. Any future candidate can now be ranked locally *without* spending a slot.
* **Retire the old instruments.** SGMC off-catalogue ranks **−0.928** against the portal over the
  15 artifacts with owner-reported scores; the catalogue-segment holdout is documented
  anti-correlated (IR-30-046). Fields promoted on them were promoted on an inverted signal.
* **Blocked but highest value:** a field on `S*` projects 0.34–0.42 but duplicates the incumbent
  h33 field by the protocol's own test — documented, not emitted
  (`datum62/docs/decision-note.md`). This needs an owner decision on whether shared pixels of
  public prior submissions are permissible; the competition ruleset does not forbid it.
* **H-2 next:** rebuild the incumbents' multi-physics oriented-lineament consensus *from the
  organiser 19-band stack* as **features** for the supervised detector; target blocked
  DTI(`S*`) ≥ 0.60 before any slot is spent.

## Added 2026-10-11 by session `arena/d0303476-62gemsdoe` (branch `arena/d0303476-62gemsdoe`)

### Ranked, with the measurement that produced the rank

1. **Get one ORGANIZER-CONFIRMED score into `evidence/` — now the single highest-value action.**
   This session measured what the two local instruments are worth over **20** owner-reported scores
   (`evidence/e2b_reference_frame_20261011b.json`, `evidence/e4_gates_20261011b.json`):
   * credit per dot against SGMC 1:750 k minus catalogue → **ρ = +0.617** (p = 0.0038) with the leaderboard;
   * credit per dot against the **mapped** catalogue → **ρ = −0.597** (p = 0.0054);
   * the published DTI *evaluated on* the SGMC instrument → **ρ = −0.442** (p = 0.0513).
   The third line is new and it invalidates promotion by proxy metric: the two highest DTI values on
   that instrument belong to a 0.0904-scoring lattice and to a never-submitted file.

2. **Retire the two promotion gates.** The segmented catalogue holdout is anti-correlated with the
   leaderboard (`IR-62-HOLDOUT-01`, ρ = −0.9141), and this session's field fails it at 0.00073 *for
   the measured reason that it obeys the leaderboard's own preference* (stay off the mapped
   catalogue). A gate that rewards the opposite of the target is worse than no gate.

3. **Spend the next slot on a paired experiment, not on a bigger field.** §2(c) of
   `docs/research/beating-02778-2026-10-11b.md` makes the mass term exact and cheap to reason about
   (`DTI = c/(0.2 + 0.8K/M)`), and the group's own history shows its credit falling faster than the
   mass term gains. One field at 120,000 dots with the *same* detector as a 40,000-dot field
   measures `dc/dM` directly — the one number nobody in this group has.

4. **H62-M — along-strike catalogue extension** (untried; specified in
   `docs/hypotheses-2026-10-11b.md`). It is the only construction that targets *by design* the
   population the organizers explicitly include ("newly mapped geometry of existing systems",
   thread 11536), and its dots are off-catalogue by construction.

5. **Screen H62-Q (geothermal proximity) before the next structural bet.** It is the only untried
   hypothesis that speaks to the competition's stated purpose, it needs one free official dataset
   (DOE Geothermal Data Repository wells/springs, `https://gdr.openei.org/`), and it needs the
   GitHub-runner transport that already exists for the DEM. The test is fixed in
   `docs/hypotheses-2026-10-11b.md`: per-dot credit inside vs outside a 5/10/20 km buffer, with a
   mass-matched random control. Below 1.0× it dies; above 1.5× it multiplies H62-L.
6. **Resolve `IR-62-21` / `docs/data.md` §1:** the official stack carries **19** bands with their own
   `band_name` tags in the file (verified this session by re-reading the bytes,
   sha256 `4371c82e…` = the pin), not the 35 claimed in `docs/data.md`. Band names are therefore no
   longer "second-hand"; the docs need one edit.

### Limitations this session could not remove

* **Still zero organizer-confirmed scores.** Every number in this repository is a proxy.
* `drivendata.org` and USGS hosts remain unreachable from the sandbox; GitHub is the transport.
* The official stack's coverage is complete inside the footprint (measured: 5,167,373 cells with no
  nodata), but the 1 m LiDAR scarp composite covers 75 % of the footprint and the 3 m scarp product
  58 %, so ~25 % of the grid is mapped only from 10 m topography.
* The protocol's "≤ 70 % of dots within 3 px of one registry raster" leg is **unsatisfiable by any
  field** (measured: uniform-random 0.9987, 3 px lattice 0.9988 against the same comparator).


## Added 2026-10-12 by session `arena/b7846648-62gemsdoe` (datum-offset lane)

The ranking above (`arena/d0303476`, 2026-10-11b, then corrected by `arena/778884cc` on 2026-10-12)
stands as the group's list; this one is what the datum lane would add to or change in it, with the measurements behind every line in `evidence/h62j*`
and `docs/run-card.html`. Where the two disagree the disagreement is named, not averaged.

1. **The `GEMSDOE32` rank-1 advice is retracted, and this lane agrees — drop it.** It was written from
   instrument-B credit **0.29294** (3.0× the submitted family's 0.09892, no owner-reported score anywhere)
   and it has now been killed twice from independent directions: session `d0303476` measured that
   per-dot credit on that instrument tracks the leaderboard at ρ = **+0.617** while the published DTI
   evaluated on it tracks it at **−0.442** (`IR-62-20`, their numbering), and session `778884cc`
   re-measured the same field on the kernel-*fixed* portal-calibrated instrument at **0.0408 credit/dot,
   projection 0.0295** — below their own lane file and ~10× below the champion family (`IR-62-25`/`26`,
   including the S* kernel-radius bug that inflated every earlier projection). Two proxies now point the
   same way; no slot. **What this lane adds, and what survives the retraction:** the band table says any
   detector's mass should sit *near* a mapped trace, not beyond 4 km — a placement rule, not a ranking.
2. **Run the collar ladder — it is now the cheapest untried experiment in the group.** The band table
   (this session, `evidence/h62j-bands.json`) measures per-dot credit 0.178 / 0.153 / 0.108 inside
   500 m of a mapped trace against 0.018 beyond 4 km, with same-band controls giving ratios 1.33 / 1.21 /
   1.29 versus 0.51. Every lane here emits dots *pushed away* from the catalogue by a 250–300 m collar.
   Emitting the same detector at collars {200, 300, 500, 1000} m and comparing model DTI costs one sweep
   per lane and settles whether "new geometry" should mean *near the trace* rather than *far from it*.
   Note the asymmetry that makes this non-trivial: dots within ~250 m of the catalogue are masked out of
   the organiser's truth, so the gain has to come from the flanking damage zone, which is exactly what
   0.108–0.178 per dot says is there.
3. **H62-K, along-strike continuation of mapped systems into DEM-evident but unmapped ground.** Still
   untried, still the best physical idea in the lane, and now with a measured reason to expect it to
   work: continuation is by construction 0–1,500 m off a trace, the band this session found pays 2–5×
   the far field. Inputs already in the checkout: `qfault_attributes.csv`, `trace_segments_utm11.csv`,
   `gdr_qfaults_traces.csv`.
4. **The datum lane needs coverage, not cleverness.** 9.42 % of footprint cells are measurable by the
   doublet at all (`IR-62-22`), which caps mass at 10,870 dots and the lane's ceiling at 5 × credit =
   0.203. Reaching a footprint-wide datum field means the remaining 12–16 3DEP tiles on the
   `dem-fetch.yml` runner (~90 min, >90 MB) — a real cost, worth spending only after (2) or (3) show
   the *method* beats chance at full coverage.
5. **Geothermal: stop using thermal occurrences as structure, for this metric.** Measured 0.75–0.84×
   control for Hot/Warm cells and corridors, 0.10–0.21× for mapped vents (`evidence/h62j2-geothermal.json`,
   mass-matched controls). If the geothermal lane still wants thermal data, it must be as a *prior
   weighted by the band table*, not as a placement rule — and the burden is now on it to show that.
6. **The claim-vs-bytes gate exists and should run in CI.** `scripts/audit_downloads.py --write` now
   generates every download verdict from the file bytes, `tests/test_download_manifest.py` (10 tests)
   fails on drift, and `scripts/render_doc_pages.py --check` fails when a `.md` and its `.html` disagree.
   Next step: add all three to `.github/workflows/ci.yml` so a stale site claim cannot be merged.
7. **Still true from before:** holdout and SGMC instruments are diagnostic, never gating; `S*` is never a
   placement objective; no file here has an organiser-confirmed score.
## Added 2026-10-12 by session `arena/7b275dfb-62gemsdoe` (branch `arena/7b275dfb-62gemsdoe`)

### Ranked, with the measurement that produced the rank

1. **Spend one weekly slot on a receipt — still the highest-value action.** This session shipped the
   group's best primary-data detector on the fixed-kernel instrument (blocked DTI(S\* v2) 0.1979 at
   125,890 dots, +15 % over raw bands) but every number is still a proxy. One ORGANIZER-CONFIRMED
   row in `evidence/` calibrates everything.
2. **Mass-credit transfer experiment (H62-N), now runnable from an own field.** The pre-registered
   condition from `docs/research/beating-02778-2026-10-11b.md`: at 120k isolated dots the hidden-set
   credit must exceed 0.0778 per dot to beat 0.2778. This session's field is the first own field with
   a measured same-instrument improvement; re-emit its OOF ranking at 40k and 200k to measure
   `dc/dM` directly, as the 2026-10-11b session prescribed.
3. **H62-M — along-strike catalogue extension**, still untried and still the only construction that
   targets "newly mapped geometry of existing systems" by design (specified in
   `docs/hypotheses-2026-10-11b.md`).
4. **Vent-node point process (H62-Z5)** — the surviving half of the geothermal hypothesis after the
   proximity refutation (e5: 0.64× control). Cross-K test of vent points against lineament nodes;
   if the node interaction fails too, retire the vent family with a measured negative.
5. **Fix `docs/data.md` §1 (IR-62-21)** — the stack is 19 bands, not 35. One-line edit, done in
   passing if a session touches that file.

### Limitations this session could not remove

* **Zero ORGANIZER-CONFIRMED scores.** Every comparison remains a proxy argument.
* The h30 proximity (0.692 vs 0.70, IR-62-26) needs a human eye before the slot is spent: the
  letter of the protocol passes, the spirit is "disclosed enrichment".
* The S\* v2 instrument is still a *fit to 56 self-reported scores* — its truth is the group's
  behaviour, not the organizers' labels. A detector trained toward it inherits that limitation.
* `drivendata.org` and USGS/GDR hosts remain unreachable from the sandbox; all transport is GitHub
  mirrors with sha256 receipts.
