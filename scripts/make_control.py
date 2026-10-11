#!/usr/bin/env python3
"""Poisson (uniform-random) dot control on the official competition grid.

Why this exists
---------------
The competition truth is faults that are **not** in the USGS/INGENIOUS catalogue, and catalogue
pixels are masked out of scoring.  A catalogue-based holdout therefore scores the *wrong*
quantity, and the sibling repository measured how badly: its `catalogue_hidden` proxy correlates
with the live board at Spearman rho = +0.087, and a 300 m Poisson control scores *higher* on that
proxy (0.098) than the artifact that actually scored 0.2778 live (0.019).

The fix is not to delete the instrument but to give it a **null**: score a uniform-random field of
the same density and footprint through the identical code path.  An emission is only interesting
to the extent it separates from its own Poisson null.  Usage:

  python scripts/make_control.py --sample <example_submission.tif> --n 1660 --seed 7 \
      --out build/controls/poisson_1660_seed7.tif
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import grid  # noqa: E402


def main() -> int:
    import rasterio

    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True, help="official example_submission.tif (grid + footprint)")
    ap.add_argument("--n", type=int, required=True, help="number of dots")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with rasterio.open(args.sample) as s:
        valid = np.isfinite(s.read(1))

    idx = np.flatnonzero(valid.ravel())
    rng = np.random.default_rng(args.seed)
    pick = rng.choice(idx, size=min(args.n, idx.size), replace=False)
    out = np.zeros(valid.shape, np.float32)
    out.ravel()[pick] = 1.0
    # finite values in [0,1] inside; shared writer masks outside as NaN and leaves nodata unset
    path = pathlib.Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    grid.write_submission(path, out, footprint=valid)
    print(f"wrote {path} n={int((out > 0).sum())} seed={args.seed} "
          f"footprint_cells={idx.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
