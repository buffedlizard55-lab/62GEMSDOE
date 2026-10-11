"""Grid constants and IO for the GEMS Prize (DrivenData #306) 100 m GeoDAWN grid.

Every constant in this module is *measured from the official competition bytes*
(sha256-pinned in ``registry/data_pins.json``), never assumed.

Official submission contract, transcribed from the competition problem page
(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/):

* "same projected coordinate reference system as the training data ... EPSG 32611"
* "same resolution ... 100m"
* "same bounds as the training data, and data outside the bounds is null or nan"
* "a single layer with datatype of 32-bit float (float32) with values between 0 and 1"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

# --- Measured grid constants (see registry/data_pins.json) -------------------
HEIGHT = 3730
WIDTH = 3292
CRS = "EPSG:32611"
PIXEL_M = 100.0
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
BOUNDS = (243350.0, 4135550.0, 572550.0, 4508550.0)
SHAPE = (HEIGHT, WIDTH)

#: Number of cells inside the survey footprint (labels != nodata).
FOOTPRINT_CELLS = 5_167_373
#: Number of catalogue ("known USGS/INGENIOUS fault") pixels in labels.tif.
CATALOGUE_CELLS = 60_988
#: Cells outside the footprint, where the contract asks for null/nan.
OUTSIDE_CELLS = HEIGHT * WIDTH - FOOTPRINT_CELLS

#: Competition nodata sentinels.
FEATURE_NODATA = np.float32(-3.4028234663852886e38)
LABEL_NODATA = np.int8(-1)

#: Published metric constants (problem page).
ALPHA = 0.2
BETA = 0.8
KERNEL_RADIUS_M = 300.0


@dataclass(frozen=True)
class Scene:
    """A co-registered view of the competition grid."""

    labels: np.ndarray          # int8, -1 outside footprint, 0/1 inside
    dem: np.ndarray             # float64 elevation (m), NaN outside
    features: np.ndarray | None  # float32 (bands, H, W), NaN where nodata

    @property
    def footprint(self) -> np.ndarray:
        return self.labels != LABEL_NODATA

    @property
    def catalogue(self) -> np.ndarray:
        return self.labels == 1


def read_labels(path: str | Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1)


def read_dem(path: str | Path) -> np.ndarray:
    """Read a single-band elevation raster as float64 with NaN outside the DEM."""
    with rasterio.open(path) as src:
        arr = src.read(1).astype(np.float64)
        nodata = src.nodata
    if nodata is not None:
        arr[arr == float(nodata)] = np.nan
    # Treat implausible sentinels as void even if the tag is absent.
    arr[arr < -1000.0] = np.nan
    return arr


def read_stack(path: str | Path, bands: list[int] | None = None) -> np.ndarray:
    """Read the official 19-band feature stack; nodata becomes NaN."""
    with rasterio.open(path) as src:
        idx = bands if bands is not None else list(range(1, src.count + 1))
        arr = src.read(idx).astype(np.float32)
        nodata = src.nodata
    if nodata is not None:
        arr[arr == np.float32(nodata)] = np.nan
    return arr


def write_float32(path: str | Path, array: np.ndarray, *, nodata=None, compress="deflate") -> None:
    """Write a single-band float32 GeoTIFF on the official grid."""
    arr = np.asarray(array, dtype=np.float32)
    if arr.shape != SHAPE:
        raise ValueError(f"expected shape {SHAPE}, got {arr.shape}")
    profile = {
        "driver": "GTiff",
        "height": HEIGHT,
        "width": WIDTH,
        "count": 1,
        "dtype": "float32",
        "crs": CRS,
        "transform": rasterio.transform.Affine(*TRANSFORM),
        "compress": compress,
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    if nodata is not None:
        profile["nodata"] = nodata
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)


def load_scene(data_dir: str | Path = "data", *, with_features: bool = False) -> Scene:
    """Load the standard scene from ``data/`` (see scripts/download_data.sh)."""
    d = Path(data_dir)
    labels = read_labels(d / "labels.tif")
    dem = read_dem(d / "geodawn_dem_a2_100m.tif")
    feats = None
    if with_features:
        feats = read_stack(d / "training_features.tif")
    return Scene(labels=labels, dem=dem, features=feats)
