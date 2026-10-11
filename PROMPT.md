# Operating brief — read this first, every session

This file is the standing brief for the `62GEMSDOE` line of work. It is read at the
start of every session and is the base we build on. It is reproduced here so that the
aim, the constraints and the protocol never have to be reconstructed from memory.

---

## Part 1 — The lane (this session's assignment)

> **Datum-offset lane: Lake Lahontan shorelines as a strain gauge.** In the
> northwestern Great Basin the Lahontan highstand shoreline is a near-level datum about
> 15 ka. Briggs and Wesnousky (JGR, 2004) used features displaced since the highstand to
> constrain slip on the Pyramid Lake fault zone. Dong and coauthors (Geosphere)
> documented Lahontan shorelines displaced along a strike-slip fault outboard of the
> Wassuk Range front. Lidar mapping nearby has also found faults missing from earlier
> maps: Pierce and Wesnousky (SCEC poster, 2016) report two previously unmapped
> northwest-striking segments in Smith Valley's basin centre offsetting Holocene
> sediments. Map shoreline benches in the DEM and fit a smooth isobase, allowing for
> post-pluvial isostatic rebound. Flag abrupt steps or lateral deflections along strike,
> seed a trace at each, extend it while DEM-ridge evidence supports it, and emit dotted
> lines. **First deliverable: shoreline elevation-versus-distance profiles with the
> flagged steps.** If only a handful are convincing, emit only those. Coverage is
> limited to pluvial-lake margins, so this lane buys defensibility more than area. Output
> the standard validated GeoTIFF, uniqueness-checked against every earlier raster.

## Part 2 — Parallel-run protocol (binding on every session)

1. **LANE.** Stay inside the single method paragraph above. If the raster's
   rank-correlation with any registry raster exceeds **0.90**, or more than **70 %** of
   the dots fall within 3 px of one registry raster's dots, the session has drifted into
   another lane: log it as a duplicate and stop. Check on the surface *before* placement
   **and** on the final dots.
2. **REUSE, DON'T REBUILD.** Use the template's cached feature stack, `evaluate_holdout.py`
   and `submission_writer.py`. Holdout = hide-and-recover: withhold whole fault segments
   with a buffer, derive every catalogue-based feature only from the visible faults, mask
   visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular
   kernel). If a shared tool is wrong, fix it once in the template and report it; never
   keep a private fork.
3. **LABEL EVERY NUMBER** as *HOLDOUT-DTI* (evaluator version, number of withheld
   positives, 95 % CI) or *ORGANIZER-CONFIRMED* (copied from a submission-page receipt).
   **A projection is never written as a score.**
4. **LEAKAGE CANARY.** Test each feature alone on the holdout before trusting any result.
   AUC above **0.90** means leakage until proven otherwise.
5. **RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault process
   that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256;
   validator output (no NaN inside the footprint, values in [0, 1], CRS/shape/transform
   match); submission name + note of at most 140 characters; verdict **promote / negative**.
   **Negative results are deliverables.**
6. **BUDGET.** Stop after **3** experiments or **2** hours. Do not pick submissions:
   promotion to a real slot is a separate selector step, within the weekly cap on the
   submission page.

## Part 3 — Standing brief (applies to every session in this line)

* **Goal: place at the top of the leaderboard** for the
  [DOE GEMS Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/).
  Understand the problem from the
  [overview and problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/),
  the [about page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/),
  the [data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
  and the [official rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf).
  The [reference solution](https://github.com/drivendataorg/gems-prize-reference-solution)
  is the documented baseline.
* **A unique TIF submission must be generated.** Never copy a previous submission
  except to learn; the artifact must be unique, and **it must be obvious on the site
  whether it is OK to download and submit**. The download lives at the very top of the
  landing page and in the executive summary.
* **The submission file must be one click away** and format-valid: single-band float32
  GeoTIFF, EPSG 32611, 100 m, same bounds as the training data, values in [0, 1],
  null/NaN outside the bounds. The portal error *"Predicted values must be in range
  [0, 1]"* is caused by an out-of-range nodata sentinel or a NaN nodata tag.
* **Before implementing anything**, generate 3–5 candidate geological hypotheses that
  have not been tried, each naming: the specific layer(s) involved; the physical signature
  targeted; why it should catch a fault missing from the USGS/INGENIOUS catalogue rather
  than one already in it; and how it differs from everything already implemented. Rank
  them by expected DTI improvement and implementation cost. **Validate the top candidate
  on a spatially-blocked holdout before touching a weekly submission slot.** If a
  candidate cannot be validated without new external data, name the specific free,
  official source needed and confirm it is obtainable before proposing it as viable.
* **Deep-research the science of geothermal vents and store it** as a reusable knowledge
  base built from official, verified sources. Be contrarian but sound: find data others
  overlook, and think outside the box while staying grounded in proper research.
* **No hallucinations.** Work line by line, verify against official and trusted sources,
  and provide links for manual review. Flag every irregularity. Work autonomously: do not
  wait for manual input.
* **Every task runs in at least three passes.** Pass 1 implement and verify; Pass 2 review
  for bugs, missing requirements, incorrect assumptions and edge cases and fix them;
  Pass 3 re-check the whole implementation against the original request and improve
  accuracy, reliability, completeness and code quality. Do not stop after the first pass.
* **Ship through a pull request** and merge it to `main`, then state what work remains
  and what limitations are in the way of a successful project.

## Part 4 — Core values (Arena AI), kept central to every decision

> **Maximize P(Win).** *"Maximize the Probability of Winning"* is our decision-making
> framework. In every decision we weigh tradeoffs, assess risk, and choose the path that
> maximizes the probability that we win. We set aside our emotions and make tough
> decisions in order to maximize P(Win). It frees us from constraints and clarifies that
> we must put the outcome first.
>
> **Own the Outcome.** We own results end to end — not just our individual slice of the
> work. When problems arise and we have the means to act, we act without waiting for
> permission or assignment. We treat failure and success as signals and use them to
> improve. We stay accountable to the final outcome.

**How they are applied here.** *Maximize P(Win)* is why the weekly slots are treated as
an experiment design rather than three lottery tickets, and why every artifact gets a
**hard upper bound** computed before a slot is recommended. *Own the Outcome* is why
negative results are published with the algebra that produces them, and why the defect
in a rule we were told to follow (the 3-px lane check is unsatisfiable against
near-blanketing rasters) is measured, published and flagged rather than quietly obeyed.
