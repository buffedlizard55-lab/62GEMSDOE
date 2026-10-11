"""Fail-closed submission validator + writer.

The portal rejected a previous upload with

    "Predicted values must be in range [0, 1]"

Two independent mechanisms produce that message and both are properties of the
competition's own inputs (measured, see docs/irregularities.html IR-62-02):

  M1  `training_features.tif` declares nodata = -3.4028234663852886e+38, the
      float32 sentinel.  Any pipeline that carries a feature band through
      unchanged ships cells at that value, which is outside [0, 1].
  M2  a nodata tag of NaN (or any negative sentinel) on the SUBMISSION is read
      by a whole-raster range check as a value outside [0, 1].

The writer below therefore enforces, by re-opening the bytes from disk:

  * single band, dtype float32
  * CRS EPSG:32611, 100 m, 3730 x 3292, transform exactly the template's
  * EVERY cell of the 12,279,160 finite and inside [0, 1]
  * NO nodata tag (nodata is None)
  * zero positive mass outside the footprint

and refuses to exit successfully otherwise -- no receipt, no sidecar.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import (CRS, HEIGHT, TRANSFORM, TOTAL_CELLS, WIDTH, sha256_file)

# The literal contract, quoted from the official problem description:
#   "Your submission is in the same projected coordinate reference system as
#    the training data (projected coordinate system for UTM zone 11N, EPSG
#    32611)"; "same resolution ... (100m)"; "same bounds as the training data,
#    and data outside the bounds is null or nan"; "a single layer with datatype
#    of 32-bit float (float32) with values between 0 and 1".
# Source: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
NULL_OUTSIDE_CLAUSE = "null_outside_template_footprint"


def write_submission(out_path: str | Path, values: np.ndarray,
                     footprint: np.ndarray, *, outside: str = "zero") -> dict:
    """Write a portal-legal GeoTIFF, then re-read the bytes and verify.

    `outside` is 'zero' (all-finite variant, the one this repository ships as
    primary because it cannot trip *any* whole-raster range check) or 'nan'
    (the literal reading of the published clause).  In-footprint values are
    bit-identical between the two.
    """
    out_path = Path(out_path)
    values = np.asarray(values, np.float64)
    if values.shape != (HEIGHT, WIDTH):
        raise ValueError(f"shape {values.shape} != {(HEIGHT, WIDTH)}")
    if not np.isfinite(values[footprint]).all():
        raise ValueError("non-finite value inside the footprint")
    if (values[footprint] < 0).any() or (values[footprint] > 1).any():
        raise ValueError("value inside the footprint outside [0, 1]")

    rast = np.zeros((HEIGHT, WIDTH), np.float32)
    rast[footprint] = values[footprint].astype(np.float32)
    if outside == "nan":
        rast[~footprint] = np.float32("nan")
    elif outside != "zero":
        raise ValueError("outside must be 'zero' or 'nan'")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", driver="GTiff", height=HEIGHT, width=WIDTH,
                       count=1, dtype="float32", crs=CRS, transform=rasterio.Affine(*TRANSFORM),
                       nodata=None, compress="deflate", predictor=3, tiled=False) as dst:
        dst.write(rast, 1)
        dst.update_tags(nodata_policy=outside)

    return validate_submission(out_path, footprint)


def validate_submission(path: str | Path, footprint: np.ndarray | None = None) -> dict:
    """Re-open the file from disk and check every clause.  Raises on failure."""
    path = Path(path)
    checks: list[dict] = []

    def add(name: str, ok: bool, detail):
        checks.append(dict(check=name, ok=bool(ok), detail=detail))
        return ok

    with rasterio.open(path) as d:
        arr = d.read(1)
        meta = dict(height=d.height, width=d.width, count=d.count,
                    dtype=d.dtypes[0], crs=str(d.crs),
                    transform=[float(v) for v in tuple(d.transform)[:6]],
                    nodata=d.nodata, bounds=[float(v) for v in d.bounds])
    ok = True
    ok &= add("single_band", meta["count"] == 1, meta["count"])
    ok &= add("dtype_float32", meta["dtype"] == "float32", meta["dtype"])
    ok &= add("crs", meta["crs"] == CRS, meta["crs"])
    ok &= add("shape", (meta["height"], meta["width"]) == (HEIGHT, WIDTH),
              [meta["height"], meta["width"]])
    ok &= add("transform", tuple(meta["transform"]) == TRANSFORM, meta["transform"])
    ok &= add("pixel_size_100m",
              meta["transform"][0] == 100.0 and meta["transform"][4] == -100.0,
              [meta["transform"][0], meta["transform"][4]])
    ok &= add("no_nodata_tag", meta["nodata"] is None, meta["nodata"])

    finite = np.isfinite(arr)
    n_nan = int((~finite).sum())
    in_nan = 0
    if footprint is not None:
        in_nan = int((~finite & footprint).sum())
        ok &= add("finite_inside_footprint", in_nan == 0, in_nan)
        ok &= add("zero_outside_footprint",
                  float(arr[~footprint][finite[~footprint]].sum()) == 0.0,
                  float(arr[~footprint][finite[~footprint]].sum()) if finite[~footprint].any() else 0.0)
        ok &= add("no_nan_outside_footprint_allfinite",
                  n_nan == 0, n_nan)
    v = arr[finite]
    ok &= add("all_values_ge_0", bool((v >= 0).all()), float(v.min()) if v.size else None)
    ok &= add("all_values_le_1", bool((v <= 1).all()), float(v.max()) if v.size else None)
    ok &= add("no_sentinel", bool((np.abs(v.astype(np.float64)) < 1e37).all()), None)
    ok &= add("total_cells", int(arr.size) == TOTAL_CELLS, int(arr.size))

    rep = dict(file=str(path), bytes=path.stat().st_size,
               sha256=sha256_file(path), meta=meta,
               n_finite=int(finite.sum()), n_non_finite=n_nan,
               n_non_finite_inside_footprint=in_nan,
               n_positive_inside_footprint=int((arr[footprint] > 0).sum()) if footprint is not None else None,
               min_inside=float(arr[footprint].min()) if footprint is not None else float(v.min()),
               max_inside=float(arr[footprint].max()) if footprint is not None else float(v.max()),
               portal_error_cannot_occur=bool(ok),
               checks=checks)
    if not ok:
        bad = [c["check"] for c in checks if not c["ok"]]
        raise AssertionError(f"submission validation FAILED: {bad}")
    return rep


def dots_on_catalogue(path: str | Path, catalogue: np.ndarray,
                      footprint: np.ndarray) -> dict:
    """The IR-30-047 going-forward rule: probability mass on catalogue pixels
    earns no TP and no FP, so it is pure waste.  Count it."""
    with rasterio.open(path) as d:
        arr = d.read(1).astype(np.float64)
        arr[~np.isfinite(arr)] = 0.0
    pos = arr > 0
    return dict(n_positive=int(pos.sum()),
                n_positive_on_catalogue=int((pos & catalogue).sum()),
                mass_on_catalogue=float(arr[catalogue].sum()),
                n_positive_outside_footprint=int((pos & ~footprint).sum()))
