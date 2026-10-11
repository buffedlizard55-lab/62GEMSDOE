#!/usr/bin/env python3
"""Produce the published-format NaN-outside twin of a shipped submission.

The competition's wording is "data outside the bounds is null or nan".  A
whole-raster validator can, however, read NaN as a value outside [0, 1] -- that is
mechanism M2 of the portal error "Predicted values must be in range [0, 1]".  The
group's own score ledger records the same portal score (0.1294) for a NaN-outside
file and its all-finite twin, so both readings are scoreable.  This repository
ships the all-finite file as the primary and generates the twin on demand, because
the twin is ~49 MB (NaN blocks do not compress) and must not bloat the repository.

  python3 scripts/make_variants.py                    # both shipped candidates
  python3 scripts/make_variants.py <some.tif>         # one file
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid as G          # noqa: E402


def twin(src: Path, footprint: np.ndarray) -> Path:
    dst = src.with_name(src.stem + "-nanoutside" + src.suffix)
    with rasterio.open(src) as d:
        arr = d.read(1)
    out = arr.astype(np.float32).copy()
    out[~footprint] = np.float32("nan")
    with rasterio.open(dst, "w", driver="GTiff", height=G.HEIGHT, width=G.WIDTH, count=1,
                       dtype="float32", crs=G.CRS,
                       transform=rasterio.Affine(*G.TRANSFORM), nodata=float("nan")) as d:
        d.write(out, 1)
    # verify: in-footprint values bit-identical, outside all NaN, no other difference
    with rasterio.open(dst) as d:
        b = d.read(1)
    assert np.array_equal(arr[footprint], b[footprint]), "in-footprint values differ"
    assert np.isnan(b[~footprint]).all(), "outside-footprint cells are not all NaN"
    assert np.isfinite(b[footprint]).all()
    assert (b[footprint] >= 0).all() and (b[footprint] <= 1).all()
    return dst


def main():
    g = G.load_grid(ROOT)
    args = sys.argv[1:]
    targets = [Path(a) for a in args] if args else [
        ROOT / "docs/downloads/gems62-lahontan-datum-break-dotted-primary-zeros.tif",
        ROOT / "docs/downloads/gems62-lahontan-flagged-breaks-selective-secondary-zeros.tif"]
    for t in targets:
        out = twin(t, g.footprint)
        print(f"{out.name}  {out.stat().st_size:,} bytes  sha256 {G.sha256_file(out)[:16]}…")


if __name__ == "__main__":
    main()
