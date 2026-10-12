#!/usr/bin/env python3
"""Where does NEW geometry pay?  Instrument-B credit of a field, by distance band.

Every datum-lane argument in this repo turns on the same question: how far off the
catalogue has to be a dot before it is real information rather than noise, and does the
organiser's metric pay for it?  `docs/why-h33-scored.md` answers the second half in the
abstract (add a dot only while its credit exceeds 0.2*DTI, ~0.056 at 0.2778); this script
answers it per band, on a file you actually emitted, against a mass-matched isolated-random
control drawn from the SAME band.  Bands are Euclidean distance from the dot to the nearest
catalogue pixel, so `cat_dilate` is the realised collar of the emission, not the intended one.

    .venv/bin/python scripts/report_bands.py docs/downloads/<file>.tif \
        --out-json evidence/h62j-bands.json

Read-only: it never writes a raster.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid as G                                   # noqa: E402
from gems62 import metric as MT                                # noqa: E402

SEP_PX = 3.0
BANDS = [(0, 250), (250, 300), (300, 500), (500, 1000), (1000, 2000),
         (2000, 4000), (4000, 1e9)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tif")
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--draws", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261012)
    args = ap.parse_args()

    labels = G.read_labels(ROOT / "data/labels.tif")
    foot = labels != G.LABEL_NODATA
    cat = labels == 1
    with rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif") as d:
        sgmc = d.read(1).astype(bool)
    truthB = sgmc & foot & ~cat
    dgB = ndi.distance_transform_edt(~truthB, sampling=(G.PIXEL_M, G.PIXEL_M))
    dgC = ndi.distance_transform_edt(~cat, sampling=(G.PIXEL_M, G.PIXEL_M))

    with rasterio.open(args.tif) as d:
        s = d.read(1)
    pred = np.isfinite(s) & (s > 0) & foot
    ys, xs = np.nonzero(pred)
    if len(ys) == 0:
        print("no positive cells in", args.tif)
        return 1
    co = np.column_stack([ys, xs]).astype(float)
    cred = MT.kernel(dgB[ys, xs], MT.RADIUS_M)
    dcat = dgC[ys, xs]
    M = int(len(ys))
    dti_bar = 0.2 * (cred.sum() / (0.2 * M + 0.8 * 12000.0))
    print(f"{M} dots  mean credit {cred.mean():.5f}  marginal bar at this mass "
          f"(0.2*model DTI) = {dti_bar:.5f}")

    pool = foot & ~cat
    rng = np.random.default_rng(args.seed)
    rows = []
    for lo, hi in BANDS:
        sel = (dcat >= lo) & (dcat < hi)
        n = int(sel.sum())
        band_pool = pool & (dgC >= lo) & (dgC < hi)   # per-cell band, dgC is the grid field
        ctrl = []
        if n and int(band_pool.sum()) > n:
            cand = np.nonzero(band_pool)
            def greedy(gy, gx):
                gp = np.column_stack([gy, gx]).astype(float)
                tr = cKDTree(gp)
                ban = np.zeros(gy.size, bool)
                keep = []
                for i in range(gy.size):
                    if ban[i]:
                        continue
                    keep.append(i)
                    ban[tr.query_ball_point(gp[i], SEP_PX)] = True
                    if len(keep) >= n:
                        break
                return np.array(keep, dtype=int)

            for k in range(args.draws):
                # permute a bounded sample, not the whole band (bands can hold 5e6 cells);
                # if the sample is too sparse to fill n isolated dots, fall back to all of it,
                # so the control is always mass-matched to the field.
                for cap in (min(cand[0].size, max(4 * n, 4000)), cand[0].size):
                    o = rng.permutation(cand[0].size)[:cap]
                    gy, gx = cand[0][o], cand[1][o]
                    keep = greedy(gy, gx)
                    if len(keep) >= n or cap == cand[0].size:
                        break
                ctrl.append(float(MT.kernel(dgB[gy[keep], gx[keep]], MT.RADIUS_M).mean()))
        cm = float(np.mean(ctrl)) if ctrl else None
        cs = float(np.std(ctrl)) if ctrl else None
        cr = float(cred[sel].mean()) if n else None
        rows.append(dict(band_m=f"{lo:.0f}-{hi:.0f}" if hi < 1e8 else f">{lo:.0f}",
                         n_dots=n, frac_dots=round(n / M, 4),
                         credit=None if cr is None else round(cr, 6),
                         control_mean=None if cm is None else round(cm, 6),
                         control_sd=None if cs is None else round(cs, 6),
                         ratio=None if not cm else round(cr / cm, 3),
                         pool_cells=int(band_pool.sum()),
                         pays_above_bar=None if cr is None else bool(cr > dti_bar)))
        r = rows[-1]
        crs = "" if cr is None else f"{cr:.5f}"
        cms = "" if cm is None else f"{cm:.5f}+-{cs:.5f}"
        rat = "" if r["ratio"] is None else f"{r['ratio']:.2f}x"
        print(f"  {r['band_m']:>12s}  n={n:6d} ({100*r['frac_dots']:5.1f}%)  "
              f"credit={crs}  control={cms}  ratio={rat}  above-bar={r['pays_above_bar']}")
    payload = dict(tif=str(args.tif), sha256=G.sha256(args.tif), n_dots=M,
                   mean_credit=round(float(cred.mean()), 6),
                   marginal_bar=round(dti_bar, 6), bands=rows,
                   instrument="SGMC quaternary faults minus catalogue, 300 m kernel")
    if args.out_json:
        pathlib.Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.out_json).write_text(json.dumps(payload, indent=2))
        print("wrote", args.out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
