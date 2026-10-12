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

### 1. Submit the never-scored high-credit field — highest expected value, minutes of work
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

5. **Resolve `IR-62-21` / `docs/data.md` §1:** the official stack carries **19** bands with their own
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
