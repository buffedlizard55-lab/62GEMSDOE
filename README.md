# 62GEMSDOE — datum-offset lane: Lake Lahontan shorelines as a strain gauge

**Competition:** DOE *Geologic Enhanced Mapping System (GEMS) Prize* (DrivenData #306, GeoDAWN /
northwestern Great Basin). Task: predict fault traces that are **not** in the USGS / INGENIOUS
catalogue, as a single-band 100 m GeoTIFF with values in `[0, 1]`.

**This session's lane (assigned by the run protocol below):** *datum-offset — map pluvial-lake
shoreline benches in the DEM, fit a smooth isobase allowing for post-pluvial isostatic rebound,
flag abrupt steps and lateral deflections along strike, seed a trace at each, extend it while
DEM-ridge evidence supports it, emit dotted lines.* Coverage is limited to pluvial-lake margins,
so this lane buys **defensibility more than area**.

---

## ⛔ Is it OK to download and submit the candidate?

### **NO — DO NOT SUBMIT**

The linked v8 GeoTIFF is an **archival artifact only**, not an approved submission:
[`docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif`](docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif).
It is a prior raster, and an independent strict check found a hard-stop duplicate condition:
1,601 of 1,660 positive dots (**96.45%**) fall within 3 px of `13GEMSDOE`'s r11 greedy-mp raster
(272,853 positive cells; required: **≤70%**); rank correlation was −0.3318 (limit: ≤0.90). The
fail-fast registry scan stopped after 9 of 525 rasters at this comparator. The result is
`DUPLICATE-STOP`, not a submission verdict.

The same old file also has finite zero-valued pixels outside the competition footprint, while the
official format requires null/NaN outside it. The corrected shared writer now emits NaN outside and
validates its bytes, but **the prior TIF has not been re-emitted** because the strict uniqueness
stop was reached. No slot is recommended or selected. The registry fetch covered 88 repositories
and 525 TIFFs; 12 repositories exceeded the 90 MB fetch cap, so the broad registry snapshot is
incomplete. The one independently checked comparator is already sufficient to stop.

**Evidence (not organizer scores):** `HOLDOUT-DTI`, evaluator `root-run_holdout-v3`, six spatial
blocks, 60,362 withheld catalogue positives, 95% spatial-block bootstrap CI `[0, 0.006842]`;
feature-alone canary AUCs were 0.5020 and 0.4999 (neither exceeds the 0.90 leakage threshold).
This is a catalogue proxy, not the competition's hidden-new-fault truth. No organizer-confirmed
submission receipt exists for this raster. Details: [`docs/executive-summary.md`](docs/executive-summary.md),
[`docs/run-card.md`](docs/run-card.md), [`evidence/lahontan_run_card_20261011.json`](evidence/lahontan_run_card_20261011.json).

### Format rules enforced by the shared writer

`src/gems62/grid.py::write_submission` writes NaN pixels outside the template footprint, leaves the
GeoTIFF nodata tag unset, then reopens and checks the bytes. This validates the local format only;
it does not establish uniqueness or organizer acceptance.

| requirement | local check |
| --- | --- |
| one band, `float32` | re-read from output |
| EPSG:32611, 100 m, 3730×3292, matching transform and bounds | compared to the pinned official sample grid |
| finite values in `[0,1]` inside the footprint | asserted before write and re-counted after |
| NaN outside footprint; no nodata tag | asserted from the written bytes |

---

## What is in this repository

| path | what it is |
| --- | --- |
| `src/gems62/metric.py` | independent implementation of the published DTI metric + the marginal-credit derivation |
| `src/gems62/grid.py` | competition grid, sha256 pins of the official rasters, submission writer + format receipt |
| `src/gems62/datum.py` | **the lane**: bench detection, isobase fit, step/deflection flagging, DEM-ridge trace extension, dotted emission |
| `scripts/fetch_3dep.py` + `.github/workflows/dem-fetch.yml` | transports the official USGS 3DEP DEM (the driving sandbox cannot reach USGS hosts; GitHub runners can) |
| `scripts/run_lane.py` | end-to-end: DEM → benches → isobase → loci → traces → submission GeoTIFF + receipts |
| `scripts/run_holdout.py` | hide-and-recover holdout (spatially blocked, buffer, pooled DTI, leakage canary) |
| `scripts/check_uniqueness.py` + `src/gems62/uniqueness.py` | strict stop if rho > 0.90 or raw Euclidean 3 px overlap > 70 % vs any registry raster; no dense-comparator exemption |
| `docs/` | executive summary, run card, hypothesis ranking, sources, irregularities, evidence JSON |
| `evidence/` | receipts committed by the GitHub runner: DEM provenance, network probes |

The 25 m Lahontan 3DEP DEM and official grid/catalogue mirrors are tracked in this checkout; the
418 MB feature stack is not present, and the full registry is external/transient. Availability and
reproduction limits are recorded in [`docs/data.md`](docs/data.md).

---

## Results so far (every number carries its evidence class)

| item | value | class |
| --- | --- | --- |
| published metric | `DTI = TP_w / (TP_w + 0.2 FP_w + 0.8 FN_w)`, `k(d)=max(1-d/300m,0)` | OFFICIAL (competition page 967, quoted in `docs/sources.md`) |
| published worked example reproduced | `3.00/(3.00+0.2·1.89+0.8·2.00) = 0.60` | OFFICIAL, reproduced in `tests/` |
| known USGS/INGENIOUS faults | masked/excluded from scoring in both rounds | OFFICIAL (organizer post, thread 11516) |
| "new fault" | any pixel not captured by USGS/INGENIOUS, **including new geometry of an existing system** | OFFICIAL (organizer post, thread 11536) |
| Phase 2 label set | updated by expert review of Phase 1 submissions | OFFICIAL (organizer post, thread 11527) |
| historical v8 holdout | **0.002863**, 95% cluster-bootstrap CI `[0, 0.006842]`, 60,362 withheld positives; **not a score** | HOLDOUT-DTI (`root-run_holdout-v3`, six spatial blocks; `evidence/holdout_v8_strict_review.json`) |
| feature-alone leakage canary | AUC 0.5020 and 0.4999; below the 0.90 alarm | HOLDOUT-DTI canary (`evidence/holdout_v8_strict_review.json`) |
| historical v8 strict registry check | **DUPLICATE-STOP**: raw 3 px overlap 0.9645 (1,601/1,660) vs 13GEMSDOE r11-greedy-mp (limit 0.70); rho −0.3318; stopped after 9/525 TIFFs | LOCAL-STRICT-REGISTRY-CHECK (`evidence/uniqueness_v8_strict_review.json`) |
| historical v8 format | `legal = false`; finite zeros remain outside footprint, failed `all_nan_outside_footprint` | LOCAL-FORMAT-CHECK (`grid.check_submission`) |
| organizer scores of any file here | **none exist** | no ORGANIZER-CONFIRMED receipt |

Scores the user reported for earlier sites (0.2778, 0.3774, …) are recorded in
`docs/irregularities.md` **as claims**, with what could and could not be verified.

---

## THE BRIEF (kept verbatim, re-read at the start of every session)

The full session brief is reproduced below so that the aim, the lane, the parallel-run protocol
and the constraints are always in front of whoever (or whatever) works on this repository next.
Read it before changing anything.

<details>
<summary><b>Click to expand the complete original brief</b></summary>

### Session brief (verbatim)

Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS SUBMISSION
UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION. IT MUST BE
OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt. Read the
entire prompt.

**Datum-offset lane: Lake Lahontan shorelines as a strain gauge.** In the northwestern Great
Basin the Lahontan highstand shoreline is a near-level datum about 15 ka. Briggs and Wesnousky
(JGR, 2004) used features displaced since the highstand to constrain slip on the Pyramid Lake
fault zone. Dong and coauthors (Geosphere) documented Lahontan shorelines displaced along a
strike-slip fault outboard of the Wassuk Range front. Lidar mapping nearby has also found faults
missing from earlier maps: Pierce and Wesnousky (SCEC poster, 2016) report two previously
unmapped northwest-striking segments in Smith Valley's basin centre offsetting Holocene
sediments. Map shoreline benches in the DEM and fit a smooth isobase, allowing for post-pluvial
isostatic rebound. Flag abrupt steps or lateral deflections along strike, seed a trace at each,
extend it while DEM-ridge evidence supports it, and emit dotted lines. First deliverable:
shoreline elevation-versus-distance profiles with the flagged steps. If only a handful are
convincing, emit only those. Coverage is limited to pluvial-lake margins, so this lane buys
defensibility more than area. Output the standard validated GeoTIFF, uniqueness-checked against
every earlier raster.

**PARALLEL-RUN PROTOCOL — read first.** This session is one of several running from this same
prompt.

1. **LANE.** Your lane is the single method paragraph below. Stay inside it. If your raster's
   rank-correlation with any registry raster exceeds [0.90], or more than [70 %] of your dots
   fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as
   a duplicate and stop. Check this on the surface before placement AND on the final dots.
2. **REUSE, DON'T REBUILD.** Use the template's cached feature stack, `evaluate_holdout.py` and
   `submission_writer.py`. Holdout = hide-and-recover: withhold whole fault segments with a
   buffer, derive every catalogue-based feature only from the visible faults, mask visible
   faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a
   shared tool is wrong, fix it once in the template and report it; never keep a private fork.
3. **LABEL EVERY NUMBER** as HOLDOUT-DTI (evaluator version, number of withheld positives,
   95 % CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is
   never written as a score.
4. **LEAKAGE CANARY.** Test each feature alone on the holdout before trusting any result. AUC
   above [0.90] means leakage until proven otherwise.
5. **RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault process that
   could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator
   output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission
   name + note of at most 140 characters; verdict promote / negative. Negative results are
   deliverables.
6. **BUDGET.** Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a
   real slot is a separate selector step, within the weekly cap shown on the submission page.

The following sites should serve as a starting point for understanding how to generate TIF
submissions. These websites are researched, and tested and have generated TIF submissions. But we
need to generate high scoring submissions. Here are the results from submissions into the
competition, separated by .... (list of ~60 sibling sites and their claimed scores omitted here
for brevity — the claims are tabulated in `docs/irregularities.md`, each tagged with its
provenance and whether it could be verified.)

We need to quickly look at the results and results from the GEMSDOE websites above.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each
naming: the specific layer(s) involved, the physical signature being targeted (e.g., an
edge-detection or curvature transform), why it should catch a fault missing from the
USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already
implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate
the top candidate on our spatially-blocked holdout set before touching a weekly submission slot —
do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a
candidate can't be validated without new external data, name the specific free, official source
needed and check it's obtainable before proposing the idea as viable. → `docs/hypotheses.md`

Work line by line verifying from official verified trusted sources, provide links for manual
review. There should be no manual input, work on your own to complete tasks. Flag any
irregularities for review. No hallucinations. Verify no hallucinations.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done
so we should be able to figure out a way to score higher on the leaderboard using previous
results and scoring that we have across the sites listed above. We need to come up with distinct
and unique strategies to score higher in this competition leaderboard. We need to start doing
heavy and deep research into the part of the project that matters the most, which is the
scientific discovery of geothermal vents. We should store all of our information and knowledge
that we can gather from official verified sources. This will serve as a starting point for other
projects as well. We need to think outside the box but still be grounded in proper scientific
research, we are ultimately aiming for a top prize that many others are competing for. So it's
important to be contrarian but be smart about it. We need to find sources of data that others are
over looking or areas of the project when it comes to geothermal vents. We need to do deep
research and critical thinking and come up with new hypothesis to test.

0.3195 is the highest score right now so we need to design a new strategy, research, testing,
analyzing, and generating submission system than the current website. It should be unique, take
unique approaches to generating a submission that can score higher than 0.3195.

Put this prompt into the repo readme and read it everytime we work on the project as a starting
point to make sure we are building what we are aiming for and have a strong base to continue
building and improving on making something useful for everyday use. It should solve the problem
of having to manually check everything ourselves and having an up to date current feed.

Review the repo.

The following is taken from the Arena AI team and I think it makes a good point on building a
successful project, so let's keep the Core Values and Own the Outcome as a focal point when
building, developing, researching, suggesting upgrades, and implementing the work.

**Our Core Values.** *Maximize P(Win)* — "Maximize the Probability of Winning": our decision
making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that
maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions
in order to maximize P(Win). "Maximize P(Win)" frees us from constraints and clarifies that we
must put Arena first. *Own the Outcome* — We own results end to end — not just our individual
slice of the work. When problems arise and we have the means to act, we do so without waiting for
permission or assignment. We treat failure and success as signals and use them to improve. At
Arena, we stay accountable to the final outcome.

We need to focus on being able to generate a submission into the competition. The site should be
able to generate a TIF file that is required for submission. It should be as easy as download to
click a File to submit into the competition. This needs to be in the executive summary or the
very beginning of the site. it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the
submission form: "Predicted values must be in range [0, 1]". Also we need to give it a unique
name and A short comment to help you or your team tell submissions apart later e.g. clustering
with k=25.

New submission — File to submit. You can submit a single-band GeoTIFF (.tif) file, or a .zip file
containing a single GeoTIFF, with your predictions. It must match the submission format's CRS,
shape, and geotransform. You may wish to review the competition rules first. Note (optional): A
short comment to help you or your team tell submissions apart later e.g. clustering with k=25.

Create a executive summary subpage that explains exactly how to make a submission into the
contest. Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition. […] We need to
create a project that can compete and place top of the leaderboard. We need to understand the
problem, collect all the data and organize it into a clean easily auditable table with official
verified links for manual verification. […] Download the data from the data tab. Create and train
your own model. Use your model to generate predictions that match the submission format. Tell me
what are you limitations and what you need access to during this project. We will need to find
free publicly available sources and data from official and verified sources if we are to use 3rd
party or external data. This pdf outlines how submissions must be entered into the competition:
https://docs.nlr.gov/docs/fy26osti/96647.pdf . You must be able to do your own research, deep
research, scientific literature research and organize the knowledge so that we can critically
think through the problem and generate a solution through scientific and free publicly available
information. this must be done autonomously and must be constantly reviewed and improved upon.
Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif,
sample_submission.tif, 1m_DEM_links.csv from the data tab (verified redirect to login). See below
for links from the above site. […] Work line by line verifying from official verified trusted
sources, provide links for manual review. There should be no manual input, work on your own to
complete tasks. Flag any irregularities for review. No hallucinations. Verify no hallucinations.

**The single remaining blocker to training is data placement**: run
`bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then
`python scripts/prepare_data.py` — after that the full train→inference→validate pipeline is ready
to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

you need to complete the above task by yourself. Work line by line verifying from official
verified trusted sources, provide links for manual review. There should be no manual input, work
on your own to complete tasks. Flag any irregularities for review. No hallucinations. Verify no
hallucinations. The goal of this project is to get a full list that follow our requirements. No
hallucinations. Verify line by line.

Run this task through multiple passes. Pass 1: Implement the task completely and verify the
result. Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge
cases. Fix everything you find. Pass 3: Re-check the entire implementation against the original
request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.
Do not stop after the first pass. Each pass must build on the previous one. Before finishing,
verify that the final result fully satisfies the original request. Work line by line verify
everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make
suggestions for what work still needs to be done and any limitations that is in the way of a
successful project. It should be worked on in this next session or the next session.

</details>

---

## Verified state and safe next steps

This checkout currently has **no cleared submission TIF**. The historical v8 artifact is
`DUPLICATE-STOP` under the literal raw-overlap rule and fails the current NaN-outside format check.
Do not rerun the old pipeline to create a downloadable candidate without first persisting and
passing a pre-placement surface gate; then recheck final dots after emission.

Re-run local code tests with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests -q
```

Current evidence and access limits are maintained in [`docs/next-steps.md`](docs/next-steps.md),
[`docs/data.md`](docs/data.md), and [`docs/run-card.md`](docs/run-card.md). The failed historical
TIF, strict registry receipt, and HOLDOUT-DTI receipt are linked at the top of this README.
No weekly slot is selected or recommended.

The `lane62/` directory is a separate archived parallel run and is not part of this review's
candidate selection. Its historical artifacts and uniqueness reports are not used to clear the
root v8 TIF; each would require its own strict registry and format checks before use.
