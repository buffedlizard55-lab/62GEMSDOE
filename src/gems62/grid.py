"""The competition grid and the official rasters, with sha256 pins.

Every pin below was verified by re-hashing the bytes on disk (see evidence/*.json receipts);
the canonical hashes come from the official data-tab rasters, transported by the sibling
repository's data bridge (buffedlizard55-lab/GEMSDOE data/bridge/manifest.json), whose sha256
values are themselves the pins recorded from an unrestricted runner.

Official sources:
  data tab (login-walled): https://www.drivendata.org/competitions/306/competition-doe-gems/data/
  format spec:             https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
"""
from __future__ import annotations

import hashlib
import pathlib

import numpy as np

# ---- competition grid (read back from labels.tif / sample_submission.tif) -------------------
GRID = dict(crs="EPSG:32611", height=3730, width=3292, res=100.0,
            x0=243350.0, y1=4508550.0)
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
BOUNDS = (243350.0, 4135550.0, 572550.0, 4508550.0)

PINS = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}

# default local locations (heavy rasters live outside the repository; see README "Data")
DEFAULT_DATA = pathlib.Path("/tmp/gems")
DEFAULT_BRIDGE = pathlib.Path("/tmp/gems/../work/bridge")


def sha256(path: str | pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_catalogue(path: str | pathlib.Path) -> np.ndarray:
    """Known-fault raster (labels.tif == existing_faults.tif): 1 on catalogue pixels, 0 inside
    the footprint, nodata(-1) outside. Returns (known_mask, footprint_mask)."""
    import rasterio
    with rasterio.open(path) as src:
        a = src.read(1)
        nodata = src.nodata
    known = a == 1
    footprint = np.ones(a.shape, bool)
    if nodata is not None:
        footprint = a != nodata
    return known, footprint


def load_band(path: str | pathlib.Path, band: int | str) -> tuple[np.ndarray, dict]:
    """Read one band of the official feature stack by index or by band_name tag."""
    import rasterio
    with rasterio.open(path) as src:
        idx = band
        if isinstance(band, str):
            idx = None
            for i in range(1, src.count + 1):
                tg = src.tags(i)
                desc = (src.descriptions[i - 1] or "")
                if tg.get("band_name") == band or desc.startswith(band + " "):
                    idx = i
                    break
            if idx is None:
                raise KeyError(f"band {band!r} not found in {path}")
        a = src.read(idx)
        meta = dict(crs=str(src.crs), transform=tuple(src.transform)[:6], shape=src.shape,
                    band_name=src.tags(idx).get("band_name", str(idx)), nodata=src.nodata)
    return a, meta


def write_submission(path: str | pathlib.Path, arr: np.ndarray, *, nodata=None) -> dict:
    """Write a competition-legal GeoTIFF and re-read it from disk to build the receipt.

    Legal per the official spec: single band, float32, EPSG:32611, 100 m, same bounds as the
    training data, values in [0, 1]; data outside the footprint may be null/nan.  We write
    ALL-FINITE zeros outside the footprint and no nodata tag at all, which removes both
    mechanisms behind the portal error "Predicted values must be in range [0, 1]".
    """
    import rasterio
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.asarray(arr, dtype=np.float32)
    assert a.shape == (GRID["height"], GRID["width"]), a.shape
    assert np.isfinite(a).all(), "all-finite output required"
    assert float(a.min()) >= 0.0 and float(a.max()) <= 1.0, (float(a.min()), float(a.max()))
    with rasterio.open(path, "w", driver="GTiff", dtype="float32", count=1,
                       height=a.shape[0], width=a.shape[1], crs=GRID["crs"],
                       transform=TRANSFORM, nodata=nodata, compress="deflate",
                       predictor=3, tiled=True, blockxsize=256, blockysize=256) as dst:
        dst.write(a, 1)
    return check_submission(path)


def check_submission(path: str | pathlib.Path) -> dict:
    """Independent re-read of the bytes on disk: format receipt for the submission page."""
    import rasterio
    path = pathlib.Path(path)
    rec: dict = {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
    with rasterio.open(path) as src:
        a = src.read(1)
        rec.update({
            "driver": src.driver, "count": src.count, "dtype": src.dtypes[0],
            "crs": str(src.crs), "transform": [round(v, 6) for v in tuple(src.transform)[:6]],
            "shape": list(src.shape), "res": list(src.res), "nodata": src.nodata,
            "width_height_match": list(src.shape) == [GRID["height"], GRID["width"]],
            "crs_match": str(src.crs) == GRID["crs"],
            "transform_match": tuple(round(v, 6) for v in tuple(src.transform)[:6]) == TRANSFORM,
            "all_finite": bool(np.isfinite(a).all()),
            "nan_count": int((~np.isfinite(a)).sum()),
            "min": float(a.min()), "max": float(a.max()),
            "n_outside_0_1": int(((a < 0) | (a > 1)).sum()),
            "n_positive": int((a > 0).sum()),
            "total_mass": float(a.sum()),
        })
        rec["legal"] = bool(rec["count"] == 1 and rec["dtype"] == "float32"
                            and rec["crs_match"] and rec["transform_match"]
                            and rec["all_finite"] and rec["n_outside_0_1"] == 0
                            and rec["nodata"] is None)
    return rec
