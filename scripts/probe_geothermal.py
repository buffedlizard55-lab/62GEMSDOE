#!/usr/bin/env python3
"""H62-J2 — a screen, not a lane: do GEOTHERMAL indicators mark UNMAPPED structure?

Written for the geothermal lane (and for the selector) by the datum-offset lane, because
both lanes keep pointing at the same cells and nobody had measured it.  This script emits
no submission and changes no gate; it answers one question in one number:

  a dot placed at a Hot/Warm spring or a mapped vent, but OFF the catalogue the scoring
  file contains — does it find fault pixels at the rate an INDEPENDENT compilation says
  they should be there, better than an isolated random dot in the same allowed area?

Protocol copied from scripts/run_h62i.py so the numbers are comparable across lanes:
truth B = USGS SGMC quaternary faults & footprint & ~catalogue; a dot scores the mean
MT.kernel of its distance to truth B (300 m support); the control is isolated random
dots in the same allowed pool at the same mass; pool excludes a 3-cell dilation of the
catalogue, and "isolated" means 3 cells apart.

  .venv/bin/python scripts/probe_geothermal.py --out-json evidence/h62j2-geothermal.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
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
CAT_DILATE_PX = 3
N_PLAN = 12000
EXT = ROOT / "data/external"


def points_from_csv(path, want):
    """Unique (row, col) cells from a GDR extract whose `want(record)` is true."""
    out = set()
    with open(path) as fh:
        for r in csv.DictReader(fh):
            if want(r):
                try:
                    out.add((int(float(r["row"])), int(float(r["col"]))))
                except (KeyError, ValueError, TypeError):
                    pass
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext", default=str(EXT))
    ap.add_argument("--out-json", default=str(ROOT / "evidence/h62j2-geothermal.json"))
    ap.add_argument("--corridor-m", type=float, default=600.0,
                    help="also score every allowed cell within this distance of an indicator")
    ap.add_argument("--buffers-m", default="",
                    help="comma-separated radii, e.g. 5000,10000,20000 -- the H62-Q test as "
                         "specified in docs/hypotheses-2026-10-11b.md: credit INSIDE each buffer "
                         "against a mass-matched control drawn from the SAME buffer, plus the "
                         "complementary field OUTSIDE every buffer")
    ap.add_argument("--max-mass", type=int, default=60000)
    ap.add_argument("--placebo-trials", type=int, default=0,
                    help="for each buffer radius, draw N point sets of the SAME COUNT at random "
                         "in the allowed pool and build the same buffers: if a random belt scores "
                         "like the real one, the indicator adds nothing to its geography. This is "
                         "the control that makes a 1.1x at 20 km interpretable.")
    args = ap.parse_args()
    ext = pathlib.Path(args.ext)

    labels = G.read_labels(ROOT / "data/labels.tif")
    foot = labels != G.LABEL_NODATA
    cat = labels == 1
    with rasterio.open(ext / "derived_sgmc_faults_100m.tif") as d:
        sgmc = d.read(1).astype(bool)
    truthB = sgmc & foot & ~cat
    dgB = ndi.distance_transform_edt(~truthB, sampling=(G.PIXEL_M, G.PIXEL_M))
    pool = foot & ~ndi.binary_dilation(cat, iterations=CAT_DILATE_PX)

    def mc(m):
        p = m & foot & ~cat
        ys, xs = np.nonzero(p)
        return (float(MT.kernel(dgB[ys, xs], MT.RADIUS_M).mean()), int(ys.size)) if ys.size else (0.0, 0)

    def hardcore(field, M, rank=None, seed=20261012):
        """Greedy hard-core thinning of the allowed cells of `field`.

        `rank` (optional) is an ascending cost array: cells with the smallest cost are
        offered first, so a mass-capped corridor keeps the cells nearest its indicators.
        """
        cand = np.nonzero(field & pool)
        if rank is None:
            key = np.zeros(len(cand[0]))
        else:
            key = rank[cand[0], cand[1]].astype(float)
        o = np.argsort(key + np.random.default_rng(seed).random(len(key)) * 1e-6)
        ys, xs = cand[0][o], cand[1][o]
        co = np.column_stack([ys, xs]).astype(float)
        tr = cKDTree(co)
        ban = np.zeros(ys.size, bool)
        keep = []
        for i in range(ys.size):
            if ban[i]:
                continue
            keep.append(i)
            ban[tr.query_ball_point(co[i], SEP_PX)] = True
            if len(keep) >= M:
                break
        m = np.zeros(foot.shape, bool)
        m[ys[keep], xs[keep]] = True
        return m

    def control_at(M, draws=5):
        """Mean credit of `draws` isolated-RANDOM fields of exactly M dots in the same pool.

        Mass-matched on purpose: an unmatched control is the mistake that made h62g look
        better than it was.  Draws differ only by seed, and the spread is reported.
        """
        if M in controls:
            v = controls[M]
            return v["mean"], v["sd"]
        cs = []
        for k in range(draws):
            m = hardcore(np.ones(foot.shape, bool), M, seed=20261012 + 101 * k)
            c, n = mc(m)
            if n:
                cs.append(c)
        controls[M] = dict(mean=float(np.mean(cs)), sd=float(np.std(cs)), M=int(M), draws=draws)
        return controls[M]["mean"], controls[M]["sd"]

    controls = {}

    thermal = lambda r: (r.get("thermalclass") or "").strip().lower() in ("hot", "warm")
    hot = lambda r: (r.get("thermalclass") or "").strip().lower() == "hot"
    anything = lambda r: True
    sets = {
        "hot+warm spring/well cells": points_from_csv(ext / "gdr_wellspring_in_footprint.csv", thermal),
        "hot-only cells": points_from_csv(ext / "gdr_wellspring_in_footprint.csv", hot),
        "mapped volcanic vents": points_from_csv(ext / "gdr_volcanic_vents_in_footprint.csv", anything),
    }
    checks = []
    for name, pts in sets.items():
        raw = np.zeros(foot.shape, bool)
        for (r, c) in pts:
            if 0 <= r < foot.shape[0] and 0 <= c < foot.shape[1]:
                raw[r, c] = True
        inside = int(raw.sum())
        dist = ndi.distance_transform_edt(~raw)
        for tag, fld in (("points", raw),
                         (f"corridor {args.corridor_m:.0f} m",
                          ndi.binary_dilation(raw, iterations=int(math.ceil(args.corridor_m / 100.0))))):
            m = hardcore(fld, args.max_mass, rank=dist)
            cr, n = mc(m)
            if n == 0:
                print(f"{name:26s} {tag:16s} no allowed cells")
                continue
            c_ctrl, s_ctrl = control_at(n)
            s = cr * n / (0.2 * n + 0.8 * N_PLAN)
            rec = dict(name=name, field=tag, n_indicator_cells=inside, M=n, credit=round(cr, 6),
                       control_mean=round(c_ctrl, 6), control_sd=round(s_ctrl, 6),
                       credit_vs_control=round(cr / c_ctrl, 3),
                       z=(round((cr - c_ctrl) / s_ctrl, 2) if s_ctrl > 1e-12 else None),
                       model_dti_N12000=round(s, 6),
                       marginal_bar=round(0.2 * s, 6))
            checks.append(rec)
            print(f"{name:26s} {tag:16s} M={n:6d} credit={cr:.5f}"
                  f" ({cr/c_ctrl:5.2f}x control {c_ctrl:.5f}+-{s_ctrl:.5f}) modelDTI={s:.4f}")
    radii = [float(x) for x in args.buffers_m.split(",") if x.strip()]
    for name, pts in sets.items():
        raw = np.zeros(foot.shape, bool)
        for (r, c) in pts:
            if 0 <= r < foot.shape[0] and 0 <= c < foot.shape[1]:
                raw[r, c] = True
        dist = ndi.distance_transform_edt(~raw, sampling=(100.0, 100.0))
        for R in radii:
            inside = dist <= R
            m = hardcore(inside, args.max_mass, rank=dist)
            cr, n = mc(m)
            if n:
                c_ctrl, s_ctrl = control_at(n) if False else control_at(n)
                s_m = cr * n / (0.2 * n + 0.8 * N_PLAN)
                rec = dict(name=name, field=f"inside {R:.0f} m buffer", M=n,
                           cells_available=int((inside & pool).sum()), credit=round(cr, 6),
                           control_mean=round(c_ctrl, 6), control_sd=round(s_ctrl, 6),
                           credit_vs_control=round(cr / c_ctrl, 3) if c_ctrl > 0 else None,
                           z=(round((cr - c_ctrl) / s_ctrl, 2) if s_ctrl > 1e-12 else None),
                           model_dti_N12000=round(s_m, 6))
                checks.append(rec)
                print(f"{name:26s} {R/1000:5.0f} km buffer   M={n:6d} credit={cr:.5f}"
                      f" ({cr/c_ctrl:5.2f}x control {c_ctrl:.5f}+-{s_ctrl:.5f}) modelDTI={s_m:.4f}")
        if radii:
            outside = dist > max(radii)
            m = hardcore(outside, args.max_mass, rank=-dist)
            cr, n = mc(m)
            if n:
                c_ctrl, s_ctrl = control_at(n)
                s_m = cr * n / (0.2 * n + 0.8 * N_PLAN)
                checks.append(dict(name=name, field=f"outside {max(radii):.0f} m", M=n,
                                   credit=round(cr, 6), control_mean=round(c_ctrl, 6),
                                   control_sd=round(s_ctrl, 6),
                                   credit_vs_control=round(cr / c_ctrl, 3) if c_ctrl > 0 else None,
                                   model_dti_N12000=round(s_m, 6)))
                print(f"{name:26s} outside all buffers M={n:6d} credit={cr:.5f}"
                      f" ({cr/c_ctrl:5.2f}x) modelDTI={s_m:.4f}")
    for name, pts in sets.items():
        if args.placebo_trials <= 0:
            break
        raw = np.zeros(foot.shape, bool)
        for (r, c) in pts:
            if 0 <= r < foot.shape[0] and 0 <= c < foot.shape[1]:
                raw[r, c] = True
        cand = np.nonzero(pool)
        rng = np.random.default_rng(20261012)
        for R in radii:
            vals = []
            for t in range(args.placebo_trials):
                pick = rng.choice(cand[0].size, size=len(pts), replace=False)
                fake = np.zeros(foot.shape, bool)
                fake[cand[0][pick], cand[1][pick]] = True
                fd = ndi.distance_transform_edt(~fake, sampling=(100.0, 100.0))
                m = hardcore(fd <= R, args.max_mass, rank=fd)
                cr, n = mc(m)
                if n:
                    vals.append(cr)
            if vals:
                checks.append(dict(name=name, field=f"PLACEBO {len(pts)} random points, {R:.0f} m buffer",
                                   M=int(args.max_mass), credit=round(float(np.mean(vals)), 6),
                                   placebo_sd=round(float(np.std(vals)), 6), trials=len(vals)))
                print(f"{name:26s} placebo {R/1000:5.0f} km   credit={np.mean(vals):.5f}"
                      f" +-{np.std(vals):.5f}  ({len(vals)} random point sets of the same count)")
    out = pathlib.Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(checks=checks,
                   mass_matched_controls=list(controls.values()),
                   pool_cells=int(pool.sum()), truthB_cells=int(truthB.sum()),
                   instrument=("SGMC quaternary faults minus catalogue, "
                               "300 m kernel, isolated-random control at equal mass"),
                   note=("screen only: the datum-offset lane did not emit this "
                         "field; the geothermal lane owns it"))
    out.write_text(json.dumps(payload, indent=2))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
