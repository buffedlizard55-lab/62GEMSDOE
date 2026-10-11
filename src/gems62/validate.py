"""Submission format validator.

Checks are transcribed from the competition problem page
(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) and
from the observed submission-form behaviour recorded by the sibling repositories:

* "same projected coordinate reference system as the training data ... EPSG 32611"
* "same resolution ... 100m"
* "same bounds as the training data, and data outside the bounds is null or nan"
* "a single layer with datatype of 32-bit float (``float32``) with values between 0 and 1"

The portal error the owner hit -- ``Predicted values must be in range [0, 1]`` -- is
reproduced by any file whose values outside [0, 1] leak into the portal's range
check, most commonly a float32 nodata sentinel such as ``-3.4028235e38`` or a NaN
nodata tag.  This validator therefore reports *three* separate facts and never
conflates them:

1. every finite value in the scored footprint lies in ``[0, 1]``;
2. whether any non-finite value occurs inside the footprint;
3. how the file encodes the region outside the footprint (finite zeros vs NaN).

A local pass is **not** an organizer acceptance receipt.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import rasterio

from .grid import CRS, HEIGHT, WIDTH, TRANSFORM


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


@dataclass
class ValidationReport:
    path: str
    sha256: str
    bytes: int
    count: int
    dtype: str
    crs: str
    shape: tuple[int, int]
    transform: tuple[float, ...]
    nodata: float | None
    values_min: float
    values_max: float
    nan_inside_footprint: int
    nan_outside_footprint: int
    outside_encoding: str
    positive_cells: int
    max_positive_value: float
    unique_positive_values: list[float]
    passed: bool
    failures: list[str]
    notes: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, default=str)


def validate_submission(path: str | Path, footprint: np.ndarray,
                        *, expected_positive_values: tuple[float, ...] = (1.0,)) -> ValidationReport:
    """Validate a candidate GeoTIFF against the published submission contract."""
    path = Path(path)
    failures: list[str] = []
    notes: list[str] = []

    with rasterio.open(path) as src:
        count = src.count
        dtype = src.dtypes[0]
        crs = str(src.crs)
        shape = (src.height, src.width)
        transform = tuple(float(v) for v in src.transform[:6])
        nodata = None if src.nodata is None else float(src.nodata)
        arr = src.read(1)

    if count != 1:
        failures.append(f"single band required, found {count}")
    if dtype != "float32":
        failures.append(f"float32 required, found {dtype}")
    if crs.upper().replace(" ", "") not in {CRS, "EPSG:32611"}:
        failures.append(f"CRS must be {CRS}, found {crs}")
    if shape != (HEIGHT, WIDTH):
        failures.append(f"shape must be {(HEIGHT, WIDTH)}, found {shape}")
    if len(transform) != 6 or any(
        abs(a - b) > 1e-6 for a, b in zip(transform, TRANSFORM)
    ):
        failures.append(f"geotransform must be {TRANSFORM}, found {transform}")

    inside = footprint
    vals_in = arr[inside]
    finite_in = np.isfinite(vals_in)
    nan_inside = int((~finite_in).sum())

    if nan_inside:
        failures.append(f"{nan_inside} non-finite values inside the scored footprint")

    finite_vals = vals_in[finite_in]
    vmin = float(finite_vals.min()) if finite_vals.size else float("nan")
    vmax = float(finite_vals.max()) if finite_vals.size else float("nan")
    if finite_vals.size and ((finite_vals < 0.0) | (finite_vals > 1.0)).any():
        failures.append(
            "values outside [0,1] inside the footprint "
            f"({int(((finite_vals < 0) | (finite_vals > 1)).sum())} cells)"
        )

    outside_vals = arr[~inside]
    outside_nan = int((~np.isfinite(outside_vals)).sum())
    if outside_nan == outside_vals.size:
        outside_encoding = "all NaN outside the footprint"
    elif outside_nan == 0:
        outside_encoding = "all finite outside the footprint"
    else:
        outside_encoding = f"mixed ({outside_nan} of {outside_vals.size} NaN)"
    if outside_nan not in (0, outside_vals.size):
        failures.append("outside-footprint encoding is mixed (NaN and finite)")

    finite_out = outside_vals[np.isfinite(outside_vals)]
    if finite_out.size and ((finite_out < 0.0) | (finite_out > 1.0)).any():
        failures.append(
            "finite values outside the footprint fall outside [0,1]; this is the "
            "class of file that triggers 'Predicted values must be in range [0, 1]'"
        )

    if nodata is not None:
        notes.append(
            f"file declares nodata={nodata!r}; the reference template declares nodata=nan"
        )

    pos = arr > 0
    positive_cells = int((pos & inside).sum())
    unique_pos = np.unique(arr[pos & inside]).astype(float).tolist() if positive_cells else []
    max_pos = float(max(unique_pos)) if unique_pos else 0.0
    if expected_positive_values and unique_pos:
        extra = [v for v in unique_pos if v not in expected_positive_values]
        if extra:
            notes.append(f"positive values beyond {expected_positive_values}: {extra[:5]}")

    return ValidationReport(
        path=str(path),
        sha256=sha256_file(path),
        bytes=path.stat().st_size,
        count=count,
        dtype=dtype,
        crs=crs,
        shape=shape,
        transform=transform,
        nodata=nodata,
        values_min=vmin,
        values_max=vmax,
        nan_inside_footprint=nan_inside,
        nan_outside_footprint=outside_nan,
        outside_encoding=outside_encoding,
        positive_cells=positive_cells,
        max_positive_value=max_pos,
        unique_positive_values=unique_pos[:10],
        passed=not failures,
        failures=failures,
        notes=notes,
    )
