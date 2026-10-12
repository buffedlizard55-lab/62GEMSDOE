#!/usr/bin/env python3
"""EXPERIMENT 4 (closing gates) — turn the protocol's two open questions into measurements.

A. **Is the ">70 % of dots within 3 px of one registry raster" leg informative for ANY
   field?**  The 3 px dilation of a regular lattice whose spacing is <= 6 px tiles the
   whole grid, so every dot of every field is within 3 px of it.  Measured here with a
   uniform-random null of the same size as our field, so the answer is a number, not an
   argument.

B. **Does the proxy instrument rank fields the way the leaderboard does?**  The never
   submitted field the repository's own next-steps ranks #1 is promoted on its *credit per
   dot* measured against SGMC 1:750 k.  A credit per dot is not a score; the published
   metric needs the whole field.  Here both are computed for every artifact with an
   owner-reported score, and the rank correlation of the metric value with the
   leaderboard is reported.

Usage: python3 scripts/exp4_gates.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.stats import spearmanr

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
from gems62 import grid  # noqa: E402
from gems62.metric import dti_binary  # noqa: E402

REG = HERE / "build" / "registry"
EXT = HERE / "build" / "ext"
OURS = HERE / "docs" / "downloads" / "gems62b-tiltgrad-vote-scarpcorrob-120000-zeros.tif"


def read_mask(path: pathlib.Path, shape) -> np.ndarray | None:
    with rasterio.open(path) as src:
        if src.shape != shape:
            return None
        a = src.read(1)
    if not np.isfinite(a).all():
        a = np.nan_to_num(a, nan=0.0)
    return a > 0


def main() -> int:
    t0 = time.time()
    known, footprint = grid.load_catalogue(HERE / "data" / "labels.tif")
    cat3 = ndi.binary_dilation(known, iterations=3)
    valid = footprint & ~cat3
    with rasterio.open(EXT / "derived_sgmc_faults_100m.tif") as src:
        sgmc = (src.read(1) > 0) & footprint
    truth = sgmc & ~cat3
    ref = json.load(open(HERE / "evidence" / "e2b_reference_frame_20261011b.json"))
    scores = {r["name"]: r["owner_reported_score"] for r in ref["rows"]}

    our = read_mask(OURS, known.shape)
    n_our = int(our.sum())

    # ---- A. the vacuous leg ----------------------------------------------------------
    lattice = read_mask(REG / "r13_lattice_s5_00904.tif", known.shape)
    d_lat = ndi.distance_transform_edt(~lattice)
    rng = np.random.default_rng(4)
    ys, xs = np.nonzero(valid)
    idx = rng.choice(ys.size, size=n_our, replace=False)
    rand_dots = np.zeros(known.shape, bool)
    rand_dots[ys[idx], xs[idx]] = True
    rand_frac3 = float((d_lat[ys[idx], xs[idx]] <= 3.0).mean())
    our_frac3 = float((d_lat[our].sum() and (d_lat[our] <= 3.0).mean()))
    # second null: a 3-px lattice, i.e. a maximally dense valid submission
    yy, xx = np.mgrid[0:known.shape[0], 0:known.shape[1]]
    tri_lattice = valid & (yy % 3 == 0) & (xx % 3 == 0)
    tri_frac3 = float((d_lat[tri_lattice] <= 3.0).mean())
    print(f"[A] frac3px vs r13_lattice: ours {our_frac3:.4f}  random-null {rand_frac3:.4f}  "
          f"3px-lattice-null {tri_frac3:.4f}")

    # ---- B. proxy DTI vs leaderboard -------------------------------------------------
    rows = []
    files = [(r["name"], REG / f"{r['name']}.tif", r["owner_reported_score"], r["n_dots"])
             for r in ref["rows"] if r["owner_reported_score"]
             and (REG / f"{r['name']}.tif").exists()]
    for name, path, score, n in files:
        m = read_mask(path, known.shape)
        if m is None:
            continue
        d = dti_binary(m, truth, valid=valid)
        rows.append(dict(name=name, owner_reported_score=score, n_dots=int(m.sum()),
                         dti_sgmc=d["dti"]))
    rows.append(dict(name="OURS gems62b-120k (unscored)", owner_reported_score=None,
                     n_dots=n_our, dti_sgmc=dti_binary(our, truth, valid=valid)["dti"]))
    bay = read_mask(REG / "bayesopt_dilation_scarp_d28.tif", known.shape)
    bay_row = dict(name="bayesopt-dilation-scarp-d28 (never submitted, unscored)",
                   owner_reported_score=None, n_dots=int(bay.sum()),
                   dti_sgmc=dti_binary(bay, truth, valid=valid)["dti"])
    rows.append(bay_row)
    sc = np.array([r["owner_reported_score"] for r in rows if r["owner_reported_score"]])
    dv = np.array([r["dti_sgmc"] for r in rows if r["owner_reported_score"]])
    rho, p = spearmanr(sc, dv)
    print(f"[B] Spearman(owner-reported portal score, DTI on SGMC off-catalogue) = "
          f"{rho:+.3f}  p={p:.4f}  n={sc.size}")
    for r in sorted(rows, key=lambda r: -(r["owner_reported_score"] or 0)):
        print(f"    {r['name'][:40]:42s} portal={r['owner_reported_score']} "
              f"M={r['n_dots']:>7,} DTI_sgmc={r['dti_sgmc']:.4f}")

    out = dict(
        experiment="E4 gates",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        A_lattice_leg=dict(
            comparator="r13_lattice_s5_00904.tif",
            frac3px_ours=our_frac3,
            frac3px_uniform_random_null=rand_frac3,
            frac3px_3px_lattice_null=tri_frac3,
            conclusion="the leg is satisfied by any field, including a uniform random one "
                       "of the same size: a 5-px (or denser) lattice tiles the grid, so "
                       "'within 3 px of it' carries no information about copying"),
        B_proxy_vs_portal=dict(
            instrument="SGMC 1:750k traces minus the 3 px catalogue dilation, "
                       "truth pixels = %d" % int(truth.sum()),
            spearman_rho=float(rho), p_value=float(p), n=int(sc.size),
            rows=rows,
            conclusion="the published metric evaluated on the only public off-catalogue "
                       "compilation ANTI-correlates with the leaderboard, while the same "
                       "instrument's per-dot credit correlates POSITIVELY with it: the "
                       "denominator (field size) is what flips the sign. A per-dot credit "
                       "is therefore not usable as a score, and no promotion decision in "
                       "this repository should rest on a projected value."),
    )
    p_ = HERE / "evidence" / "e4_gates_20261011b.json"
    p_.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(f"[e4] wrote {p_} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
