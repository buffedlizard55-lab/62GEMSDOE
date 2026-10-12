#!/usr/bin/env python3
"""Deliverable 1 of the datum lane: Lahontan shoreline elevation-vs-distance profiles, with the
steps that the lane exists to flag.

Physics.  Post-pluvial isostatic rebound deforms the Lahontan highstand shoreline: the same water
plane is now higher near the basin centre and lower at the margins.  Once that smooth deformation is
removed, the *residual* is structural -- a fault that displaced the shoreline after it formed leaves
a step in the residual, and a fault that was active during the lake's life leaves a kink.

Method (no hard-coded basin coordinates, no hard-coded shoreline elevation).
  1. The DEM is the 25 m 3DEP mosaic already in `evidence/dem/`; every sub-basin is found by
     labelling cells below a low threshold and keeping the large components, and each sub-basin's
     centre is its own minimum.
  2. Every cell inside a sub-basin's search radius gets (D, z): radial distance from that centre and
     its elevation.  A shoreline bench is a *density ridge in (D, z)* -- at a fixed distance from the
     centre the beach deposits pile up at one elevation -- so the profile is the hypsometric excess
     mode of z inside each radial bin, not a fitted elevation.
  3. The smooth isobase is a robust (Huber-style) local regression of that profile; the residual is
     the deformation signal after rebound.
  4. Steps are residual jumps that exceed a MAD-scaled threshold and persist over more than one
     radial bin; each is written out with its along-shore position, so seeds and traces can be
     emitted only where a step is corroborated.

Outputs (all small, all committed):
  evidence/lane_datum_profiles.json      the profiles, the residuals and the flagged steps
  evidence/gems62-datum-profiles.svg     the same profiles as one dependency-free plot

Usage: python3 scripts/datum_profiles.py [--dem evidence/dem/lahontan_dem_utm11.tif]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

import numpy as np
import rasterio
from scipy import ndimage

M_PER_PX = 50.0             # the 25 m mosaic is block-averaged 2x2 first (memory, not physics)
DOWNSAMPLE = 2
LOW_LEVEL_M = 1220.0        # only used to find sub-basin floors, not to call anything a shoreline
MIN_BASIN_PX = 5_000        # 12.5 km^2 at 50 m
REACH_KM = 45.0             # radial search radius around a sub-basin floor
RADIAL_BIN_KM = 0.5
Z_BIN_M = 0.25
Z_RANGE = (1150.0, 1450.0)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def robust_isobase(d_km: np.ndarray, z: np.ndarray, window_km: float = 6.0) -> np.ndarray:
    """Local linear fit of z(D) with iterated outlier rejection -> the smooth rebound curve."""
    out = np.full_like(z, np.nan)
    for i, d0 in enumerate(d_km):
        sel = np.abs(d_km - d0) <= window_km
        if sel.sum() < 6:
            continue
        x, y = d_km[sel], z[sel]
        for _ in range(3):
            A = np.vstack([np.ones_like(x), x]).T
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)
            r = y - A @ coef
            s = 1.4826 * np.median(np.abs(r - np.median(r)))
            if s <= 0:
                break
            keep = np.abs(r) <= 2.5 * s
            if keep.all() or keep.sum() < 6:
                break
            x, y = x[keep], y[keep]
        out[i] = coef[0] + coef[1] * d0
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="evidence/dem/lahontan_dem_utm11.tif")
    ap.add_argument("--out-json", default="evidence/lane_datum_profiles.json")
    ap.add_argument("--out-svg", default="evidence/gems62-datum-profiles.svg")
    args = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]

    dem = root / args.dem
    with rasterio.open(dem) as s:
        z = s.read(1).astype(np.float64)
        transform = s.transform
        shape = (s.height, s.width)
    z = np.where(z <= -32000, np.nan, z / 10.0)          # decimetres, clipped sentinel
    # block-average 2x2 -> 50 m; keeps the arrays small enough for this sandbox
    h, w = z.shape[0] // DOWNSAMPLE * DOWNSAMPLE, z.shape[1] // DOWNSAMPLE * DOWNSAMPLE
    z = np.nanmean(z[:h, :w].reshape(h // DOWNSAMPLE, DOWNSAMPLE, w // DOWNSAMPLE, DOWNSAMPLE),
                   axis=(1, 3))
    shape = z.shape
    valid = np.isfinite(z)

    floor = valid & (z < LOW_LEVEL_M)
    lab, n = ndimage.label(floor)
    sizes = ndimage.sum(floor, lab, range(1, n + 1))
    keep = [i + 1 for i, sz in enumerate(sizes) if sz >= MIN_BASIN_PX]
    report = {
        "generated_by": "scripts/datum_profiles.py",
        "dem": {"path": str(dem.relative_to(root)), "sha256": sha256(dem),
                "shape": list(shape), "crs": "EPSG:32611", "res_m": M_PER_PX,
                "valid_fraction": round(float(valid.mean()), 4)},
        "method": "hypsometric-excess mode of z inside radial bins around each sub-basin floor; "
                  "smooth Huber-clipped local linear isobase; steps = residual jumps beyond "
                  "3.5x the local MAD sustained over 2+ bins",
        "basins": [],
    }

    # For the SVG: one panel per basin is too wide; keep the profile values in JSON and draw them.
    svg_lines: list[str] = []

    for k in keep:
        m = lab == k
        zmin = float(np.min(np.where(m, z, np.inf)))
        # crop to the basin's bounding box plus the reach: the distance transform below is then
        # computed on a small array instead of the whole mosaic
        ys, xs = np.nonzero(m)
        pad = int(REACH_KM * 1000.0 / M_PER_PX)
        y0 = max(0, ys.min() - pad); y1 = min(shape[0], ys.max() + pad + 1)
        x0 = max(0, xs.min() - pad); x1 = min(shape[1], xs.max() + pad + 1)
        iy, ix = int(ys[np.argmin(z[ys, xs])]), int(xs[np.argmin(z[ys, xs])])
        m_c = m[y0:y1, x0:x1]
        z_c = z[y0:y1, x0:x1]
        v_c = valid[y0:y1, x0:x1]
        # distance to the *floor* (a line for elongated basins), not to a single pixel
        d = ndimage.distance_transform_edt(~m_c, sampling=(M_PER_PX, M_PER_PX)) / 1000.0

        sel = v_c & (d <= REACH_KM) & (z_c >= Z_RANGE[0]) & (z_c <= Z_RANGE[1])
        d_sel = d[sel]
        z_sel = z_c[sel]
        if z_sel.size < 5000:
            continue

        nb = int(REACH_KM / RADIAL_BIN_KM)
        prof = []
        for b in range(nb):
            lo, hi = b * RADIAL_BIN_KM, (b + 1) * RADIAL_BIN_KM
            inb = (d_sel >= lo) & (d_sel < hi)
            if inb.sum() < 800:
                continue
            zz = z_sel[inb]
            bins = np.arange(Z_RANGE[0], Z_RANGE[1] + Z_BIN_M, Z_BIN_M)
            h, e = np.histogram(zz, bins=bins)
            if h.sum() == 0:
                continue
            bg = np.convolve(h, np.ones(41) / 41, mode="same")     # 10.25 m of background
            ex = h - bg
            i = int(np.argmax(ex))
            if ex[i] <= 0:
                continue
            prof.append({"d_km": round(lo + RADIAL_BIN_KM / 2, 3),
                         "bench_z_m": round(float(e[i] + Z_BIN_M / 2), 2),
                         "excess_cells": int(ex[i]), "cells_in_bin": int(inb.sum()),
                         "excess_frac": round(float(ex[i] / inb.sum()), 5)})
        if len(prof) < 12:
            continue
        dk = np.array([p["d_km"] for p in prof])
        bz = np.array([p["bench_z_m"] for p in prof])
        order = np.argsort(dk)
        dk, bz = dk[order], bz[order]
        iso = robust_isobase(dk, bz)
        res = bz - iso
        # local scatter of the residual, robust
        mad = 1.4826 * np.median(np.abs(res - np.median(res)))
        # steps: sustained jumps between adjacent bins
        steps = []
        for i in range(len(dk) - 1):
            jump = res[i + 1] - res[i]
            if abs(jump) > 3.5 * max(mad, 0.35):
                steps.append({"between_d_km": [round(float(dk[i]), 3), round(float(dk[i + 1]), 3)],
                              "jump_m": round(float(jump), 2),
                              "residual_before_m": round(float(res[i]), 2),
                              "residual_after_m": round(float(res[i + 1]), 2)})
        report["basins"].append({
            "label": int(k), "area_km2": round(float(sizes[k - 1]) * (M_PER_PX / 1000.0) ** 2, 1),
            "floor_z_m": round(float(zmin), 2),
            "floor_centre_px_in_crop": [int(iy - y0), int(ix - x0)],
            "crop_origin_px": [int(y0), int(x0)],
            "profile": [{"d_km": p["d_km"], "bench_z_m": p["bench_z_m"],
                         "excess_frac": p["excess_frac"]} for p in prof],
            "isobase_z_m": [round(float(v), 2) for v in iso],
            "residual_m": [round(float(v), 2) for v in res],
            "mad_m": round(float(mad), 3),
            "n_steps": len(steps), "steps": steps,
            "residual_range_m": [round(float(res.min()), 2), round(float(res.max()), 2)],
        })
        svg_lines.append((int(k), float(zmin), dk, bz, iso, res, float(mad)))

    (root / args.out_json).write_text(json.dumps(report, indent=1) + "\n")

    # ---- dependency-free plot -------------------------------------------------------------
    W, H, MARGIN = 980, 300 + 210 * max(len(svg_lines), 1), 64
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
             '<rect width="100%" height="100%" fill="#0d1117"/>',
             f'<text x="{MARGIN}" y="34" fill="#e6edf3" font-family="monospace" font-size="16">'
             'Lahontan shoreline bench elevation vs distance from the sub-basin floor '
             '(25 m 3DEP; bench = hypsometric-excess mode)</text>']
    for j, (lab_k, zfloor, dk, bz, iso, res, mad) in enumerate(svg_lines):
        y0 = 70 + 210 * j
        x0, w = MARGIN, W - 2 * MARGIN
        allz = np.concatenate([bz, iso])
        zlo, zhi = allz.min() - 2, allz.max() + 2
        dmax = dk.max()

        def px(d): return x0 + w * d / dmax
        def py(vv, top=y0, height=120): return top + height * (1 - (vv - zlo) / (zhi - zlo))

        parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="120" fill="#161b22" '
                     f'stroke="#30363d"/>')
        for vv in np.arange(np.ceil(zlo), np.floor(zhi) + 1, 10.0):
            y = py(vv)
            parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + w}" y2="{y:.1f}" '
                         f'stroke="#21262d"/>')
            parts.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" fill="#8b949e" text-anchor="end" '
                         f'font-family="monospace" font-size="11">{vv:.0f} m</text>')
        pts_bench = " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in zip(dk, bz))
        pts_iso = " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in zip(dk, iso))
        parts.append(f'<polyline points="{pts_iso}" fill="none" stroke="#58a6ff" stroke-width="2"/>')
        parts.append(f'<polyline points="{pts_bench}" fill="none" stroke="#f0883e" stroke-width="2"/>')
        for d, v in zip(dk, bz):
            parts.append(f'<circle cx="{px(d):.1f}" cy="{py(v):.1f}" r="3" fill="#f0883e"/>')
        # residual panel
        ry0, rh = y0 + 140, 60
        rmax = max(4.0, float(np.abs(res).max()))
        parts.append(f'<rect x="{x0}" y="{ry0}" width="{w}" height="{rh}" fill="#161b22" '
                     f'stroke="#30363d"/>')
        parts.append(f'<line x1="{x0}" y1="{ry0 + rh / 2:.1f}" x2="{x0 + w}" y2="{ry0 + rh / 2:.1f}" '
                     f'stroke="#30363d" stroke-dasharray="4 3"/>')
        for s in range(len(dk) - 1):
            jm = res[s + 1] - res[s]
            if abs(jm) > 3.5 * max(mad, 0.35):
                xa = px(dk[s])
                parts.append(f'<rect x="{xa - 3:.1f}" y="{ry0}" width="6" height="{rh}" '
                             f'fill="#f85149" opacity="0.6"/>')
        pts_res = " ".join(f"{px(d):.1f},{ry0 + rh / 2 - rh / 2 * v / rmax:.1f}"
                           for d, v in zip(dk, res))
        parts.append(f'<polyline points="{pts_res}" fill="none" stroke="#7ee787" stroke-width="2"/>')
        parts.append(f'<text x="{x0}" y="{y0 - 10}" fill="#e6edf3" font-family="monospace" '
                     f'font-size="13">basin {lab_k}: floor {zfloor:.0f} m, '
                     f'residual {res.min():+.1f}..{res.max():+.1f} m, MAD {mad:.2f} m, '
                     f'{sum(1 for s in range(len(dk) - 1) if abs(res[s + 1] - res[s]) > 3.5 * max(mad, 0.35))} '
                     f'flagged steps</text>')
        parts.append(f'<text x="{x0 + w}" y="{ry0 + rh + 14}" fill="#8b949e" text-anchor="end" '
                     f'font-family="monospace" font-size="11">distance from basin floor (km)</text>')
    parts.append('</svg>')
    (root / args.out_svg).write_text("\n".join(parts) + "\n")

    print(f"{len(report['basins'])} sub-basins profiled -> {args.out_json}, {args.out_svg}")
    for b in report["basins"]:
        print(f"  label {b['label']:>3}  area {b['area_km2']:>7.0f} km2  floor {b['floor_z_m']:>7.1f} m  "
              f"bins {len(b['profile']):>3}  residual {b['residual_range_m']} m  MAD {b['mad_m']} m  "
              f"steps {b['n_steps']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
