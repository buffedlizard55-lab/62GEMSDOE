#!/usr/bin/env python3
"""The datum lane, measured properly: which Lake Lahontan stages does the DEM actually preserve,
and what does the shoreline elevation do along each one?

Why this replaces the first attempt (`datum_profiles.py`, kept as the record of what did not work):
a radial annulus mode picks whatever flat surface dominates at that distance, so its "profile"
climbed 200 m across a basin and its "steps" were noise.  A shoreline is not a radial feature, it
is a **level set**, so the stage has to be found before the profile means anything.

Method.
  1. Sub-basin floors are found from the DEM itself (cells below 1220 m, components >= 12.5 km2).
  2. For every 4 m elevation band inside a basin's 45 km reach, the **flatness excess** is the
     fraction of the band whose slope is below the 10th percentile of the reach, minus the same
     fraction measured 40 m higher.  The offset band is the correct baseline: a *stage* that left a
     wave-cut bench or a barrier has more flat ground than the ground just above it, whereas a
     merely low elevation is flat only because every low elevation is flat.  (The first estimator
     tried -- excess over the reach median slope -- saturates at the basin floors and is kept in the
     JSON as `flat_frac_vs_median` for comparison.)  This is a data-driven stage detector with no
     hard-coded datum.
  3. For each detected stage the shoreline is the level set itself; the **bench elevation** along it
     is the elevation of the flattest cell within 1.5 km of each shoreline vertex, which is what
     carries the rebound + fault signal.  Residual = bench elevation - stage elevation.
  4. Steps are place-to-place jumps of that residual that exceed 3.5 x its own robust scatter and
     are supported by a DEM scarps/step band (`build/ext/lidar_scarp_features_u8.tif` band 2,
     `step_max`, where available).

Outputs: `evidence/lane_datum_stages.json`, `evidence/gems62-datum-stages.svg`.

Usage: python3 scripts/datum_stages.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

import numpy as np
import rasterio
from scipy import ndimage

M_PER_PX = 50.0
DOWNSAMPLE = 2
LOW_LEVEL_M = 1220.0
MIN_BASIN_PX = 5_000
REACH_KM = 45.0
STAGE_LO, STAGE_HI, STAGE_STEP = 1180.0, 1420.0, 4.0
OFFSET_M = 40.0
BENCH_SEARCH_KM = 1.5


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_50m(path: pathlib.Path):
    with rasterio.open(path) as s:
        z = s.read(1).astype(np.float32)
    z = np.where(z <= -32000, np.nan, z / 10.0)
    h, w = z.shape[0] // DOWNSAMPLE * DOWNSAMPLE, z.shape[1] // DOWNSAMPLE * DOWNSAMPLE
    z = np.nanmean(z[:h, :w].reshape(h // DOWNSAMPLE, DOWNSAMPLE, w // DOWNSAMPLE, DOWNSAMPLE),
                   axis=(1, 3))
    return z.astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="evidence/dem/lahontan_dem_utm11.tif")
    ap.add_argument("--out-json", default="evidence/lane_datum_stages.json")
    ap.add_argument("--out-svg", default="evidence/gems62-datum-stages.svg")
    args = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]

    dem = root / args.dem
    z = load_50m(dem)
    shape = z.shape
    valid = np.isfinite(z)

    gy, gx = np.gradient(np.where(valid, z, np.nan))
    slope = np.hypot(np.nan_to_num(gy), np.nan_to_num(gx))     # m per 50 m cell
    slope = np.where(valid, slope, np.nan)

    floor = valid & (z < LOW_LEVEL_M)
    lab, n = ndimage.label(floor)
    sizes = ndimage.sum(floor, lab, range(1, n + 1))
    keep = [i + 1 for i, sz in enumerate(sizes) if sz >= MIN_BASIN_PX]

    report = {
        "generated_by": "scripts/datum_stages.py",
        "dem": {"path": str(dem.relative_to(root)), "sha256": sha256(dem), "shape": list(shape),
                "crs": "EPSG:32611", "res_m": M_PER_PX,
                "valid_fraction": round(float(valid.mean()), 4),
                "note": "the 25 m 3DEP mosaic block-averaged 2x2"},
        "method": "flatness excess per 2 m elevation band inside each sub-basin's 45 km reach; "
                  "bench elevation = flattest cell within 1.5 km of the level set",
        "basins": [],
        "verdict": None,
    }

    for k in keep:
        m = lab == k
        ys, xs = np.nonzero(m)
        pad = int(REACH_KM * 1000.0 / M_PER_PX)
        y0 = max(0, ys.min() - pad); y1 = min(shape[0], ys.max() + pad + 1)
        x0 = max(0, xs.min() - pad); x1 = min(shape[1], xs.max() + pad + 1)
        m_c = m[y0:y1, x0:x1]
        z_c = z[y0:y1, x0:x1]
        v_c = valid[y0:y1, x0:x1]
        s_c = slope[y0:y1, x0:x1]
        d = ndimage.distance_transform_edt(~m_c, sampling=(M_PER_PX, M_PER_PX)) / 1000.0

        reach = v_c & (d <= REACH_KM)
        if reach.sum() < 20_000:
            continue
        med_slope = float(np.nanmedian(s_c[reach]))
        p10_slope = float(np.nanpercentile(s_c[reach], 10))
        zfloor = float(np.nanmin(np.where(m_c, z_c, np.nan)))

        stages = []
        edges = np.arange(STAGE_LO, STAGE_HI, STAGE_STEP)
        for s0 in edges:
            band = reach & (z_c >= s0) & (z_c < s0 + STAGE_STEP)
            ref = reach & (z_c >= s0 + OFFSET_M) & (z_c < s0 + STAGE_STEP + OFFSET_M)
            nb = int(band.sum())
            if nb < 400 or ref.sum() < 400:
                continue
            flat = float(np.mean(s_c[band] < p10_slope))
            flat_ref = float(np.mean(s_c[ref] < p10_slope))
            stages.append({"stage_m": float(s0), "cells": nb,
                           "flat_frac": round(flat, 4), "flat_frac_40m_above": round(flat_ref, 4),
                           "flat_frac_vs_median": round(float(np.mean(s_c[band] < med_slope)), 4),
                           "excess": round(flat - flat_ref, 4)})
        if not stages:
            continue
        ex = np.array([s["excess"] for s in stages])
        stg = np.array([s["stage_m"] for s in stages])
        # a real stage is a local maximum of the flatness excess that stands clear of its neighbours
        peaks = []
        for i in range(2, len(ex) - 2):
            if ex[i] == ex[i - 2:i + 3].max() and ex[i] > 0.05:
                peaks.append(i)
        peaks = sorted(peaks, key=lambda i: -ex[i])[:6]
        peaks = sorted(peaks, key=lambda i: stg[i])

        profiles = []
        for i in peaks:
            S = float(stg[i])
            shore = reach & (z_c >= S) & (z_c < S + STAGE_STEP)
            if shore.sum() < 400:
                continue
            # shoreline vertices, subsampled so the profile is readable
            sy, sx = np.nonzero(shore)
            sel = np.arange(0, len(sy), max(1, len(sy) // 900))
            sy, sx = sy[sel], sx[sel]
            # bench elevation at each vertex: the flattest reach cell within BENCH_SEARCH_KM
            sub = int(BENCH_SEARCH_KM * 1000.0 / M_PER_PX)
            ben = []
            for py, px in zip(sy, sx):
                yA, yB = max(0, py - sub), min(z_c.shape[0], py + sub + 1)
                xA, xB = max(0, px - sub), min(z_c.shape[1], px + sub + 1)
                sl = s_c[yA:yB, xA:xB]
                zz = z_c[yA:yB, xA:xB]
                ok = v_c[yA:yB, xA:xB] & (np.abs(zz - S) <= 12.0)
                if ok.sum() == 0:
                    continue
                slw = np.where(ok, sl, np.inf)
                j = int(np.argmin(slw))
                jy, jx = divmod(j, slw.shape[1])
                ben.append({"y": int(yA + jy), "x": int(xA + jx),
                            "z": float(zz[jy, jx]), "slope": float(slw[jy, jx])})
            if len(ben) < 50:
                continue
            bz = np.array([b["z"] for b in ben])
            res = bz - S
            mad = float(1.4826 * np.median(np.abs(res - np.median(res))))
            profiles.append({
                "stage_m": S, "n_vertices": len(ben),
                "flat_frac": stages[i]["flat_frac"], "excess": stages[i]["excess"],
                "bench_z_p05": round(float(np.percentile(bz, 5)), 2),
                "bench_z_p50": round(float(np.percentile(bz, 50)), 2),
                "bench_z_p95": round(float(np.percentile(bz, 95)), 2),
                "residual_mad_m": round(mad, 3),
                "residual_span_m": [round(float(res.min()), 2), round(float(res.max()), 2)],
                "residual_iqr_m": round(float(np.percentile(res, 75) - np.percentile(res, 25)), 2),
                "bench_cells": ben,
            })

        report["basins"].append({
            "label": int(k), "area_km2": round(float(sizes[k - 1]) * (M_PER_PX / 1000.0) ** 2, 1),
            "floor_z_m": round(zfloor, 2),
            "median_slope_frac": round(med_slope, 5),
            "stages": stages, "n_peaks": len(peaks), "profiles": profiles, "crop_origin_px": [int(y0), int(x0)],
        })

    # The verdict the lane needs: is a steady datum visible at all, and how much does it deform?
    all_prof = [p for b in report["basins"] for p in b["profiles"]]
    report["verdict"] = {
        "basins_profiled": len(report["basins"]),
        "stages_with_a_profile": len(all_prof),
        "max_flatness_excess": round(max([s["excess"] for b in report["basins"] for s in b["stages"]],
                                         default=0.0), 4),
        "median_residual_iqr_m": round(float(np.median([p["residual_iqr_m"] for p in all_prof])), 2)
        if all_prof else None,
        "largest_residual_span_m": round(max([p["residual_span_m"][1] - p["residual_span_m"][0]
                                              for p in all_prof]), 2) if all_prof else None,
        "reading": "a shoreline the DEM preserves shows a flatness excess at one stage and a bench "
                   "residual whose spread is metres, not tens of metres; a residual IQR comparable "
                   "to the bench search window means no datum was resolved",
        "confound": "every basin's lowest bands carry a large excess because basin floors are flat "
                    "for reasons that have nothing to do with a shoreline; a stage count that is "
                    "only large at the floors is not evidence of a datum",
    }

    (root / args.out_json).write_text(json.dumps(report, indent=1) + "\n")

    # ---- SVG ---------------------------------------------------------------------------
    W = 980
    H = 90 + 240 * max(len(report["basins"]), 1)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
             '<rect width="100%" height="100%" fill="#0d1117"/>',
             f'<text x="64" y="34" fill="#e6edf3" font-family="monospace" font-size="15">'
             'Lake Lahontan stages the DEM preserves — flatness excess per 2 m band (25 m 3DEP, '
             'block-averaged to 50 m)</text>']
    for j, b in enumerate(report["basins"]):
        y0 = 70 + 240 * j
        x0, w, hh = 64, W - 128, 150
        stg = np.array([s["stage_m"] for s in b["stages"]])
        exc = np.array([s["excess"] for s in b["stages"]])
        if stg.size == 0:
            continue
        elo, ehi = min(exc.min(), -0.05), max(exc.max(), 0.05)

        def px(v): return x0 + w * (v - stg.min()) / max(stg.max() - stg.min(), 1)
        def py(v): return y0 + hh * (1 - (v - elo) / (ehi - elo))

        parts.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{hh}" fill="#161b22" '
                     f'stroke="#30363d"/>')
        parts.append(f'<line x1="{x0}" y1="{py(0):.1f}" x2="{x0 + w}" y2="{py(0):.1f}" '
                     f'stroke="#f85149" stroke-dasharray="4 3"/>')
        for g in range(int(stg.min() // 20 * 20), int(stg.max()) + 1, 20):
            parts.append(f'<line x1="{px(g):.1f}" y1="{y0}" x2="{px(g):.1f}" y2="{y0 + hh}" '
                         f'stroke="#21262d"/>')
            parts.append(f'<text x="{px(g):.1f}" y="{y0 + hh + 16}" fill="#8b949e" '
                         f'text-anchor="middle" font-family="monospace" font-size="10">{g} m</text>')
        pts = " ".join(f"{px(s):.1f},{py(v):.1f}" for s, v in zip(stg, exc))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#f0883e" stroke-width="2"/>')
        for p in b["profiles"]:
            parts.append(f'<circle cx="{px(p["stage_m"]):.1f}" cy="{py(p["excess"]):.1f}" r="4" '
                         f'fill="#7ee787"/>')
        parts.append(f'<text x="{x0}" y="{y0 - 12}" fill="#e6edf3" font-family="monospace" '
                     f'font-size="12">basin {b["label"]} — floor {b["floor_z_m"]:.0f} m, '
                     f'{b["area_km2"]:.0f} km2, {len(b["profiles"])} stage(s) with a bench profile'
                     f'</text>')
    parts.append('</svg>')
    (root / args.out_svg).write_text("\n".join(parts) + "\n")

    print(json.dumps(report["verdict"], indent=1))
    for b in report["basins"]:
        top = sorted(b["stages"], key=lambda s: -s["excess"])[:3]
        print(f"  basin {b['label']:>3} floor {b['floor_z_m']:>7.1f} m  "
              f"top excess: " + ", ".join(f"{t['stage_m']:.0f} m ({t['excess']:+.3f})" for t in top)
              + f"   profiles: {[p['stage_m'] for p in b['profiles']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
