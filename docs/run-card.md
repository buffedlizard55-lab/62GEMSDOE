# Run card — `gemsdoe62-datum-lahontan-isobase-v8`

One JSON run card per experiment, as the brief requires. The machine-readable copy is
[`../evidence/run_card_v8.json`](../evidence/run_card_v8.json).

```json
{
  "experiment": "gemsdoe62-datum-lahontan-isobase-v8",
  "date_utc": "2026-10-11",
  "lane": "datum-offset (Lake Lahontan shorelines as a strain gauge) — the assigned lane",
  "hypothesis": "Post-pluvial Lake Lahontan left a near-level shoreline datum across the basin. Subtracting a smooth isobase (robust quadratic, allowing for isostatic rebound) leaves a residual r = z - isobase whose ridge structure marks shoreline benches; a fault that crosses and offsets that datum produces a step in r whose trace CROSSES the datum contours. Such steps are faults the catalogue lacks, because the catalogue was built from lineament/single-dataset mapping rather than from a displaced geodetic datum.",
  "mechanism": "flat-pixel stand filter (local tile mode, 8 km tiles) -> robust quadratic isobase (Huber IRLS, 6 terms) -> r = z - isobase -> Frangi ridge of |grad r| -> offset = |r(+250 m) - r(-250 m)| across the ridge -> gates (evidence >= 0.10, step >= 2 m, <= 1500 m from a bench, cross-cut >= 30 deg, 2 km suppression) -> 5-candidate heading trace growth while DEM-ridge evidence >= 0.15 -> dotted emission at 100 m.",
  "named_non_fault_process_that_could_mimic_it": "Wave-cut bluffs, beach berms, fan-head risers and delta topsets are all level steps in the same elevation band as the shoreline, and 15 separate 'stands' were measured in the flat-pixel histogram between 1175 and 1437 m. The cross-cut gate (drop steps whose trace is contour-parallel) is the defence against exactly this family; it is a defence, not a proof. Aeolian/playa-margin steps and agricultural terracing on the basin floor are the same physical confuser.",
  "holdout": {
    "instrument": "scripts/run_holdout.py v2 (session 2026-10-11 fix: fold-confined scoring, block-scale whole-segment withholding, 3 px erosion = one kernel radius, same-fold canary negatives)",
    "protocol": "6 spatial folds (3 rows x 2 cols) over the footprint; truth = catalogue geometry inside the eroded block; scored domain = the eroded block; alpha 0.2, beta 0.8, 300 m triangular kernel; pooled over folds",
    "n_withheld_positives": 60362,
    "pooled_dti": 0.00286,
    "pooled_tp": 139.269,
    "pooled_fp": 1603.316,
    "pooled_fn": 60222.731,
    "recall": 0.002307,
    "recall_wilson95": [0.001955, 0.002723],
    "per_fold_dti": [0.009173, 0.0, 0.0, 0.0, 0.0, 0.0],
    "ci_note": "fold-wise CI is not estimable: 5 of 6 folds contain no predictions (the emission is concentrated in one sub-region). The Wilson interval quoted is on the pooled kernel-weighted recall.",
    "leakage_canary": {
      "lane_kernel_proximity_auc_mean": 0.5002,
      "lane_binary_mask_auc_mean": 0.4999,
      "verdict": "no leakage — and, given the AUC is at chance, no signal about catalogue faults either"
    },
    "instrument_calibration": {
      "h33_2_b2_zeros_live_0p2778": 0.00670,
      "poisson_1660_dots_null": 0.00389,
      "poisson_37654_dots_null": 0.06691,
      "verdict": "the instrument ranks a uniform-random field ABOVE the artifact that scored 0.2778 live; it is a novelty screen, never a score"
    }
  },
  "registry": {
    "n_registry": 289,
    "max_rank_correlation": -0.0652,
    "max_asymmetric_overlap": 1.0,
    "max_symmetric_jaccard": 0.0302,
    "verdict": "UNIQUE-VS-REGISTRY"
  },
  "raster": {
    "file": "docs/downloads/gemsdoe62-datum-lahontan-isobase-v8.tif",
    "bytes": 62709,
    "sha256": "3d4b66e651bc8e3f58779e4c52e4af66c70d6f8d871308b21720e9003ebd43ba",
    "n_dots": 1660,
    "total_mass": 1660.0
  },
  "validator": {
    "single_band": true, "dtype": "float32", "crs": "EPSG:32611",
    "shape": [3730, 3292], "res_m": [100.0, 100.0],
    "transform_matches_official_sample": true,
    "min": 0.0, "max": 1.0, "n_outside_0_1": 0, "nan_count": 0,
    "nodata_tag": null, "all_finite": true, "legal": true
  },
  "cost": {"wall_seconds": 191, "cpu": "2 cores"},
  "submission_name": "gemsdoe62-datum-lahontan-isobase-v8",
  "submission_note": "Lake Lahontan pluvial-bench isobase: 1660 dots on stepped/deflected shoreline benches; 221 DEM-ridge traces; unique vs registry.",
  "submission_note_chars": 128,
  "verdict": "NEGATIVE as a detector of catalogue faults; NOVEL versus the catalogue; promoted to the download page as a low-risk Phase-1 novelty probe, explicitly not as the lead horse (expectation below h33's owner-reported 0.2778)."
}
```

## The six bugs that stood between the first run and this one

Each was found by a targeted probe, fixed, and re-verified before the next full run — they are
recorded because a lane that reports only its successes is not reproducible.

| # | symptom | cause | fix |
| --- | --- | --- | --- |
| 1 | every elevation gate false | DEM is int16 **decimetres**, and the fetch had clipped a −32767 sentinel to −32766 | `read_z()` divides by 10 and masks ≤ −32000; fetch writes the sentinel after the clip |
| 2 | `IndexError` in the profile sampler | float index into an array | `rint(...).astype(int)` |
| 3 | scarp field never exceeded 0.02 | Frangi criterion used the algebraically larger eigenvalue | use the largest-**magnitude** eigenvalue; probe then showed p99 ≈ 0.85 on real scarps |
| 4 | traces were single points, always rejected | the walk used `(row += step·sin θ, col += step·cos θ)` — wrong axis *and* wrong sign, so it ran across the scarp | `step_rc`: `drow = −step·cos θ`, `dcol = +step·sin θ` |
| 5 | loci sat on 2 km jumps between parallel strands of one component | greedy nearest-neighbour chaining across strands | `chains_from_component(max_jump_m=150)` |
| 6 | `ValueError: GCPTransformer requires sequence of GroundControlPoint` | `rasterio.transform.rowcol` with a plain tuple silently selects the GCP transformer | arithmetic UTM → row/col |

Then, once it ran end-to-end, two *scientific* corrections, each of which changed the picture
and neither of which fixed it alone: the tile-mode isobase was replaced by the robust quadratic
(v6 → v8), and the cross-cut gate was added. The v6 → v8 comparison is the honest one:
redundancy against the catalogue fell from 0.764 (v5) to 0.279, i.e. the lane stopped
re-detecting known faults — but the visual diagnostic (`_overview.png`) is otherwise unchanged,
with traces still following range fronts. That visual check, not the holdout number, is what
identifies the remaining failure mode.
