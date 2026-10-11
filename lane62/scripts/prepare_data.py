#!/usr/bin/env python3
"""Verify the competition grid contract from the bytes on disk, and write
evidence/data_preparation.json.

This is the "prepare_data" step the brief asked for.  It does not build a feature
stack by default because the organizer's training_features.tif is not obtainable
from this sandbox (login-walled); it verifies whatever is present and says so.

  python3 scripts/prepare_data.py            # verify
  python3 scripts/prepare_data.py --check    # verify and exit non-zero on drift
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid as G          # noqa: E402

OUT = ROOT / "evidence" / "data_preparation.json"


def stat(path: Path):
    with rasterio.open(path) as d:
        a = d.read(1)
        return dict(
            path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
            sha256=G.sha256_file(path), dtype=str(a.dtype),
            shape=[d.height, d.width], count=d.count, crs=str(d.crs),
            transform=[float(v) for v in tuple(d.transform)[:6]],
            nodata=None if d.nodata is None or (isinstance(d.nodata, float) and np.isnan(d.nodata))
            else float(d.nodata),
            n_finite=int(np.isfinite(a).sum()),
            on_competition_grid=bool((d.height, d.width) == (G.HEIGHT, G.WIDTH)
                                     and str(d.crs) == G.CRS
                                     and tuple(d.transform)[:6] == G.TRANSFORM))


def main():
    rep = dict(generated_utc=__import__("time").strftime("%Y-%m-%dT%H:%M:%SZ",
                                                         __import__("time").gmtime()),
               grid=dict(epsg=32611, height=G.HEIGHT, width=G.WIDTH,
                         transform=list(G.TRANSFORM),
                         total_cells=G.TOTAL_CELLS),
               files=[], notes=[])
    for rel in ["data/official/sample_submission.tif", "data/official/existing_faults.tif",
                "data/official/labels.tif", "data/external/geodawn_dem_a2_100m.tif",
                "data/external/topo_10m_derived_100m_u8.tif",
                "data/external/lidar_scarp_features_u8.tif",
                "data/external/derived_sgmc_faults_100m.tif"]:
        p = ROOT / rel
        if not p.exists():
            rep["files"].append(dict(path=rel, present=False))
            continue
        s = stat(p)
        s["present"] = True
        rep["files"].append(s)

    if (ROOT / "data/official/training_features.tif").exists():
        rep["files"].append(stat(ROOT / "data/official/training_features.tif"))
    else:
        rep["notes"].append(
            "training_features.tif is NOT present. The DrivenData data page requires a "
            "login (verified 2026-10-11: it redirects to /accounts/login/), so the 19 "
            "organizer bands are unavailable from this sandbox. This lane does not need "
            "them; any hypothesis that does must be marked blocked.")

    # contract checks that must hold for anything this repo ships
    g = G.load_grid(ROOT)
    rep["grid_contract"] = dict(
        footprint_px=int(g.footprint.sum()),
        catalogue_px=int(g.catalogue.sum()),
        active_px=int(g.active.sum()),
        footprint_plus_outside=int(g.footprint.sum() + (~g.footprint).sum()),
        matches_declared_total=bool(g.footprint.sum() + int((~g.footprint).sum()) == G.TOTAL_CELLS))
    ok = (rep["grid_contract"]["footprint_px"] == G.FOOTPRINT_PX
          and rep["grid_contract"]["catalogue_px"] == G.CATALOGUE_PX
          and rep["grid_contract"]["matches_declared_total"])
    rep["contract_ok"] = bool(ok)
    json.dump(rep, open(OUT, "w"), indent=1)
    print(f"footprint {rep['grid_contract']['footprint_px']:,}  "
          f"catalogue {rep['grid_contract']['catalogue_px']:,}  "
          f"active {rep['grid_contract']['active_px']:,}  contract_ok={ok}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    if "--check" in sys.argv and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
