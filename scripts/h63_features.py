#!/usr/bin/env python3
"""H63M — build the flat design matrix for the competition grid.

Inputs (all hash-pinned, see evidence/h63_data.json):
  data/training_features.tif        19-band GeoDAWN numerical stack (official, sha256 pinned)
  data/external/geodawn_dem_a2_100m.tif   100 m DEM (pinned)
  data/existing_faults.tif          the USGS/INGENIOUS catalogue (== labels.tif, official)
  data/sibling/proxy_catalogue.tif  code 1 = in competition catalogue, code 2 = SGMC
                                    faults absent from the catalogue (free official source:
                                    USGS State Geologic Map Compilation, fetched by
                                    buffedlizard55-lab/GEMSDOE scripts/fetch_proxy_faults.py)

Output (gitignored, under data/h63/):
  design.f32          float32 memmap, (n_valid, n_feat) row-major over the valid mask
  valid_mask.npy      bool (H, W)  -- cells usable for training AND scoring
  idx.npy             int32 (H, W) -- flat index into design rows, -1 outside
  feature_names.json
  dem_features.npz    the DEM-derived channels, on the grid (float32)

Nothing here invents data: every channel is a transform of a pinned raster, or a
geometric property of the catalogue raster itself.
"""
from __future__ import annotations

import json
import sys
import pathlib
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62.grid import (  # noqa: E402
    HEIGHT, WIDTH, PIXEL_M, FEATURE_NODATA, sha256,
)

OUT = HERE / "data" / "h63"
OUT.mkdir(parents=True, exist_ok=True)

STACK = HERE / "data" / "training_features.tif"
DEM = HERE / "data" / "external" / "geodawn_dem_a2_100m.tif"
CAT = HERE / "data" / "existing_faults.tif"
PROXY = HERE / "data" / "sibling" / "proxy_catalogue.tif"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- rasters
def read_stack_bands() -> tuple[np.ndarray, list[str], np.ndarray]:
    """Return (bands float32 (H,W,19), names, per-band nan mask)."""
    with rasterio.open(STACK) as src:
        names = [src.descriptions[i].split(" - ")[0] for i in range(src.count)]
        arr = src.read().astype(np.float32)          # (19, H, W)
        nodata = src.nodata
    bad = ~np.isfinite(arr)
    if nodata is not None:
        bad |= (arr == np.float32(nodata))
    arr[bad] = np.nan
    return np.moveaxis(arr, 0, -1), names, bad.any(axis=0)


def read_dem() -> np.ndarray:
    with rasterio.open(DEM) as src:
        a = src.read(1).astype(np.float32)
        nd = src.nodata
    if nd is not None:
        a[a == np.float32(nd)] = np.nan
    a[a < -1000.0] = np.nan
    return a


def dem_channels(dem: np.ndarray, foot: np.ndarray) -> dict[str, np.ndarray]:
    """Cheap, standard geomorphic channels.  All are transforms of the DEM only."""
    z = np.where(foot, dem, np.nan).astype(np.float32)

    def fill(a: np.ndarray) -> np.ndarray:
        """Nearest-valid fill so filters do not propagate NaN across the footprint."""
        out = a.copy()
        nan = ~np.isfinite(out)
        if nan.any():
            idx = ndi.distance_transform_edt(nan, return_distances=False, return_indices=True)
            out = out[tuple(idx)]
            out[~foot] = np.nan
        return out

    zf = fill(z)

    def smooth(a: np.ndarray, r: int) -> np.ndarray:
        return ndi.uniform_filter(a, size=2 * r + 1, mode="nearest")

    tpi3 = zf - smooth(zf, 3)
    tpi9 = zf - smooth(zf, 9)
    tpi21 = zf - smooth(zf, 21)

    gy, gx = np.gradient(zf.astype(np.float64))
    slope = np.degrees(np.hypot(gx, gy))                      # deg, 100 m cells
    gradmag = np.hypot(gx, gy).astype(np.float32)

    lap = ndi.laplace(zf.astype(np.float64), mode="nearest").astype(np.float32)
    # ridge / valley strength: |TPI| weighted by local relief; sign kept separately
    relief = (ndi.maximum_filter(zf, size=15) - ndi.minimum_filter(zf, size=15)).astype(np.float32)

    ch = {
        "dem_elev": zf,
        "dem_slope_deg": slope.astype(np.float32),
        "dem_gradmag": gradmag,
        "dem_tpi3": tpi3.astype(np.float32),
        "dem_tpi9": tpi9.astype(np.float32),
        "dem_tpi21": tpi21.astype(np.float32),
        "dem_laplacian": lap,
        "dem_relief15": relief,
        "dem_abstpi9": np.abs(tpi9).astype(np.float32),
    }
    for k, v in ch.items():
        v[~foot] = np.nan
    return ch


# --------------------------------------------------------------------------- main
def main() -> int:
    import hashlib

    t0 = time.time()
    rec: dict = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    log("reading catalogue + proxy")
    with rasterio.open(CAT) as s:
        cat_raw = s.read(1)
    catalogue = (cat_raw == 1)
    footprint = (cat_raw != -1)
    with rasterio.open(PROXY) as s:
        px = s.read(1)
    proxy_off = (px == 2) & footprint          # SGMC faults NOT in the competition catalogue

    log("reading 19-band stack")
    bands, band_names, band_bad = read_stack_bands()
    rec["stack"] = {"file": str(STACK.relative_to(HERE)), "sha256": sha256(STACK),
                    "bytes": STACK.stat().st_size, "bands": band_names}

    log("reading DEM")
    dem = read_dem()
    rec["dem"] = {"file": str(DEM.relative_to(HERE)), "sha256": sha256(DEM),
                  "bytes": DEM.stat().st_size}

    # ---- usable cell mask: footprint AND stack-valid AND dem-valid ---------------
    usable = footprint & ~band_bad & np.isfinite(dem)
    log(f"footprint {footprint.sum()}  stack-invalid {int(band_bad.sum())}  usable {usable.sum()}")

    log("computing DEM channels")
    demch = dem_channels(dem, usable)

    # ---- assemble flat design matrix over `usable` ------------------------------
    names: list[str] = []
    cols: list[np.ndarray] = []

    for i, nm in enumerate(band_names):
        v = bands[:, :, i][usable].astype(np.float32)
        v = np.nan_to_num(v, nan=np.float32(0.0), posinf=np.float32(0.0), neginf=np.float32(0.0))
        cols.append(v)
        names.append(f"stack_{nm}")

    for nm, arr in demch.items():
        v = arr[usable].astype(np.float32)
        v = np.nan_to_num(v, nan=np.float32(0.0), posinf=np.float32(0.0), neginf=np.float32(0.0))
        cols.append(v)
        names.append(nm)

    X = np.stack(cols, axis=1)
    log(f"design matrix {X.shape}  ({X.nbytes/1e6:.0f} MB)")

    fp = OUT / "design.f32"
    mm = np.memmap(fp, dtype=np.float32, mode="w+", shape=X.shape)
    mm[:] = X
    mm.flush()
    del mm

    idx = -np.ones((HEIGHT, WIDTH), dtype=np.int32)
    idx[usable] = np.arange(int(usable.sum()), dtype=np.int32)

    np.save(OUT / "valid_mask.npy", usable)
    np.save(OUT / "idx.npy", idx)
    np.save(OUT / "catalogue.npy", catalogue)
    np.save(OUT / "proxy_off.npy", proxy_off)
    np.save(OUT / "footprint.npy", footprint)
    (OUT / "dem_features.npz").unlink(missing_ok=True)
    np.savez_compressed(OUT / "dem_features.npz", **{k: v.astype(np.float32) for k, v in demch.items()})
    (OUT / "feature_names.json").write_text(json.dumps(names, indent=1))

    rec["design"] = {
        "path": str(fp.relative_to(HERE)), "shape": list(X.shape),
        "dtype": "float32", "sha256": sha256(fp), "bytes": fp.stat().st_size,
        "feature_names": names,
    }
    rec["masks"] = {
        "footprint_cells": int(footprint.sum()),
        "usable_cells": int(usable.sum()),
        "catalogue_cells": int(catalogue.sum()),
        "catalogue_cells_in_usable": int((catalogue & usable).sum()),
        "proxy_off_cells": int(proxy_off.sum()),
        "proxy_off_cells_in_usable": int((proxy_off & usable).sum()),
        "proxy_off_overlap_with_catalogue": int((proxy_off & catalogue).sum()),
    }
    rec["seconds"] = round(time.time() - t0, 1)
    (HERE / "evidence" / "h63_features.json").write_text(json.dumps(rec, indent=1))
    log("done " + json.dumps(rec["masks"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
