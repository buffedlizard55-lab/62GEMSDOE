"""Pinned competition grid, scored footprint and the mapped-fault catalogue.

Every constant here is re-derived from the two hash-pinned bridge files in
``data/bridge/``; nothing is hard-coded without a verification path.

===================  =====
CRS                  EPSG:32611 (UTM zone 11N)
shape (rows, cols)   3730 x 3292
transform            (100, 0, 243350, 0, -100, 4508550)
cell                 100 m
footprint            5,167,373 finite cells of ``sample_submission.tif``
catalogue            60,988 mapped-fault cells inside the footprint
===================  =====

Bridge SHA-256 (byte identity with the public bridge, **not** an independent
organiser receipt):

* ``existing_faults.tif``  ``7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093``
* ``sample_submission.tif`` ``2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc``

The bridge ``labels.tif`` is byte-identical to ``existing_faults.tif``: the
published "labels" raster *is* the mapped catalogue.  The scored truth (faults
absent from the catalogue) is not published, which is why every number in this
repository is a hide-and-recover HOLDOUT-DTI and never a leaderboard score.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

EPSG = 32611
HEIGHT = 3730
WIDTH = 3292
SHAPE = (HEIGHT, WIDTH)
TRANSFORM = Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
PIXEL_M = 100.0
CRS_EPSG = f"EPSG:{EPSG}"
CELL_M = PIXEL_M

SHA256_EXISTING_FAULTS = "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093"
SHA256_SAMPLE_SUBMISSION = "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc"

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "bridge"
CACHE_DIR = REPO_ROOT / ".cache"


@dataclass(frozen=True)
class Grid:
    footprint: np.ndarray      # bool, scored study-area cells
    catalogue: np.ndarray      # bool, mapped USGS/INGENIOUS fault cells
    crs: object
    transform: Affine
    height: int
    width: int

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)


def _check(src, what: str) -> None:
    if str(src.crs) != CRS_EPSG:
        raise ValueError(f"{what}: CRS is {src.crs}, expected {CRS_EPSG}")
    if (src.height, src.width) != SHAPE:
        raise ValueError(f"{what}: shape {src.height}x{src.width}, expected {SHAPE}")
    if tuple(float(v) for v in src.transform)[:6] != tuple(TRANSFORM)[:6]:
        raise ValueError(f"{what}: transform {tuple(src.transform)}, expected {tuple(TRANSFORM)}")


def load_grid(data_dir: Path | None = None) -> Grid:
    d = Path(data_dir) if data_dir else DATA_DIR
    with rasterio.open(d / "existing_faults.tif") as src:
        _check(src, "existing_faults.tif")
        cat = src.read(1)
    with rasterio.open(d / "sample_submission.tif") as src:
        _check(src, "sample_submission.tif")
        sub = src.read(1)
    footprint = np.isfinite(sub)
    catalogue = (cat > 0) & footprint
    return Grid(footprint=footprint, catalogue=catalogue, crs=CRS_EPSG,
                transform=TRANSFORM, height=HEIGHT, width=WIDTH)


def load_band(number: int, root: Path | None = None) -> np.ndarray:
    """Load a cached band of the pinned 19-band feature stack (float32, NaN outside)."""
    root = Path(root) if root else REPO_ROOT
    path = root / ".cache" / "features" / f"band-{number:02d}.npy"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing; run `python scripts/prepare_data.py --fetch --cache-bands`")
    return np.load(path, mmap_mode="r")


def band_index() -> dict[str, int]:
    """Band number by the organiser's own band tag."""
    root = REPO_ROOT
    report = root / "evidence" / "feature_cache.json"
    if not report.exists():
        raise FileNotFoundError("evidence/feature_cache.json missing; cache the bands first")
    import json
    data = json.loads(report.read_text())
    return {b["description"].split(" - ")[0].strip(): b["band"] for b in data["bands"]}


def read_geotiff(path: str | Path) -> dict:
    """Everything a validator can complain about, re-derived from the bytes on disk."""
    import hashlib

    p = Path(path)
    with rasterio.open(p) as src:
        a = src.read(1)
        info = dict(
            path=str(p), bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            bands=src.count, dtype=src.dtypes[0], height=src.height, width=src.width,
            crs=str(src.crs) if src.crs is not None else None,
            transform=[float(v) for v in tuple(src.transform)[:6]],
            res=[float(v) for v in src.res],
            nodata=src.nodata, nodata_repr=repr(src.nodata),
        )
    finite = np.isfinite(a)
    info.update(
        finite_pixels=int(finite.sum()),
        min=float(np.nanmin(a)) if finite.any() else None,
        max=float(np.nanmax(a)) if finite.any() else None,
        positive_pixels=int((a > 0).sum()),
        nonzero_in_footprint=int(((a > 0) & finite).sum()),
        unique_values=int(len(np.unique(a[finite]))) if finite.any() else 0,
    )
    return info


def write_geotiff(path: str | Path, arr: np.ndarray, *, nodata: float | None = None) -> dict:
    """Write a single-band float32 GeoTIFF on the pinned grid and re-read it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(arr)
    if arr.dtype != np.float32:
        raise TypeError(f"submission must be float32, got {arr.dtype}")
    if arr.shape != SHAPE:
        raise ValueError(f"submission must be {SHAPE}, got {arr.shape}")
    if not np.isfinite(arr).all():
        raise ValueError("submission contains NaN/inf; the export policy rejects it")
    if arr.min() < 0.0 or arr.max() > 1.0:
        raise ValueError(f"submission out of range: min={arr.min()} max={arr.max()}")
    profile = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                   dtype="float32", crs=CRS_EPSG, transform=TRANSFORM,
                   tiled=True, blockxsize=256, blockysize=256,
                   compress="deflate", predictor=2)
    if nodata is not None:
        profile["nodata"] = float(nodata)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.set_band_description(1, "predicted_new_fault_probability")
    return read_geotiff(path)


# ---------------------------------------------------------------------------
# merged from the parallel lane on origin/main (names kept only where this
# module did not already define them)
# ---------------------------------------------------------------------------

def _default_data_dir() -> Path:
    """Locate the pinned rasters.

    IR-61-PATH-01: this module was written against a ``data/bridge/`` layout that
    does not exist in this repository -- the pinned rasters live in
    ``data/official/`` (``scripts/prepare_data.py`` writes them there and verifies
    their sha256).  ``load_grid()`` therefore raised ``FileNotFoundError`` for every
    caller that did not pass ``data_dir`` explicitly.  Fixed once, here, rather than
    forked: try ``data/bridge`` first (the original layout, still honoured if a
    caller creates it), then ``data/official``.
    """
    for name in ("bridge", "official"):
        candidate = REPO_ROOT / "data" / name
        if (candidate / "existing_faults.tif").exists() and (candidate / "sample_submission.tif").exists():
            return candidate
    return REPO_ROOT / "data" / "official"


DATA_DIR = _default_data_dir()


def write_submission(path: Path, values: np.ndarray, *, mode: str = "zeros") -> dict:
    """Serialize a pre-normalized array on the pinned grid without repairing it.

    ``mode="zeros"`` is the only submission-compatible mode: callers must pass
    an all-finite field already in ``[0,1]`` (normally with cells outside the
    footprint explicitly set to zero). Out-of-range and non-finite values are
    rejected; nothing is clipped or silently replaced.

    ``mode="nan"`` is retained for local diagnostics only. The organizer's
    nodata handling is not inferred here, and a prior portal range error does
    not establish NaN as its cause. Prefer the stricter all-finite zeros policy
    for any future candidate.
    """
    values = np.asarray(values)
    if values.shape != (HEIGHT, WIDTH):
        raise ValueError(f"values shape {values.shape} != {(HEIGHT, WIDTH)}")
    if not np.issubdtype(values.dtype, np.number):
        raise ValueError("values must be numeric")
    if mode == "zeros":
        if not np.isfinite(values).all():
            raise ValueError("zeros mode requires all values finite; set outside-footprint cells to 0 explicitly")
        if (values < 0.0).any() or (values > 1.0).any():
            raise ValueError("submission values must already be in [0,1]; no clipping")
        out = values.astype(np.float32, copy=False)
        nodata = None
    elif mode == "nan":
        finite = np.isfinite(values)
        if np.isinf(values).any() or (values[finite] < 0.0).any() or (values[finite] > 1.0).any():
            raise ValueError("diagnostic values must remain in [0,1] except for NaN cells; no silent clipping")
        out = values.astype(np.float32, copy=False)
        nodata = float("nan")
    else:
        raise ValueError("mode must be 'zeros' or 'nan'")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path, "w", driver="GTiff", height=HEIGHT, width=WIDTH, count=1,
        dtype="float32", crs=f"EPSG:{EPSG}", transform=TRANSFORM,
        nodata=nodata, compress="lzw", tiled=False,
    ) as dst:
        dst.write(out, 1)
        dst.set_band_description(1, "predicted_new_fault_probability")
    return {"path": str(path), "mode": mode, "nodata": nodata}
