#!/usr/bin/env python3
"""H63M — the lane's FIRST DELIVERABLE, rebuilt on the full-footprint 100 m DEM.

The brief: *"Map shoreline benches in the DEM and fit a smooth isobase, allowing for
post-pluvial isostatic rebound. Flag abrupt steps or lateral deflections along strike ...
First deliverable: shoreline elevation-versus-distance profiles with the flagged steps."*

This script reuses ``src/gems62/lahontan.py`` unchanged (the template's implementation,
protocol rule 2: reuse, do not rebuild) and drives it with the 100 m DEM
``data/external/geodawn_dem_a2_100m.tif`` (sha256-pinned), which covers the whole
competition footprint rather than only the Lahontan sub-area the 25 m transport covers.

Everything it writes is MEASURED.  It does NOT write a submission.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import rasterio

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62.grid import PIXEL_M, HEIGHT, WIDTH  # noqa: E402
import gems62.lahontan as L  # noqa: E402

EV = HERE / "evidence"
DOCS = HERE / "lane62-h63m" / "docs"
DEM = HERE / "data" / "external" / "geodawn_dem_a2_100m.tif"
DEM_SHA = "d32762a38222764389e948da423ebc6cadd00ac617ad3938d3dd79c6cfe14431"


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


LAHONTAN_BOX = (240000.0, 4250000.0, 430000.0, 4480000.0)


def run_domain(dem, foot, transform, tag, out):
    benches = L.describe_benches(dem, foot, transform)
    log(f"[{tag}] benches: {len(benches)}")
    if len(benches) < 6:
        return {"tag": tag, "n_benches": len(benches), "note": "too few benches to fit an isobase"}
    coef, info = L.fit_isobase(benches, order=2)
    x = np.array([b.x for b in benches]); y = np.array([b.y for b in benches])
    z = np.array([b.z for b in benches])
    iso = L.isobase_at(coef, info["terms"], info["x0"], info["y0"], x, y)
    residual = z - iso
    stats = {}
    steps = L.flag_steps(benches, residual, stats=stats)
    defl = L.flag_deflections(benches)
    log(f"[{tag}] isobase sigma {info['residual_sigma_m']:.2f} m, steps {len(steps)}, "
        f"deflections {len(defl)}, gate {stats.get('significance_gate_m')}")
    profiles = {int(t): L.shoreline_profile(benches, residual, track_deg=t)
                for t in (0.0, 45.0, 90.0, 135.0)}
    return {"tag": tag, "benches": benches, "isobase": info, "residual": residual,
            "steps": steps, "deflections": defl, "stats": stats, "profiles": profiles,
            "coef": coef}


def main() -> int:
    t0 = time.time()
    with rasterio.open(DEM) as s:
        dem = s.read(1).astype(np.float32)
        nd = s.nodata
    if nd is not None:
        dem[dem == np.float32(nd)] = np.nan
    dem[dem < -1000] = np.nan
    foot = np.isfinite(dem)
    log(f"DEM {dem.shape}, {int(foot.sum())} valid cells")

    import rasterio as _rio
    with _rio.open(DEM) as _s:
        _tr = tuple(_s.transform)[:6]
    # arm A: the whole footprint.  arm B: the Lahontan sub-basin box (the area the
    # official 3DEP transport covers), where the datum really is one isochronous surface.
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    XW = _tr[2] + xx * _tr[0]
    YN = _tr[5] + yy * _tr[4]
    in_box = ((XW >= LAHONTAN_BOX[0]) & (XW <= LAHONTAN_BOX[2]) &
              (YN >= LAHONTAN_BOX[1]) & (YN <= LAHONTAN_BOX[3]))
    runs = {
        "footprint": run_domain(dem, foot, _tr, "footprint", None),
        "lahontan_box": run_domain(dem, foot & in_box, _tr, "lahontan_box", None),
    }
    benches = runs["footprint"]["benches"]
    log(f"benches: {len(benches)}")
    if not benches:
        (EV / "h63_lane.json").write_text(json.dumps({"benches": 0}, indent=1))
        return 0

    coef, info = L.fit_isobase(benches, order=2)
    log(f"isobase order {info['order']}, residual sigma {info['residual_sigma_m']:.3f} m, "
        f"n_benches {info['n_benches']}")

    x = np.array([b.x for b in benches])
    y = np.array([b.y for b in benches])
    z = np.array([b.z for b in benches])
    iso = L.isobase_at(coef, info["terms"], info["x0"], info["y0"], x, y)
    residual = z - iso

    stats: dict = {}
    steps = L.flag_steps(benches, residual, stats=stats)
    log(f"flagged steps: {len(steps)}  stats={json.dumps(stats)}")
    defl = L.flag_deflections(benches)
    log(f"flagged lateral deflections: {len(defl)}")

    # ---- profiles along a set of tracks --------------------------------------
    tracks = [0.0, 45.0, 90.0, 135.0]
    profiles = {}
    for t in tracks:
        profiles[int(t)] = L.shoreline_profile(benches, residual, track_deg=t)

    # ---- write ----------------------------------------------------------------
    bench_rows = [{
        "i": i, "x": round(float(b.x), 1), "y": round(float(b.y), 1),
        "z_m": round(float(b.z), 2), "n_cells": int(b.n_cells),
        "azimuth_deg": round(float(b.azimuth_deg), 2),
        "elongation": round(float(b.elongation), 3),
        "length_m": round(float(b.length_m), 1),
        "residual_m": round(float(residual[i]), 3),
        "isobase_m": round(float(iso[i]), 2),
    } for i, b in enumerate(benches)]

    step_rows = [{
        "x": round(float(s.x), 1), "y": round(float(s.y), 1),
        "residual_jump_m": round(float(s.residual_jump_m), 3),
        "pair_distance_m": round(float(s.pair_distance_m), 1),
        "az_deg": round(float(s.az_deg), 2),
    } for s in steps]
    defl_rows = [{
        "x": round(float(d.x), 1), "y": round(float(d.y), 1),
        "az_change_deg": round(float(d.az_change_deg), 2),
        "gap_m": round(float(d.gap_m), 1),
        "az_in_deg": round(float(d.az_in_deg), 2),
        "az_out_deg": round(float(d.az_out_deg), 2),
        "kind": d.kind,
    } for d in defl]

    res = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": "MEASURED (src/gems62/lahontan.py on the pinned 100 m DEM)",
        "dem": {"path": str(DEM.relative_to(HERE)), "sha256": DEM_SHA},
        "constants": {
            "HIGHSTAND_LO_M": L.HIGHSTAND_LO_M, "HIGHSTAND_HI_M": L.HIGHSTAND_HI_M,
            "ELEVATION_RESOLUTION_M": L.ELEVATION_RESOLUTION_M,
            "BENCH_SLOPE_MAX_DEG": L.BENCH_SLOPE_MAX_DEG,
            "BENCH_MIN_CELLS": L.BENCH_MIN_CELLS,
            "STEP_PAIR_RADIUS_M": L.STEP_PAIR_RADIUS_M,
            "GRADIENT_MAX_M_PER_KM": L.GRADIENT_MAX_M_PER_KM,
            "DEFLECTION_MIN_DEG": L.DEFLECTION_MIN_DEG,
        },
        "isobase": info,
        "n_benches": len(benches),
        "n_flagged_steps": len(steps),
        "n_flagged_deflections": len(defl),
        "step_gate_stats": stats,
        "steps": step_rows,
        "deflections": defl_rows,
        "domains": {k: {"n_benches": len(v["benches"]),
                        "isobase_sigma_m": round(v["isobase"]["residual_sigma_m"], 3),
                        "n_flagged_steps": len(v["steps"]),
                        "n_flagged_deflections": len(v["deflections"]),
                        "significance_gate_m": v["stats"].get("significance_gate_m"),
                        "pairs_within_radius": v["stats"].get("pairs_within_radius"),
                        "pairs_clearing_resolution_gate": v["stats"].get("pairs_clearing_resolution_gate"),
                        "pairs_accepted": v["stats"].get("pairs_accepted")}
                    for k, v in runs.items()},
        "lahontan_box_steps": [{"x": round(float(s2.x), 1), "y": round(float(s2.y), 1),
                                "residual_jump_m": round(float(s2.residual_jump_m), 3),
                                "pair_distance_m": round(float(s2.pair_distance_m), 1),
                                "az_deg": round(float(s2.az_deg), 2)}
                               for s2 in runs["lahontan_box"]["steps"]],
        "benches": bench_rows,
        "profiles": {str(k): v for k, v in profiles.items()},
        "seconds": round(time.time() - t0, 1),
    }
    (EV / "h63_lane.json").write_text(json.dumps(res, indent=1))
    log("wrote " + str(EV / "h63_lane.json"))

    # human-readable CSV of the primary (N-S) profile
    import csv
    (DOCS / "profiles").mkdir(parents=True, exist_ok=True)
    with open(DOCS / "profiles" / "shoreline_profile_track0.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(profiles[0][0].keys()) if profiles[0] else ["bench"])
        w.writeheader()
        for r in profiles[0]:
            w.writerow(r)
    log("wrote shoreline_profile_track0.csv")

    # ---- figure ---------------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 4.2), dpi=120)
        for t in tracks:
            pr = profiles[t]
            if not pr:
                continue
            d = [r["distance_track_m"] / 1000.0 for r in pr]
            e = [r["elevation_m"] for r in pr]
            ax.plot(d, e, "-", lw=0.9, alpha=0.7, label=f"track {int(t)}deg")
            ib = [r["isobase_m"] for r in pr]
            ax.plot(d, ib, "--", lw=0.8, alpha=0.5)
        if step_rows:
            ax.scatter([s["x"] / 1000.0 for s in step_rows],
                       [np.nan] * len(step_rows), s=0)
        ax.set_xlabel("distance along track (km)")
        ax.set_ylabel("bench elevation (m)")
        ax.set_title("Pluvial shoreline benches: elevation vs distance\n"
                     f"{len(benches)} benches, isobase order {info['order']}, "
                     f"residual sigma {info['residual_sigma_m']:.2f} m, "
                     f"{len(steps)} flagged steps", fontsize=9)
        ax.legend(fontsize=7)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        (DOCS / "assets").mkdir(parents=True, exist_ok=True)
        fig.savefig(DOCS / "assets" / "h63_shoreline_profiles.png")
        plt.close(fig)
        log("wrote h63_shoreline_profiles.png")
    except Exception as exc:                                    # pragma: no cover
        log(f"figure skipped: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
