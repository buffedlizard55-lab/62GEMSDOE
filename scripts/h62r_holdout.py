#!/usr/bin/env python3
"""H62-R holdout: score the frozen artifact on the segmented hide-and-recover instrument.

The emission function returns the **frozen** dots of the shipped GeoTIFF, clipped to
``~visible`` exactly as ``holdout_segmented.run_holdout`` requires, so the number is a
measurement of the artifact as emitted and not of a re-derivation.

Two numbers come out, and the difference between them is the point:

* ``pooled_dti`` -- the artifact against *withheld catalogue segments*;
* ``controls_mean`` -- three equal-budget controls on the same folds.

The instrument's truth is the **mapped catalogue**, and the competition masks that
catalogue out of live scoring; it therefore cannot reward finding a fault the
catalogue misses (``IR-62-HOLDOUT-01``).  The number is reported because protocol
item 3 requires it, and labelled HOLDOUT-DTI -- never as a score.

Usage:  .venv/bin/python scripts/h62r_holdout.py --tif <file> --out <json>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import grid                                       # noqa: E402
from gems62.holdout_segmented import run_holdout              # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tif", required=True)
    ap.add_argument("--labels", default="data/labels.tif")
    ap.add_argument("--sample", default="data/sample_submission.tif")
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget", type=int, default=0)
    args = ap.parse_args()

    import rasterio
    with rasterio.open(args.sample) as src:
        footprint = np.isfinite(src.read(1))
    lab = grid.read_labels(args.labels)
    catalogue = lab == 1
    with rasterio.open(args.tif) as src:
        mine = src.read(1) > 0
    mine &= footprint
    budget = args.budget or int(mine.sum())

    def emission_fn(eligible, priority, foot, visible, b):
        return mine & foot & ~visible

    res = run_holdout(np.ones_like(footprint), mine.astype(np.float64), footprint,
                      catalogue, emission_fn, n_folds=4, frac_withheld=0.35,
                      seeds=(20, 21), buffer_px=3, controls=True, budget=budget)
    res["artifact"] = args.tif
    res["n_dots"] = budget
    res["label"] = ("HOLDOUT-DTI. NOT a score. The instrument's truth is the MAPPED "
                    "catalogue, which the competition masks out of live scoring, so the "
                    "instrument cannot reward finding a catalogue-missing fault.")
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(f"pooled DTI {res['pooled_dti']:.6f}  CI95 {np.round(res['fold_dti_ci95'], 6).tolist()}"
          f"  withheld positives {res['withheld_positives_total']}")
    print(f"controls (mean): { {k: round(v, 6) for k, v in res['controls_mean'].items()} }")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
