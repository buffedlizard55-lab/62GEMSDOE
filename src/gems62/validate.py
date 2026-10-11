"""Submission-format validation, re-derived from the bytes on disk.

The organiser accepts a single-band GeoTIFF (or a zip containing one) whose CRS,
shape and geotransform match the template, with predicted values in ``[0, 1]``.
A local portal rejection ("Predicted values must be in range [0, 1]") is the
reason every check here is run against the *written file*, not the in-memory
array: the file is the deliverable.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

from . import grid as gd

CHECKS = (
    "single_band", "dtype_float32", "dimensions_3730x3292", "crs_epsg_32611",
    "transform_matches_template", "nodata_unset_or_nan",
    "in_footprint_all_finite", "in_footprint_no_nan", "in_footprint_no_inf",
    "in_footprint_no_sentinel", "in_footprint_range_0_1",
    "outside_footprint_zero", "zero_on_catalogue", "nonempty",
)


def validate(path: str | Path, footprint: np.ndarray, catalogue: np.ndarray) -> dict:
    import hashlib

    p = Path(path)
    with rasterio.open(p) as src:
        arr = src.read(1)
        meta = dict(bands=src.count, dtype=src.dtypes[0], height=src.height, width=src.width,
                    crs=str(src.crs) if src.crs is not None else None,
                    transform=[float(v) for v in tuple(src.transform)[:6]],
                    res=[float(v) for v in src.res], nodata=src.nodata)
    results = {}
    results["single_band"] = meta["bands"] == 1
    results["dtype_float32"] = meta["dtype"] == "float32"
    results["dimensions_3730x3292"] = (meta["height"], meta["width"]) == gd.SHAPE
    results["crs_epsg_32611"] = meta["crs"] == gd.CRS_EPSG
    results["transform_matches_template"] = \
        meta["transform"] == [float(v) for v in tuple(gd.TRANSFORM)[:6]]
    results["nodata_unset_or_nan"] = meta["nodata"] is None or np.isnan(meta["nodata"])

    inside = arr[footprint]
    results["in_footprint_all_finite"] = bool(np.isfinite(inside).all())
    results["in_footprint_no_nan"] = bool(not np.isnan(inside).any())
    results["in_footprint_no_inf"] = bool(not np.isinf(inside).any())
    results["in_footprint_no_sentinel"] = bool(not (np.abs(inside) > 1e30).any())
    results["in_footprint_range_0_1"] = bool(inside.size > 0
                                             and inside.min() >= 0.0 and inside.max() <= 1.0)
    outside = arr[~np.asarray(footprint, bool)]
    results["outside_footprint_zero"] = bool(outside.size == 0 or (outside == 0).all())
    results["zero_on_catalogue"] = bool(not arr[np.asarray(catalogue, bool) & footprint].any())
    results["nonempty"] = bool((inside > 0).any())
    # ------------------------------------------------------------------
    # aliases: the parallel lanes on origin/main read these check names
    # back from the receipt. They are the same facts under different keys.
    # ------------------------------------------------------------------
    fin = np.isfinite(arr)
    finite_vals = arr[fin]
    results["zero_dots_on_mapped_catalogue"] = results["zero_on_catalogue"]
    results["transform_matches"] = results["transform_matches_template"]
    results["transform_matches_sample_submission"] = results["transform_matches_template"]
    results["no_nan_anywhere"] = bool(not np.isnan(arr).any())
    results["no_inf_anywhere"] = bool(not np.isinf(arr).any())
    results["no_sentinel_values"] = bool(not (np.abs(arr) > 1e30).any())
    results["no_float32_sentinel"] = results["no_sentinel_values"]
    results["range_0_1_guaranteed"] = bool(fin.all() and (arr.size == 0
                                                          or (arr.min() >= 0.0 and arr.max() <= 1.0)))
    results["min_ge_0"] = bool(np.nanmin(arr) >= 0.0)
    results["max_le_1"] = bool(np.nanmax(arr) <= 1.0)
    results["in_footprint_range_0_1_legacy"] = results["in_footprint_range_0_1"]
    results["whole_raster_all_finite"] = bool(fin.all())
    results["whole_raster_range_0_1"] = bool(finite_vals.size > 0
                                             and finite_vals.min() >= 0.0
                                             and finite_vals.max() <= 1.0)

    info = dict(
        path=str(p), bytes=p.stat().st_size,
        sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        positive_pixels=int((arr > 0).sum()),
        positive_in_footprint=int((arr[footprint] > 0).sum()),
        on_catalogue_positive=int((arr[np.asarray(catalogue, bool) & footprint] > 0).sum()),
        unique_positive_values=sorted(float(v) for v in np.unique(arr[arr > 0])[:8]),
        in_footprint_min=float(inside.min()) if inside.size else None,
        in_footprint_max=float(inside.max()) if inside.size else None,
        # counters the parallel lanes read back from the receipt
        n_nan=int(np.isnan(arr).sum()), n_inf=int(np.isinf(arr).sum()),
        min=float(np.nanmin(arr)), max=float(np.nanmax(arr)),
        **meta)
    out = dict(checks=results, all_checks_passed=bool(all(results[k] for k in CHECKS)),
               validator_version="gems61-validate-v1", info=info)
    # the parallel lanes read their counters from the top level of the receipt
    out.update(n_nan=info["n_nan"], n_inf=info["n_inf"],
               min=info["min"], max=info["max"])
    return out


def assert_valid(path: str | Path, footprint: np.ndarray, catalogue: np.ndarray) -> dict:
    out = validate(path, footprint, catalogue)
    failed = [k for k, v in out["checks"].items() if not v]
    if failed:
        raise ValueError(f"submission failed local validation: {failed}")
    return out


# ---------------------------------------------------------------------------
# merged from the parallel lane on origin/main (names kept only where this
# module did not already define them)
# ---------------------------------------------------------------------------

EXPECTED = dict(width=3292, height=3730, crs="EPSG:32611", count=1, dtype="float32",
                transform=(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0))


def template_meta():
    """Return (rasterio write-meta, footprint mask) for the organiser template."""
    with rasterio.open(TEMPLATE_TIF) as src:
        return (dict(driver="GTiff", height=src.height, width=src.width,
                     count=1, dtype="float32", crs=src.crs, transform=src.transform),
                np.isfinite(src.read(1)))


def write_submission(pred: np.ndarray, path: pathlib.Path, outside: str = "zeros",
                     footprint: np.ndarray | None = None) -> dict:
    """Write a portal-valid GeoTIFF. ``outside`` is 'zeros' (all-finite) or 'nan'."""
    meta, fp = template_meta()
    if footprint is None:
        footprint = fp
    if pred.shape != (meta["height"], meta["width"]):
        raise ValueError(f"shape {pred.shape} != template")
    if not np.isfinite(pred[footprint]).all():
        raise ValueError("non-finite prediction inside the footprint")
    if pred[footprint].min() < 0 or pred[footprint].max() > 1:
        raise ValueError("prediction outside [0, 1] inside the footprint")
    if outside == "nan":
        out = np.full(pred.shape, np.nan, np.float32)
        out[footprint] = pred[footprint]
        meta = dict(meta, nodata=float("nan"))
    elif outside == "zeros":
        out = np.zeros(pred.shape, np.float32)
        out[footprint] = pred[footprint]
    else:
        raise ValueError("outside must be 'zeros' or 'nan'")
    with rasterio.open(path, "w", compress="deflate", **meta) as dst:
        dst.write(out, 1)
    return validate(path, footprint=fp)


def assert_submittable(rep: dict) -> None:
    """Raise AssertionError if any validation check in ``rep`` failed."""
    if not rep.get("all_checks_passed", False):
        bad = [k for k, v in rep.get("checks", {}).items() if not v]
        raise AssertionError(f"failed submission validation checks: {bad}")
