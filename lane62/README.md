# 62GEMSDOE — Lake Lahontan shoreline datum-offset lane

**DOE GEMS Prize** · DrivenData competition #306 · branch `arena/4e304372-62gemsdoe` · 2026-10-11

Site: `docs/index.html` (serve with `python3 -m http.server 8080 --directory docs`)
· [Executive summary & how to submit](docs/executive-summary.html)
· [Results](docs/results.html)
· [Profiles — deliverable 1](docs/profiles.html)
· [Research & hypotheses](docs/research.html)
· [Sources](docs/sources.html)
· [Irregularities](docs/irregularities.html)
· [Run card](docs/run-card.html)

---

## 1. THE STANDING BRIEF — read this first, every session

*Transcribed from the session's standing prompt (2026-10-11); the section headings,
the protocol rules and the bracketed thresholds are as issued. This section is the
acceptance criteria, not a summary of them.*

> **THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!**
>
> **MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.** DO NOT COPY A PREVIOUS
> SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF
> SUBMISSION. IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF
> SUBMISSION.
>
> There should be an easy to download submission tif file as described by the prompt. Read
> the entire prompt.
>
> **Datum-offset lane: Lake Lahontan shorelines as a strain gauge.** In the northwestern
> Great Basin the Lahontan highstand shoreline is a near-level datum about 15 ka. Briggs and
> Wesnousky (JGR, 2004) used features displaced since the highstand to constrain slip on the
> Pyramid Lake fault zone. Dong and coauthors (Geosphere) documented Lahontan shorelines
> displaced along a strike-slip fault outboard of the Wassuk Range front. Lidar mapping
> nearby has also found faults missing from earlier maps: Pierce and Wesnousky (SCEC poster,
> 2016) report two previously unmapped northwest-striking segments in Smith Valley's basin
> centre offsetting Holocene sediments. Map shoreline benches in the DEM and fit a smooth
> isobase, allowing for post-pluvial isostatic rebound. Flag abrupt steps or lateral
> deflections along strike, seed a trace at each, extend it while DEM-ridge evidence supports
> it, and emit dotted lines. First deliverable: shoreline elevation-versus-distance profiles
> with the flagged steps. If only a handful are convincing, emit only those. Coverage is
> limited to pluvial-lake margins, so this lane buys defensibility more than area. Output the
> standard validated GeoTIFF, uniqueness-checked against every earlier raster.
>
> **PARALLEL-RUN PROTOCOL — read first.** This session is one of several running from this
> same prompt.
>
> 1. **LANE.** Your lane is the single method paragraph below. Stay inside it. If your
>    raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of
>    your dots fall within 3 px of one registry raster's dots, you have drifted into another
>    lane: log it as a duplicate and stop. Check this on the surface before placement AND on
>    the final dots.
> 2. **REUSE, DON'T REBUILD.** Use the template's cached feature stack,
>    `evaluate_holdout.py` and `submission_writer.py`. Holdout = hide-and-recover: withhold
>    whole fault segments with a buffer, derive every catalogue-based feature only from the
>    visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta
>    0.8, 300 m triangular kernel). If a shared tool is wrong, fix it once in the template
>    and report it; never keep a private fork.
> 3. **LABEL EVERY NUMBER** as HOLDOUT-DTI (evaluator version, number of withheld positives,
>    95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is
>    never written as a score.
> 4. **LEAKAGE CANARY.** Test each feature alone on the holdout before trusting any result.
>    AUC above [0.90] means leakage until proven otherwise.
> 5. **RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault process
>    that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256;
>    validator output (no NaN inside the footprint, values in [0,1], CRS/shape/transform
>    match); submission name + note of at most 140 characters; verdict promote / negative.
>    Negative results are deliverables.
> 6. **BUDGET.** Stop after [3] experiments or [2] hours. Do not pick submissions: promotion
>    to a real slot is a separate selector step, within the weekly cap shown on the
>    submission page.
>
> Work line by line verifying from official verified trusted sources, provide links for
> manual review. There should be no manual input, work on your own to complete tasks. Flag
> any irregularities for review. **No hallucinations.**
>
> Run this task through multiple passes. Pass 1: implement and verify. Pass 2: review for
> bugs, missing requirements, incorrect assumptions, edge cases; fix everything found.
> Pass 3: re-check the entire implementation against the original request; improve accuracy,
> reliability, completeness and code quality.

**Our Core Values.**
**Maximize P(Win)** — "Maximize the Probability of Winning": our decision-making framework.
In every decision we weigh tradeoffs, assess risk, and choose the path that maximizes the
probability that Arena succeeds. We set aside our emotions and make tough decisions in order
to maximize P(Win). "Maximize P(Win)" frees us from constraints and clarifies that we must
put Arena first.
**Own the Outcome** — We own results end to end, not just our individual slice of the work.
When problems arise and we have the means to act, we do so without waiting for permission or
assignment. We treat failure and success as signals and use them to improve. At Arena, we
stay accountable to the final outcome.

---

## 2. STATUS OF THE NEWEST FILE — read this second

| question | answer |
|---|---|
| Where is the artifact? | [`docs/downloads/gems62-lahontan-datum-break-dotted-primary-zeros.tif`](docs/downloads/gems62-lahontan-datum-break-dotted-primary-zeros.tif) — 518,595 bytes, 86,968 dots, sha256 `f58ae055030e5edd…`; available for inspection only. |
| Is it OK to download? | **YES, for review only. DO NOT UPLOAD.** Single band, `float32`, EPSG:32611, 3730×3292, exact sample transform, all 12,279,160 cells finite, values in [0, 1], `nodata = None`, zero positive mass outside the footprint, 0 dots on the mapped catalogue. These are format checks only. |
| Is it unique under the required protocol? | **NO — DUPLICATE - STOP.** Strict maximum one-sided 3 px overlap is **1.00 > 0.70** across all 508 comparators. The max positive rank correlation is **0.0325 < 0.90**, so that leg does not trip. The lower 0.4066 overlap on the 321-comparator informative subset and Jaccard 0.030 are diagnostics, not waivers. The top comparator is dense enough to make the overlap test uninformative, but the protocol still says log duplicate and stop (`IR-62-04`). |
| Was the pre-placement surface gate passed? | **NOT VERIFIED.** No passing surface-before-placement receipt is present for this lane62 artifact. The final-dot strict trip already blocks submission. |
| Should it be given a weekly slot? | **NO.** Do not submit. The local HOLDOUT-DTI results are proxy measurements, not organizer scores; instrument B has no retained 95% CI and its evaluator is not version-tagged in the legacy record. |
| Has an organizer scored it? | **No.** No submission-page receipt is present; there is no ORGANIZER-CONFIRMED score. |
| What is the second file? | [`…flagged-breaks-selective-secondary-zeros.tif`](docs/downloads/gems62-lahontan-flagged-breaks-selective-secondary-zeros.tif) (87 dots) is also **DO NOT SUBMIT**: it fails the strict all-comparator overlap gate (maximum 1.00) and independently has 0.9885 overlap against a sparse comparator. |

¹ mean credit 0.12006 per dot on instrument B.

**Leaderboard claims are unverified here.** Prior drafts reported values such as 0.4133 and 0.2778,
but this checkout contains no current leaderboard export or submission-page receipt. Treat all such
figures as owner-reported, not ORGANIZER-CONFIRMED, and do not use them as competition scores.

---

## 3. WHAT THIS SESSION MEASURED, AND WHY THE LANE LOSES

1. **The metric's marginal bar is `α·s`.** From the published formulas,
   `DTI = T/(0.2T + 0.2F + 0.8K)`; a non-redundant dot raises the score iff its realised
   kernel credit exceeds `0.2·s`. At s = 0.2778 that bar is **0.055556** per dot. Every
   candidate in this repository is judged against it (`tests/test_metric.py`).
2. **The lane's most selective dot class is genuinely good per dot** — one dot per flagged
   datum break carries mean credit **0.157–0.161**, roughly 3× the bar — **but there are
   only ≈90 of them.** Ninety dots cannot move a denominator of `0.8·K ≈ 6,300`.
3. **At the mass end the credit collapses** to 0.039 per dot at 86,968 dots.
4. **The decisive control is same-instrument.** Comparing like with like on independent
   off-catalogue truth, the best registered prior field reaches **0.29294** per dot on
   45,000 dots. Lane/best-champion = **0.55**; the lane is dominated on *both* axes of the
   metric (credit density and count), so no amount of budget tuning rescues it.
5. **Forward lead for the selector (measured, not guessed):** the registry raster with the
   highest mean credit per dot on the same instrument is
   `gems32-bayesopt-dilation-scarp-d28-20261004-nan.tif` at **0.29294** — about 3× the
   0.2778 family's own dots. If instrument B predicts the portal at all, that family is
   where this group's remaining headroom sits.

**How to actually beat 0.2778**, stated as arithmetic rather than aspiration: with
`K ≈ 7,905` (the group's published inference of the hidden test mass) and the champion's
own measured dot class (mean credit 0.1022 at 37,654 dots → T = 3,849), the identity yields
exactly 0.2778. To reach 0.32 you need `T ≈ 4,430`, i.e. ≈ +580 credit at the same mass —
about 12,000 dots of a class that delivers 0.15 instead of 0.10. That is a **better
detector**, not a better emitter: no re-emission of an existing field closes the gap, which
is why this lane's negative result matters.

---

## 4. REPRODUCE

```bash
git clone https://github.com/buffedlizard55-lab/62GEMSDOE && cd 62GEMSDOE/lane62
python3 -m pip install -r requirements.txt

bash scripts/download_competition_data.sh     # hash-checks data/official/; never logs in
python3 scripts/prepare_data.py               # grid contract from the bytes
bash scripts/build_registry.sh                # comparison set for the uniqueness gate
python3 scripts/run_lane.py                   # traces, profiles, holdout, candidates
python3 scripts/exp2_selectivity.py           # experiment 2
python3 scripts/exp3_economics.py             # experiment 3
python3 scripts/verify_economics.py           # same-instrument control (verification)
python3 scripts/finalize.py                   # selection + receipts
python3 scripts/uniqueness_gate.py docs/downloads/*primary-zeros.tif
python3 scripts/build_site.py                 # regenerates every page from evidence/
python3 scripts/make_variants.py              # reproduces the NaN-outside twin (49 MB, not committed)
python3 -m pytest tests -q                    # 45 tests, incl. site/receipt consistency
```

GitHub Actions (`.github/workflows/ci.yml`) runs the same hash-pinned data download, the grid
contract, and the suite on every push.

---

## 4b. THIS LANE SHARES AN ASSIGNMENT WITH A SIBLING LANE ALREADY ON `main`

`main` carries an **independently merged datum-offset lane** (the sibling session's v8/v99
work: `docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif`, `src/gems62/{datum,emit,uniqueness,score_model}.py`,
`registry/`, `tools/`). A naive merge of this branch was add/add-conflicted in ten files because
both sessions used the same root paths. This session therefore lives entirely under `lane62/`
and touches **none** of the sibling lane's files; the sibling lane is left canonical at the root.

**Are the two artefacts copies of each other? No.** `lane62/scripts/crosscheck_sibling_lane.py`
re-runs the protocol's duplicate test against the sibling's shipped TIFs, with the same
convention as the 508-raster gate (positivity `value > 0`, "within 3 px" =
`binary_dilation(iterations=3)`, rank correlation sampled from the footprint):

| this lane's file | sibling file | one-sided 3 px overlap | exact pixel overlap | Spearman | verdict |
|---|---|---|---|---|---|
| primary (86,968 dots) | `gemsdoe62-datum-lahontan-isobase-v8.tif` | 0.0099 | 0.0005 | +0.0021 | distinct |
| primary | `gems62-lahontan-isobase-99dots-zeros.tif` | 0.0009 | 0.0000 | −0.0007 | distinct |
| primary | `gems62-lahontan-isobase-99dots-nan.tif` | 0.0009 | 0.0000 | −0.0007 | distinct |
| secondary (87 dots) | all three | 0.0000 | 0.0000 | −0.0001…0.0000 | distinct |

Evidence: `lane62/evidence/crosscheck_sibling_lane.json`. The shipped rasters are distinct from
one another under the recorded pairwise comparison, but **neither is cleared against the full
registry**: both strict all-comparator overlap gates trip against dense registry rasters. The
root v8 `UNIQUE-VS-REGISTRY` label is withdrawn; its preserved one-sided maximum is 1.00 (>0.70).
The lane62 primary also trips at 1.00. These are negative protocol results; do not submit either.

**One defect found while merging, reported and not fixed (out of lane).** After the merge the
repository-root suite cannot collect on a clean `origin/main` worktree either:
`src/gems62/lahontan.py` imports `PIXEL_M` from `src/gems62/grid.py` (not defined there), and
`tests/test_metric.py` imports `brute_force_components` from `src/gems62/metric.py` (not defined
there; both symbols exist in `src/gems62/superseded_20261011/`). Guessing which variant is
canonical would be a silent overwrite of another session's files, so it is logged as `IR-62-11`
and left to the lane that owns them. This lane's own suite is independent and green.

---

## 5. WHAT IS STILL BLOCKED, AND WHAT TO DO NEXT

**Blocked here (flagged as irregularities, not worked around):**

- The DrivenData **data page is login-walled**; a fetch on 2026-10-11 redirected to
  `/accounts/login/`. The organizer's `training_features.tif` (19 bands) and
  `1m_DEM_links.csv` therefore cannot be obtained from this sandbox. Hashing the
  owner-mirrored files authenticates the *bytes*, not their *origin* (`IR-62-07`).
- **No outbound TLS** to `sciencebase.gov`, `earthquake.usgs.gov`, the USGS 3DEP endpoints,
  `raw.githubusercontent.com` or `drivendata.org` from the shell. The competition pages
  contained in this repository's citations were read through the browsing path, which is why
  each one carries a read date.
- No GPU (~2 vCPU), so no neural detector was trained; this lane is deliberately physics-first.

**Next steps, in priority order (handed to the next session):**

0. **Read `main`'s sibling lane before spending anything.** It is the same assignment, it is
   already merged, and its README states its own honest expectation. The only reason this lane
   exists as a separate tree is that both sessions were told to stay in-lane; nothing here
   should be promoted over the sibling's v8 without the selector comparing the two.
1. **H62-B — per-flag screening on two independent compilations.** Highest value, lowest
   cost: the flag set is already on disk (`evidence/profiles.json`, 3,552 flags) and the
   registry is already downloaded. Ask whether flags that *two* independent compilations both
   miss carry a higher credit density than the raw ranking. This is the one cheap test that
   could overturn the negative verdict.
2. **H62-E — metre-scale shoreline pick (USGS 3DEP 1 m lidar, public domain).** This is the
   only way to fix the lane's core defect: at 100 m posting the berms are sub-pixel, which is
   why the median per-dot credit is 0. Blocked on network access; the named source is The
   National Map / 3DEP. With it, the lane could reasonably claim a *localisation* result
   rather than a coverage result.
3. **H62-C — replace the fitted isobase with a published rebound/viscosity model** (e.g. the
   Bills–Adams–Wesnousky profiles). Would repair `IR-62-03` and remove the dominant
   non-fault mimic.
4. **Run the selector** on the mean-credit-per-dot metric this session introduced (section 3
   point 5) before spending any weekly slot, and **re-read the leaderboard** rather than
   quoting the brief's stale numbers.

**Known limitations of this repository, stated plainly:** the isobase fit is degenerate in
its linear part (`IR-62-03`); the traces are the ζ = 0 contour of a block-median surface, not
a digitised shoreline; instrument B is a 1:750k public compilation, not the organizer's
private expert set (`IR-62-08`); and no file here has ever been scored.
