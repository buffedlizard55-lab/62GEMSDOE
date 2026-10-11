# Research-source index — current review

Use the current, source-qualified bibliography at [`../sources.md`](../sources.md). That file links
only the official competition metric/rules, official USGS 3DEP discovery, and regional peer-reviewed
Lake Lahontan / Walker Lane context, with evidence classes.

## Corrections to the archived research page

- The 70%-within-3-px condition is applied literally. A comparator whose dilation covers much of
  the footprint is **not** exempt; its coverage is a diagnostic only. The current strict result for
  historical v8 is `DUPLICATE-STOP` against one fetched 13GEMSDOE lattice.
- Old “vacuous comparator” summaries, Jaccard-based clearance, and `DISTINCT LANE` labels are
  superseded and must not be used as uniqueness clearance.
- Public leaderboard observations are not submission-page receipts. No
  ORGANIZER-CONFIRMED score exists for this repository's artifacts.
- The shoreline profile asset is from a prior 99-dot exploratory run, not the v8 raster. It is
  linked and labeled as historical in [`../executive-summary.md`](../executive-summary.md).

Current evidence: [`../evidence/lahontan_run_card_20261011.json`](../evidence/lahontan_run_card_20261011.json),
[`../evidence/uniqueness_v8_strict_review.json`](../evidence/uniqueness_v8_strict_review.json),
and [`../evidence/holdout_v8_strict_review.json`](../evidence/holdout_v8_strict_review.json).
