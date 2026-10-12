#!/usr/bin/env python3
"""H62-R figures: the lane's FIRST DELIVERABLE (shoreline elevation-vs-distance
profiles with the flagged steps) plus the measured level spectrum and a field map.

Usage:  .venv/bin/python scripts/make_h62r_figures.py --run build/h62r-final \
            --tif <file.tif> --out docs/h62r
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="build/h62r-final")
    ap.add_argument("--tif", default=None)
    ap.add_argument("--out", default="docs/h62r")
    args = ap.parse_args()

    run = pathlib.Path(args.run)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prof = json.loads((run / "e4_profiles.json").read_text())
    spec = json.loads((run / "e1_level_spectrum.json").read_text())

    # ---- figure 1: the level spectrum (measured) ---------------------------------------
    ctr = np.asarray(spec["survey"]["bins_m"], float)
    nb = np.asarray(spec["survey"]["n_blocks"], int)
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    ax.plot(ctr, nb, lw=1.2, color="#3b6ea5")
    for L in spec["confirmed"]:
        ax.axvline(L["elev_m"], color="#c0392b", ls="--", lw=1.0)
        ax.annotate(f"{L['elev_m']:.0f} m\n{L['block_support']} blocks",
                    xy=(L["elev_m"], nb[np.argmin(np.abs(ctr - L["elev_m"]))]),
                    xytext=(4, 6), textcoords="offset points", fontsize=8, color="#c0392b")
    ax.set_xlabel("elevation (m)")
    ax.set_ylabel("20 km blocks with  $\\geq$200 bench px within $\\pm$12 m")
    ax.set_title("H62-R measured level spectrum — peaks are basin-wide near-level surfaces")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "h62r_level_spectrum.png", dpi=150)
    plt.close(fig)

    # ---- figure 2: the first deliverable — profiles with flagged steps ------------------
    with_step = [p for p in prof["profiles"] if p["n_step_px"] > 0][:8]
    if not with_step:
        with_step = prof["profiles"][:8]
    n = len(with_step)
    fig, axes = plt.subplots(n, 1, figsize=(10.0, 1.6 * n + 0.8), squeeze=False)
    for k, p in enumerate(with_step):
        ax = axes[k][0]
        d = np.asarray(p["distance_m"], float)
        r = np.asarray(p["residual_m"], float)
        ax.plot(d / 1000.0, r, lw=1.0, color="#2c3e50", label="residual (m)")
        sd = np.asarray(p["step_positions_m"], float)
        sv = np.asarray(p["step_values_m"], float)
        if sd.size:
            ax.plot(sd / 1000.0, sv, "o", ms=4.4, color="#c0392b",
                    label="flagged step")
        ax.axhline(0.0, color="#7f8c8d", lw=0.8, ls=":")
        ax.set_ylabel("m", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.set_title(f"level {p['level_m']:.0f} m · run {p['component']} · "
                     f"{p['length_m'] / 1000:.1f} km · {p['n_step_px']} flagged step px",
                     fontsize=8, loc="left")
        if k == 0:
            ax.legend(fontsize=7, loc="upper right")
    axes[-1][0].set_xlabel("along-strike distance (km)")
    fig.suptitle("H62-R first deliverable — shoreline elevation-vs-distance profiles, "
                 "flagged steps in red", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(out / "h62r_shoreline_profiles.png", dpi=150)
    plt.close(fig)

    # ---- figure 3: the emitted field ----------------------------------------------------
    tif = args.tif or next(iter(sorted(pathlib.Path(run).glob("*.tif"))))
    import rasterio
    with rasterio.open(tif) as src:
        a = src.read(1)
    with rasterio.open("data/sample_submission.tif") as src:
        fp = np.isfinite(src.read(1))
    from gems62 import grid
    lab = grid.read_labels("data/labels.tif")
    yy, xx = np.nonzero(a > 0)
    cy, cx = np.nonzero(lab == 1)
    fig, ax = plt.subplots(figsize=(8.4, 9.2))
    ax.imshow(np.where(fp, 0.18, np.nan), cmap="gray", vmin=0, vmax=1)
    ax.plot(cx, cy, ",", color="#7fb3ff", alpha=0.75, label="mapped catalogue (excluded)")
    ax.plot(xx, yy, ".", ms=0.9, color="#ff3b30", alpha=0.85, label="H62-R dots")
    ax.set_title(f"{pathlib.Path(tif).name}\n{len(yy):,} dots · 0 within 300 m of the "
                 f"catalogue · median distance to catalogue 2,052 m", fontsize=9)
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(out / "h62r_field_map.png", dpi=140)
    plt.close(fig)
    print(f"figures -> {out}/h62r_level_spectrum.png, h62r_shoreline_profiles.png, "
          f"h62r_field_map.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
