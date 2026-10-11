#!/usr/bin/env python3
"""Fetch official USGS 3DEP elevation for the Lake Lahontan pluvial margins.

WHY THIS RUNS ON A GITHUB RUNNER
--------------------------------
The development sandbox that drives this repository reaches only github.com /
codeload / pypi (every USGS host returns HTTP 000 there, verified by curl).  GitHub-hosted
runners have unrestricted egress, so this script runs inside
``.github/workflows/dem-fetch.yml`` and publishes its products as workflow artifacts plus
a small JSON receipt that is committed back to the branch.  Same transport pattern the
sibling repositories use (buffedlizard55-lab/GEMSDOE48 ``scripts/dem_pilot_fetch.py``).

DATA PROVENANCE (every URL is recorded in the receipt; nothing is reconstructed)
-------------------------------------------------------------------------------
* USGS 3DEP 1/3 arc-second (≈10 m) seamless DEM, product "National Elevation Dataset (NED)
  1/3 arc-second", discovered through the authoritative USGS TNM Access API
  https://tnmaccess.nationalmap.gov/api/v1/products and downloaded from the URL the API
  itself returns (host prd-tnm.s3.amazonaws.com).
* 3DEP products carry no use restrictions; acknowledgement: "Map services and data
  available from U.S. Geological Survey, National Geospatial Program."
  https://www.usgs.gov/3d-elevation-program/about-3dep-products-services

OUTPUT (UTM zone 11N, aligned to the competition grid origin so 25 m nests 4x4 in 100 m)
---------------------------------------------------------------------------------------
* ``dem_25m_utm11.tif``  int16 decimetres (z_m = value/10), nodata -32768, deflate
* ``derived_25m/*.tif``  slope (Horn), curvature (Laplacian-based profile proxy) -- float32
* ``receipt.json``       per-tile URL, HTTP status, byte count, sha256, CRS, shape

Usage: python scripts/fetch_3dep.py --tiles n39w119,n40w119 --out out/dem --res 25
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.parse

import numpy as np

TNM_API = "https://tnmaccess.nationalmap.gov/api/v1/products"
NED_13 = "National Elevation Dataset (NED) 1/3 arc-second"
# competition submission grid (verified from labels.tif / sample_submission.tif in the bridge)
GRID = dict(crs="EPSG:32611", x0=243350.0, y1=4508550.0, px=100.0, rows=3730, cols=3292)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def curl_json(url: str, payload_path: pathlib.Path) -> tuple[int, dict | None]:
    r = subprocess.run(["curl", "-sS", "-L", "-w", "%{http_code}", "-o", str(payload_path),
                        "--max-time", "120", url], capture_output=True, text=True)
    code = int(r.stdout.strip() or 0) if r.stdout.strip().isdigit() else 0
    if code != 200:
        return code, None
    try:
        return code, json.loads(payload_path.read_text())
    except Exception:
        return code, None


def tnm_url_for_tile(tile: str, cache: pathlib.Path) -> tuple[str | None, dict]:
    """Ask the authoritative TNM API for the 1/3 arc-second GeoTIFF covering `tile`.

    Query strategy: a *tiny* bbox at the tile centre (0.005 deg), so every product that
    contains that point is returned and the exact tile cannot be pushed off the result list
    by neighbouring tiles.  With `max=1` in a coarse bbox the requested tile was missing from
    the first page and the whole run silently produced an empty mosaic (receipt kept, so the
    failure is visible) -- this is the fix for that defect.
    """
    lat_n = int(tile.split("w")[0][1:])
    lon_w = int(tile.split("w")[1])
    lat_c = lat_n - 0.5          # tile n<lat> spans [lat-1, lat]
    lon_c = -(lon_w - 0.5)       # tile w<lon> spans [-lon, -lon+1]
    bbox = f"{lon_c - 0.005:.6f},{lat_c - 0.005:.6f},{lon_c + 0.005:.6f},{lat_c + 0.005:.6f}"
    params = urllib.parse.urlencode({
        "datasets": NED_13, "bbox": bbox, "prodFormats": "GeoTIFF",
        "max": "30", "outputFormat": "JSON",
    })
    url = f"{TNM_API}?{params}"
    code, body = curl_json(url, cache)
    rec = {"tile": tile, "bbox_deg": bbox, "api_url": url, "api_http": code,
           "api_total": (body or {}).get("total"), "candidates": []}
    if not body:
        return None, rec
    want = f"USGS_13_{tile}"
    best = None
    for it in body.get("items", []):
        urls = [u for u in (it.get("downloadURL") or "").split(",") if u.strip()]
        for u in urls:
            base = u.rsplit("/", 1)[-1]
            rec["candidates"].append({"title": it.get("title"), "url": u,
                                      "bytes": it.get("sizeInBytes"), "format": it.get("format")})
            if base.startswith(want) and base.endswith(".tif"):
                # prefer the seamless "current" product over historical dated products
                score = (0 if "/current/" in u else 1,
                         0 if base == f"{want}.tif" else 1)
                if best is None or score < best[0]:
                    best = (score, u)
    if best is None:
        # documented static layout fallback, HTTP-checked before it is trusted
        cand = (f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/"
                f"current/{tile}/USGS_13_{tile}.tif")
        r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
                            "--head", "--max-time", "60", cand], capture_output=True, text=True)
        code2 = int(r.stdout.strip() or 0) if (r.stdout or "").strip().isdigit() else 0
        rec["pattern_fallback"] = {"url": cand, "http_head": code2}
        if code2 == 200:
            return cand, rec
    return (best[1] if best else None), rec


def download(url: str, dest: pathlib.Path) -> dict:
    r = subprocess.run(["curl", "-sS", "-L", "-w", "%{http_code} %{size_download}",
                        "-o", str(dest), "--max-time", "1800", url],
                       capture_output=True, text=True)
    parts = r.stdout.split()
    code = int(parts[0]) if parts and parts[0].isdigit() else 0
    size = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else (dest.stat().st_size if dest.exists() else 0)
    out = {"url": url, "http": code, "bytes": size}
    if dest.exists() and dest.stat().st_size > 0:
        out["sha256"] = sha256(dest)
    return out


def reproject_tile_to_utm(src_path: pathlib.Path, res: float, roi: tuple[float, float]) -> tuple:
    """Reproject one NED tile into UTM 11N at `res` m on a grid *snapped to the ROI origin*.

    Returns (array, dst_transform, meta).  The snapped grid is what makes the county-sized
    mosaic seamless: every tile lands on the same 25 m lattice as the ROI, so pasting is an
    integer offset and there is no half-pixel seam that a scarp detector could mistake for a
    fault step.
    """
    import math

    import rasterio
    from rasterio.warp import reproject, transform_bounds, Resampling
    from rasterio.transform import from_origin

    x0, y1 = roi
    with rasterio.open(src_path) as src:
        left, bottom, right, top = transform_bounds(src.crs, GRID["crs"], *src.bounds,
                                                    densify_pts=21)
        tx0 = x0 + res * math.floor((left - x0) / res) - res
        ty1 = y1 - res * math.floor((y1 - top) / res) + res
        w = int(math.ceil((right - tx0) / res)) + 1
        h = int(math.ceil((ty1 - bottom) / res)) + 1
        dst_transform = from_origin(tx0, ty1, res, res)
        arr = np.full((h, w), np.nan, dtype=np.float32)
        reproject(source=rasterio.band(src, 1), destination=arr,
                  src_transform=src.transform, src_crs=src.crs,
                  dst_transform=dst_transform, dst_crs=GRID["crs"],
                  resampling=Resampling.bilinear, dst_nodata=np.nan)
        meta = {"src_crs": str(src.crs), "src_shape": [src.height, src.width],
                "src_res": [abs(src.res[0]), abs(src.res[1])], "src_dtype": src.dtypes[0],
                "dst_shape": [h, w], "dst_transform": list(dst_transform)[:6],
                "utm_bounds": [left, bottom, right, top]}
    return arr, dst_transform, meta


def horn_slope(z: np.ndarray, res: float) -> np.ndarray:
    zz = np.where(np.isfinite(z), z, np.nan)
    padded = np.pad(zz, 1, mode="edge")
    a = padded[:-2, :-2]; b = padded[:-2, 1:-1]; c = padded[:-2, 2:]
    d = padded[1:-1, :-2]; f = padded[1:-1, 2:]
    g = padded[2:, :-2];  h = padded[2:, 1:-1]; i = padded[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * res)
    sl = np.arctan(np.hypot(dzdx, dzdy))
    sl[~np.isfinite(zz)] = np.nan
    return sl.astype(np.float32)


def laplacian_curvature(z: np.ndarray, res: float) -> np.ndarray:
    """Second-order (Laplacian) curvature proxy: negative on convex risers, ~0 on flats."""
    zz = np.where(np.isfinite(z), z, np.nan)
    padded = np.pad(zz, 1, mode="edge")
    lap = (padded[:-2, 1:-1] + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:]
           - 4 * padded[1:-1, 1:-1]) / (res * res)
    lap[~np.isfinite(zz)] = np.nan
    return lap.astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", required=True, help="comma-separated 1-degree tile ids, e.g. n40w119")
    ap.add_argument("--out", default="out/dem")
    ap.add_argument("--res", type=float, default=25.0)
    ap.add_argument("--workdir", default="/tmp/dem_work")
    ap.add_argument("--bounds", default="240000,4135550,430000,4508550",
                    help="x0,y0,x1,y1 in EPSG:32611 (default: Lahontan basins ROI)")
    ap.add_argument("--skip-derived", action="store_true")
    args = ap.parse_args()

    import rasterio
    from rasterio.transform import from_origin

    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(args.workdir); work.mkdir(parents=True, exist_ok=True)
    bounds = tuple(float(v) for v in args.bounds.split(","))
    receipt = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "product": NED_13, "api": TNM_API, "res_m": args.res, "crs": GRID["crs"],
               "bounds_utm11": list(bounds), "grid_aligned_to": GRID, "tiles": []}

    x0, y0, x1, y1 = bounds
    w = int(round((x1 - x0) / args.res)); h = int(round((y1 - y0) / args.res))
    mosaic = np.full((h, w), np.nan, dtype=np.float32)
    transform = from_origin(x0, y1, args.res, args.res)

    for tile in [t.strip() for t in args.tiles.split(",") if t.strip()]:
        entry: dict = {"tile": tile}
        url, api_rec = tnm_url_for_tile(tile, work / f"tnm_{tile}.json")
        entry["discovery"] = api_rec
        if not url:
            entry["status"] = "no-url-from-api"
            log(f"{tile}: NO URL ({api_rec.get('api_http')})")
            receipt["tiles"].append(entry); continue
        raw = work / f"{tile}.tif"
        try:
            entry["download"] = download(url, raw)
        except Exception as exc:  # pragma: no cover - transport failure path
            entry["status"] = f"download-failed: {exc}"
            receipt["tiles"].append(entry); continue
        if entry["download"].get("http") != 200:
            entry["status"] = "http-error"
            receipt["tiles"].append(entry); continue
        try:
            arr, tr, meta = reproject_tile_to_utm(raw, args.res, (x0, y1))
            tx0, ty1 = tr.c, tr.f
            col0 = int(round((tx0 - x0) / args.res))
            row0 = int(round((y1 - ty1) / args.res))
            th, tw = arr.shape
            r1, c1 = min(h, row0 + th), min(w, col0 + tw)
            row0c, col0c = max(0, row0), max(0, col0)
            sub = arr[row0c - row0:r1 - row0, col0c - col0:c1 - col0]
            tgt = mosaic[row0c:r1, col0c:c1]
            take = (~np.isfinite(tgt)) & np.isfinite(sub)
            tgt[take] = sub[take]
            entry.update({"status": "ok", "src_meta": meta, "dst_shape": list(arr.shape),
                          "paste_row0": row0c, "paste_col0": col0c})
            tile_vals = arr[np.isfinite(arr)]
            entry["z_min"] = float(tile_vals.min()) if tile_vals.size else None
            entry["z_max"] = float(tile_vals.max()) if tile_vals.size else None
            entry["valid_fraction"] = float(np.isfinite(arr).mean())
            log(f"{tile}: ok {entry['download']['bytes']/1e6:.0f} MB -> {arr.shape} "
                f"z=[{entry['z_min']:.0f},{entry['z_max']:.0f}] pasted=({row0c},{col0c})")
        except Exception as exc:
            entry["status"] = f"reproject-failed: {exc}"
            log(f"{tile}: reproject failed {exc}")
        finally:
            raw.unlink(missing_ok=True)
        receipt["tiles"].append(entry)

    valid = np.isfinite(mosaic)
    if not valid.any():
        log("FATAL: mosaic has zero valid cells -- no tile produced data; receipt written")
        (out / "receipt.json").write_text(json.dumps(receipt, indent=1))
        return 2
    receipt["mosaic"] = {"shape": [h, w], "valid_cells": int(valid.sum()),
                         "valid_fraction": float(valid.mean()),
                         "z_min": float(mosaic[valid].min()) if valid.any() else None,
                         "z_max": float(mosaic[valid].max()) if valid.any() else None}
    q = np.where(valid, np.round(mosaic * 10.0), -32768.0)
    q = np.clip(q, -32767, 32767).astype(np.int16)
    with rasterio.open(out / "dem_25m_utm11.tif", "w", driver="GTiff", dtype="int16",
                       count=1, height=h, width=w, crs=GRID["crs"], transform=transform,
                       nodata=-32768, compress="deflate", predictor=2, tiled=True,
                       blockxsize=512, blockysize=512, zlevel=9) as dst:
        dst.write(q, 1)
        dst.update_tags(ENCODING="z_m = value/10", PRODUCT=NED_13, SOURCE="receipt.json")
    log(f"wrote dem_25m_utm11.tif  valid={valid.sum()}")

    if not args.skip_derived:
        d = out / "derived_25m"; d.mkdir(exist_ok=True)
        slope = horn_slope(mosaic, args.res)
        curv = laplacian_curvature(mosaic, args.res)
        for name, arr in (("slope_rad", slope), ("laplacian_curv", curv)):
            with rasterio.open(d / f"{name}.tif", "w", driver="GTiff", dtype="float32",
                               count=1, height=h, width=w, crs=GRID["crs"],
                               transform=transform, nodata=np.nan, compress="deflate",
                               predictor=3, tiled=True, blockxsize=512, blockysize=512) as dst:
                dst.write(arr.astype(np.float32), 1)
        log("wrote derived slope + curvature")

    (out / "receipt.json").write_text(json.dumps(receipt, indent=1))
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
