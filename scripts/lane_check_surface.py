#!/usr/bin/env python3
"""Pre-placement half of the lane check (the protocol requires both halves).

The binding rule is: "check on the SURFACE before placement AND on the final
dots".  ``run_lane.py`` records the final-dots half.  This script records the
surface half from the same pipeline state, so the receipt for a session is
complete: it rebuilds stages 1-4 only (no emission, no holdout) and compares the
datum-offset surface against every registry raster with the same machinery
(``gems62.uniqueness.compare``), which is exactly what the rule asks for.

Two surface variants are reported, and the *stricter* of the two decides:

``full``
    the datum-offset surface itself: |local-isobase residual| in metres on every
    dominant-strand datum cell, 0 elsewhere.  This is what the placement step
    reads, so it is the honest "surface before placement".
``evidence``
    the same field restricted to the flagged benches (|residual| >= the step
    threshold).  This is the analogue of "my dots" for the 3-px overlap rule,
    because the full surface is a broad field, not a set of emitters.

Correlation is a drift check, not a score: it answers "is this the same object
another lane already emitted?", nothing more.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems62 import grid as gridmod  # noqa: E402
from gems62 import lahontan  # noqa: E402
from gems62.uniqueness import compare, OVERLAP_LIMIT, RHO_LIMIT  # noqa: E402


def build_surfaces(data: str, *, order: int, slope_max_deg: float, min_cells: int,
                   step_threshold_m: float):
    dem = gridmod.read_dem(Path(data) / "geodawn_dem_a2_100m.tif")
    foot = np.isfinite(dem)
    benches = lahontan.describe_benches(dem, foot, gridmod.TRANSFORM,
                                        slope_max_deg=slope_max_deg, min_cells=min_cells)
    coef, info = lahontan.fit_isobase(benches, order=order)
    bx = np.array([b.x for b in benches]); by = np.array([b.y for b in benches])
    bz = np.array([b.z for b in benches]); bn = np.array([b.n_cells for b in benches], float)
    ib = lahontan.isobase_at(coef, info["terms"], info["x0"], info["y0"], bx, by)
    keep, levels = lahontan.dominant_strand_mask(bz - ib, bn)
    idx = np.nonzero(keep)[0]
    benches = [benches[i] for i in idx]
    rho, _ = lahontan.local_isobase(benches, (bz - ib)[idx])
    residual = (bz - ib)[idx] - rho

    full, evid = lahontan.datum_offset_surface(
        benches, residual, dem.shape, step_threshold_m=step_threshold_m)
    return dem, foot, full, evid, levels


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--registry", required=True)
    ap.add_argument("--out", default="evidence")
    ap.add_argument("--name", required=True)
    ap.add_argument("--isobase-order", type=int, default=3)
    ap.add_argument("--bench-slope-max-deg", type=float, default=3.0)
    ap.add_argument("--bench-min-cells", type=int, default=8)
    ap.add_argument("--step-threshold-m", type=float, default=3.0)
    a = ap.parse_args()

    dem, foot, full, evid, levels = build_surfaces(
        a.data, order=a.isobase_order, slope_max_deg=a.bench_slope_max_deg,
        min_cells=a.bench_min_cells, step_threshold_m=a.step_threshold_m)
    print(f"surface: {int((full > 0).sum()):,} datum cells, "
          f"{int((evid > 0).sum()):,} flagged-evidence cells, "
          f"|residual| median {np.median(full[full > 0]):.2f} m")

    reg = {p.stem: p for p in sorted(Path(a.registry).glob("*.tif"))}
    report = {"evaluator": "gems62.uniqueness.compare", "rule": {
        "rho_limit": RHO_LIMIT, "overlap_limit": OVERLAP_LIMIT, "tolerance_px": 3}}
    worst = 0.0
    for variant, surf in (("full", full), ("evidence", evid)):
        entries = compare(surf, reg, foot)
        nonvac = [e for e in entries if not e.vacuous]
        rho_max = max((abs(e.rho) for e in entries if np.isfinite(e.rho)), default=float("nan"))
        ov = max((e.frac3px for e in nonvac), default=0.0)
        worst = max(worst, rho_max if np.isfinite(rho_max) else 0.0, ov)
        report[variant] = {
            "n_registry": len(entries), "n_vacuous": len(entries) - len(nonvac),
            "max_abs_rho": rho_max, "max_3px_overlap_non_vacuous": ov,
            "closest": (max(nonvac, key=lambda e: e.frac3px).alias if nonvac else None),
            "per_raster": [{"alias": e.alias, "rho": e.rho, "frac3px": e.frac3px,
                            "coverage3px": e.coverage3px, "vacuous": e.vacuous,
                            "sha256": e.sha256} for e in entries],
        }
        print(f"  {variant:8s} max|rho|={rho_max:.6f} (limit {RHO_LIMIT})  "
              f"max 3px={ov:.4f} (limit {OVERLAP_LIMIT})  vacuous={report[variant]['n_vacuous']}")

    trip = (worst >= min(RHO_LIMIT, OVERLAP_LIMIT))
    report["passed"] = None if trip else True
    report["verdict"] = "SURFACE DISTINCT" if not trip else "REVIEW"
    report["note"] = ("pre-placement half of the lane rule; the final-dots half is in the run card"
                      " field correlation_overlap_vs_registry. Correlation on a broad, mostly-zero"
                      " field is a drift check, not a score.")
    report["isobase"] = {"order": a.isobase_order, "residual_sigma_m": levels.get("sigma_m")}
    out = Path(a.out) / f"{a.name}-lane-surface.json"
    out.write_text(json.dumps(report, indent=1))
    np.save(Path(a.out) / f"{a.name}-surface.npy", full)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
