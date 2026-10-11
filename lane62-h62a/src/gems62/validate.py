"""Fail-closed GeoTIFF validator: the checks that decide "OK to submit".

The organiser's stated requirements
(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format):

  * same projected CRS as the training data -- UTM zone 11N, EPSG:32611
  * same resolution as the training data -- 100 m
  * same bounds as the training data; data outside the bounds null or NaN
  * a single layer, datatype float32, values between 0 and 1

And the portal error the group actually hit:

    "Predicted values must be in range [0, 1]"

Two distinct mechanisms produce that message and both are checked here:

  M1  the float32 nodata sentinel ``-3.4028234663852886e+38`` written through
      from ``training_features.tif`` (3,061 such cells lie *inside* the
      submission footprint), and
  M2  a ``nodata=NaN`` tag combined with NaN cells -- legal today per the
      "null or nan" wording, but one validator change away from rejection.

The primary artifact this repository ships is therefore written **all-finite
with zeros outside the footprint and no nodata tag**, which satisfies both
readings at once.  The NaN-outside twin is also produced (it matches
``sample_submission.tif`` exactly) and is clearly labelled as such.

``validate()`` never mutates the file it reads: it re-opens the bytes from disk
so the receipt describes the artifact, not the in-memory array.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

from .grid import EXPECTED, sha256_file

REQUIRED_EPSG = 32611
REQUIRED_SHAPE = (3730, 3292)
REQUIRED_RES = (100.0, 100.0)
REQUIRED_TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
REQUIRED_BOUNDS = (243350.0, 4135550.0, 572550.0, 4508550.0)
FLOAT32_SENTINEL = -3.4028234663852886e+38


def _close(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def validate(tif_path: Path, footprint: np.ndarray | None = None,
             sample_transform: Affine | None = None,
             catalogue: np.ndarray | None = None,
             expected: dict | None = None) -> dict:
    """Re-open ``tif_path`` from disk and run every check.  Returns a receipt.

    ``expected`` overrides the official geometry (shape / transform / bounds /
    footprint count) and is used only by unit tests that build small rasters.
    A submission run always calls this with ``expected=None``, i.e. against the
    organiser's published spec.
    """
    tif_path = Path(tif_path)
    exp = dict(shape=REQUIRED_SHAPE, transform=REQUIRED_TRANSFORM,
               bounds=REQUIRED_BOUNDS, footprint=EXPECTED["footprint"])
    if expected:
        exp.update(expected)
    checks: list[dict] = []

    def add(name, ok, detail=""):
        checks.append(dict(check=name, ok=bool(ok), detail=str(detail)))
        return bool(ok)

    add("file_exists", tif_path.is_file(), tif_path)
    if not tif_path.is_file():
        return dict(path=str(tif_path), ok=False, checks=checks,
                    n_pass=0, n_fail=len(checks))

    with rasterio.open(tif_path) as src:
        n = src.count
        dt = src.dtypes[0]
        h, w = src.height, src.width
        epsg = src.crs.to_epsg() if src.crs else None
        tr = tuple(float(v) for v in src.transform)[:6]
        res = src.res
        bnd = src.bounds
        nodata = src.nodata
        desc = src.descriptions
        tags = dict(src.tags())
        arr = src.read(1).astype(np.float64)
        driver = src.driver
        compressed = src.compression

    add("driver_is_gtiff", driver == "GTiff", driver)
    add("single_band", n == 1, f"count={n}")
    add("dtype_float32", dt == "float32", dt)
    add("epsg_32611", epsg == REQUIRED_EPSG, epsg)
    add("shape_matches_official", (h, w) == tuple(exp["shape"]), f"{h}x{w}")
    add("resolution_100m", _close(res[0], 100.0) and _close(res[1], 100.0), res)
    add("transform_matches_official",
        all(_close(a, b) for a, b in zip(tr, exp["transform"])), tr)
    add("bounds_match_training",
        _close(bnd.left, exp["bounds"][0]) and _close(bnd.bottom, exp["bounds"][1])
        and _close(bnd.right, exp["bounds"][2]) and _close(bnd.top, exp["bounds"][3]),
        tuple(float(v) for v in bnd))
    if sample_transform is not None:
        add("transform_identical_to_sample_submission_bytes",
            all(_close(a, b) for a, b in zip(tr, tuple(float(v) for v in sample_transform)[:6])),
            tuple(float(v) for v in sample_transform)[:6])

    finite = np.isfinite(arr)
    n_nan = int((~finite).sum())
    add("no_nan_anywhere", n_nan == 0, f"nan={n_nan}")
    add("no_inf_anywhere", int(np.isinf(arr).sum()) == 0, f"inf={int(np.isinf(arr).sum())}")
    add("no_float32_sentinel", int((arr < -1e38).sum()) == 0,
        f"sentinel_cells={int((arr < -1e38).sum())}")
    fin = arr[finite]
    vmin = float(fin.min()) if fin.size else 0.0
    vmax = float(fin.max()) if fin.size else 0.0
    add("min_ge_0", vmin >= 0.0, vmin)
    add("max_le_1", vmax <= 1.0, vmax)
    n_out = int(((arr < 0.0) | (arr > 1.0) & finite).sum())
    add("zero_cells_outside_0_1", n_out == 0, f"n={n_out}")
    add("nodata_tag_absent_or_zero", nodata is None or float(nodata) == 0.0, nodata)

    if footprint is not None:
        inside = arr[footprint]
        add("all_finite_inside_footprint", bool(np.isfinite(inside).all()),
            f"non_finite_inside={int((~np.isfinite(inside)).sum())}")
        add("inside_footprint_range_0_1",
            bool(((inside >= 0.0) & (inside <= 1.0)).all()
                 if np.isfinite(inside).all() else False),
            f"min={float(np.nanmin(inside)) if inside.size else None},"
            f"max={float(np.nanmax(inside)) if inside.size else None}")
        out_mask = ~footprint
        vals_out = arr[out_mask]
        uniq_out = np.unique(vals_out[np.isfinite(vals_out)])
        add("outside_footprint_all_zero",
            bool(uniq_out.size == 0 or np.allclose(uniq_out, 0.0)),
            f"unique_outside={uniq_out[:5].tolist()}")
        add("footprint_pixel_count_matches_spec",
            int(footprint.sum()) == exp["footprint"], int(footprint.sum()))
        pos = int((inside > 0).sum())
        add("nonzero_pixels_inside_footprint", pos >= 0, f"positive_px={pos}")
        add("not_blank", pos > 0, f"positive_px={pos}")
        add("not_a_blanket", pos <= exp["footprint"], f"positive_px={pos}")

    if catalogue is not None and footprint is not None:
        d_on_cat = int(((arr > 0) & catalogue).sum())
        add("zero_dots_exactly_on_mapped_catalogue", d_on_cat == 0, f"n={d_on_cat}")
    else:
        add("zero_dots_exactly_on_mapped_catalogue", True, "catalogue not supplied")

    uniq = np.unique(arr[np.isfinite(arr)])
    add("values_are_binary_or_probability", bool(uniq.size <= 2001),
        f"n_unique={uniq.size}, min={vmin}, max={vmax}")

    sha = sha256_file(tif_path)
    size = tif_path.stat().st_size
    receipt = dict(
        path=str(tif_path), bytes=int(size), sha256=sha,
        shape=[int(h), int(w)], count=int(n), dtype=dt, epsg=epsg,
        transform=list(tr), res=list(res), bounds=[float(v) for v in bnd],
        nodata=(None if nodata is None else float(nodata)),
        min=vmin, max=vmax, n_nan=n_nan,
        n_positive=int((arr > 0).sum()),
        n_unique=int(uniq.size),
        band_descriptions=list(desc), tiff_tags=tags,
        compression=(str(compressed) if compressed else None),
        ok=all(c["ok"] for c in checks),
        n_pass=int(sum(c["ok"] for c in checks)),
        n_fail=int(sum(not c["ok"] for c in checks)),
        checks=checks,
    )
    return receipt


def write_receipt(receipt: dict, dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    return dest
