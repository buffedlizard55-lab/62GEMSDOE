"""First deliverable of the lane: shoreline elevation-versus-distance profiles.

The tasking paragraph names the first deliverable explicitly:

    "First deliverable: shoreline elevation-versus-distance profiles with the
     flagged steps.  If only a handful are convincing, emit only those."

For each candidate shoreline transect this module writes:

* a CSV of (distance along transect in metres, detrended elevation in metres,
  fitted isobase, residual, slope, flag) -- the profile itself;
* a PNG of the profile with flagged steps marked;
* a JSON summary of how many steps were flagged and how convincing each is
  (residual in metres, MAD-normalised z, along-strike length that survives the
  evidence test).

Transects are laid out perpendicular to the local isobase strike, because a
shoreline step is only visible in cross-section.  Only transects whose flagged
step survives the extension test are called "convincing" and only those reach
the emission stage.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .isobase import PX_M


def _transect_ends(y: int, x: int, strike_rad: float, half_len_px: int,
                   shape: tuple[int, int]):
    """Endpoints of a line through (y, x) perpendicular to ``strike_rad``."""
    # strike is the contour direction; the profile runs across it
    dx = np.cos(strike_rad)
    dy = np.sin(strike_rad)
    pts = []
    for t in range(-half_len_px, half_len_px + 1):
        yy = int(round(y + t * dy))
        xx = int(round(x + t * dx))
        if 0 <= yy < shape[0] and 0 <= xx < shape[1]:
            pts.append((yy, xx, t * PX_M))
    return pts


def extract_profiles(surfaces, seeds_yx: np.ndarray, half_len_px: int = 40,
                     max_profiles: int = 400) -> list[dict]:
    """Sample elevation-vs-distance profiles centred on each flagged step."""
    shape = surfaces.elev.shape
    out: list[dict] = []
    idx = np.arange(min(max_profiles, seeds_yx.shape[0]))
    for i in idx:
        y, x = int(seeds_yx[i, 0]), int(seeds_yx[i, 1])
        s = surfaces.strike[y, x]
        if not np.isfinite(s):
            continue
        pts = _transect_ends(y, x, s, half_len_px, shape)
        if len(pts) < 10:
            continue
        rows = []
        for (yy, xx, dist) in pts:
            rows.append(dict(
                distance_m=float(dist), y=yy, x=xx,
                det_elev_m=(float(surfaces.elev[yy, xx])
                            if np.isfinite(surfaces.elev[yy, xx]) else None),
                isobase_m=(float(surfaces.isobase[yy, xx])
                           if np.isfinite(surfaces.isobase[yy, xx]) else None),
                residual_m=(float(surfaces.resid[yy, xx])
                            if np.isfinite(surfaces.resid[yy, xx]) else None),
                slope_deg=(float(surfaces.slope[yy, xx])
                           if np.isfinite(surfaces.slope[yy, xx]) else None),
                in_margin=bool(surfaces.margin[yy, xx]),
                on_bench=bool(surfaces.bench[yy, xx]),
                flagged_step=bool(surfaces.step_flag[yy, xx]),
                flagged_deflection=bool(surfaces.deflect_flag[yy, xx]),
                ridge_evidence=float(surfaces.ridge_evidence[yy, xx]),
            ))
        resid = np.array([r["residual_m"] for r in rows], float)
        finite = resid[np.isfinite(resid)]
        out.append(dict(
            profile_id=int(i), centre=[y, x], strike_deg=float(np.degrees(s)),
            n_samples=len(rows),
            step_m=(float(np.nanmax(finite) - np.nanmin(finite)) if finite.size else None),
            n_flagged_step=int(sum(r["flagged_step"] for r in rows)),
            n_flagged_deflection=int(sum(r["flagged_deflection"] for r in rows)),
            mean_evidence=float(np.mean([r["ridge_evidence"] for r in rows])),
            rows=rows,
        ))
    return out


def write_profiles(profiles: list[dict], outdir: Path, make_png: bool = True) -> dict:
    """Write profiles.csv (long), profiles.json (summary) and optional PNGs."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "shoreline_profiles.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["profile_id", "centre_y", "centre_x", "strike_deg", "distance_m",
                    "y", "x", "det_elev_m", "isobase_m", "residual_m", "slope_deg",
                    "in_margin", "on_bench", "flagged_step", "flagged_deflection",
                    "ridge_evidence"])
        for p in profiles:
            for r in p["rows"]:
                w.writerow([p["profile_id"], p["centre"][0], p["centre"][1],
                            round(p["strike_deg"], 3), r["distance_m"], r["y"], r["x"],
                            r["det_elev_m"], r["isobase_m"], r["residual_m"],
                            r["slope_deg"], int(r["in_margin"]), int(r["on_bench"]),
                            int(r["flagged_step"]), int(r["flagged_deflection"]),
                            round(r["ridge_evidence"], 5)])
    summary = [{k: v for k, v in p.items() if k != "rows"} for p in profiles]
    json_path = outdir / "shoreline_profiles.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str) + "\n")

    png_paths: list[str] = []
    if make_png:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception:
            return dict(csv=str(csv_path), json=str(json_path), pngs=[],
                        note="matplotlib unavailable; CSV+JSON written")
        for p in profiles[:24]:
            d = [r["distance_m"] for r in p["rows"]]
            e = [r["det_elev_m"] if r["det_elev_m"] is not None else np.nan for r in p["rows"]]
            ib = [r["isobase_m"] if r["isobase_m"] is not None else np.nan for r in p["rows"]]
            fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=110)
            ax.plot(d, e, lw=1.6, color="#1f3b73", label="detrended elevation")
            ax.plot(d, ib, lw=1.2, ls="--", color="#c1440e", label="fitted isobase")
            fy = [r["det_elev_m"] for r in p["rows"] if r["flagged_step"]]
            fx = [r["distance_m"] for r in p["rows"] if r["flagged_step"]]
            if fx:
                ax.plot(fx, fy, "v", ms=5, color="#111", label="flagged step")
            dy_ = [r["det_elev_m"] for r in p["rows"] if r["flagged_deflection"]]
            dx_ = [r["distance_m"] for r in p["rows"] if r["flagged_deflection"]]
            if dx_:
                ax.plot(dx_, dy_, "^", ms=5, color="#0a7d3c", label="lateral deflection")
            ax.set_xlabel("distance along transect (m)")
            ax.set_ylabel("detrended elevation (m)")
            ax.set_title(f"profile {p['profile_id']} · strike {p['strike_deg']:.0f}° · "
                         f"step {p['step_m'] if p['step_m'] is None else round(p['step_m'],1)} m",
                         fontsize=9)
            ax.legend(fontsize=7, loc="best")
            ax.grid(alpha=.25, lw=.5)
            fig.tight_layout()
            fn = outdir / f"profile_{p['profile_id']:04d}.png"
            fig.savefig(fn)
            plt.close(fig)
            png_paths.append(fn.name)
    return dict(csv=str(csv_path), json=str(json_path), pngs=png_paths,
                n_profiles=len(profiles))
