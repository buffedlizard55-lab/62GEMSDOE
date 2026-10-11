"""Competition grid IO and fail-closed GeoTIFF writer.

The constants are pinned to the supplied sample submission and labels.  The
published format requires EPSG:32611, a 100 m grid with matching bounds, one
float32 band with values in [0, 1], and null/NaN outside the training footprint.
The writer uses NaN pixel values outside the footprint but deliberately does
not add a NaN nodata tag; a local format pass is not an organizer receipt.

Official format source:
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

HEIGHT = 3730
WIDTH = 3292
SHAPE = (HEIGHT, WIDTH)
CRS = "EPSG:32611"
PIXEL_M = 100.0
RES_M = PIXEL_M
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
BOUNDS = (243350.0, 4135550.0, 572550.0, 4508550.0)
TOTAL_CELLS = HEIGHT * WIDTH
FOOTPRINT_CELLS = 5_167_373
CATALOGUE_CELLS = 60_988
RADIUS_M = 300.0

PINS = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "existing_faults.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE = REPO_ROOT / "data" / "sample_submission.tif"
DEFAULT_DATA = REPO_ROOT / "data"


@dataclass(frozen=True)
class Scene:
    """Small compatibility container for the earlier lane utilities."""

    labels: np.ndarray
    dem: np.ndarray
    features: np.ndarray | None = None

    @property
    def footprint(self) -> np.ndarray:
        return self.labels != -1

    @property
    def catalogue(self) -> np.ndarray:
        return self.labels == 1


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


# Older call sites used this spelling.  Keep one implementation.
sha256_file = sha256


def _assert_grid(src: rasterio.io.DatasetReader, path: str | Path) -> None:
    if (src.height, src.width) != SHAPE:
        raise ValueError(f"{path}: shape {(src.height, src.width)} != {SHAPE}")
    if str(src.crs) != CRS:
        raise ValueError(f"{path}: CRS {src.crs} != {CRS}")
    if tuple(float(x) for x in src.transform[:6]) != TRANSFORM:
        raise ValueError(f"{path}: transform {tuple(src.transform)[:6]} != {TRANSFORM}")


def load_catalogue(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Read a catalogue/label raster; return ``(known, footprint)`` masks."""
    with rasterio.open(path) as src:
        a = src.read(1)
        nodata = src.nodata
        # Validate transform and CRS when the raster claims to be on the GEMS grid.
        if (src.height, src.width) == SHAPE:
            _assert_grid(src, path)
    known = a == 1
    if nodata is None:
        footprint = np.isfinite(a)
    elif np.isnan(nodata):
        footprint = np.isfinite(a)
    else:
        footprint = a != nodata
    return known & footprint, footprint


def load_band(path: str | Path, band: int | str) -> tuple[np.ndarray, dict]:
    """Read one feature band by index or its ``band_name``/description tag."""
    with rasterio.open(path) as src:
        if isinstance(band, str):
            idx = None
            for i in range(1, src.count + 1):
                description = src.descriptions[i - 1] or ""
                if src.tags(i).get("band_name") == band or description.startswith(band + " "):
                    idx = i
                    break
            if idx is None:
                raise KeyError(f"band {band!r} not found in {path}")
        else:
            idx = int(band)
        a = src.read(idx)
        meta = dict(crs=str(src.crs), transform=tuple(src.transform)[:6],
                    shape=src.shape, band_name=src.tags(idx).get("band_name", str(idx)),
                    nodata=src.nodata)
    return a, meta


def read_dem(path: str | Path) -> np.ndarray:
    """Read a single-band elevation raster, converting declared nodata to NaN."""
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        if np.isnan(nodata):
            a[~np.isfinite(a)] = np.nan
        else:
            a[a == float(nodata)] = np.nan
    return a


def read_stack(path: str | Path, bands: list[int] | None = None) -> np.ndarray:
    """Read a multiband feature stack, converting its declared nodata to NaN."""
    with rasterio.open(path) as src:
        indices = bands if bands is not None else list(range(1, src.count + 1))
        a = src.read(indices).astype(np.float32)
        nodata = src.nodata
    if nodata is not None:
        if np.isnan(nodata):
            a[~np.isfinite(a)] = np.nan
        else:
            a[a == np.float32(nodata)] = np.nan
    return a


def load_scene(data_dir: str | Path = DEFAULT_DATA, *, with_features: bool = False) -> Scene:
    """Load the standard earlier-session scene layout under ``data_dir``."""
    root = Path(data_dir)
    label_path = root / "labels.tif"
    dem_path = root / "geodawn_dem_a2_100m.tif"
    with rasterio.open(label_path) as src:
        labels = src.read(1)
    dem = read_dem(dem_path)
    features = read_stack(root / "training_features.tif") if with_features else None
    return Scene(labels=labels, dem=dem, features=features)


def _get_footprint(footprint: np.ndarray | None) -> np.ndarray:
    if footprint is not None:
        fp = np.asarray(footprint, dtype=bool)
    else:
        if not DEFAULT_SAMPLE.exists():
            raise FileNotFoundError(
                "footprint is required when the pinned data/sample_submission.tif is unavailable")
        with rasterio.open(DEFAULT_SAMPLE) as src:
            _assert_grid(src, DEFAULT_SAMPLE)
            fp = np.isfinite(src.read(1))
    if fp.shape != SHAPE:
        raise ValueError(f"footprint shape {fp.shape} != {SHAPE}")
    return fp


def write_submission(path: str | Path, arr: np.ndarray, *,
                     footprint: np.ndarray | None = None, nodata=None,
                     outside: str = "nan") -> dict:
    """Write, reopen and validate a competition-format prediction GeoTIFF.

    All in-footprint values must be finite and in [0, 1].  Every cell outside
    the supplied (or pinned-template) footprint is written as NaN, matching the
    published format.  A nodata tag or zero-filled outside region is refused.
    """
    if nodata is not None:
        raise ValueError("submission nodata tags are disabled; use NaN pixel values outside")
    if outside != "nan":
        raise ValueError("outside must be 'nan' under the published submission format")
    fp = _get_footprint(footprint)
    values = np.asarray(arr)
    if values.shape != SHAPE:
        raise ValueError(f"submission shape {values.shape} != {SHAPE}")
    inside = np.asarray(values[fp], dtype=np.float64)
    if not np.isfinite(inside).all():
        raise ValueError("non-finite prediction inside the footprint")
    if ((inside < 0.0) | (inside > 1.0)).any():
        raise ValueError("prediction inside the footprint must be in [0, 1]")

    output = np.full(SHAPE, np.nan, dtype=np.float32)
    output[fp] = inside.astype(np.float32)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_path, "w", driver="GTiff", height=HEIGHT, width=WIDTH,
        count=1, dtype="float32", crs=CRS, transform=Affine(*TRANSFORM),
        nodata=None, compress="deflate", predictor=3, tiled=True,
        blockxsize=256, blockysize=256,
    ) as dst:
        dst.write(output, 1)
        dst.update_tags(outside_footprint="NaN; nodata tag intentionally unset")

    receipt = check_submission(out_path, footprint=fp)
    if not receipt["legal"]:
        raise ValueError(f"written GeoTIFF failed local format checks: {receipt['failed_checks']}")
    return receipt


def check_submission(path: str | Path, *, footprint: np.ndarray | None = None) -> dict:
    """Re-read the file and check the published format; this is not an upload receipt."""
    path = Path(path)
    fp = _get_footprint(footprint)
    with rasterio.open(path) as src:
        arr = src.read(1)
        transform = tuple(float(x) for x in src.transform[:6])
        bounds = tuple(float(x) for x in src.bounds)
        meta = dict(driver=src.driver, count=src.count, dtype=src.dtypes[0],
                    crs=str(src.crs), height=src.height, width=src.width,
                    shape=[src.height, src.width], transform=list(transform),
                    resolution=[float(x) for x in src.res], nodata=src.nodata,
                    bounds=list(bounds))

    shape_match = arr.shape == SHAPE
    footprint_shape_match = fp.shape == arr.shape
    can_check_pixels = shape_match and footprint_shape_match
    if can_check_pixels:
        in_values = arr[fp]
        out_values = arr[~fp]
        finite_inside = bool(np.isfinite(in_values).all())
        range_ok = bool(finite_inside and ((in_values >= 0.0) & (in_values <= 1.0)).all())
        outside_all_nan = bool(np.isnan(out_values).all())
        outside_non_nan = int((~np.isnan(out_values)).sum())
        nan_inside = int((~np.isfinite(in_values)).sum())
        min_inside = float(in_values.min()) if in_values.size and finite_inside else None
        max_inside = float(in_values.max()) if in_values.size and finite_inside else None
        n_positive = int((in_values > 0).sum())
        n_invalid_inside = int((~np.isfinite(in_values) | (in_values < 0) | (in_values > 1)).sum())
    else:
        finite_inside = range_ok = outside_all_nan = False
        outside_non_nan = nan_inside = n_positive = n_invalid_inside = None
        min_inside = max_inside = None

    checks = {
        "geotiff": meta["driver"] == "GTiff",
        "single_band": meta["count"] == 1,
        "float32": meta["dtype"] == "float32",
        "crs_epsg_32611": meta["crs"] == CRS,
        "shape": shape_match,
        "transform": transform == TRANSFORM,
        "resolution_100m": meta["resolution"] == [PIXEL_M, PIXEL_M],
        "bounds": bounds == BOUNDS,
        "nodata_tag_absent": meta["nodata"] is None,
        "footprint_shape": footprint_shape_match,
        "finite_values_in_footprint": finite_inside,
        "values_0_to_1_in_footprint": range_ok,
        "all_nan_outside_footprint": outside_all_nan,
    }
    failed = [name for name, ok in checks.items() if not ok]
    legal = not failed
    return {
        "file": path.name,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "meta": meta,
        "checks": checks,
        "failed_checks": failed,
        "legal": legal,
        "n_cells": int(arr.size),
        "n_finite_total": int(np.isfinite(arr).sum()),
        "n_nan_total": int(np.isnan(arr).sum()),
        "n_non_finite_inside_footprint": nan_inside,
        "n_non_nan_outside_footprint": outside_non_nan,
        "n_invalid_inside_footprint": n_invalid_inside,
        "n_positive_inside_footprint": n_positive,
        "min_inside": min_inside,
        "max_inside": max_inside,
        "note": "Local format validation only; not an organizer acceptance or score receipt.",
    }


def write_float32(path: str | Path, array: np.ndarray, *, nodata=None,
                  compress: str = "deflate") -> None:
    """Write a generic, single-band float32 raster on the pinned GEMS grid."""
    if nodata is not None:
        raise ValueError("write_float32 does not write nodata tags; pass an explicit pixel mask")
    a = np.asarray(array, dtype=np.float32)
    if a.shape != SHAPE:
        raise ValueError(f"expected shape {SHAPE}, got {a.shape}")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", driver="GTiff", dtype="float32", count=1,
                       height=HEIGHT, width=WIDTH, crs=CRS,
                       transform=Affine(*TRANSFORM), compress=compress,
                       predictor=3, tiled=True, blockxsize=256, blockysize=256) as dst:
        dst.write(a, 1)
