# Run card — negative review, 2026-10-11

**Verdict: `negative`.** The historical v8 artifact is not a cleared download and must not be
submitted. It fails the strict raw-overlap stop and the current local outside-footprint format
check. No new TIF was emitted after the stop, and no real submission slot was selected.

The canonical machine-readable JSON card, including hypothesis, mechanism, named non-fault mimic,
HOLDOUT-DTI/CI, leakage canary, strict registry correlation/overlap, SHA-256, validator results,
submission name/note, source links, review passes, and remaining work is:

[`evidence/lahontan_run_card_20261011.json`](evidence/lahontan_run_card_20261011.json)

Supporting receipts: [strict registry](evidence/uniqueness_v8_strict_review.json),
[holdout/canary](evidence/holdout_v8_strict_review.json), and
[local format validator](evidence/v8_format_review.json).

## Evidence snapshot

| field | value | class / note |
|---|---|---|
| Candidate | `docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif` | Historical artifact only |
| HOLDOUT-DTI | 0.002863; 95% cluster-bootstrap CI `[0, 0.006842]`; 60,362 withheld positives | `root-run_holdout-v3`, six spatial folds; catalogue proxy, not organizer score |
| Leakage canary | AUC 0.5020 and 0.4999 | Both below 0.90 alarm; no canary alarm |
| Registry comparison | rho = −0.3318; raw overlap = 0.9645 (1,601/1,660) within 3 px | Against fetched 13GEMSDOE `r11-greedy-mp-v2`; fail-fast stop after 9/525 TIFFs; strict **DUPLICATE-STOP** |
| Validator | `legal: false`; `all_nan_outside_footprint` failed | 7,111,787 non-NaN pixels outside the official footprint |
| Raster SHA-256 | `3d4b66e651bc8e3f58779e4c52e4af66c70d6f8d871308b21720e9003ebd43ba` | Historical file; no new output hash |
| Organizer-confirmed score | none | No submission-page receipt exists |

**Pre-placement surface check:** not run for this historical v8 candidate because the original
pre-placement surface was not retained as a raster. There was no new emission or placement during
this review. Any future candidate must be checked on its surface before emission and on final dots
after emission; a strict failure is an immediate stop.

The prior [`evidence/run_card_v8.json`](evidence/run_card_v8.json) is preserved as historical
provenance, but its `UNIQUE-VS-REGISTRY` and all-finite format verdicts are superseded by this
review and must not be used to authorize submission.
