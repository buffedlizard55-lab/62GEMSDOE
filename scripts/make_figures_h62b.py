#!/usr/bin/env python3
"""Figures for the site: the artifact map and the lane's first deliverable — shoreline
elevation-versus-distance profiles with the flagged steps marked."""
from __future__ import annotations

import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import datum_base as db  # noqa: E402

SURF = ROOT / "build" / "surfaces"
BUILD = ROOT / "build" / "h62b"
FIG = ROOT / "docs" / "assets"
FIG.mkdir(parents=True, exist_ok=True)


def main() -> int:
    footprint = np.asarray(np.load(SURF / "footprint.npy"), bool)
    poscat = np.asarray(np.load(SURF / "catalogue.npy"), bool)
    dem = np.load(SURF / "dem.npy")
    base = np.load(SURF / "base.npy")
    iso = np.load(SURF / "isobase.npy")
    rows = np.load(BUILD / "cand_rows.npy")
    cols = np.load(BUILD / "cand_cols.npy")
    score = np.load(BUILD / "cand_score.npy")
    order = np.argsort(score)[::-1][:37654]
    dots = np.zeros(footprint.shape, bool)
    dots[rows[order], cols[order]] = True

    # ---------------------------------------------------------------- map
    fig, ax = plt.subplots(figsize=(9.2, 8.1), dpi=110)
    ax.imshow(np.where(footprint, dem, np.nan), cmap="gray_r",
              vmin=np.nanpercentile(dem[footprint], 2),
              vmax=np.nanpercentile(dem[footprint], 98), interpolation="nearest")
    cy, cx = np.nonzero(poscat)
    ax.plot(cx, cy, "|", color="#f0c257", ms=1.6, alpha=0.85, label="USGS/INGENIOUS catalogue")
    dy, dx = np.nonzero(dots)
    ax.plot(dx, dy, ".", color="#5aa9f0", ms=1.5, label="H62-B dots (37,654)")
    ax.set_title("H62-B datum-step seeded, ridge-relief traced dot field\n"
                 "grey = 100 m DEM, yellow = mapped faults, blue = emitted dots",
                 fontsize=11)
    ax.legend(loc="lower left", fontsize=9, framealpha=0.85)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(FIG / "h62b_map.png")
    plt.close(fig)

    # ------------------------------------------------------- seed attribute figure
    hab = np.load(SURF / "hab.npy")
    rel = np.load(SURF / "relief.npy")
    fig, axs = plt.subplots(1, 2, figsize=(11.0, 4.6), dpi=110)
    for ax, (arr, ttl, vmax) in zip(axs, [
            (hab, "Height above base level (m)", 200.0),
            (rel, "Local relief, 900 m window (m)", 250.0)]):
        im = ax.imshow(np.where(footprint, arr, np.nan), cmap="viridis",
                       vmin=0, vmax=vmax, interpolation="nearest")
        ax.set_title(ttl, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle("The pluvial datum: base level, and height above it", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "h62b_datum.png")
    plt.close(fig)

    # ---------------------------------------------------------- shoreline profiles
    prof = json.loads((BUILD / "shoreline_profiles.json").read_text())
    rows_p = [p for p in prof["profiles"] if p["step_m"] is not None]
    rows_p.sort(key=lambda p: -abs(p["step_m"]))
    n_show = min(12, len(rows_p))
    ncols = 3
    nrows = int(np.ceil(n_show / ncols))
    fig, axs = plt.subplots(nrows, ncols, figsize=(13.5, 3.0 * nrows), dpi=110, squeeze=False)
    for i, ax in enumerate(axs.ravel()):
        if i >= n_show:
            ax.axis("off")
            continue
        p = rows_p[i]
        r, c = p["row"], p["col"]
        half = 40
        prof2 = db.profile_through(r, c, p["azimuth_deg"], base=base.astype(np.float64),
                                   isobarm=iso.astype(np.float64), half_len_px=half)
        if prof2 is None:
            ax.axis("off")
            continue
        d = prof2.dist_m / 1000.0
        ax.plot(d, prof2.base_m, color="#5aa9f0", lw=1.3, label="base level (measured)")
        ax.plot(d, prof2.isobase_m, color="#f0c257", lw=1.1, ls="--", label="fitted isobase")
        ax.axvline(0, color="#f0776a", lw=1.0, alpha=0.8)
        ax.set_title(f"#{i+1}  row {r} col {c} · strike {p['azimuth_deg']:.0f}°\n"
                     f"flagged step {p['step_m']:+.1f} m", fontsize=9)
        ax.set_xlabel("distance along datum strike (km)", fontsize=8)
        ax.set_ylabel("elevation (m)", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.25, lw=0.5)
        if i == 0:
            ax.legend(fontsize=7, loc="best")
    fig.suptitle("Lane deliverable 1 — shoreline elevation-versus-distance profiles at the "
                 "flagged loci\n(measured base level vs the fitted isobase; the flag is the "
                 "step across the locus, marked in red)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "h62b_profiles.png")
    plt.close(fig)

    (ROOT / "evidence" / "figures_h62b.json").write_text(json.dumps(dict(
        map=str(FIG / "h62b_map.png"), datum=str(FIG / "h62b_datum.png"),
        profiles=str(FIG / "h62b_profiles.png"),
        n_profiles=len(prof["profiles"]), n_flagged=len(rows_p),
        step_m=[round(p["step_m"], 2) for p in rows_p[:40]]), indent=1))
    print("figures written:", n_show, "profiles,", len(rows_p), "flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
