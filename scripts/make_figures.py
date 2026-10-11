"""Rebuild the two figures from the receipts and the shipped raster.

The figures are part of the deliverable, so they are generated from the same
numbers as the run card rather than stored by hand:

* ``evidence/<slug>-profile.png``     -- elevation and residual vs along-shoreline distance
* ``evidence/<slug>-map.png``         -- spatial context: datum band, catalogue, emitted dots
* both copied to ``docs/assets/`` for the site

    python scripts/make_figures.py --data data

Requires the restored inputs (``scripts/download_data.sh``).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems62 import grid, lahontan  # noqa: E402
from gems62.grid import read_dem, read_labels, FOOTPRINT_CELLS  # noqa: E402
import run_lane  # noqa: E402  (the figure renderers live with the run)


def newest_card() -> pathlib.Path:
    cards = sorted((ROOT / "evidence").glob("*-runcard.json"), key=lambda p: p.stat().st_mtime)
    if not cards:
        raise SystemExit("no run card in evidence/")
    return cards[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data"))
    ap.add_argument("--card", default="")
    a = ap.parse_args()

    card_path = pathlib.Path(a.card) if a.card else newest_card()
    card = json.loads(card_path.read_text())
    slug = card["slug"]
    prof = json.loads((ROOT / "evidence" / f"{slug}-profile.json").read_text())

    # ---------------- profile ----------------
    rows = prof["rows"]
    X = np.array([r["x"] for r in rows])
    Y = np.array([r["y"] for r in rows])
    flags = []
    for f in card["step_locations_detail"]:
        k = int(np.argmin((X - f["x"]) ** 2 + (Y - f["y"]) ** 2))
        flags.append({"distance_track_m": rows[k]["distance_track_m"],
                      "residual_jump_m": f["jump_m"]})
    label = (f"track azimuth {prof['track_azimuth_deg']:.1f} deg | {len(rows)} benches | "
             f"local strand isobase sigma {prof['isobase']['local_strand']['residual_sigma_m']:.2f} m "
             f"(global {prof['isobase']['global']['residual_sigma_m']:.2f} m) | "
             f"{len(card['step_locations_detail'])} step location(s), "
             f"{len(card['deflection_locations_detail'])} deflection location(s)")
    out_profile = ROOT / "evidence" / f"{slug}-profile.png"
    run_lane.save_profile_png(
        rows, out_profile,
        "Lake Lahontan highstand datum: elevation and residual vs along-shoreline distance",
        label, flags=flags, radius_m=card["gates"]["step_significance"])
    print("wrote", out_profile.relative_to(ROOT))

    # ---------------- map ----------------
    data = pathlib.Path(a.data)
    scene = grid.load_scene(data)      # the SAME loader the lane uses: footprint = labels != nodata
    labels, dem = scene.labels, scene.dem
    foot = scene.footprint
    assert int(foot.sum()) == FOOTPRINT_CELLS, int(foot.sum())
    catalogue = labels == 1          # labels.tif: 1 = catalogue fault, 0 = none, -1 = outside
    assert int(catalogue.sum()) == grid.CATALOGUE_CELLS
    # The DEM mirror does not cover every footprint cell (IR-62-007); show that
    # region as flat rather than letting NaN leak into the shading.
    dem = np.where(foot & ~np.isfinite(dem), np.nanmedian(dem[foot & np.isfinite(dem)]), dem)
    band = lahontan.bench_cells(dem, foot)
    raster_path = ROOT / "docs" / "downloads" / f"{slug}-zeros.tif"
    dots = np.zeros(foot.shape, bool)
    with __import__("rasterio").open(raster_path) as src:
        vals = src.read(1)
    dots = vals > 0
    out_map = ROOT / "evidence" / f"{slug}-map.png"
    run_lane.save_map_png(dem, foot, catalogue, band, dots, out_map,
                          flags=[{"x": f["x"], "y": f["y"], "jump_m": f["jump_m"]}
                                 for f in card["step_locations_detail"]])
    print("wrote", out_map.relative_to(ROOT))

    assets = ROOT / "docs" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for src_png, name in ((out_profile, "profile.png"), (out_map, "map.png")):
        (assets / name).write_bytes(src_png.read_bytes())
        print("copied ->", (assets / name).relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
